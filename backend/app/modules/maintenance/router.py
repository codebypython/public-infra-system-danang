"""Maintenance logs + schedules."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.security import require_roles
from app.db.models import MaintenanceLog, MaintenanceSchedule
from app.db.session import get_db

router = APIRouter(prefix="/maintenance", tags=["maintenance"])


class ScheduleCreate(BaseModel):
    asset_id: UUID
    recurrence: str = Field(pattern="^(weekly|monthly|quarterly|yearly)$")
    next_due_at: datetime


@router.get("")
async def list_logs(
    db: AsyncSession = Depends(get_db),
    auth=Depends(require_roles("operator", "admin", "taskforce")),
    asset_id: UUID | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    stmt = select(MaintenanceLog)
    if asset_id:
        stmt = stmt.where(MaintenanceLog.asset_id == asset_id)
    total = int(
        (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    )
    res = await db.execute(
        stmt.order_by(desc(MaintenanceLog.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return {
        "items": [
            {
                "id": l.id,
                "asset_id": l.asset_id,
                "task_id": l.task_id,
                "type": l.type,
                "scheduled_at": l.scheduled_at,
                "completed_at": l.completed_at,
                "notes": l.notes,
                "cost": float(l.cost) if l.cost is not None else None,
            }
            for l in res.scalars().all()
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/schedules", status_code=status.HTTP_201_CREATED)
async def create_schedule(
    body: ScheduleCreate,
    db: AsyncSession = Depends(get_db),
    auth=Depends(require_roles("operator", "admin")),
):
    s = MaintenanceSchedule(
        asset_id=body.asset_id, recurrence=body.recurrence, next_due_at=body.next_due_at
    )
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return {"id": s.id}


@router.get("/schedules/upcoming")
async def upcoming(
    db: AsyncSession = Depends(get_db),
    auth=Depends(require_roles("operator", "admin", "taskforce")),
    days: int = Query(7, ge=1, le=90),
):
    from datetime import timedelta

    soon = datetime.utcnow() + timedelta(days=days)
    res = await db.execute(
        select(MaintenanceSchedule)
        .where(
            MaintenanceSchedule.is_active.is_(True),
            MaintenanceSchedule.next_due_at <= soon,
        )
        .order_by(MaintenanceSchedule.next_due_at)
    )
    return [
        {
            "id": s.id,
            "asset_id": s.asset_id,
            "recurrence": s.recurrence,
            "next_due_at": s.next_due_at,
        }
        for s in res.scalars().all()
    ]
