"""Auth router: login / register / refresh / logout / me."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_request_ip, get_token_payload, require_roles
from app.db.session import get_db
from app.modules.auth import service
from app.modules.auth.schemas import (
    LoginRequest,
    PasswordChangeRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserPublic,
    UserUpdate,
)
from app.core.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)):
    return await service.register_user(db, payload)


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    ip = get_request_ip(request)
    ua = request.headers.get("user-agent")
    user, access, refresh, expires = await service.authenticate(
        db, payload, ip=ip, user_agent=ua
    )
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.jwt_access_ttl_minutes * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    payload: RefreshRequest, request: Request, db: AsyncSession = Depends(get_db)
):
    access, refresh, _ = await service.refresh_tokens(
        db,
        payload.refresh_token,
        ip=get_request_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.jwt_access_ttl_minutes * 60,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(payload: RefreshRequest, db: AsyncSession = Depends(get_db)):
    await service.logout(db, payload.refresh_token)


@router.get("/me", response_model=UserPublic)
async def me(
    db: AsyncSession = Depends(get_db),
    payload: dict = Depends(get_token_payload),
):
    return await service.get_user(db, UUID(payload["sub"]))


@router.patch("/me", response_model=UserPublic)
async def update_me(
    body: UserUpdate,
    db: AsyncSession = Depends(get_db),
    payload: dict = Depends(get_token_payload),
):
    user = await service.get_user(db, UUID(payload["sub"]))
    if body.full_name is not None:
        user.full_name = body.full_name
    if body.phone is not None:
        user.phone = body.phone
    if body.avatar_url is not None:
        user.avatar_url = body.avatar_url
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/password/change", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    body: PasswordChangeRequest,
    db: AsyncSession = Depends(get_db),
    payload: dict = Depends(get_token_payload),
):
    await service.change_password(
        db, UUID(payload["sub"]), body.current_password, body.new_password
    )


@router.post("/sessions/revoke-all", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_all(
    db: AsyncSession = Depends(get_db),
    payload: dict = Depends(require_roles("citizen", "operator", "taskforce", "admin")),
):
    await service.revoke_all_sessions(db, UUID(payload["sub"]))
