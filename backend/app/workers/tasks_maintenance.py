"""Recurring maintenance schedules → auto-create tasks."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models import Asset, MaintenanceSchedule, Task
from app.db.session import AsyncSessionLocal
from app.utils.codes import task_code
from app.workers.celery_app import celery_app

logger = get_logger(__name__)

NEXT_OFFSETS = {
    "weekly": timedelta(days=7),
    "monthly": timedelta(days=30),
    "quarterly": timedelta(days=90),
    "yearly": timedelta(days=365),
}


async def _run() -> int:
    async with AsyncSessionLocal() as db:  # type: AsyncSession
        now = datetime.utcnow()
        res = await db.execute(
            select(MaintenanceSchedule).where(
                MaintenanceSchedule.is_active.is_(True),
                MaintenanceSchedule.next_due_at <= now,
            )
        )
        schedules = list(res.scalars().all())
        for s in schedules:
            asset = await db.get(Asset, s.asset_id)
            if not asset:
                continue
            from sqlalchemy import func as sql_func

            seq_res = await db.execute(
                select(sql_func.count(Task.id)).where(
                    sql_func.extract("year", Task.created_at) == datetime.utcnow().year
                )
            )
            seq = int(seq_res.scalar_one() or 0) + 1
            db.add(
                Task(
                    code=task_code(seq),
                    title=f"Bảo trì định kỳ {asset.code}",
                    related_asset_id=asset.id,
                    area_id=asset.area_id,
                    priority="medium",
                    status="open",
                    due_at=now + timedelta(days=2),
                )
            )
            offset = NEXT_OFFSETS.get(s.recurrence, timedelta(days=30))
            s.next_due_at = now + offset
        await db.commit()
        return len(schedules)


@celery_app.task(name="app.workers.tasks_maintenance.run_maintenance_schedules")
def run_maintenance_schedules() -> int:
    n = asyncio.run(_run())
    logger.info("maintenance.schedules.run", count=n)
    return n
