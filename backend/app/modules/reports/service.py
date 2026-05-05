"""Report service — create with AI, status workflow, duplicate detection, SLA."""

from __future__ import annotations

import io
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import httpx
from PIL import Image, ImageOps
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    AppError,
    ConflictError,
    NotFoundError,
    PermissionError as PermErr,
    RateLimitError,
    ValidationError,
)
from app.db.models import (
    ActivityLog,
    Area,
    Asset,
    Attachment,
    Comment,
    IncidentReport,
)
from app.modules.auth.service import get_redis
from app.utils.codes import report_code
from app.utils.geo import is_in_danang, point_lng_lat, wkt_point
from app.utils.storage import upload_bytes


SLA_HOURS = {"urgent": 2, "high": 8, "medium": 24, "low": 72}


def compute_sla_due(severity: str, created: datetime) -> datetime:
    return created + timedelta(hours=SLA_HOURS.get(severity, 24))


async def check_report_rate_limit(reporter_id: UUID) -> None:
    r = get_redis()
    key = f"report:rate:{reporter_id}"
    val = await r.get(key)
    if val and int(val) >= settings.rate_limit_report_per_hour:
        raise RateLimitError("Bạn đã gửi quá nhiều báo cáo trong 1 giờ qua, vui lòng thử lại sau")
    pipe = r.pipeline()
    pipe.incr(key, 1)
    pipe.expire(key, 3600)
    await pipe.execute()


async def detect_duplicate(
    db: AsyncSession, lng: float, lat: float, incident_type: str | None
) -> IncidentReport | None:
    if not incident_type:
        return None
    point = func.ST_GeomFromEWKT(wkt_point(lng, lat))
    res = await db.execute(
        select(IncidentReport)
        .where(
            func.ST_DWithin(
                func.ST_Transform(IncidentReport.location, 3857),
                func.ST_Transform(point, 3857),
                50,
            ),
            IncidentReport.incident_type == incident_type,
            IncidentReport.created_at >= datetime.now(UTC) - timedelta(hours=1),
            IncidentReport.status.in_(("pending", "accepted", "in_progress")),
        )
        .limit(1)
    )
    return res.scalar_one_or_none()


async def call_ai_classify(image_bytes: bytes, filename: str, content_type: str) -> dict[str, Any]:
    """Call AI service /classify; tolerate failure (return mock)."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{settings.ai_service_url}/classify",
                files={"file": (filename, image_bytes, content_type)},
            )
            if resp.status_code == 200:
                return resp.json()
    except Exception:  # noqa: BLE001
        pass
    return {"primary_class": None, "confidence": 0.0, "detections": [], "is_valid_report": False}


async def auto_assign_area(db: AsyncSession, lng: float, lat: float) -> UUID | None:
    res = await db.execute(
        select(Area.id).where(
            func.ST_Contains(Area.geometry, func.ST_GeomFromEWKT(wkt_point(lng, lat)))
        )
    )
    row = res.first()
    return row.id if row else None


async def find_nearest_asset(
    db: AsyncSession, lng: float, lat: float, radius_m: int = 30
) -> UUID | None:
    point = func.ST_GeomFromEWKT(wkt_point(lng, lat))
    res = await db.execute(
        select(Asset.id)
        .where(
            Asset.deleted_at.is_(None),
            func.ST_DWithin(
                func.ST_Transform(Asset.location, 3857),
                func.ST_Transform(point, 3857),
                radius_m,
            ),
        )
        .order_by(
            func.ST_Distance(
                func.ST_Transform(Asset.location, 3857), func.ST_Transform(point, 3857)
            )
        )
        .limit(1)
    )
    row = res.first()
    return row.id if row else None


async def _next_report_seq(db: AsyncSession) -> int:
    year = datetime.utcnow().year
    res = await db.execute(
        select(func.count(IncidentReport.id)).where(
            func.extract("year", IncidentReport.created_at) == year
        )
    )
    return int(res.scalar_one() or 0) + 1


async def create_report(
    db: AsyncSession,
    *,
    reporter_id: UUID,
    lng: float,
    lat: float,
    incident_type: str | None,
    severity: str,
    description: str | None,
    related_asset_id: UUID | None,
    image_bytes: bytes | None,
    image_filename: str | None,
    image_content_type: str | None,
) -> IncidentReport:
    if not is_in_danang(lng, lat):
        raise ValidationError("Tọa độ ngoài phạm vi Đà Nẵng")
    await check_report_rate_limit(reporter_id)

    ai_class = None
    ai_confidence = None
    ai_bbox = None
    image_url = None
    image_thumb_url = None
    if image_bytes:
        # Image moderation: max 10MB, jpeg/png/webp
        if len(image_bytes) > 10 * 1024 * 1024:
            raise ValidationError("Image too large (max 10MB)")
        if image_content_type not in ("image/jpeg", "image/png", "image/webp"):
            raise ValidationError("Image must be JPEG/PNG/WEBP")

        # Compress + thumbnail
        try:
            img = Image.open(io.BytesIO(image_bytes))
            img = ImageOps.exif_transpose(img)
            img.thumbnail((1920, 1920))
            buf = io.BytesIO()
            img.convert("RGB").save(buf, format="JPEG", quality=85, optimize=True)
            buf.seek(0)
            image_url = upload_bytes(
                buf.getvalue(),
                folder="reports",
                filename=(image_filename or "report.jpg"),
                content_type="image/jpeg",
            )
            # Thumbnail
            tbuf = io.BytesIO()
            timg = img.copy()
            timg.thumbnail((400, 400))
            timg.convert("RGB").save(tbuf, format="JPEG", quality=80)
            tbuf.seek(0)
            image_thumb_url = upload_bytes(
                tbuf.getvalue(),
                folder="reports/thumb",
                filename=f"thumb_{image_filename or 'report.jpg'}",
                content_type="image/jpeg",
            )
        except Exception as exc:  # noqa: BLE001
            raise ValidationError(f"Invalid image: {exc}") from exc

        ai = await call_ai_classify(image_bytes, image_filename or "img.jpg", image_content_type or "image/jpeg")
        ai_class = ai.get("primary_class")
        ai_confidence = ai.get("confidence")
        ai_bbox = ai
        if (
            (incident_type is None)
            and ai_class
            and ai_confidence
            and ai_confidence >= settings.ai_confidence_threshold
        ):
            incident_type = ai_class

    if severity not in {"low", "medium", "high", "urgent"}:
        raise ValidationError("Invalid severity")

    # Duplicate detection
    dup = await detect_duplicate(db, lng, lat, incident_type)
    if dup:
        raise ConflictError(
            f"Đã có báo cáo tương tự gần đây (mã {dup.code}). Vui lòng kiểm tra trang theo dõi."
        )

    if not related_asset_id:
        related_asset_id = await find_nearest_asset(db, lng, lat)

    area_id = await auto_assign_area(db, lng, lat)
    seq = await _next_report_seq(db)
    code = report_code(seq)
    now = datetime.now(UTC)

    report = IncidentReport(
        code=code,
        reporter_id=reporter_id,
        related_asset_id=related_asset_id,
        area_id=area_id,
        location=wkt_point(lng, lat),
        incident_type=incident_type,
        severity=severity,
        description=description,
        ai_class=ai_class,
        ai_confidence=ai_confidence,
        ai_bbox=ai_bbox,
        status="pending",
        sla_due_at=compute_sla_due(severity, now),
    )
    db.add(report)
    await db.flush()

    if image_url:
        db.add(
            Attachment(
                owner_type="report",
                owner_id=report.id,
                type="image",
                url=image_url,
                thumbnail_url=image_thumb_url,
                size_bytes=len(image_bytes),
                mime_type=image_content_type,
                role="evidence",
                uploaded_by=reporter_id,
            )
        )
    db.add(
        ActivityLog(
            user_id=reporter_id,
            action="report.created",
            target_type="report",
            target_id=report.id,
            after={"code": code, "incident_type": incident_type, "severity": severity},
        )
    )
    await db.commit()
    await db.refresh(report)
    return report


async def to_dict(db: AsyncSession, report: IncidentReport) -> dict[str, Any]:
    ll = point_lng_lat(report.location)
    images_q = await db.execute(
        select(Attachment.url).where(
            Attachment.owner_type == "report", Attachment.owner_id == report.id
        )
    )
    return {
        "id": report.id,
        "code": report.code,
        "reporter_id": report.reporter_id,
        "related_asset_id": report.related_asset_id,
        "area_id": report.area_id,
        "lng": ll[0] if ll else None,
        "lat": ll[1] if ll else None,
        "incident_type": report.incident_type,
        "severity": report.severity,
        "description": report.description,
        "ai_class": report.ai_class,
        "ai_confidence": report.ai_confidence,
        "status": report.status,
        "rejection_reason": report.rejection_reason,
        "sla_due_at": report.sla_due_at,
        "resolved_at": report.resolved_at,
        "rating": report.rating,
        "created_at": report.created_at,
        "updated_at": report.updated_at,
        "images": [r[0] for r in images_q.all()],
    }


async def list_reports(
    db: AsyncSession,
    *,
    status: str | None,
    area_id: UUID | None,
    reporter_id: UUID | None,
    incident_type: str | None,
    page: int,
    page_size: int,
) -> tuple[list[dict[str, Any]], int]:
    stmt = select(IncidentReport)
    if status:
        stmt = stmt.where(IncidentReport.status == status)
    if area_id:
        stmt = stmt.where(IncidentReport.area_id == area_id)
    if reporter_id:
        stmt = stmt.where(IncidentReport.reporter_id == reporter_id)
    if incident_type:
        stmt = stmt.where(IncidentReport.incident_type == incident_type)
    total = int(
        (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    )
    res = await db.execute(
        stmt.order_by(desc(IncidentReport.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [await to_dict(db, r) for r in res.scalars().all()]
    return items, total


async def get_report(db: AsyncSession, report_id: UUID) -> dict[str, Any]:
    r = await db.get(IncidentReport, report_id)
    if not r:
        raise NotFoundError("Report not found")
    return await to_dict(db, r)


async def update_status(
    db: AsyncSession,
    *,
    report_id: UUID,
    new_status: str,
    actor_id: UUID,
    rejection_reason: str | None = None,
) -> IncidentReport:
    r = await db.get(IncidentReport, report_id)
    if not r:
        raise NotFoundError("Report not found")
    valid_transitions = {
        "pending": ("accepted", "rejected"),
        "accepted": ("in_progress", "rejected"),
        "in_progress": ("pending_review",),
        "pending_review": ("resolved", "in_progress"),
        "resolved": ("reopened",),
        "reopened": ("in_progress",),
    }
    if new_status not in valid_transitions.get(r.status, ()):
        raise ValidationError(f"Invalid transition {r.status} -> {new_status}")
    r.status = new_status
    if new_status == "rejected":
        r.rejection_reason = rejection_reason
    if new_status == "resolved":
        r.resolved_at = datetime.now(UTC)
    db.add(
        ActivityLog(
            user_id=actor_id,
            action=f"report.{new_status}",
            target_type="report",
            target_id=r.id,
            after={"status": new_status, "reason": rejection_reason},
        )
    )
    await db.commit()
    await db.refresh(r)
    return r


async def add_comment(
    db: AsyncSession, *, report_id: UUID, user_id: UUID, body: str, is_internal: bool
) -> Comment:
    r = await db.get(IncidentReport, report_id)
    if not r:
        raise NotFoundError("Report not found")
    c = Comment(
        owner_type="report",
        owner_id=r.id,
        user_id=user_id,
        body=body,
        is_internal=is_internal,
    )
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c


async def list_comments(db: AsyncSession, report_id: UUID, *, include_internal: bool):
    stmt = select(Comment).where(Comment.owner_type == "report", Comment.owner_id == report_id)
    if not include_internal:
        stmt = stmt.where(Comment.is_internal.is_(False))
    res = await db.execute(stmt.order_by(Comment.created_at))
    return [
        {
            "id": c.id,
            "user_id": c.user_id,
            "body": c.body,
            "is_internal": c.is_internal,
            "created_at": c.created_at,
        }
        for c in res.scalars().all()
    ]


async def submit_rating(
    db: AsyncSession, *, report_id: UUID, user_id: UUID, rating: int, comment: str | None
) -> IncidentReport:
    r = await db.get(IncidentReport, report_id)
    if not r:
        raise NotFoundError("Report not found")
    if r.reporter_id != user_id:
        raise PermErr("Only the reporter can rate the resolution")
    if r.status != "resolved":
        raise ValidationError("Rating only allowed after resolved")
    r.rating = rating
    r.rating_comment = comment
    await db.commit()
    return r


async def get_timeline(db: AsyncSession, report_id: UUID) -> list[dict[str, Any]]:
    r = await db.get(IncidentReport, report_id)
    if not r:
        raise NotFoundError("Report not found")
    res = await db.execute(
        select(ActivityLog)
        .where(ActivityLog.target_type == "report", ActivityLog.target_id == r.id)
        .order_by(ActivityLog.created_at)
    )
    return [
        {
            "at": l.created_at,
            "actor_id": l.user_id,
            "action": l.action,
            "detail": l.after,
        }
        for l in res.scalars().all()
    ]


async def stats(db: AsyncSession) -> dict[str, Any]:
    total = int(
        (await db.execute(select(func.count(IncidentReport.id)))).scalar_one()
    )
    by_status = dict(
        (
            await db.execute(
                select(IncidentReport.status, func.count(IncidentReport.id)).group_by(
                    IncidentReport.status
                )
            )
        ).all()
    )
    by_type = dict(
        (
            await db.execute(
                select(IncidentReport.incident_type, func.count(IncidentReport.id))
                .where(IncidentReport.incident_type.is_not(None))
                .group_by(IncidentReport.incident_type)
            )
        ).all()
    )
    avg_conf = (
        await db.execute(select(func.avg(IncidentReport.ai_confidence)))
    ).scalar_one() or 0.0
    return {
        "total": total,
        "by_status": by_status,
        "by_type": by_type,
        "avg_ai_confidence": float(avg_conf),
    }
