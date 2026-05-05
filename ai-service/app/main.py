"""AI inference FastAPI service."""

from __future__ import annotations

import io
import time
from typing import Any

import structlog
from fastapi import FastAPI, File, HTTPException, UploadFile
from PIL import Image, ExifTags

from app import __version__
from app.classifier import INCIDENT_CLASSES, classify
from app.config import settings

logger = structlog.get_logger()

app = FastAPI(
    title="Đà Nẵng Infrastructure — AI Service",
    version=__version__,
    description="YOLOv8 inference + image moderation + EXIF GPS extraction",
)


def _exif_gps(image_bytes: bytes) -> dict[str, float] | None:
    try:
        img = Image.open(io.BytesIO(image_bytes))
        exif = img._getexif() or {}
        gps_info = exif.get(next(k for k, v in ExifTags.TAGS.items() if v == "GPSInfo"), None)
        if not gps_info:
            return None
        # Convert
        def _conv(coord, ref):
            d, m, s = coord
            val = float(d) + float(m) / 60 + float(s) / 3600
            if ref in ("S", "W"):
                val = -val
            return val

        lat_ref = gps_info.get(1)
        lat = gps_info.get(2)
        lng_ref = gps_info.get(3)
        lng = gps_info.get(4)
        if lat and lng and lat_ref and lng_ref:
            return {"lat": _conv(lat, lat_ref), "lng": _conv(lng, lng_ref)}
    except Exception:  # noqa: BLE001
        return None
    return None


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "version": __version__,
        "model": "real" if settings.use_real_model else "mock",
        "model_path": settings.model_path,
        "classes": INCIDENT_CLASSES,
    }


@app.post("/classify")
async def classify_endpoint(file: UploadFile = File(...)) -> dict[str, Any]:
    if file.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(status_code=400, detail="Image must be JPEG/PNG/WEBP")
    content = await file.read()
    if len(content) > settings.max_image_bytes:
        raise HTTPException(status_code=413, detail="Image too large (max 10MB)")
    if len(content) < 256:
        raise HTTPException(status_code=400, detail="Image too small / corrupt")
    started = time.perf_counter()
    result = classify(content, file.filename or "img.jpg")
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    gps = _exif_gps(content)
    logger.info(
        "ai.classify",
        primary=result.get("primary_class"),
        confidence=result.get("confidence"),
        latency_ms=elapsed_ms,
        size=len(content),
    )
    return {**result, "latency_ms": elapsed_ms, "exif_gps": gps}


@app.post("/analyze-video")
async def analyze_video(camera_id: str, video_url: str) -> dict[str, Any]:
    """Stub — production worker handles RTSP/HLS streams asynchronously."""
    return {
        "camera_id": camera_id,
        "video_url": video_url,
        "events": [],
        "note": "Use the dedicated stream worker for live RTSP/HLS analysis",
    }
