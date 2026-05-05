"""User management (admin + operator)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.security import hash_password, require_roles
from app.db.models import User
from app.db.session import get_db

router = APIRouter(prefix="/users", tags=["users"])


class UserCreate(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_.\-]+$")
    password: str = Field(min_length=8, max_length=128)
    role: str
    full_name: str | None = None
    phone: str | None = None
    area_id: UUID | None = None


class UserPatch(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    role: str | None = None
    is_active: bool | None = None
    area_id: UUID | None = None


@router.get("")
async def list_users(
    db: AsyncSession = Depends(get_db),
    auth=Depends(require_roles("admin", "operator")),
    role: str | None = None,
    q: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    stmt = select(User).where(User.deleted_at.is_(None))
    if role:
        stmt = stmt.where(User.role == role)
    if q:
        stmt = stmt.where(
            (User.email.ilike(f"%{q}%"))
            | (User.username.ilike(f"%{q}%"))
            | (User.full_name.ilike(f"%{q}%"))
        )
    total = int(
        (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    )
    res = await db.execute(
        stmt.order_by(desc(User.created_at)).offset((page - 1) * page_size).limit(page_size)
    )
    return {
        "items": [
            {
                "id": u.id,
                "email": u.email,
                "username": u.username,
                "role": u.role,
                "full_name": u.full_name,
                "phone": u.phone,
                "area_id": u.area_id,
                "is_active": u.is_active,
                "last_login_at": u.last_login_at,
                "created_at": u.created_at,
            }
            for u in res.scalars().all()
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreate,
    db: AsyncSession = Depends(get_db),
    auth=Depends(require_roles("admin")),
):
    if body.role not in {"citizen", "operator", "taskforce", "admin"}:
        raise ValidationError("Invalid role")
    existing = await db.execute(
        select(User).where((User.email == body.email) | (User.username == body.username))
    )
    if existing.scalar_one_or_none():
        raise ConflictError("Email or username already exists")
    u = User(
        email=body.email,
        username=body.username,
        password_hash=hash_password(body.password),
        role=body.role,
        full_name=body.full_name,
        phone=body.phone,
        area_id=body.area_id,
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return {"id": u.id, "email": u.email, "role": u.role}


@router.patch("/{user_id}")
async def update_user(
    user_id: UUID,
    body: UserPatch,
    db: AsyncSession = Depends(get_db),
    auth=Depends(require_roles("admin")),
):
    u = await db.get(User, user_id)
    if not u or u.deleted_at:
        raise NotFoundError("User not found")
    for field, val in body.model_dump(exclude_unset=True).items():
        setattr(u, field, val)
    await db.commit()
    return {"id": u.id}


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    auth=Depends(require_roles("admin")),
):
    from datetime import UTC, datetime

    u = await db.get(User, user_id)
    if not u:
        raise NotFoundError("User not found")
    u.deleted_at = datetime.now(UTC)
    u.is_active = False
    await db.commit()
