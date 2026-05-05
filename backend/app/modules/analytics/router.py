"""Analytics & BI — heatmap (H3 binning), KPI, predictive maintenance."""

from __future__ import annotations

import io
from datetime import datetime, timedelta
from typing import Any

import h3
import openpyxl
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_roles
from app.db.models import Asset, IncidentReport, MaintenanceLog, Task
from app.db.session import get_db
from app.utils.geo import point_lng_lat

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/heatmap")
async def heatmap(
    db: AsyncSession = Depends(get_db),
    auth=Depends(require_roles("operator", "admin")),
    type: str = Query("incidents", pattern="^(incidents|assets)$"),
    resolution: int = Query(8, ge=5, le=10),
    from_: datetime | None = Query(None, alias="from"),
    to: datetime | None = None,
):
    """Group geo points into H3 cells; returns list of {h3, count, lng, lat}."""
    if type == "incidents":
        stmt = select(IncidentReport.location)
        if from_:
            stmt = stmt.where(IncidentReport.created_at >= from_)
        if to:
            stmt = stmt.where(IncidentReport.created_at <= to)
    else:
        stmt = select(Asset.location).where(Asset.deleted_at.is_(None))
    res = await db.execute(stmt)
    cells: dict[str, int] = {}
    for row in res.all():
        ll = point_lng_lat(row[0])
        if not ll:
            continue
        cell = h3.latlng_to_cell(ll[1], ll[0], resolution)
        cells[cell] = cells.get(cell, 0) + 1
    out = []
    for cell, count in cells.items():
        lat, lng = h3.cell_to_latlng(cell)
        out.append({"h3": cell, "lng": lng, "lat": lat, "count": count})
    return out


@router.get("/kpi")
async def kpi(
    db: AsyncSession = Depends(get_db),
    auth=Depends(require_roles("operator", "admin")),
    period: str = Query("month", pattern="^(week|month|quarter|year)$"),
):
    delta = {"week": 7, "month": 30, "quarter": 90, "year": 365}[period]
    since = datetime.utcnow() - timedelta(days=delta)
    total_reports = int(
        (
            await db.execute(
                select(func.count(IncidentReport.id)).where(IncidentReport.created_at >= since)
            )
        ).scalar_one()
    )
    resolved = int(
        (
            await db.execute(
                select(func.count(IncidentReport.id)).where(
                    IncidentReport.created_at >= since,
                    IncidentReport.status == "resolved",
                )
            )
        ).scalar_one()
    )
    avg_resolve_h = (
        await db.execute(
            select(
                func.avg(
                    func.extract(
                        "epoch",
                        IncidentReport.resolved_at - IncidentReport.created_at,
                    )
                    / 3600
                )
            ).where(
                IncidentReport.created_at >= since,
                IncidentReport.resolved_at.is_not(None),
            )
        )
    ).scalar_one() or 0.0
    sla_total = total_reports
    sla_breaches = int(
        (
            await db.execute(
                select(func.count(IncidentReport.id)).where(
                    IncidentReport.created_at >= since,
                    IncidentReport.sla_due_at < func.coalesce(
                        IncidentReport.resolved_at, func.now()
                    ),
                )
            )
        ).scalar_one()
    )
    sla_compliance = (
        round((sla_total - sla_breaches) / sla_total * 100, 2) if sla_total else 100.0
    )
    return {
        "period": period,
        "total_reports": total_reports,
        "resolved": resolved,
        "resolution_rate": round(resolved / total_reports * 100, 2) if total_reports else 0.0,
        "avg_resolve_hours": round(float(avg_resolve_h), 2),
        "sla_compliance_pct": sla_compliance,
    }


@router.get("/predictive-maintenance")
async def predictive(
    db: AsyncSession = Depends(get_db),
    auth=Depends(require_roles("operator", "admin")),
    limit: int = Query(20, ge=1, le=200),
):
    """Simple risk score = age_days * 0.001 + recent_reports_count * 0.5
    (placeholder for ML model — production uses scikit-learn pickle)."""
    res = await db.execute(
        select(
            Asset.id,
            Asset.code,
            Asset.name,
            Asset.asset_type,
            Asset.installed_at,
            Asset.last_maintained_at,
            func.count(IncidentReport.id).label("recent_reports"),
        )
        .outerjoin(
            IncidentReport,
            (IncidentReport.related_asset_id == Asset.id)
            & (IncidentReport.created_at > datetime.utcnow() - timedelta(days=180)),
        )
        .where(Asset.deleted_at.is_(None))
        .group_by(Asset.id)
    )
    rows = res.all()
    today = datetime.utcnow()
    scored = []
    for r in rows:
        age_days = (today - r.installed_at).days if r.installed_at else 365
        since_maint = (
            (today - r.last_maintained_at).days if r.last_maintained_at else age_days
        )
        risk = age_days * 0.001 + int(r.recent_reports) * 0.5 + since_maint * 0.002
        scored.append(
            {
                "id": r.id,
                "code": r.code,
                "name": r.name,
                "asset_type": r.asset_type,
                "recent_reports": int(r.recent_reports),
                "since_maintenance_days": since_maint,
                "risk_score": round(risk, 3),
            }
        )
    scored.sort(key=lambda x: x["risk_score"], reverse=True)
    return scored[:limit]


@router.get("/export.xlsx")
async def export_xlsx(
    db: AsyncSession = Depends(get_db),
    auth=Depends(require_roles("operator", "admin")),
    dataset: str = Query("reports", pattern="^(reports|tasks|assets|maintenance)$"),
    from_: datetime | None = Query(None, alias="from"),
    to: datetime | None = None,
):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = dataset

    if dataset == "reports":
        ws.append(["code", "type", "severity", "status", "created_at", "resolved_at"])
        stmt = select(
            IncidentReport.code,
            IncidentReport.incident_type,
            IncidentReport.severity,
            IncidentReport.status,
            IncidentReport.created_at,
            IncidentReport.resolved_at,
        )
        if from_:
            stmt = stmt.where(IncidentReport.created_at >= from_)
        if to:
            stmt = stmt.where(IncidentReport.created_at <= to)
        for r in (await db.execute(stmt)).all():
            ws.append(list(r))
    elif dataset == "tasks":
        ws.append(["code", "title", "priority", "status", "created_at", "completed_at"])
        for r in (
            await db.execute(
                select(Task.code, Task.title, Task.priority, Task.status, Task.created_at, Task.completed_at)
            )
        ).all():
            ws.append(list(r))
    elif dataset == "assets":
        ws.append(["code", "name", "asset_type", "status", "installed_at"])
        for r in (
            await db.execute(
                select(Asset.code, Asset.name, Asset.asset_type, Asset.status, Asset.installed_at).where(
                    Asset.deleted_at.is_(None)
                )
            )
        ).all():
            ws.append(list(r))
    elif dataset == "maintenance":
        ws.append(["asset_id", "type", "scheduled_at", "completed_at", "cost"])
        for r in (
            await db.execute(
                select(
                    MaintenanceLog.asset_id,
                    MaintenanceLog.type,
                    MaintenanceLog.scheduled_at,
                    MaintenanceLog.completed_at,
                    MaintenanceLog.cost,
                )
            )
        ).all():
            ws.append(list(r))

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={dataset}.xlsx"},
    )


@router.get("/trend")
async def trend(
    db: AsyncSession = Depends(get_db),
    auth=Depends(require_roles("operator", "admin")),
    days: int = Query(30, ge=1, le=365),
):
    since = datetime.utcnow() - timedelta(days=days)
    res = await db.execute(
        select(
            func.date_trunc("day", IncidentReport.created_at).label("day"),
            func.count(IncidentReport.id).label("count"),
        )
        .where(IncidentReport.created_at >= since)
        .group_by("day")
        .order_by("day")
    )
    return [{"day": r.day.isoformat() if r.day else None, "count": int(r.count)} for r in res.all()]
