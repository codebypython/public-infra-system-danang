"""Seed Đà Nẵng baseline data: 8 areas, 4 demo users, ~200 assets, 3 alert layers, sample reports.

Run: `python -m app.scripts.seed_danang`
"""

from __future__ import annotations

import asyncio
import json
import math
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.db.models import (
    AlertLayer,
    Area,
    Asset,
    Camera,
    IncidentReport,
    User,
)
from app.db.session import AsyncSessionLocal
from app.utils.codes import asset_code, report_code
from app.utils.geo import wkt_point


# Approximate centroids for Đà Nẵng districts (lon, lat) plus area_km^2 + population
DISTRICTS = [
    {"code": "HC", "name": "Hải Châu", "lng": 108.220, "lat": 16.060, "size_deg": 0.020, "pop": 197000},
    {"code": "ST", "name": "Sơn Trà", "lng": 108.260, "lat": 16.080, "size_deg": 0.025, "pop": 165000},
    {"code": "TK", "name": "Thanh Khê", "lng": 108.190, "lat": 16.065, "size_deg": 0.018, "pop": 187000},
    {"code": "LC", "name": "Liên Chiểu", "lng": 108.140, "lat": 16.075, "size_deg": 0.030, "pop": 167000},
    {"code": "CL", "name": "Cẩm Lệ", "lng": 108.205, "lat": 16.025, "size_deg": 0.022, "pop": 121000},
    {"code": "NHS", "name": "Ngũ Hành Sơn", "lng": 108.260, "lat": 16.005, "size_deg": 0.025, "pop": 89000},
    {"code": "HV", "name": "Hòa Vang", "lng": 108.130, "lat": 16.020, "size_deg": 0.060, "pop": 142000},
    {"code": "HS", "name": "Hoàng Sa", "lng": 112.000, "lat": 16.500, "size_deg": 0.500, "pop": 0},
]

# Distribution per district (HS=0 because uninhabited paracel-island administrative)
ASSET_PER_DISTRICT = {"HC": 50, "ST": 40, "TK": 25, "LC": 25, "CL": 20, "NHS": 20, "HV": 15, "HS": 5}

# 8 asset types from PlanQLDA
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

# Famous Đà Nẵng landmarks (lng, lat, name, type)
LANDMARKS = [
    (108.2300, 16.0617, "Cầu Rồng", "lamp"),
    (108.2273, 16.0670, "Cầu Sông Hàn", "lamp"),
    (108.2398, 16.0477, "Cầu Trần Thị Lý", "lamp"),
    (108.2475, 16.0561, "Bãi biển Mỹ Khê", "trash_can"),
    (108.2204, 16.0693, "Chợ Hàn", "smart_bin"),
    (108.2080, 16.0700, "Chợ Cồn", "smart_bin"),
    (108.2222, 16.0608, "Bảo tàng Chăm", "sign"),
    (108.2191, 16.0616, "Công viên 29/3", "bench"),
    (108.2240, 16.0697, "Đường Bạch Đằng", "lamp"),
    (108.2155, 16.0593, "Nhà hát Trưng Vương", "sign"),
    (108.2767, 16.1011, "Chùa Linh Ứng — Sơn Trà", "toilet"),
    (108.2455, 16.0367, "Marble Mountains", "trash_can"),
    (108.2155, 16.0394, "Asia Park (Sun World)", "ev_charging"),
    (108.2010, 16.0440, "Đại học Bách Khoa", "ev_charging"),
    (108.2330, 16.0760, "Cầu Tình Yêu", "lamp"),
    (108.2390, 16.0640, "Công viên APEC", "bench"),
]

DEMO_USERS = [
    ("admin@danang.gov.vn", "admin", "Admin@123", "admin", "Quản trị viên"),
    ("operator@danang.gov.vn", "operator", "Op@12345", "operator", "Điều phối viên Hải Châu"),
    ("tech@danang.gov.vn", "tech", "Tech@123", "taskforce", "Kỹ thuật viên"),
    ("citizen@danang.gov.vn", "citizen", "User@123", "citizen", "Công dân Đà Nẵng"),
]


def _build_district_polygon_wkt(d: dict) -> str:
    """Approximate square polygon centred on the district centroid."""
    half = d["size_deg"] / 2
    cx, cy = d["lng"], d["lat"]
    return (
        f"SRID=4326;MULTIPOLYGON((("
        f"{cx - half} {cy - half},"
        f"{cx + half} {cy - half},"
        f"{cx + half} {cy + half},"
        f"{cx - half} {cy + half},"
        f"{cx - half} {cy - half})))"
    )


def _random_point_in(d: dict) -> tuple[float, float]:
    half = d["size_deg"] / 2
    lng = d["lng"] + random.uniform(-half * 0.85, half * 0.85)
    lat = d["lat"] + random.uniform(-half * 0.85, half * 0.85)
    return lng, lat


async def seed_areas(db: AsyncSession) -> dict[str, Area]:
    res = await db.execute(select(Area))
    existing = {a.code: a for a in res.scalars().all()}
    out = {}
    for d in DISTRICTS:
        if d["code"] in existing:
            out[d["code"]] = existing[d["code"]]
            continue
        a = Area(
            code=d["code"],
            name=d["name"],
            geometry=_build_district_polygon_wkt(d),
            center=wkt_point(d["lng"], d["lat"]),
            population=d["pop"],
        )
        db.add(a)
        await db.flush()
        out[d["code"]] = a
    await db.commit()
    print(f"  ✓ Seeded {len(out)} areas")
    return out


async def seed_users(db: AsyncSession, areas: dict[str, Area]) -> dict[str, User]:
    res = await db.execute(select(User))
    existing = {u.email: u for u in res.scalars().all()}
    out = {}
    for email, username, password, role, full_name in DEMO_USERS:
        if email in existing:
            out[role] = existing[email]
            continue
        u = User(
            email=email,
            username=username,
            password_hash=hash_password(password),
            role=role,
            full_name=full_name,
            area_id=areas["HC"].id if role in ("operator", "taskforce") else None,
            is_active=True,
        )
        db.add(u)
        await db.flush()
        out[role] = u
    await db.commit()
    print(f"  ✓ Seeded {len(out)} demo users")
    return out


async def seed_assets(
    db: AsyncSession, areas: dict[str, Area], creator: User
) -> int:
    res = await db.execute(select(func.count(Asset.id)))
    if res.scalar_one() > 50:
        print("  · Assets already seeded — skipping")
        return 0
    count = 0
    seq_per_district_type: dict[str, int] = {}
    # Landmarks first
    for lng, lat, name, atype in LANDMARKS:
        # find nearest district
        nearest = min(
            DISTRICTS,
            key=lambda d: math.hypot(d["lng"] - lng, d["lat"] - lat),
        )
        key = f"{nearest['code']}-{atype}"
        seq_per_district_type[key] = seq_per_district_type.get(key, 0) + 1
        a = Asset(
            code=asset_code(nearest["code"], atype, seq_per_district_type[key]),
            name=name,
            asset_type=atype,
            location=wkt_point(lng, lat),
            area_id=areas[nearest["code"]].id,
            status="active",
            installed_at=datetime.now(UTC) - timedelta(days=random.randint(30, 1000)),
            metadata_={"landmark": True},
            created_by=creator.id,
        )
        db.add(a)
        count += 1
    # Random distribution
    for d in DISTRICTS:
        n = ASSET_PER_DISTRICT.get(d["code"], 0)
        for i in range(n):
            atype = random.choice(ASSET_TYPES)
            key = f"{d['code']}-{atype}"
            seq_per_district_type[key] = seq_per_district_type.get(key, 0) + 1
            lng, lat = _random_point_in(d)
            status = random.choices(
                ["active", "damaged", "maintenance", "retired"],
                weights=[70, 15, 10, 5],
            )[0]
            a = Asset(
                code=asset_code(d["code"], atype, seq_per_district_type[key]),
                name=f"{d['name']} {atype} #{seq_per_district_type[key]:03d}",
                asset_type=atype,
                location=wkt_point(lng, lat),
                area_id=areas[d["code"]].id,
                status=status,
                installed_at=datetime.now(UTC) - timedelta(days=random.randint(30, 1500)),
                metadata_={},
                created_by=creator.id,
            )
            db.add(a)
            count += 1
    await db.commit()
    print(f"  ✓ Seeded {count} assets across 8 districts")
    return count


async def seed_alerts(db: AsyncSession) -> None:
    res = await db.execute(select(func.count(AlertLayer.id)))
    if res.scalar_one() > 0:
        print("  · Alert layers already seeded — skipping")
        return
    layers = [
        {
            "layer_type": "construction",
            "severity": "medium",
            "title": "Thi công hạ tầng cáp ngầm — đường Bạch Đằng",
            "polygon": [(108.220, 16.063), (108.230, 16.063), (108.230, 16.070), (108.220, 16.070)],
            "starts_at": datetime.now(UTC),
            "ends_at": datetime.now(UTC) + timedelta(days=30),
        },
        {
            "layer_type": "flood",
            "severity": "high",
            "title": "Điểm ngập sâu mùa mưa — Hòa Vang",
            "polygon": [(108.130, 16.015), (108.140, 16.015), (108.140, 16.025), (108.130, 16.025)],
            "starts_at": None,
            "ends_at": None,
        },
        {
            "layer_type": "aqi",
            "severity": "low",
            "title": "AQI khu vực trung tâm — chấp nhận được",
            "polygon": [(108.215, 16.055), (108.235, 16.055), (108.235, 16.075), (108.215, 16.075)],
            "starts_at": datetime.now(UTC),
            "ends_at": datetime.now(UTC) + timedelta(hours=1),
        },
    ]
    for lay in layers:
        coords_wkt = ", ".join(f"{x} {y}" for x, y in lay["polygon"]) + f", {lay['polygon'][0][0]} {lay['polygon'][0][1]}"
        wkt = f"SRID=4326;POLYGON(({coords_wkt}))"
        db.add(
            AlertLayer(
                layer_type=lay["layer_type"],
                geometry=wkt,
                severity=lay["severity"],
                title=lay["title"],
                starts_at=lay["starts_at"],
                ends_at=lay["ends_at"],
                source="seed",
            )
        )
    await db.commit()
    print(f"  ✓ Seeded {len(layers)} alert layers")


async def seed_sample_reports(db: AsyncSession, citizen: User, areas: dict[str, Area]) -> None:
    res = await db.execute(select(func.count(IncidentReport.id)))
    if res.scalar_one() > 0:
        print("  · Reports already seeded — skipping")
        return
    types = ["pothole", "littering", "broken_lamp", "vandalism", "flooding", "fallen_tree"]
    statuses = ["pending", "accepted", "in_progress", "resolved"]
    for i in range(20):
        t = random.choice(types)
        s = random.choice(statuses)
        d = random.choice(list(areas.values()))
        # Random point near district center
        center_res = await db.execute(
            select(func.ST_X(d.center), func.ST_Y(d.center)).where(Area.id == d.id)
        )
        cx, cy = center_res.first()
        lng = cx + random.uniform(-0.005, 0.005)
        lat = cy + random.uniform(-0.005, 0.005)
        sev = random.choice(["low", "medium", "high"])
        r = IncidentReport(
            code=report_code(i + 1),
            reporter_id=citizen.id,
            area_id=d.id,
            location=wkt_point(lng, lat),
            incident_type=t,
            severity=sev,
            description=f"Mẫu báo cáo {t} tại {d.name}",
            status=s,
            ai_class=t,
            ai_confidence=round(random.uniform(0.65, 0.95), 2),
            sla_due_at=datetime.now(UTC) + timedelta(hours=24),
            resolved_at=datetime.now(UTC) if s == "resolved" else None,
            created_at=datetime.now(UTC) - timedelta(days=random.randint(0, 30)),
        )
        db.add(r)
    await db.commit()
    print("  ✓ Seeded 20 sample incident reports")


async def main() -> None:
    print("Seeding Đà Nẵng baseline data…")
    async with AsyncSessionLocal() as db:
        areas = await seed_areas(db)
        users = await seed_users(db, areas)
        await seed_assets(db, areas, users["admin"])
        await seed_alerts(db)
        await seed_sample_reports(db, users["citizen"], areas)
    print("\nDONE. Demo accounts:")
    for email, _, password, role, _ in DEMO_USERS:
        print(f"  {role:10s} {email:30s} {password}")


if __name__ == "__main__":
    asyncio.run(main())
