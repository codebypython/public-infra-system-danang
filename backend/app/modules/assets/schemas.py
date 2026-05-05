"""Asset Pydantic schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

ASSET_TYPES = (
    "bench",
    "trash_can",
    "lamp",
    "toilet",
    "tree",
    "sign",
    "ev_charging",
    "smart_bin",
)
ASSET_STATUSES = ("active", "damaged", "maintenance", "retired")


class AssetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    asset_type: str
    lng: float = Field(ge=-180, le=180)
    lat: float = Field(ge=-90, le=90)
    area_id: UUID | None = None
    status: str = "active"
    installed_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AssetUpdate(BaseModel):
    name: str | None = None
    asset_type: str | None = None
    lng: float | None = None
    lat: float | None = None
    area_id: UUID | None = None
    status: str | None = None
    installed_at: datetime | None = None
    last_maintained_at: datetime | None = None
    next_maintenance_at: datetime | None = None
    metadata: dict[str, Any] | None = None


class AssetOut(BaseModel):
    id: UUID
    code: str | None
    name: str
    asset_type: str
    status: str
    lng: float
    lat: float
    area_id: UUID | None
    installed_at: datetime | None
    last_maintained_at: datetime | None
    next_maintenance_at: datetime | None
    metadata: dict[str, Any]
    qr_code_url: str | None
    created_at: datetime
    updated_at: datetime | None


class AssetGeoJSON(BaseModel):
    """GeoJSON Feature shape for map rendering."""

    type: str = "Feature"
    geometry: dict[str, Any]
    properties: dict[str, Any]


class AssetStats(BaseModel):
    total: int
    by_type: dict[str, int]
    by_status: dict[str, int]
    by_area: dict[str, int]
