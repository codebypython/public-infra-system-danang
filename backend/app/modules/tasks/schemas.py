"""Task schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

PRIORITIES = ("low", "medium", "high", "urgent")
STATUSES = ("open", "assigned", "in_progress", "pending_review", "completed", "cancelled")


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    related_report_id: UUID | None = None
    related_asset_id: UUID | None = None
    priority: str = "medium"
    due_at: datetime | None = None
    assignee_ids: list[UUID] = Field(default_factory=list)


class TaskAssignRequest(BaseModel):
    assignee_ids: list[UUID]


class TaskCheckInRequest(BaseModel):
    lng: float = Field(ge=-180, le=180)
    lat: float = Field(ge=-90, le=90)


class TaskCompleteRequest(BaseModel):
    notes: str | None = None
    parts_used: dict[str, Any] | None = None


class TaskOut(BaseModel):
    id: UUID
    code: str
    title: str
    description: str | None
    related_report_id: UUID | None
    related_asset_id: UUID | None
    area_id: UUID | None
    priority: str
    status: str
    due_at: datetime | None
    check_in_at: datetime | None
    completed_at: datetime | None
    notes: str | None
    parts_used: dict[str, Any] | None
    created_at: datetime
    assignees: list[UUID] = []
    before_images: list[str] = []
    after_images: list[str] = []


class AssigneeSuggestion(BaseModel):
    user_id: UUID
    full_name: str | None
    email: str
    distance_m: float | None
    current_load: int


class RouteOptimizationOut(BaseModel):
    ordered_task_ids: list[UUID]
    total_distance_m: float
    estimated_duration_minutes: int
