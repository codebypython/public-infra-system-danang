"""Periodic AQI fetch from OpenAQ → upsert alert layers."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

import httpx
from sqlalchemy import delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models import AlertLayer
from app.db.session import AsyncSessionLocal
from app.workers.celery_app import celery_app

logger = get_logger(__name__)


async def _fetch_async() -> int:
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            r = await client.get(
                f"{settings.openaq_api_base}/measurements",
                params={
                    "country": "VN",
                    "city": "Da Nang",
                    "limit": 50,
                    "parameter": "pm25",
                },
            )
            data = r.json() if r.status_code == 200 else {"results": []}
        except Exception as exc:  # noqa: BLE001
            logger.warning("aqi.fetch_failed", error=str(exc))
            return 0

    measurements = data.get("results", [])
    if not measurements:
        return 0

    async with AsyncSessionLocal() as db:  # type: AsyncSession
        # Wipe expired aqi layers
        await db.execute(
            delete(AlertLayer).where(
                AlertLayer.layer_type == "aqi",
                AlertLayer.ends_at < datetime.utcnow(),
            )
        )
        for m in measurements:
            coords = m.get("coordinates") or {}
            if not coords:
                continue
            lng, lat = coords.get("longitude"), coords.get("latitude")
            if lng is None or lat is None:
                continue
            value = m.get("value", 0)
            severity = (
                "high" if value > 100 else "medium" if value > 50 else "low"
            )
            # Polygon = small square around the station
            half = 0.005
            wkt = (
                f"SRID=4326;POLYGON(("
                f"{lng - half} {lat - half}, {lng + half} {lat - half},"
                f"{lng + half} {lat + half}, {lng - half} {lat + half},"
                f"{lng - half} {lat - half}))"
            )
            db.add(
                AlertLayer(
                    layer_type="aqi",
                    geometry=wkt,
                    severity=severity,
                    title=f"AQI station — PM2.5 {value:.1f}μg/m³",
                    description=str(m.get("location")),
                    starts_at=datetime.utcnow(),
                    ends_at=datetime.utcnow() + timedelta(hours=1),
                    source="openaq",
                    metadata_={"value": value, "raw": m},
                )
            )
        await db.commit()
        return len(measurements)


@celery_app.task(name="app.workers.tasks_aqi.fetch_aqi")
def fetch_aqi() -> int:
    n = asyncio.run(_fetch_async())
    logger.info("aqi.fetch.done", count=n)
    return n
