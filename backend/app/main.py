"""FastAPI application factory + global wiring."""

from __future__ import annotations

from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.gzip import GZipMiddleware

from app import __version__
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.modules.alert_layers import router as alert_router
from app.modules.analytics import router as analytics_router
from app.modules.areas import router as areas_router
from app.modules.assets import router as assets_router
from app.modules.audit import AuditMiddleware
from app.modules.audit import router as audit_router
from app.modules.auth import router as auth_router
from app.modules.cameras import router as cameras_router
from app.modules.maintenance import router as maintenance_router
from app.modules.notifications import router as notifications_router
from app.modules.notifications.broker import broker
from app.modules.reports import router as reports_router
from app.modules.tasks import router as tasks_router
from app.modules.users import router as users_router

configure_logging()
logger = get_logger(__name__)

if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.env,
        traces_sample_rate=0.1 if settings.env == "production" else 1.0,
        send_default_pii=False,
    )

limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await broker.start()
    logger.info("app.startup", env=settings.env, version=__version__)
    yield
    await broker.stop()
    logger.info("app.shutdown")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Đà Nẵng Public Infrastructure System — API",
        version=__version__,
        description="Production-grade API for Đà Nẵng smart-city infrastructure platform",
        lifespan=lifespan,
        openapi_url="/api/v1/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Middlewares
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(AuditMiddleware)

    # Rate limiter
    app.state.limiter = limiter

    @app.exception_handler(RateLimitExceeded)
    async def _rl(_: Request, exc: RateLimitExceeded):
        return JSONResponse(
            status_code=429,
            content={"error": {"code": "rate_limited", "message": "Too many requests"}},
        )

    register_exception_handlers(app)

    # Health
    @app.get("/health", tags=["health"])
    async def health():
        return {"status": "ok", "version": __version__, "env": settings.env}

    @app.get("/ready", tags=["health"])
    async def ready():
        # Simple readiness — extend with DB ping if needed
        return {"ready": True}

    @app.get("/", tags=["health"])
    async def root():
        return {
            "name": "Đà Nẵng Public Infrastructure System",
            "version": __version__,
            "docs": "/docs",
        }

    # Routers
    base = "/api/v1"
    app.include_router(auth_router, prefix=base)
    app.include_router(users_router, prefix=base)
    app.include_router(areas_router, prefix=base)
    app.include_router(assets_router, prefix=base)
    app.include_router(reports_router, prefix=base)
    app.include_router(tasks_router, prefix=base)
    app.include_router(maintenance_router, prefix=base)
    app.include_router(cameras_router, prefix=base)
    app.include_router(alert_router, prefix=base)
    app.include_router(notifications_router, prefix=base)
    app.include_router(analytics_router, prefix=base)
    app.include_router(audit_router, prefix=base)

    # Prometheus metrics endpoint (lightweight)
    try:
        from prometheus_client import (
            CONTENT_TYPE_LATEST,
            CollectorRegistry,
            generate_latest,
            multiprocess,
        )

        @app.get("/metrics", tags=["health"])
        async def metrics():
            from fastapi.responses import Response

            registry = CollectorRegistry()
            try:
                multiprocess.MultiProcessCollector(registry)
            except Exception:  # noqa: BLE001
                from prometheus_client import REGISTRY as _R

                registry = _R
            return Response(content=generate_latest(registry), media_type=CONTENT_TYPE_LATEST)
    except ImportError:
        pass

    return app


app = create_app()
