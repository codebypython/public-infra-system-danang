"""Auth business logic — login throttle, token issuance, refresh token rotation."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from uuid import UUID

import redis.asyncio as redis_async
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppError, ConflictError, NotFoundError, RateLimitError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.db.models import RefreshToken, User
from app.modules.auth.schemas import LoginRequest, RegisterRequest


_redis: redis_async.Redis | None = None


def get_redis() -> redis_async.Redis:
    global _redis
    if _redis is None:
        _redis = redis_async.from_url(settings.redis_url, decode_responses=True)
    return _redis


def _hash_refresh(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def throttle_login(ip: str, email: str) -> None:
    """Lock out after N fails / 15 min — Redis-backed counter."""
    r = get_redis()
    key = f"login:fail:{ip}:{email.lower()}"
    val = await r.get(key)
    if val and int(val) >= settings.rate_limit_login_per_15m:
        raise RateLimitError("Too many failed login attempts, try again in 15 minutes")


async def record_login_failure(ip: str, email: str) -> None:
    r = get_redis()
    key = f"login:fail:{ip}:{email.lower()}"
    pipe = r.pipeline()
    pipe.incr(key, 1)
    pipe.expire(key, 60 * 15)
    await pipe.execute()


async def clear_login_failures(ip: str, email: str) -> None:
    r = get_redis()
    await r.delete(f"login:fail:{ip}:{email.lower()}")


async def register_user(db: AsyncSession, payload: RegisterRequest) -> User:
    # Public registration restricted to citizen role
    if payload.role != "citizen":
        raise AppError("Public registration only allows citizen role", status_code=403)
    existing = await db.execute(
        select(User).where((User.email == payload.email) | (User.username == payload.username))
    )
    if existing.scalar_one_or_none():
        raise ConflictError("Email or username already registered")
    user = User(
        email=payload.email,
        username=payload.username,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        phone=payload.phone,
        role=payload.role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate(
    db: AsyncSession, payload: LoginRequest, *, ip: str, user_agent: str | None
) -> tuple[User, str, str, datetime]:
    """Verify creds, issue tokens, persist refresh token row."""
    await throttle_login(ip, payload.email)
    res = await db.execute(select(User).where(User.email == payload.email))
    user = res.scalar_one_or_none()
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        await record_login_failure(ip, payload.email)
        raise AppError("Invalid credentials", status_code=401, code="invalid_credentials")
    await clear_login_failures(ip, payload.email)
    access = create_access_token(user.id, user.role)
    refresh, expires = create_refresh_token(user.id)
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=_hash_refresh(refresh),
            user_agent=(user_agent or "")[:500],
            ip=ip,
            expires_at=expires,
        )
    )
    user.last_login_at = datetime.now(UTC)
    await db.commit()
    return user, access, refresh, expires


async def refresh_tokens(
    db: AsyncSession, raw_refresh: str, *, ip: str, user_agent: str | None
) -> tuple[str, str, datetime]:
    """Refresh-token rotation: invalidate old, issue new pair."""
    payload = decode_token(raw_refresh)
    if payload.get("type") != "refresh":
        raise AppError("Wrong token type", status_code=401)
    user_id = UUID(payload["sub"])
    token_hash = _hash_refresh(raw_refresh)
    res = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked_at.is_(None),
        )
    )
    rt = res.scalar_one_or_none()
    if not rt or rt.expires_at < datetime.now(UTC):
        raise AppError("Refresh token revoked or expired", status_code=401)
    rt.revoked_at = datetime.now(UTC)
    user = await db.get(User, user_id)
    if not user or not user.is_active:
        raise AppError("User inactive", status_code=401)
    new_access = create_access_token(user.id, user.role)
    new_refresh, expires = create_refresh_token(user.id)
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=_hash_refresh(new_refresh),
            user_agent=(user_agent or "")[:500],
            ip=ip,
            expires_at=expires,
        )
    )
    await db.commit()
    return new_access, new_refresh, expires


async def logout(db: AsyncSession, raw_refresh: str | None) -> None:
    if not raw_refresh:
        return
    h = _hash_refresh(raw_refresh)
    res = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == h))
    rt = res.scalar_one_or_none()
    if rt and rt.revoked_at is None:
        rt.revoked_at = datetime.now(UTC)
        await db.commit()


async def revoke_all_sessions(db: AsyncSession, user_id: UUID) -> int:
    res = await db.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None)
        )
    )
    tokens = list(res.scalars().all())
    for t in tokens:
        t.revoked_at = datetime.now(UTC)
    await db.commit()
    return len(tokens)


async def get_user(db: AsyncSession, user_id: UUID) -> User:
    user = await db.get(User, user_id)
    if not user:
        raise NotFoundError("User not found")
    return user


async def change_password(
    db: AsyncSession, user_id: UUID, current_password: str, new_password: str
) -> None:
    user = await get_user(db, user_id)
    if not verify_password(current_password, user.password_hash):
        raise AppError("Current password is incorrect", status_code=400)
    user.password_hash = hash_password(new_password)
    await db.commit()
    # Force logout of every other session
    await revoke_all_sessions(db, user.id)
