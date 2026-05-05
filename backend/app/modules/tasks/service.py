"""Task service — auto-create from accepted report, smart dispatch, GPS check-in,
before/after photo upload with watermark, route optimization (TSP nearest-neighbor)."""

from __future__ import annotations

import io
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, PermissionError as PermErr, ValidationError
from app.db.models import (
    ActivityLog,
    Asset,
    Attachment,
    IncidentReport,
    MaintenanceLog,
    Task,
    TaskAssignment,
    User,
)
from app.modules.notifications.broker import broker
from app.modules.notifications.router import create_notification
from app.modules.reports.service import compute_sla_due
from app.utils.codes import task_code
from app.utils.geo import point_lng_lat, wkt_point
from app.utils.storage import upload_bytes


async def _next_task_seq(db: AsyncSession) -> int:
    year = datetime.utcnow().year
    res = await db.execute(
        select(func.count(Task.id)).where(func.extract("year", Task.created_at) == year)
    )
    return int(res.scalar_one() or 0) + 1


def _priority_from_severity(sev: str) -> str:
    return {"urgent": "urgent", "high": "high", "medium": "medium", "low": "low"}.get(sev, "medium")


async def auto_create_task_from_report(
    db: AsyncSession, report: IncidentReport, *, created_by: UUID
) -> Task | None:
    """Called when operator accepts a report — create + auto-assign nearest taskforce."""
    seq = await _next_task_seq(db)
    code = task_code(seq)
    task = Task(
        code=code,
        title=f"{report.code}: {report.incident_type or 'Sự cố'}",
        description=report.description,
        related_report_id=report.id,
        related_asset_id=report.related_asset_id,
        area_id=report.area_id,
        priority=_priority_from_severity(report.severity),
        status="open",
        due_at=report.sla_due_at,
        created_by=created_by,
    )
    db.add(task)
    await db.flush()

    # Auto-suggest assignee (nearest idle taskforce in same area)
    suggestions = await suggest_assignees(db, report_id=report.id, limit=1)
    if suggestions:
        await assign_task(db, task.id, [suggestions[0]["user_id"]], assigned_by=created_by)
    db.add(
        ActivityLog(
            user_id=created_by,
            action="task.created",
            target_type="task",
            target_id=task.id,
            after={"code": code, "from_report": str(report.id)},
        )
    )
    await db.commit()
    await db.refresh(task)
    return task


async def suggest_assignees(
    db: AsyncSession, *, report_id: UUID, limit: int = 5
) -> list[dict[str, Any]]:
    report = await db.get(IncidentReport, report_id)
    if not report:
        raise NotFoundError("Report not found")

    # Subquery: count of active tasks per user (load metric)
    active_load = (
        select(TaskAssignment.user_id, func.count(TaskAssignment.task_id).label("load"))
        .join(Task, Task.id == TaskAssignment.task_id)
        .where(Task.status.in_(("assigned", "in_progress")))
        .group_by(TaskAssignment.user_id)
        .subquery()
    )

    stmt = (
        select(
            User.id,
            User.full_name,
            User.email,
            func.coalesce(active_load.c.load, 0).label("load"),
            func.ST_Distance(
                func.ST_Transform(User.last_known_location, 3857),
                func.ST_Transform(report.location, 3857),
            ).label("dist"),
        )
        .outerjoin(active_load, active_load.c.user_id == User.id)
        .where(
            User.role == "taskforce",
            User.is_active.is_(True),
            User.deleted_at.is_(None),
        )
    )
    if report.area_id:
        stmt = stmt.where((User.area_id == report.area_id) | (User.area_id.is_(None)))
    stmt = stmt.order_by("load", "dist").limit(limit)
    res = await db.execute(stmt)
    return [
        {
            "user_id": r.id,
            "full_name": r.full_name,
            "email": r.email,
            "distance_m": float(r.dist) if r.dist is not None else None,
            "current_load": int(r.load),
        }
        for r in res.all()
    ]


async def assign_task(
    db: AsyncSession, task_id: UUID, assignee_ids: list[UUID], *, assigned_by: UUID
) -> Task:
    task = await db.get(Task, task_id)
    if not task:
        raise NotFoundError("Task not found")
    # Replace assignments
    await db.execute(
        TaskAssignment.__table__.delete().where(TaskAssignment.task_id == task_id)
    )
    for uid in assignee_ids:
        db.add(TaskAssignment(task_id=task_id, user_id=uid))
    if assignee_ids:
        task.status = "assigned"
    db.add(
        ActivityLog(
            user_id=assigned_by,
            action="task.assigned",
            target_type="task",
            target_id=task.id,
            after={"assignees": [str(u) for u in assignee_ids]},
        )
    )
    await db.commit()
    # Notify each assignee
    for uid in assignee_ids:
        await create_notification(
            db,
            user_id=uid,
            type="task.assigned",
            title=f"Bạn được phân công task {task.code}",
            body=task.title,
            data={"task_id": str(task.id)},
        )
    return task


async def to_dict(db: AsyncSession, task: Task) -> dict[str, Any]:
    res_a = await db.execute(
        select(TaskAssignment.user_id).where(TaskAssignment.task_id == task.id)
    )
    res_imgs = await db.execute(
        select(Attachment.url, Attachment.role).where(
            Attachment.owner_type == "task", Attachment.owner_id == task.id
        )
    )
    before, after = [], []
    for url, role in res_imgs.all():
        if role == "before":
            before.append(url)
        elif role == "after":
            after.append(url)
    return {
        "id": task.id,
        "code": task.code,
        "title": task.title,
        "description": task.description,
        "related_report_id": task.related_report_id,
        "related_asset_id": task.related_asset_id,
        "area_id": task.area_id,
        "priority": task.priority,
        "status": task.status,
        "due_at": task.due_at,
        "check_in_at": task.check_in_at,
        "completed_at": task.completed_at,
        "notes": task.notes,
        "parts_used": task.parts_used,
        "created_at": task.created_at,
        "assignees": [r[0] for r in res_a.all()],
        "before_images": before,
        "after_images": after,
    }


async def list_tasks(
    db: AsyncSession,
    *,
    assigned_to: UUID | None,
    status: str | None,
    area_id: UUID | None,
    page: int,
    page_size: int,
) -> tuple[list[dict[str, Any]], int]:
    stmt = select(Task)
    if assigned_to:
        stmt = stmt.join(TaskAssignment, TaskAssignment.task_id == Task.id).where(
            TaskAssignment.user_id == assigned_to
        )
    if status:
        stmt = stmt.where(Task.status == status)
    if area_id:
        stmt = stmt.where(Task.area_id == area_id)
    total = int(
        (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    )
    res = await db.execute(
        stmt.order_by(desc(Task.created_at)).offset((page - 1) * page_size).limit(page_size)
    )
    items = [await to_dict(db, t) for t in res.scalars().all()]
    return items, total


async def get_task(db: AsyncSession, task_id: UUID) -> dict[str, Any]:
    t = await db.get(Task, task_id)
    if not t:
        raise NotFoundError("Task not found")
    return await to_dict(db, t)


async def check_in(db: AsyncSession, task_id: UUID, user_id: UUID, lng: float, lat: float) -> Task:
    t = await db.get(Task, task_id)
    if not t:
        raise NotFoundError("Task not found")
    res = await db.execute(
        select(TaskAssignment).where(
            TaskAssignment.task_id == task_id, TaskAssignment.user_id == user_id
        )
    )
    if not res.scalar_one_or_none():
        raise PermErr("You are not assigned to this task")
    # Verify within 100m of report location (if any)
    if t.related_report_id:
        rep = await db.get(IncidentReport, t.related_report_id)
        if rep:
            check_point = wkt_point(lng, lat)
            res_d = await db.execute(
                select(
                    func.ST_Distance(
                        func.ST_Transform(rep.location, 3857),
                        func.ST_Transform(func.ST_GeomFromEWKT(check_point), 3857),
                    )
                )
            )
            distance = float(res_d.scalar_one() or 0)
            if distance > 100:
                raise ValidationError(
                    f"Bạn cách hiện trường {int(distance)}m — phải ở trong vòng 100m"
                )
    t.check_in_at = datetime.now(UTC)
    t.check_in_location = wkt_point(lng, lat)
    if t.status == "assigned":
        t.status = "in_progress"
    db.add(
        ActivityLog(
            user_id=user_id,
            action="task.check_in",
            target_type="task",
            target_id=t.id,
            after={"location": [lng, lat]},
        )
    )
    await db.commit()
    await db.refresh(t)
    return t


async def upload_task_photo(
    db: AsyncSession,
    *,
    task_id: UUID,
    user_id: UUID,
    photo_role: str,
    image_bytes: bytes,
    filename: str,
    content_type: str,
) -> Attachment:
    if photo_role not in {"before", "after"}:
        raise ValidationError("photo role must be 'before' or 'after'")
    t = await db.get(Task, task_id)
    if not t:
        raise NotFoundError("Task not found")
    # Watermark with timestamp + user
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        draw = ImageDraw.Draw(img)
        ts = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
        watermark = f"{t.code} • {photo_role} • {ts}"
        try:
            font = ImageFont.load_default()
        except Exception:  # noqa: BLE001
            font = None
        # Background rect
        margin = 20
        text_y = img.height - 40
        draw.rectangle(
            [(margin - 5, text_y - 5), (img.width - margin + 5, text_y + 25)],
            fill=(0, 0, 0, 160),
        )
        draw.text((margin, text_y), watermark, fill="white", font=font)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        url = upload_bytes(
            buf.getvalue(), folder=f"tasks/{photo_role}", filename=filename, content_type="image/jpeg"
        )
    except Exception as exc:  # noqa: BLE001
        raise ValidationError(f"Invalid image: {exc}") from exc
    a = Attachment(
        owner_type="task",
        owner_id=t.id,
        type="image",
        url=url,
        size_bytes=len(image_bytes),
        mime_type="image/jpeg",
        role=photo_role,
        uploaded_by=user_id,
    )
    db.add(a)
    await db.commit()
    await db.refresh(a)
    return a


async def complete_task(
    db: AsyncSession, *, task_id: UUID, user_id: UUID, notes: str | None, parts_used: dict | None
) -> Task:
    t = await db.get(Task, task_id)
    if not t:
        raise NotFoundError("Task not found")
    if t.status not in ("in_progress", "assigned"):
        raise ValidationError("Task must be in_progress to complete")
    # Require at least 1 before + 1 after image
    res = await db.execute(
        select(Attachment.role).where(
            Attachment.owner_type == "task", Attachment.owner_id == t.id
        )
    )
    roles = [r[0] for r in res.all()]
    if "before" not in roles or "after" not in roles:
        raise ValidationError("Cần ít nhất 1 ảnh before và 1 ảnh after")
    t.status = "pending_review"
    t.notes = notes
    t.parts_used = parts_used
    t.completed_at = datetime.now(UTC)
    db.add(
        ActivityLog(
            user_id=user_id,
            action="task.completed_by_taskforce",
            target_type="task",
            target_id=t.id,
        )
    )
    await db.commit()
    # Notify operator
    await broker.publish(
        channel="ops",
        event="task.pending_review",
        data={"task_id": str(t.id), "code": t.code},
    )
    await db.refresh(t)
    return t


async def approve_task(db: AsyncSession, *, task_id: UUID, actor_id: UUID) -> Task:
    """Operator approves completion — task -> completed, report -> resolved, maintenance log."""
    from app.modules.reports.service import update_status as update_report_status

    t = await db.get(Task, task_id)
    if not t:
        raise NotFoundError("Task not found")
    if t.status != "pending_review":
        raise ValidationError("Task must be in pending_review")
    t.status = "completed"
    if t.related_report_id:
        await update_report_status(
            db,
            report_id=t.related_report_id,
            new_status="resolved",
            actor_id=actor_id,
        )
        # Notify reporter
        rep = await db.get(IncidentReport, t.related_report_id)
        if rep and rep.reporter_id:
            await create_notification(
                db,
                user_id=rep.reporter_id,
                type="report.resolved",
                title=f"Sự cố {rep.code} đã được giải quyết",
                body="Bạn có thể đánh giá kết quả xử lý.",
                data={"report_id": str(rep.id)},
            )
    if t.related_asset_id:
        db.add(
            MaintenanceLog(
                asset_id=t.related_asset_id,
                task_id=t.id,
                technician_id=None,
                type="reactive",
                completed_at=t.completed_at,
                notes=t.notes,
            )
        )
        a = await db.get(Asset, t.related_asset_id)
        if a:
            a.last_maintained_at = datetime.now(UTC)
    db.add(
        ActivityLog(
            user_id=actor_id,
            action="task.approved",
            target_type="task",
            target_id=t.id,
        )
    )
    await db.commit()
    await db.refresh(t)
    return t


# ---------------------------------------------------------------------------
# Route optimization (nearest-neighbor TSP — practical baseline)
# ---------------------------------------------------------------------------


async def optimize_route(
    db: AsyncSession, user_id: UUID, *, start_lng: float | None, start_lat: float | None
) -> dict[str, Any]:
    res = await db.execute(
        select(Task)
        .join(TaskAssignment, TaskAssignment.task_id == Task.id)
        .where(
            TaskAssignment.user_id == user_id,
            Task.status.in_(("assigned", "in_progress")),
        )
    )
    tasks = list(res.scalars().all())
    if not tasks:
        return {"ordered_task_ids": [], "total_distance_m": 0.0, "estimated_duration_minutes": 0}

    # Resolve coordinates from related_report or related_asset
    coords: dict[UUID, tuple[float, float]] = {}
    for t in tasks:
        if t.related_report_id:
            rep = await db.get(IncidentReport, t.related_report_id)
            if rep:
                ll = point_lng_lat(rep.location)
                if ll:
                    coords[t.id] = ll
        if t.id not in coords and t.related_asset_id:
            ass = await db.get(Asset, t.related_asset_id)
            if ass:
                ll = point_lng_lat(ass.location)
                if ll:
                    coords[t.id] = ll

    # Default start = user.last_known_location or city center
    if start_lng is None or start_lat is None:
        u = await db.get(User, user_id)
        if u and u.last_known_location is not None:
            ll = point_lng_lat(u.last_known_location)
            if ll:
                start_lng, start_lat = ll
        if start_lng is None:
            from app.core.config import settings

            start_lng, start_lat = settings.danang_center_lng, settings.danang_center_lat

    # Haversine
    import math

    def hav(a: tuple[float, float], b: tuple[float, float]) -> float:
        lon1, lat1 = a
        lon2, lat2 = b
        r = 6371000
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        x = (
            math.sin(dlat / 2) ** 2
            + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
        )
        return 2 * r * math.asin(math.sqrt(x))

    remaining = {tid: c for tid, c in coords.items()}
    ordered: list[UUID] = []
    cur = (start_lng, start_lat)
    total = 0.0
    while remaining:
        nearest = min(remaining.items(), key=lambda kv: hav(cur, kv[1]))
        total += hav(cur, nearest[1])
        cur = nearest[1]
        ordered.append(nearest[0])
        del remaining[nearest[0]]

    avg_speed_kmh = 25  # urban average
    duration = int((total / 1000) / avg_speed_kmh * 60) + len(ordered) * 15  # 15 min on-site each
    return {
        "ordered_task_ids": ordered,
        "total_distance_m": total,
        "estimated_duration_minutes": duration,
    }
