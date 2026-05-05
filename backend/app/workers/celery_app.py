"""Celery app + scheduled tasks (beat).

Usage:
    celery -A app.workers.celery_app worker -l info
    celery -A app.workers.celery_app beat -l info
"""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "danang_infra",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.workers.tasks_aqi",
        "app.workers.tasks_maintenance",
        "app.workers.tasks_kpi",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Ho_Chi_Minh",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)

celery_app.conf.beat_schedule = {
    "fetch-aqi-every-15min": {
        "task": "app.workers.tasks_aqi.fetch_aqi",
        "schedule": crontab(minute="*/15"),
    },
    "create-recurring-maintenance-tasks": {
        "task": "app.workers.tasks_maintenance.run_maintenance_schedules",
        "schedule": crontab(minute=5, hour=2),  # daily 02:05
    },
    "rollup-kpi-daily": {
        "task": "app.workers.tasks_kpi.rollup_daily_kpi",
        "schedule": crontab(minute=10, hour=2),
    },
}
