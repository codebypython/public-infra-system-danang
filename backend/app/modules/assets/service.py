"""Asset service — CRUD with PostGIS, soft-delete, version snapshot, stats."""

from __future__ import annotations

import io
import json
from typing import Any
from uuid import UUID

import qrcode
from sqlalchemy import desc, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.db.models import Area, Asset, AssetVersion
from app.modules.assets.schemas import (
    ASSET_STATUSES,
    ASSET_TYPES,
    AssetCreate,
    AssetUpdate,
)
from app.utils.codes import asset_code
from app.utils.geo import bbox_polygon_wkt, is_in_danang, parse_bbox, point_lng_lat, wkt_point
from app.utils.storage import upload_bytes


def _validate(payload: AssetCreate | AssetUpdate) -> None:
    if isinstance(payload, AssetCreate):
        if payload.asset_type not in ASSET_TYPES:
            raise ValidationError(f"asset_type must be one of {ASSET_TYPES}")
        if payload.status not in ASSET_STATUSES:
            raise ValidationError(f"status must be one of {ASSET_STATUSES}")
        if not is_in_danang(payload.lng, payload.lat):
            raise ValidationError("Coordinates outside Đà Nẵng bbox")


async def _next_seq(db: AsyncSession, area_code: str, asset_type: str) -> int:
    res = await db.execute(
        select(func.count(Asset.id)).where(
            Asset.code.like(f"DN-{area_code}-%"), Asset.asset_type == asset_type
        )
    )
    return int(res.scalar_one() or 0) + 1


async def _to_dict(db: AsyncSession, asset: Asset) -> dict[str, Any]:
    lnglat = point_lng_lat(asset.location)
    return {
        "id": asset.id,
        "code": asset.code,
        "name": asset.name,
        "asset_type": asset.asset_type,
        "status": asset.status,
        "lng": lnglat[0] if lnglat else None,
        "lat": lnglat[1] if lnglat else None,
        "area_id": asset.area_id,
        "installed_at": asset.installed_at,
        "last_maintained_at": asset.last_maintained_at,
        "next_maintenance_at": asset.next_maintenance_at,
        "metadata": asset.metadata_,
        "qr_code_url": asset.qr_code_url,
        "created_at": asset.created_at,
        "updated_at": asset.updated_at,
    }


async def create_asset(db: AsyncSession, payload: AssetCreate, created_by: UUID) -> dict[str, Any]:
    _validate(payload)
    # Auto-detect area via PostGIS if not provided
    area_id = payload.area_id
    area_code = "GEN"
    if area_id is None:
        res = await db.execute(
            select(Area.id, Area.code).where(
                func.ST_Contains(
                    Area.geometry,
                    func.ST_GeomFromEWKT(wkt_point(payload.lng, payload.lat)),
                )
            )
        )
        row = res.first()
        if row:
            area_id = row.id
            area_code = row.code
    else:
        ar = await db.get(Area, area_id)
        area_code = ar.code if ar else "GEN"

    seq = await _next_seq(db, area_code, payload.asset_type)
    code = asset_code(area_code, payload.asset_type, seq)

    asset = Asset(
        code=code,
        name=payload.name,
        asset_type=payload.asset_type,
        location=wkt_point(payload.lng, payload.lat),
        area_id=area_id,
        status=payload.status,
        installed_at=payload.installed_at,
        metadata_=payload.metadata,
        created_by=created_by,
    )
    db.add(asset)
    await db.flush()
    asset.qr_code_url = await generate_qr(str(asset.id), code)
    db.add(AssetVersion(asset_id=asset.id, snapshot=await _to_dict(db, asset), changed_by=created_by))
    await db.commit()
    await db.refresh(asset)
    return await _to_dict(db, asset)


async def update_asset(
    db: AsyncSession, asset_id: UUID, payload: AssetUpdate, changed_by: UUID
) -> dict[str, Any]:
    asset = await db.get(Asset, asset_id)
    if not asset or asset.deleted_at is not None:
        raise NotFoundError("Asset not found")

    before = await _to_dict(db, asset)

    if payload.name is not None:
        asset.name = payload.name
    if payload.asset_type is not None:
        if payload.asset_type not in ASSET_TYPES:
            raise ValidationError("Invalid asset_type")
        asset.asset_type = payload.asset_type
    if payload.lng is not None and payload.lat is not None:
        if not is_in_danang(payload.lng, payload.lat):
            raise ValidationError("Coordinates outside Đà Nẵng bbox")
        asset.location = wkt_point(payload.lng, payload.lat)
    if payload.status is not None:
        if payload.status not in ASSET_STATUSES:
            raise ValidationError("Invalid status")
        asset.status = payload.status
    if payload.area_id is not None:
        asset.area_id = payload.area_id
    if payload.installed_at is not None:
        asset.installed_at = payload.installed_at
    if payload.last_maintained_at is not None:
        asset.last_maintained_at = payload.last_maintained_at
    if payload.next_maintenance_at is not None:
        asset.next_maintenance_at = payload.next_maintenance_at
    if payload.metadata is not None:
        asset.metadata_ = payload.metadata

    db.add(AssetVersion(asset_id=asset.id, snapshot=before, changed_by=changed_by))
    await db.commit()
    await db.refresh(asset)
    return await _to_dict(db, asset)


async def soft_delete(db: AsyncSession, asset_id: UUID, changed_by: UUID) -> None:
    from datetime import UTC, datetime

    asset = await db.get(Asset, asset_id)
    if not asset or asset.deleted_at is not None:
        raise NotFoundError("Asset not found")
    asset.deleted_at = datetime.now(UTC)
    db.add(AssetVersion(asset_id=asset.id, snapshot={"deleted": True}, changed_by=changed_by))
    await db.commit()


async def restore(db: AsyncSession, asset_id: UUID) -> dict[str, Any]:
    asset = await db.get(Asset, asset_id)
    if not asset:
        raise NotFoundError("Asset not found")
    asset.deleted_at = None
    await db.commit()
    await db.refresh(asset)
    return await _to_dict(db, asset)


async def list_assets(
    db: AsyncSession,
    *,
    bbox: str | None,
    asset_type: str | None,
    status: str | None,
    area_id: UUID | None,
    q: str | None,
    page: int,
    page_size: int,
) -> tuple[list[dict[str, Any]], int]:
    stmt = select(Asset).where(Asset.deleted_at.is_(None))
    if bbox:
        b = parse_bbox(bbox)
        stmt = stmt.where(
            func.ST_Within(Asset.location, func.ST_GeomFromEWKT(bbox_polygon_wkt(b)))
        )
    if asset_type:
        stmt = stmt.where(Asset.asset_type == asset_type)
    if status:
        stmt = stmt.where(Asset.status == status)
    if area_id:
        stmt = stmt.where(Asset.area_id == area_id)
    if q:
        stmt = stmt.where(Asset.name.ilike(f"%{q}%"))

    # Count
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = int((await db.execute(count_stmt)).scalar_one())

    stmt = stmt.order_by(desc(Asset.created_at)).offset((page - 1) * page_size).limit(page_size)
    res = await db.execute(stmt)
    items = [await _to_dict(db, a) for a in res.scalars().all()]
    return items, total


async def get_asset(db: AsyncSession, asset_id: UUID) -> dict[str, Any]:
    asset = await db.get(Asset, asset_id)
    if not asset or asset.deleted_at is not None:
        raise NotFoundError("Asset not found")
    return await _to_dict(db, asset)


async def stats(db: AsyncSession) -> dict[str, Any]:
    total = int(
        (
            await db.execute(
                select(func.count(Asset.id)).where(Asset.deleted_at.is_(None))
            )
        ).scalar_one()
    )
    by_type = dict(
        (
            await db.execute(
                select(Asset.asset_type, func.count(Asset.id))
                .where(Asset.deleted_at.is_(None))
                .group_by(Asset.asset_type)
            )
        ).all()
    )
    by_status = dict(
        (
            await db.execute(
                select(Asset.status, func.count(Asset.id))
                .where(Asset.deleted_at.is_(None))
                .group_by(Asset.status)
            )
        ).all()
    )
    by_area_rows = (
        await db.execute(
            select(Area.name, func.count(Asset.id))
            .join(Asset, Asset.area_id == Area.id, isouter=True)
            .where(Asset.deleted_at.is_(None))
            .group_by(Area.name)
        )
    ).all()
    by_area = {name or "Unknown": cnt for name, cnt in by_area_rows}
    return {"total": total, "by_type": by_type, "by_status": by_status, "by_area": by_area}


async def heatmap(db: AsyncSession, bbox: str | None = None) -> list[dict[str, Any]]:
    stmt = select(Asset.id, Asset.asset_type, Asset.status, Asset.location).where(
        Asset.deleted_at.is_(None)
    )
    if bbox:
        b = parse_bbox(bbox)
        stmt = stmt.where(
            func.ST_Within(Asset.location, func.ST_GeomFromEWKT(bbox_polygon_wkt(b)))
        )
    res = await db.execute(stmt)
    out: list[dict[str, Any]] = []
    for row in res.all():
        ll = point_lng_lat(row.location)
        if not ll:
            continue
        out.append(
            {"id": str(row.id), "type": row.asset_type, "status": row.status, "lng": ll[0], "lat": ll[1]}
        )
    return out


async def generate_qr(asset_id: str, code: str) -> str:
    img = qrcode.make(f"danang-infra://asset/{asset_id}")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return upload_bytes(
        buf.read(), folder="qr-codes", filename=f"{code}.png", content_type="image/png"
    )


async def bulk_import_geojson(
    db: AsyncSession, content: bytes, created_by: UUID
) -> dict[str, Any]:
    """Import a FeatureCollection of Points into assets."""
    try:
        fc = json.loads(content)
    except json.JSONDecodeError:
        raise ValidationError("Invalid JSON")
    if fc.get("type") != "FeatureCollection":
        raise ValidationError("Expecting GeoJSON FeatureCollection")
    success, errors = 0, []
    for feat in fc.get("features", []):
        try:
            geom = feat["geometry"]
            if geom["type"] != "Point":
                raise ValueError("Only Point geometries supported")
            lng, lat = geom["coordinates"][:2]
            props = feat.get("properties", {}) or {}
            payload = AssetCreate(
                name=props.get("name", "Imported asset"),
                asset_type=props.get("asset_type", "bench"),
                lng=lng,
                lat=lat,
                status=props.get("status", "active"),
                metadata=props.get("metadata", {}),
            )
            await create_asset(db, payload, created_by)
            success += 1
        except Exception as exc:  # noqa: BLE001
            errors.append({"feature": feat.get("id"), "error": str(exc)})
    return {"success": success, "errors": errors, "total": success + len(errors)}
