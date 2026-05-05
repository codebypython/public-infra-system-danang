"""Incident report schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

INCIDENT_TYPES = (
    "littering",
    "pothole",
    "broken_lamp",
    "vandalism",
    "flooding",
    "crowd",
    "fallen_tree",
)
SEVERITIES = ("low", "medium", "high", "urgent")
REPORT_STATUSES = (
    "pending",
    "accepted",
    "rejected",
    "in_progress",
    "pending_review",
    "resolved",
    "reopened",
)


class ReportCreate(BaseModel):
    lng: float = Field(ge=-180, le=180)
    lat: float = Field(ge=-90, le=90)
    incident_type: str | None = None
    severity: str = "medium"
    description: str | None = Field(default=None, max_length=2000)
    related_asset_id: UUID | None = None


class ReportOut(BaseModel):
    id: UUID
    code: str
    reporter_id: UUID | None
    related_asset_id: UUID | None
    area_id: UUID | None
    lng: float
    lat: float
    incident_type: str | None
    severity: str
    description: str | None
    ai_class: str | None
    ai_confidence: float | None
    status: str
    rejection_reason: str | None
    sla_due_at: datetime | None
    resolved_at: datetime | None
    rating: int | None
    created_at: datetime
    updated_at: datetime | None
    images: list[str] = []


class ReportRejectRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class ReportRatingRequest(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=500)


class CommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=2000)
    is_internal: bool = False


class TimelineEvent(BaseModel):
    at: datetime
    actor_id: UUID | None
    action: str
    detail: dict[str, Any] | None = None
