# ADR 0001 — Tech Stack: FastAPI + Next.js 16 + MapLibre

**Status**: Accepted
**Date**: 2026-05-05

## Context

Three input plans suggested different stacks (Django + CesiumJS + Flutter, FastAPI + Leaflet, etc.). We needed a single coherent stack optimized for:

- Speed to ship (12-week roadmap)
- 3D map without licensing fees
- Real-time WebSocket fan-out
- Async I/O for high-concurrency citizen reports
- Web-only scope (per stakeholder direction)

## Decision

- **Backend**: FastAPI (async-first, native WebSocket, OpenAPI by default).
- **Frontend**: Next.js 16 + React 19 (App Router; server components for SEO-able landing page).
- **Map**: MapLibre GL JS (open-source fork of Mapbox; supports vector tiles + 3D pitch + globe; no API token required).
- **Database**: PostgreSQL 16 + PostGIS 3.4 (mature spatial features, indexes, ST_DWithin for duplicate detection).
- **AI**: YOLOv8 via separate FastAPI service; mock mode for dev/test.
- **Object storage**: MinIO (S3-compat) for portability; can be swapped to AWS S3 in production.

## Consequences

- ✅ Single language (Python) for backend + AI, single language (TypeScript) for frontend.
- ✅ Free 3D mapping; can upgrade to MapTiler/Mapbox tokens transparently.
- ✅ Async backend handles thousands of concurrent WebSocket clients per node.
- ⚠️ Operators of Postgres + PostGIS are slightly less common than plain Postgres; requires DBA training.
- ⚠️ MapLibre 3D buildings require a vector tile provider with building extrusions for full PlanQLDA "digital twin" feel.

## Alternatives considered

- **CesiumJS**: True 3D globe; rejected as overkill for road-level operations and heavier on bandwidth.
- **Django + DRF**: Mature ORM, but synchronous; would need separate ASGI sidecar for WebSocket.
- **Mobile-first (Flutter)**: Excluded by stakeholder per current scope; web app is responsive PWA-ready.
