# ADR 0002 — Soft delete + asset versioning

**Status**: Accepted
**Date**: 2026-05-05

## Context

Public infrastructure assets cannot be hard-deleted: maintenance history, incident references, and audit trails must survive renames, relocations, and decommissioning.

## Decision

- All write operations on `assets` produce a snapshot row in `asset_versions(snapshot JSONB, changed_by, changed_at)`.
- Logical deletion sets `assets.deleted_at = now()`. Lists default to `WHERE deleted_at IS NULL`.
- Restore endpoint (`POST /assets/{id}/restore`, admin only) clears `deleted_at`.
- Users follow the same pattern via `users.deleted_at`.

## Consequences

- ✅ Full audit trail for every CRUD on assets.
- ✅ Reports/tasks linked to deleted assets remain valid for legal retention.
- ⚠️ `asset_versions` grows unbounded — schedule a partitioning + archival job for >2y data.
- ⚠️ Indexes on `assets` must include `deleted_at IS NULL` partial filters for hot lookups.
