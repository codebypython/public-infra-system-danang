"""Daily KPI rollup — placeholder for analytics_daily denormalised table."""

from __future__ import annotations

from app.core.logging import get_logger
from app.workers.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(name="app.workers.tasks_kpi.rollup_daily_kpi")
def rollup_daily_kpi() -> int:
    """Stub: in production this writes to `analytics_daily` table for fast dashboards."""
    logger.info("kpi.rollup.placeholder")
    return 0
