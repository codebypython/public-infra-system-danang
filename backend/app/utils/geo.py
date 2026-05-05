"""Geometry helpers — WKT/WKB conversion + bbox parsing + Da Nang validators."""

from __future__ import annotations

from typing import Any

from geoalchemy2.shape import to_shape
from shapely.geometry import Point, Polygon, mapping

from app.core.config import settings


def wkt_point(lng: float, lat: float) -> str:
    """Return SRID=4326 EWKT for a point."""
    return f"SRID=4326;POINT({lng} {lat})"


def parse_bbox(raw: str) -> tuple[float, float, float, float]:
    """`min_lng,min_lat,max_lng,max_lat` -> tuple, validated."""
    parts = raw.split(",")
    if len(parts) != 4:
        raise ValueError("bbox must have 4 comma-separated floats")
    min_lng, min_lat, max_lng, max_lat = (float(p) for p in parts)
    if min_lng >= max_lng or min_lat >= max_lat:
        raise ValueError("Invalid bbox order")
    return min_lng, min_lat, max_lng, max_lat


def bbox_polygon_wkt(bbox: tuple[float, float, float, float]) -> str:
    min_lng, min_lat, max_lng, max_lat = bbox
    return (
        f"SRID=4326;POLYGON(({min_lng} {min_lat},{max_lng} {min_lat},"
        f"{max_lng} {max_lat},{min_lng} {max_lat},{min_lng} {min_lat}))"
    )


def is_in_danang(lng: float, lat: float) -> bool:
    """Cheap pre-check using city bbox; geometry intersection is more precise (DB level)."""
    return (
        settings.danang_bbox_min_lng <= lng <= settings.danang_bbox_max_lng
        and settings.danang_bbox_min_lat <= lat <= settings.danang_bbox_max_lat
    )


def geom_to_geojson(geom: Any) -> dict[str, Any] | None:
    """Convert GeoAlchemy2 element to GeoJSON dict."""
    if geom is None:
        return None
    shape = to_shape(geom)
    return mapping(shape)


def point_lng_lat(geom: Any) -> tuple[float, float] | None:
    if geom is None:
        return None
    p: Point = to_shape(geom)
    return p.x, p.y
