# Architecture

## Overview

The Đà Nẵng Public Infrastructure System is a web platform composed of:

- **Web frontend** (Next.js 16 / App Router, React 19) — single SPA serving 4 role surfaces (citizen, operator, taskforce, admin) with route-based code splitting.
- **Backend API** (FastAPI) — modular monolith with feature folders under `app/modules/`.
- **AI inference service** (FastAPI separate process) — YOLOv8 image classifier, EXIF GPS extraction, image moderation. Mock mode for dev without GPU.
- **Workers** (Celery + Beat) — periodic AQI fetch, recurring maintenance, KPI rollup.
- **Data plane** — PostgreSQL 16 + PostGIS 3.4, Redis 7 (cache + pub/sub + queue), MinIO (S3-compat object storage), Meilisearch (full-text + geo).
- **Edge** — Nginx reverse proxy + WAF rules + WebSocket upgrade + TLS termination + rate limiting.
- **Observability** — structlog JSON, Prometheus `/metrics`, OpenTelemetry traces, Sentry error tracking, Loki for log shipping.

## Diagram

See top-level Mermaid diagram in [README](../README.md).

## Module map

| Module | Path | Responsibility |
| --- | --- | --- |
| Auth + RBAC | `backend/app/modules/auth/` | JWT access/refresh, RBAC dependency, login throttle |
| Users | `backend/app/modules/users/` | Admin user CRUD, soft-delete |
| Areas | `backend/app/modules/areas/` | 8 quận/huyện Đà Nẵng |
| Assets | `backend/app/modules/assets/` | Digital twin CRUD, versioning, QR, bulk import GeoJSON |
| Reports | `backend/app/modules/reports/` | Citizen incident workflow, AI integration, duplicate detection |
| Tasks | `backend/app/modules/tasks/` | Smart dispatch, GPS check-in, before/after photos, route opt |
| Maintenance | `backend/app/modules/maintenance/` | Logs + recurring schedules |
| Cameras | `backend/app/modules/cameras/` | Camera registry + AI events |
| Alert layers | `backend/app/modules/alert_layers/` | Construction / flood / AQI polygons |
| Notifications | `backend/app/modules/notifications/` | WebSocket broker + persisted notifications |
| Analytics | `backend/app/modules/analytics/` | H3 heatmap, KPI, predictive maintenance, exports |
| Audit | `backend/app/modules/audit/` | Activity log middleware + read API |

## Status state-machines

### Report

```
pending ─accept→ accepted ─dispatch→ in_progress ─complete→ pending_review
   ├─reject→ rejected                                              │
                                                                   ├─approve→ resolved
                                                                   └─reject→ in_progress (rework)
resolved ─reopen→ reopened ─dispatch→ in_progress ...
```

### Task

```
open → assigned → in_progress → pending_review → completed
                       │
                       └→ cancelled
```

## SLA matrix

| Severity | Target resolution time |
| --- | --- |
| urgent  | 2h |
| high    | 8h |
| medium  | 24h |
| low     | 72h |

Implemented in `app/modules/reports/service.py::compute_sla_due`.
