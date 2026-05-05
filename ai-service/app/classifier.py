"""YOLOv8 classifier with mock fallback.

Real mode requires `ultralytics` and `opencv-python-headless`. When unavailable
or `use_real_model=False`, returns a deterministic-ish mock based on filename hash.
"""

from __future__ import annotations

import hashlib
import io
import random
from typing import Any

from app.config import settings

INCIDENT_CLASSES = (
    "littering",
    "pothole",
    "broken_lamp",
    "vandalism",
    "flooding",
    "crowd",
    "fallen_tree",
)

# COCO -> our incident-class mapping (heuristic when using base YOLOv8)
COCO_HINTS = {
    "person": "crowd",
    "bench": "littering",
    "bottle": "littering",
    "car": "pothole",
    "fire hydrant": "broken_lamp",
    "tree": "fallen_tree",
}

_real_model = None


def _load_real_model() -> Any | None:
    global _real_model
    if _real_model is not None:
        return _real_model
    try:
        from ultralytics import YOLO

        _real_model = YOLO(settings.model_path)
        return _real_model
    except Exception:  # noqa: BLE001
        return None


def classify(image_bytes: bytes, filename: str = "image.jpg") -> dict[str, Any]:
    if settings.use_real_model:
        model = _load_real_model()
        if model is not None:
            return _classify_real(model, image_bytes)
    return _classify_mock(image_bytes, filename)


def _classify_real(model: Any, image_bytes: bytes) -> dict[str, Any]:
    import cv2
    import numpy as np

    arr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    results = model(img, conf=settings.confidence_threshold)
    detections = []
    for r in results:
        names = r.names if hasattr(r, "names") else {}
        for box in r.boxes:
            cls_id = int(box.cls[0])
            label = names.get(cls_id, "unknown")
            mapped = COCO_HINTS.get(label, label)
            if mapped in INCIDENT_CLASSES:
                detections.append(
                    {
                        "class": mapped,
                        "confidence": float(box.conf[0]),
                        "bbox": box.xyxy[0].tolist(),
                    }
                )
    primary = max(detections, key=lambda x: x["confidence"]) if detections else None
    return {
        "detections": detections,
        "primary_class": primary["class"] if primary else None,
        "confidence": primary["confidence"] if primary else 0.0,
        "is_valid_report": bool(detections),
        "model": "yolov8-real",
    }


def _classify_mock(image_bytes: bytes, filename: str) -> dict[str, Any]:
    """Deterministic mock — same image yields same class for stable tests."""
    seed = int(hashlib.md5(image_bytes[:4096]).hexdigest(), 16) % (10**8)
    rng = random.Random(seed)
    primary = rng.choice(INCIDENT_CLASSES)
    confidence = round(rng.uniform(0.62, 0.94), 3)
    detections = [
        {
            "class": primary,
            "confidence": confidence,
            "bbox": [
                rng.randint(20, 200),
                rng.randint(20, 200),
                rng.randint(300, 500),
                rng.randint(300, 500),
            ],
        }
    ]
    # Add 0–2 secondary detections sometimes
    for _ in range(rng.randint(0, 2)):
        detections.append(
            {
                "class": rng.choice(INCIDENT_CLASSES),
                "confidence": round(rng.uniform(0.4, confidence), 3),
                "bbox": [
                    rng.randint(20, 200),
                    rng.randint(20, 200),
                    rng.randint(300, 500),
                    rng.randint(300, 500),
                ],
            }
        )
    return {
        "detections": detections,
        "primary_class": primary,
        "confidence": confidence,
        "is_valid_report": True,
        "model": "mock-yolov8",
    }
