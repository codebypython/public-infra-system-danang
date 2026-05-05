"""Areas (8 quận/huyện Đà Nẵng) — read-only public endpoint + admin update."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Area
from app.db.session import get_db
from app.utils.geo import geom_to_geojson

router = APIRouter(prefix="/areas", tags=["areas"])


@router.get("")
async def list_areas(db: AsyncSession = Depends(get_db)):
    res = await db.execute(
        select(
            Area.id,
            Area.code,
            Area.name,
            Area.population,
            func.ST_AsGeoJSON(Area.geometry).label("geojson"),
            func.ST_AsGeoJSON(Area.center).label("center_geojson"),
        ).order_by(Area.name)
    )
    rows = res.all()
    return [
        {
            "id": r.id,
            "code": r.code,
            "name": r.name,
            "population": r.population,
            "geometry": _maybe_load(r.geojson),
            "center": _maybe_load(r.center_geojson),
        }
        for r in rows
    ]


@router.get("/{area_id}")
async def get_area(area_id: UUID, db: AsyncSession = Depends(get_db)):
    area = await db.get(Area, area_id)
    if not area:
        from app.core.exceptions import NotFoundError

        raise NotFoundError("Area not found")
    return {
        "id": area.id,
        "code": area.code,
        "name": area.name,
        "population": area.population,
        "geometry": geom_to_geojson(area.geometry),
        "center": geom_to_geojson(area.center),
    }


def _maybe_load(s: str | None):
    import json

    return json.loads(s) if s else None
