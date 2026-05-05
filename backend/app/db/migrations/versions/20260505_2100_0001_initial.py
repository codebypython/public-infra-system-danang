"""initial schema — all 17 tables + PostGIS extension + indexes.

Revision ID: 0001
Revises:
Create Date: 2026-05-05 21:00:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Extensions (idempotent — also created in init.sql)
    for ext in ("postgis", "pgcrypto", "pg_trgm", "citext", "btree_gist"):
        op.execute(f"CREATE EXTENSION IF NOT EXISTS {ext}")

    op.create_table(
        "areas",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(20), nullable=False, unique=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("geometry", Geometry("MULTIPOLYGON", srid=4326), nullable=True),
        sa.Column("center", Geometry("POINT", srid=4326), nullable=True),
        sa.Column("population", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute("CREATE INDEX idx_areas_geom ON areas USING GIST(geometry)")

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", postgresql.CITEXT(), nullable=False, unique=True),
        sa.Column("username", sa.String(50), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("full_name", sa.String(255)),
        sa.Column("phone", sa.String(20)),
        sa.Column("avatar_url", sa.String(500)),
        sa.Column("area_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("areas.id")),
        sa.Column("totp_secret", sa.String(64)),
        sa.Column("is_active", sa.Boolean, default=True, server_default="true"),
        sa.Column("last_known_location", Geometry("POINT", srid=4326)),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "role IN ('citizen','operator','taskforce','admin')", name="ck_users_role_valid"
        ),
    )

    op.create_table(
        "refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(255), nullable=False, unique=True),
        sa.Column("user_agent", sa.String(500)),
        sa.Column("ip", postgresql.INET()),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])

    op.create_table(
        "assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(50), unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("asset_type", sa.String(50), nullable=False),
        sa.Column("location", Geometry("POINT", srid=4326), nullable=False),
        sa.Column("area_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("areas.id")),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("installed_at", sa.DateTime()),
        sa.Column("last_maintained_at", sa.DateTime()),
        sa.Column("next_maintenance_at", sa.DateTime()),
        sa.Column("metadata", postgresql.JSONB(), server_default="{}"),
        sa.Column("qr_code_url", sa.String(500)),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "status IN ('active','damaged','maintenance','retired')", name="ck_assets_status_valid"
        ),
    )
    op.execute("CREATE INDEX idx_assets_location ON assets USING GIST(location)")
    op.create_index("ix_assets_area_id", "assets", ["area_id"])
    op.create_index("ix_assets_asset_type", "assets", ["asset_type"])
    op.create_index("idx_assets_area_status", "assets", ["area_id", "status"])
    op.execute("CREATE INDEX idx_assets_search ON assets USING GIN(name gin_trgm_ops)")

    op.create_table(
        "asset_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "asset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("assets.id", ondelete="CASCADE"),
        ),
        sa.Column("snapshot", postgresql.JSONB()),
        sa.Column("changed_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_asset_versions_asset_id", "asset_versions", ["asset_id"])

    op.create_table(
        "incident_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(20), unique=True),
        sa.Column("reporter_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("related_asset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assets.id")),
        sa.Column("area_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("areas.id")),
        sa.Column("location", Geometry("POINT", srid=4326), nullable=False),
        sa.Column("incident_type", sa.String(50)),
        sa.Column("severity", sa.String(20), server_default="medium"),
        sa.Column("description", sa.Text),
        sa.Column("ai_class", sa.String(50)),
        sa.Column("ai_confidence", sa.Float),
        sa.Column("ai_bbox", postgresql.JSONB()),
        sa.Column("status", sa.String(30), server_default="pending"),
        sa.Column("rejection_reason", sa.Text),
        sa.Column("sla_due_at", sa.DateTime(timezone=True)),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("rating", sa.SmallInteger),
        sa.Column("rating_comment", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "severity IN ('low','medium','high','urgent')", name="ck_incident_reports_severity_valid"
        ),
        sa.CheckConstraint(
            "rating IS NULL OR rating BETWEEN 1 AND 5", name="ck_incident_reports_rating_valid"
        ),
        sa.CheckConstraint(
            "status IN ('pending','accepted','rejected','in_progress','pending_review','resolved','reopened')",
            name="ck_incident_reports_status_valid",
        ),
    )
    op.execute("CREATE INDEX idx_reports_location ON incident_reports USING GIST(location)")
    op.create_index("ix_incident_reports_reporter_id", "incident_reports", ["reporter_id"])
    op.create_index("ix_incident_reports_area_id", "incident_reports", ["area_id"])
    op.create_index("ix_incident_reports_status", "incident_reports", ["status"])
    op.create_index(
        "idx_reports_status_area", "incident_reports", ["status", "area_id"]
    )

    op.create_table(
        "tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(20), unique=True),
        sa.Column("title", sa.String(255)),
        sa.Column("description", sa.Text),
        sa.Column(
            "related_report_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("incident_reports.id"),
        ),
        sa.Column("related_asset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assets.id")),
        sa.Column("area_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("areas.id")),
        sa.Column("priority", sa.String(20), server_default="medium"),
        sa.Column("status", sa.String(30), server_default="open"),
        sa.Column("due_at", sa.DateTime(timezone=True)),
        sa.Column("check_in_at", sa.DateTime(timezone=True)),
        sa.Column("check_in_location", Geometry("POINT", srid=4326)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("notes", sa.Text),
        sa.Column("parts_used", postgresql.JSONB()),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "priority IN ('low','medium','high','urgent')", name="ck_tasks_priority_valid"
        ),
        sa.CheckConstraint(
            "status IN ('open','assigned','in_progress','pending_review','completed','cancelled')",
            name="ck_tasks_status_valid",
        ),
    )
    op.create_index("ix_tasks_area_id", "tasks", ["area_id"])
    op.create_index("ix_tasks_status", "tasks", ["status"])

    op.create_table(
        "task_assignments",
        sa.Column(
            "task_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tasks.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "maintenance_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "asset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("assets.id", ondelete="CASCADE"),
        ),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tasks.id")),
        sa.Column("technician_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("type", sa.String(20), server_default="reactive"),
        sa.Column("scheduled_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("notes", sa.Text),
        sa.Column("cost", sa.Numeric(12, 2)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "maintenance_schedules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "asset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("assets.id", ondelete="CASCADE"),
        ),
        sa.Column("recurrence", sa.String(20)),
        sa.Column("next_due_at", sa.DateTime(timezone=True)),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "attachments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_type", sa.String(30)),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True)),
        sa.Column("type", sa.String(20)),
        sa.Column("url", sa.String(500)),
        sa.Column("thumbnail_url", sa.String(500)),
        sa.Column("size_bytes", sa.BigInteger),
        sa.Column("mime_type", sa.String(50)),
        sa.Column("exif", postgresql.JSONB()),
        sa.Column("role", sa.String(20)),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_attachments_owner", "attachments", ["owner_type", "owner_id"])

    op.create_table(
        "comments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_type", sa.String(30)),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True)),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("body", sa.Text),
        sa.Column("is_internal", sa.Boolean, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_comments_owner", "comments", ["owner_type", "owner_id"])

    op.create_table(
        "cameras",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255)),
        sa.Column("rtsp_url", sa.String(500)),
        sa.Column("hls_url", sa.String(500)),
        sa.Column("location", Geometry("POINT", srid=4326)),
        sa.Column("area_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("areas.id")),
        sa.Column("classes_enabled", postgresql.ARRAY(sa.String)),
        sa.Column("auto_report_classes", postgresql.ARRAY(sa.String)),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("last_health_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "camera_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "camera_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cameras.id", ondelete="CASCADE"),
        ),
        sa.Column("event_type", sa.String(50)),
        sa.Column("confidence", sa.Float),
        sa.Column("bbox", postgresql.JSONB()),
        sa.Column("snapshot_url", sa.String(500)),
        sa.Column("detected_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "related_report_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("incident_reports.id"),
        ),
    )
    op.create_index("ix_camera_events_camera_id", "camera_events", ["camera_id"])
    op.create_index("ix_camera_events_detected_at", "camera_events", ["detected_at"])

    op.create_table(
        "alert_layers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("layer_type", sa.String(30)),
        sa.Column("geometry", Geometry("POLYGON", srid=4326)),
        sa.Column("severity", sa.String(20), server_default="medium"),
        sa.Column("title", sa.String(255)),
        sa.Column("description", sa.Text),
        sa.Column("starts_at", sa.DateTime(timezone=True)),
        sa.Column("ends_at", sa.DateTime(timezone=True)),
        sa.Column("source", sa.String(50), server_default="manual"),
        sa.Column("metadata", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_alert_layers_layer_type", "alert_layers", ["layer_type"])
    op.execute("CREATE INDEX idx_alert_geom ON alert_layers USING GIST(geometry)")

    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
        ),
        sa.Column("type", sa.String(50)),
        sa.Column("title", sa.String(255)),
        sa.Column("body", sa.Text),
        sa.Column("data", postgresql.JSONB()),
        sa.Column("is_read", sa.Boolean, server_default="false"),
        sa.Column("read_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_is_read", "notifications", ["is_read"])
    op.create_index("ix_notifications_created_at", "notifications", ["created_at"])

    op.create_table(
        "activity_logs",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("action", sa.String(50)),
        sa.Column("target_type", sa.String(30)),
        sa.Column("target_id", postgresql.UUID(as_uuid=True)),
        sa.Column("before", postgresql.JSONB()),
        sa.Column("after", postgresql.JSONB()),
        sa.Column("ip", postgresql.INET()),
        sa.Column("user_agent", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_activity_logs_user_id", "activity_logs", ["user_id"])
    op.create_index("ix_activity_logs_created_at", "activity_logs", ["created_at"])
    op.create_index("idx_audit_target", "activity_logs", ["target_type", "target_id"])

    op.create_table(
        "settings",
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("value", postgresql.JSONB()),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    for tbl in [
        "settings",
        "activity_logs",
        "notifications",
        "alert_layers",
        "camera_events",
        "cameras",
        "comments",
        "attachments",
        "maintenance_schedules",
        "maintenance_logs",
        "task_assignments",
        "tasks",
        "incident_reports",
        "asset_versions",
        "assets",
        "refresh_tokens",
        "users",
        "areas",
    ]:
        op.execute(f"DROP TABLE IF EXISTS {tbl} CASCADE")
