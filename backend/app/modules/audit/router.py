"""Audit log read API."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_roles
from app.db.models import ActivityLog
from app.db.session import get_db

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/logs")
async def list_logs(
    db: AsyncSession = Depends(get_db),
    auth=Depends(require_roles("operator", "admin")),
    user_id: UUID | None = None,
    action: str | None = None,
    target_type: str | None = None,
    target_id: UUID | None = None,
    from_: datetime | None = Query(None, alias="from"),
    to: datetime | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
):
    stmt = select(ActivityLog)
    if user_id:
        stmt = stmt.where(ActivityLog.user_id == user_id)
    if action:
        stmt = stmt.where(ActivityLog.action == action)
    if target_type:
        stmt = stmt.where(ActivityLog.target_type == target_type)
    if target_id:
        stmt = stmt.where(ActivityLog.target_id == target_id)
    if from_:
        stmt = stmt.where(ActivityLog.created_at >= from_)
    if to:
        stmt = stmt.where(ActivityLog.created_at <= to)
    total = int(
        (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    )
    res = await db.execute(
        stmt.order_by(desc(ActivityLog.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return {
        "items": [
            {
                "id": l.id,
                "user_id": l.user_id,
                "action": l.action,
                "target_type": l.target_type,
                "target_id": l.target_id,
                "before": l.before,
                "after": l.after,
                "created_at": l.created_at,
            }
            for l in res.scalars().all()
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
