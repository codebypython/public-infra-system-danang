"""Report router — citizen + operator + admin endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_token_payload, require_roles
from app.db.session import get_db
from app.modules.notifications.broker import broker
from app.modules.reports import service
from app.modules.reports.schemas import (
    CommentCreate,
    ReportRatingRequest,
    ReportRejectRequest,
)

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("")
async def list_reports(
    db: AsyncSession = Depends(get_db),
    auth=Depends(get_token_payload),
    status_: str | None = Query(None, alias="status"),
    area_id: UUID | None = None,
    reporter_id: UUID | None = None,
    type: str | None = Query(None, alias="type"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    # Citizen sees only own
    if auth["role"] == "citizen":
        reporter_id = UUID(auth["sub"])
    items, total = await service.list_reports(
        db,
        status=status_,
        area_id=area_id,
        reporter_id=reporter_id,
        incident_type=type,
        page=page,
        page_size=page_size,
    )
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/me")
async def list_my_reports(
    db: AsyncSession = Depends(get_db),
    auth=Depends(get_token_payload),
    status_: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    items, total = await service.list_reports(
        db,
        status=status_,
        area_id=None,
        reporter_id=UUID(auth["sub"]),
        incident_type=None,
        page=page,
        page_size=page_size,
    )
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/stats")
async def stats(db: AsyncSession = Depends(get_db), auth=Depends(get_token_payload)):
    return await service.stats(db)


@router.get("/{report_id}")
async def get_report(report_id: UUID, db: AsyncSession = Depends(get_db), auth=Depends(get_token_payload)):
    return await service.get_report(db, report_id)


@router.get("/{report_id}/timeline")
async def timeline(report_id: UUID, db: AsyncSession = Depends(get_db), auth=Depends(get_token_payload)):
    return await service.get_timeline(db, report_id)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_report(
    db: AsyncSession = Depends(get_db),
    auth=Depends(require_roles("citizen", "operator", "admin")),
    lng: float = Form(...),
    lat: float = Form(...),
    incident_type: str | None = Form(None),
    severity: str = Form("medium"),
    description: str | None = Form(None),
    related_asset_id: UUID | None = Form(None),
    image: UploadFile | None = File(None),
):
    image_bytes: bytes | None = None
    image_filename: str | None = None
    image_content_type: str | None = None
    if image is not None:
        image_bytes = await image.read()
        image_filename = image.filename
        image_content_type = image.content_type
    report = await service.create_report(
        db,
        reporter_id=UUID(auth["sub"]),
        lng=lng,
        lat=lat,
        incident_type=incident_type,
        severity=severity,
        description=description,
        related_asset_id=related_asset_id,
        image_bytes=image_bytes,
        image_filename=image_filename,
        image_content_type=image_content_type,
    )
    # Broadcast WebSocket event
    await broker.publish(
        channel="ops",
        event="report.created",
        data={
            "id": str(report.id),
            "code": report.code,
            "severity": report.severity,
            "incident_type": report.incident_type,
            "area_id": str(report.area_id) if report.area_id else None,
        },
    )
    return await service.to_dict(db, report)


@router.post("/{report_id}/accept")
async def accept_report(
    report_id: UUID,
    db: AsyncSession = Depends(get_db),
    auth=Depends(require_roles("operator", "admin")),
):
    from app.modules.tasks.service import auto_create_task_from_report

    r = await service.update_status(
        db, report_id=report_id, new_status="accepted", actor_id=UUID(auth["sub"])
    )
    task = await auto_create_task_from_report(db, r, created_by=UUID(auth["sub"]))
    await broker.publish(
        channel=f"user:{r.reporter_id}",
        event="report.status_changed",
        data={"id": str(r.id), "status": r.status, "task_id": str(task.id) if task else None},
    )
    return await service.to_dict(db, r)


@router.post("/{report_id}/reject")
async def reject_report(
    report_id: UUID,
    body: ReportRejectRequest,
    db: AsyncSession = Depends(get_db),
    auth=Depends(require_roles("operator", "admin")),
):
    r = await service.update_status(
        db,
        report_id=report_id,
        new_status="rejected",
        actor_id=UUID(auth["sub"]),
        rejection_reason=body.reason,
    )
    await broker.publish(
        channel=f"user:{r.reporter_id}",
        event="report.status_changed",
        data={"id": str(r.id), "status": r.status, "reason": body.reason},
    )
    return await service.to_dict(db, r)


@router.post("/{report_id}/comments", status_code=status.HTTP_201_CREATED)
async def add_comment(
    report_id: UUID,
    body: CommentCreate,
    db: AsyncSession = Depends(get_db),
    auth=Depends(get_token_payload),
):
    return await service.add_comment(
        db,
        report_id=report_id,
        user_id=UUID(auth["sub"]),
        body=body.body,
        is_internal=body.is_internal,
    )


@router.get("/{report_id}/comments")
async def list_comments(
    report_id: UUID,
    db: AsyncSession = Depends(get_db),
    auth=Depends(get_token_payload),
):
    include_internal = auth["role"] in ("operator", "admin", "taskforce")
    return await service.list_comments(db, report_id, include_internal=include_internal)


@router.post("/{report_id}/rating")
async def rate_report(
    report_id: UUID,
    body: ReportRatingRequest,
    db: AsyncSession = Depends(get_db),
    auth=Depends(require_roles("citizen")),
):
    r = await service.submit_rating(
        db,
        report_id=report_id,
        user_id=UUID(auth["sub"]),
        rating=body.rating,
        comment=body.comment,
    )
    return await service.to_dict(db, r)
