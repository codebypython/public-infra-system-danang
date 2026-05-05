"""Human-friendly business codes (RPT-2026-000123, TASK-..., DN-HC-LAMP-0001)."""

from __future__ import annotations

import secrets
from datetime import datetime
from typing import Final

ASSET_TYPE_PREFIXES: Final = {
    "bench": "BENCH",
    "trash_can": "TRASH",
    "lamp": "LAMP",
    "toilet": "WC",
    "tree": "TREE",
    "sign": "SIGN",
    "ev_charging": "EV",
    "smart_bin": "SMART",
}


def asset_code(area_code: str, asset_type: str, seq: int) -> str:
    prefix = ASSET_TYPE_PREFIXES.get(asset_type, asset_type.upper()[:5])
    return f"DN-{area_code}-{prefix}-{seq:04d}"


def report_code(seq: int, *, year: int | None = None) -> str:
    y = year or datetime.utcnow().year
    return f"RPT-{y}-{seq:06d}"


def task_code(seq: int, *, year: int | None = None) -> str:
    y = year or datetime.utcnow().year
    return f"TASK-{y}-{seq:06d}"


def short_id(n: int = 8) -> str:
    return secrets.token_hex(n // 2)
