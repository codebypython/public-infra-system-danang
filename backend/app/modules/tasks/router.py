"""Task router."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_token_payload, require_roles
from app.db.session import get_db
from app.modules.tasks import service
from app.modules.tasks.schemas import (
    TaskAssignRequest,
    TaskCheckInRequest,
    TaskCompleteRequest,
    TaskCreate,
)

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("")
async def list_tasks(
    db: AsyncSession = Depends(get_db),
    auth=Depends(get_token_payload),
    assigned_to: str | None = Query(None, description="UUID or 'me'"),
    status_: str | None = Query(None, alias="status"),
    area_id: UUID | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    if assigned_to == "me":
        target = UUID(auth["sub"])
    elif assigned_to:
        target = UUID(assigned_to)
    elif auth["role"] == "taskforce":
        target = UUID(auth["sub"])
    else:
        target = None
    items, total = await service.list_tasks(
        db, assigned_to=target, status=status_, area_id=area_id, page=page, page_size=page_size
    )
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/route-optimize")
async def route_optimize(
    db: AsyncSession = Depends(get_db),
    auth=Depends(require_roles("taskforce", "admin", "operator")),
    start_lng: float | None = Query(None),
    start_lat: float | None = Query(None),
):
    return await service.optimize_route(
        db, UUID(auth["sub"]), start_lng=start_lng, start_lat=start_lat
    )


@router.get("/{task_id}")
async def get_task(task_id: UUID, db: AsyncSession = Depends(get_db), auth=Depends(get_token_payload)):
    return await service.get_task(db, task_id)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_task(
    body: TaskCreate,
    db: AsyncSession = Depends(get_db),
    auth=Depends(require_roles("operator", "admin")),
):
    from app.db.models import Task
    from app.utils.codes import task_code

    seq = await service._next_task_seq(db)
    code = task_code(seq)
    task = Task(
        code=code,
        title=body.title,
        description=body.description,
        related_report_id=body.related_report_id,
        related_asset_id=body.related_asset_id,
        priority=body.priority,
        due_at=body.due_at,
        created_by=UUID(auth["sub"]),
    )
    db.add(task)
    await db.flush()
    if body.assignee_ids:
        await service.assign_task(db, task.id, body.assignee_ids, assigned_by=UUID(auth["sub"]))
    await db.commit()
    await db.refresh(task)
    return await service.to_dict(db, task)


@router.get("/{task_id}/suggest-assignees")
async def suggest_assignees(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    auth=Depends(require_roles("operator", "admin")),
):
    from app.db.models import Task

    t = await db.get(Task, task_id)
    if not t or not t.related_report_id:
        return []
    return await service.suggest_assignees(db, report_id=t.related_report_id, limit=5)


@router.post("/{task_id}/assign")
async def assign(
    task_id: UUID,
    body: TaskAssignRequest,
    db: AsyncSession = Depends(get_db),
    auth=Depends(require_roles("operator", "admin")),
):
    t = await service.assign_task(db, task_id, body.assignee_ids, assigned_by=UUID(auth["sub"]))
    return await service.to_dict(db, t)


@router.post("/{task_id}/check-in")
async def check_in(
    task_id: UUID,
    body: TaskCheckInRequest,
    db: AsyncSession = Depends(get_db),
    auth=Depends(require_roles("taskforce", "admin")),
):
    t = await service.check_in(db, task_id, UUID(auth["sub"]), body.lng, body.lat)
    return await service.to_dict(db, t)


@router.post("/{task_id}/photos")
async def upload_photo(
    task_id: UUID,
    role: str = Form(..., description="'before' or 'after'"),
    image: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    auth=Depends(require_roles("taskforce", "admin")),
):
    content = await image.read()
    a = await service.upload_task_photo(
        db,
        task_id=task_id,
        user_id=UUID(auth["sub"]),
        photo_role=role,
        image_bytes=content,
        filename=image.filename or "photo.jpg",
        content_type=image.content_type or "image/jpeg",
    )
    return {"id": a.id, "url": a.url, "role": a.role}


@router.post("/{task_id}/complete")
async def complete(
    task_id: UUID,
    body: TaskCompleteRequest,
    db: AsyncSession = Depends(get_db),
    auth=Depends(require_roles("taskforce", "admin")),
):
    t = await service.complete_task(
        db, task_id=task_id, user_id=UUID(auth["sub"]), notes=body.notes, parts_used=body.parts_used
    )
    return await service.to_dict(db, t)


@router.post("/{task_id}/approve")
async def approve(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    auth=Depends(require_roles("operator", "admin")),
):
    t = await service.approve_task(db, task_id=task_id, actor_id=UUID(auth["sub"]))
    return await service.to_dict(db, t)
