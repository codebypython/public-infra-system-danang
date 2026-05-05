"""Cameras + camera events (AI surveillance)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.core.security import require_roles
from app.db.models import Camera, CameraEvent
from app.db.session import get_db
from app.utils.geo import is_in_danang, point_lng_lat, wkt_point

router = APIRouter(prefix="/cameras", tags=["cameras"])


class CameraCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    rtsp_url: str | None = None
    hls_url: str | None = None
    lng: float = Field(ge=-180, le=180)
    lat: float = Field(ge=-90, le=90)
    area_id: UUID | None = None
    classes_enabled: list[str] = Field(
        default_factory=lambda: ["littering", "vandalism", "crowd"]
    )
    auto_report_classes: list[str] = Field(default_factory=list)


class CameraUpdate(BaseModel):
    name: str | None = None
    rtsp_url: str | None = None
    hls_url: str | None = None
    classes_enabled: list[str] | None = None
    auto_report_classes: list[str] | None = None
    is_active: bool | None = None


@router.get("")
async def list_cameras(
    db: AsyncSession = Depends(get_db),
    auth=Depends(require_roles("operator", "admin")),
):
    res = await db.execute(select(Camera).order_by(Camera.name))
    out = []
    for c in res.scalars().all():
        ll = point_lng_lat(c.location)
        out.append(
            {
                "id": c.id,
                "name": c.name,
                "rtsp_url": c.rtsp_url,
                "hls_url": c.hls_url,
                "lng": ll[0] if ll else None,
                "lat": ll[1] if ll else None,
                "area_id": c.area_id,
                "classes_enabled": c.classes_enabled,
                "auto_report_classes": c.auto_report_classes,
                "is_active": c.is_active,
                "last_health_at": c.last_health_at,
            }
        )
    return out


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_camera(
    body: CameraCreate,
    db: AsyncSession = Depends(get_db),
    auth=Depends(require_roles("admin")),
):
    if not is_in_danang(body.lng, body.lat):
        raise ValidationError("Coordinates outside Đà Nẵng")
    cam = Camera(
        name=body.name,
        rtsp_url=body.rtsp_url,
        hls_url=body.hls_url,
        location=wkt_point(body.lng, body.lat),
        area_id=body.area_id,
        classes_enabled=body.classes_enabled,
        auto_report_classes=body.auto_report_classes,
    )
    db.add(cam)
    await db.commit()
    await db.refresh(cam)
    return {"id": cam.id, "name": cam.name}


@router.patch("/{camera_id}")
async def update_camera(
    camera_id: UUID,
    body: CameraUpdate,
    db: AsyncSession = Depends(get_db),
    auth=Depends(require_roles("admin")),
):
    cam = await db.get(Camera, camera_id)
    if not cam:
        raise NotFoundError("Camera not found")
    for field, val in body.model_dump(exclude_unset=True).items():
        setattr(cam, field, val)
    await db.commit()
    return {"id": cam.id}


@router.delete("/{camera_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_camera(
    camera_id: UUID,
    db: AsyncSession = Depends(get_db),
    auth=Depends(require_roles("admin")),
):
    cam = await db.get(Camera, camera_id)
    if not cam:
        raise NotFoundError("Camera not found")
    await db.delete(cam)
    await db.commit()


@router.get("/events")
async def list_events(
    db: AsyncSession = Depends(get_db),
    auth=Depends(require_roles("operator", "admin")),
    camera_id: UUID | None = None,
    event_type: str | None = None,
    from_: datetime | None = Query(None, alias="from"),
    to: datetime | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    stmt = select(CameraEvent)
    if camera_id:
        stmt = stmt.where(CameraEvent.camera_id == camera_id)
    if event_type:
        stmt = stmt.where(CameraEvent.event_type == event_type)
    if from_:
        stmt = stmt.where(CameraEvent.detected_at >= from_)
    if to:
        stmt = stmt.where(CameraEvent.detected_at <= to)
    total = int(
        (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    )
    res = await db.execute(
        stmt.order_by(desc(CameraEvent.detected_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [
        {
            "id": e.id,
            "camera_id": e.camera_id,
            "event_type": e.event_type,
            "confidence": e.confidence,
            "snapshot_url": e.snapshot_url,
            "detected_at": e.detected_at,
            "related_report_id": e.related_report_id,
        }
        for e in res.scalars().all()
    ]
    return {"items": items, "total": total, "page": page, "page_size": page_size}
