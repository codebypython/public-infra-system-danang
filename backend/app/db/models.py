"""All ORM models in a single module — registered with `Base.metadata`.

Centralisation keeps Alembic autogenerate simple and avoids circular imports
between feature modules. Modules import these classes by name.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import CITEXT, INET, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPKMixin

# ---------------------------------------------------------------------------
# Core directory tables
# ---------------------------------------------------------------------------


class Area(UUIDPKMixin, TimestampMixin, Base):
    """8 quận/huyện thành phố Đà Nẵng."""

    __tablename__ = "areas"

    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    geometry: Mapped[Any | None] = mapped_column(Geometry("MULTIPOLYGON", srid=4326), nullable=True)
    center: Mapped[Any | None] = mapped_column(Geometry("POINT", srid=4326), nullable=True)
    population: Mapped[int | None] = mapped_column(Integer, nullable=True)


class User(UUIDPKMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(CITEXT(), unique=True, nullable=False)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(20))
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    area_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("areas.id"))
    totp_secret: Mapped[str | None] = mapped_column(String(64))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_known_location: Mapped[Any | None] = mapped_column(Geometry("POINT", srid=4326))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "role IN ('citizen','operator','taskforce','admin')", name="role_valid"
        ),
    )


class RefreshToken(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "refresh_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    user_agent: Mapped[str | None] = mapped_column(String(500))
    ip: Mapped[Any | None] = mapped_column(INET)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# ---------------------------------------------------------------------------
# Asset (Digital Twin)
# ---------------------------------------------------------------------------


class Asset(UUIDPKMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "assets"

    code: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    location: Mapped[Any] = mapped_column(Geometry("POINT", srid=4326), nullable=False)
    area_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("areas.id"), index=True
    )
    status: Mapped[str] = mapped_column(String(20), default="active")
    installed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    last_maintained_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    next_maintenance_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)
    qr_code_url: Mapped[str | None] = mapped_column(String(500))
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id")
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('active','damaged','maintenance','retired')", name="status_valid"
        ),
        Index("idx_assets_area_status", "area_id", "status"),
    )


class AssetVersion(UUIDPKMixin, Base):
    __tablename__ = "asset_versions"

    asset_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), index=True
    )
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    changed_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id")
    )
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ---------------------------------------------------------------------------
# Reports + Tasks + Maintenance + Comments + Attachments
# ---------------------------------------------------------------------------


class IncidentReport(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "incident_reports"

    code: Mapped[str] = mapped_column(String(20), unique=True)
    reporter_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), index=True
    )
    related_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("assets.id")
    )
    area_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("areas.id"), index=True
    )
    location: Mapped[Any] = mapped_column(Geometry("POINT", srid=4326), nullable=False)
    incident_type: Mapped[str | None] = mapped_column(String(50))
    severity: Mapped[str] = mapped_column(String(20), default="medium")
    description: Mapped[str | None] = mapped_column(Text)
    ai_class: Mapped[str | None] = mapped_column(String(50))
    ai_confidence: Mapped[float | None] = mapped_column(Float)
    ai_bbox: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    sla_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rating: Mapped[int | None] = mapped_column(SmallInteger)
    rating_comment: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(
            "severity IN ('low','medium','high','urgent')", name="severity_valid"
        ),
        CheckConstraint("rating IS NULL OR rating BETWEEN 1 AND 5", name="rating_valid"),
        CheckConstraint(
            "status IN ('pending','accepted','rejected','in_progress',"
            "'pending_review','resolved','reopened')",
            name="status_valid",
        ),
        Index("idx_reports_status_area", "status", "area_id"),
    )


class Task(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "tasks"

    code: Mapped[str] = mapped_column(String(20), unique=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    related_report_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("incident_reports.id")
    )
    related_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("assets.id")
    )
    area_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("areas.id"), index=True
    )
    priority: Mapped[str] = mapped_column(String(20), default="medium")
    status: Mapped[str] = mapped_column(String(30), default="open", index=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    check_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    check_in_location: Mapped[Any | None] = mapped_column(Geometry("POINT", srid=4326))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)
    parts_used: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id")
    )

    __table_args__ = (
        CheckConstraint(
            "priority IN ('low','medium','high','urgent')", name="priority_valid"
        ),
        CheckConstraint(
            "status IN ('open','assigned','in_progress','pending_review','completed','cancelled')",
            name="status_valid",
        ),
    )


class TaskAssignment(Base):
    __tablename__ = "task_assignments"

    task_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class MaintenanceLog(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "maintenance_logs"

    asset_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE")
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("tasks.id"))
    technician_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id")
    )
    type: Mapped[str] = mapped_column(String(20), default="reactive")
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)
    cost: Mapped[float | None] = mapped_column(Numeric(12, 2))


class MaintenanceSchedule(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "maintenance_schedules"

    asset_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE")
    )
    recurrence: Mapped[str] = mapped_column(String(20))
    next_due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Attachment(UUIDPKMixin, Base):
    __tablename__ = "attachments"

    owner_type: Mapped[str] = mapped_column(String(30), index=True)
    owner_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), index=True)
    type: Mapped[str] = mapped_column(String(20))
    url: Mapped[str] = mapped_column(String(500))
    thumbnail_url: Mapped[str | None] = mapped_column(String(500))
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    mime_type: Mapped[str | None] = mapped_column(String(50))
    exif: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    role: Mapped[str | None] = mapped_column(String(20))  # before|after|evidence|reference
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id")
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Comment(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "comments"

    owner_type: Mapped[str] = mapped_column(String(30), index=True)
    owner_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(Text)
    is_internal: Mapped[bool] = mapped_column(Boolean, default=False)


# ---------------------------------------------------------------------------
# Cameras + Alerts + Notifications + Audit + Settings
# ---------------------------------------------------------------------------


class Camera(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "cameras"

    name: Mapped[str] = mapped_column(String(255))
    rtsp_url: Mapped[str | None] = mapped_column(String(500))
    hls_url: Mapped[str | None] = mapped_column(String(500))
    location: Mapped[Any | None] = mapped_column(Geometry("POINT", srid=4326))
    area_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("areas.id")
    )
    classes_enabled: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    auto_report_classes: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_health_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CameraEvent(UUIDPKMixin, Base):
    __tablename__ = "camera_events"

    camera_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("cameras.id", ondelete="CASCADE"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(50))
    confidence: Mapped[float | None] = mapped_column(Float)
    bbox: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    snapshot_url: Mapped[str | None] = mapped_column(String(500))
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    related_report_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("incident_reports.id")
    )


class AlertLayer(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "alert_layers"

    layer_type: Mapped[str] = mapped_column(String(30), index=True)
    geometry: Mapped[Any] = mapped_column(Geometry("POLYGON", srid=4326))
    severity: Mapped[str] = mapped_column(String(20), default="medium")
    title: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source: Mapped[str] = mapped_column(String(50), default="manual")
    metadata_: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB)


class Notification(UUIDPKMixin, Base):
    __tablename__ = "notifications"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[str] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str | None] = mapped_column(Text)
    data: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), index=True
    )
    action: Mapped[str] = mapped_column(String(50))
    target_type: Mapped[str | None] = mapped_column(String(30))
    target_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    before: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    after: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    ip: Mapped[Any | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    __table_args__ = (Index("idx_audit_target", "target_type", "target_id"),)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[Any | None] = mapped_column(JSONB)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# Index helper exports for migration discovery
__all__ = [
    "ActivityLog",
    "AlertLayer",
    "Area",
    "Asset",
    "AssetVersion",
    "Attachment",
    "Camera",
    "CameraEvent",
    "Comment",
    "IncidentReport",
    "MaintenanceLog",
    "MaintenanceSchedule",
    "Notification",
    "RefreshToken",
    "Setting",
    "Task",
    "TaskAssignment",
    "User",
]
