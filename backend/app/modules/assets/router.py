"""Asset router."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_token_payload, require_roles
from app.db.session import get_db
from app.modules.assets import service
from app.modules.assets.schemas import AssetCreate, AssetUpdate

router = APIRouter(prefix="/assets", tags=["assets"])


@router.get("")
async def list_assets(
    db: AsyncSession = Depends(get_db),
    bbox: str | None = Query(None, description="min_lng,min_lat,max_lng,max_lat"),
    type: str | None = Query(None, alias="type"),
    status_: str | None = Query(None, alias="status"),
    area_id: UUID | None = None,
    q: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    items, total = await service.list_assets(
        db,
        bbox=bbox,
        asset_type=type,
        status=status_,
        area_id=area_id,
        q=q,
        page=page,
        page_size=page_size,
    )
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/stats")
async def stats(db: AsyncSession = Depends(get_db)):
    return await service.stats(db)


@router.get("/heatmap")
async def heatmap(db: AsyncSession = Depends(get_db), bbox: str | None = Query(None)):
    return await service.heatmap(db, bbox)


@router.get("/{asset_id}")
async def get_asset(asset_id: UUID, db: AsyncSession = Depends(get_db)):
    return await service.get_asset(db, asset_id)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create(
    payload: AssetCreate,
    db: AsyncSession = Depends(get_db),
    auth=Depends(require_roles("operator", "admin")),
):
    return await service.create_asset(db, payload, UUID(auth["sub"]))


@router.patch("/{asset_id}")
async def update(
    asset_id: UUID,
    payload: AssetUpdate,
    db: AsyncSession = Depends(get_db),
    auth=Depends(require_roles("operator", "admin")),
):
    return await service.update_asset(db, asset_id, payload, UUID(auth["sub"]))


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(
    asset_id: UUID,
    db: AsyncSession = Depends(get_db),
    auth=Depends(require_roles("operator", "admin")),
):
    await service.soft_delete(db, asset_id, UUID(auth["sub"]))


@router.post("/{asset_id}/restore")
async def restore(
    asset_id: UUID,
    db: AsyncSession = Depends(get_db),
    auth=Depends(require_roles("admin")),
):
    return await service.restore(db, asset_id)


@router.post("/bulk-import")
async def bulk_import(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    auth=Depends(require_roles("admin")),
):
    content = await file.read()
    return await service.bulk_import_geojson(db, content, UUID(auth["sub"]))
