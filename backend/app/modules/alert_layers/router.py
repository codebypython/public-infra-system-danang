"""Alert layers — construction zones, flood hotspots, AQI."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.core.security import require_roles
from app.db.models import AlertLayer
from app.db.session import get_db

router = APIRouter(prefix="/alert-layers", tags=["alert-layers"])

LAYER_TYPES = {"construction", "flood", "aqi"}
SEVERITIES = {"low", "medium", "high"}


class AlertLayerCreate(BaseModel):
    layer_type: str
    geometry: dict[str, Any]
    severity: str = "medium"
    title: str | None = Field(default=None, max_length=255)
    description: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    metadata: dict[str, Any] | None = None


@router.get("/{layer_type}")
async def get_layer(
    layer_type: str,
    db: AsyncSession = Depends(get_db),
    active_at: datetime | None = Query(None),
):
    if layer_type not in LAYER_TYPES:
        raise ValidationError(f"layer_type must be one of {LAYER_TYPES}")
    stmt = select(
        AlertLayer.id,
        AlertLayer.severity,
        AlertLayer.title,
        AlertLayer.description,
        AlertLayer.starts_at,
        AlertLayer.ends_at,
        AlertLayer.metadata_,
        func.ST_AsGeoJSON(AlertLayer.geometry).label("geom"),
    ).where(AlertLayer.layer_type == layer_type)
    if active_at:
        stmt = stmt.where(
            (AlertLayer.starts_at.is_(None)) | (AlertLayer.starts_at <= active_at),
            (AlertLayer.ends_at.is_(None)) | (AlertLayer.ends_at >= active_at),
        )
    res = await db.execute(stmt)
    features = []
    for row in res.all():
        features.append(
            {
                "type": "Feature",
                "id": str(row.id),
                "geometry": json.loads(row.geom) if row.geom else None,
                "properties": {
                    "severity": row.severity,
                    "title": row.title,
                    "description": row.description,
                    "starts_at": row.starts_at.isoformat() if row.starts_at else None,
                    "ends_at": row.ends_at.isoformat() if row.ends_at else None,
                    "metadata": row.metadata_,
                },
            }
        )
    return {"type": "FeatureCollection", "features": features}


@router.post("/{layer_type}", status_code=status.HTTP_201_CREATED)
async def create_layer(
    layer_type: str,
    body: AlertLayerCreate,
    db: AsyncSession = Depends(get_db),
    auth=Depends(require_roles("operator", "admin")),
):
    if layer_type not in LAYER_TYPES:
        raise ValidationError(f"layer_type must be one of {LAYER_TYPES}")
    if body.severity not in SEVERITIES:
        raise ValidationError(f"severity must be one of {SEVERITIES}")
    layer = AlertLayer(
        layer_type=layer_type,
        geometry=func.ST_GeomFromGeoJSON(json.dumps(body.geometry)),
        severity=body.severity,
        title=body.title,
        description=body.description,
        starts_at=body.starts_at,
        ends_at=body.ends_at,
        metadata_=body.metadata,
    )
    db.add(layer)
    await db.commit()
    await db.refresh(layer)
    return {"id": layer.id, "layer_type": layer.layer_type, "severity": layer.severity}


@router.delete("/{layer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_layer(
    layer_id: UUID,
    db: AsyncSession = Depends(get_db),
    auth=Depends(require_roles("operator", "admin")),
):
    layer = await db.get(AlertLayer, layer_id)
    if not layer:
        raise NotFoundError("Layer not found")
    await db.delete(layer)
    await db.commit()
