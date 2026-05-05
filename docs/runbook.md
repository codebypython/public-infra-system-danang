# Operational Runbook

## On-call playbook

### 1. Service health pulse

```bash
curl -fsS https://infra.danang.gov.vn/api/v1/../health
curl -fsS http://backend:8000/metrics | head -20
```

Watch dashboards: Grafana → "Infra · Overview" panel for p95 latency, error rate, queue depth.

### 2. Common incidents

#### Backend 5xx spike
1. Check Sentry for trending error.
2. `docker logs --tail 200 backend` (production: kubectl logs).
3. Roll back: `git revert <sha> && deploy`.

#### High WebSocket disconnect rate
1. Inspect Nginx → confirm `Connection: upgrade` header.
2. Check Redis pub/sub: `redis-cli PUBSUB NUMSUB rt:user:*`.
3. Increase Nginx `proxy_read_timeout` if reverse-proxy is timing out.

#### Database hot load
1. `pg_stat_activity` → identify long queries.
2. `pg_stat_statements` for top consumers.
3. Add an index or rewrite the query; ship migration via Alembic.

#### MinIO disk full
1. Move oldest `reports/<yyyy/mm>` archives to cold storage.
2. Adjust lifecycle policy:

```bash
mc ilm add --expiry-days 365 local/danang-infra/reports
```

### 3. Backup & restore drill

```bash
# Backup
docker exec db pg_dump -U infra -Fc danang_infra > backup-$(date +%F).dump
docker run --rm -v ${PWD}:/x -v minio-data:/d minio/mc \
  cp -r local/danang-infra /x/minio-backup-$(date +%F)/

# Restore (clean DB)
docker exec -i db pg_restore -U infra -d danang_infra -c < backup-2026-05-05.dump
```

Run a restore drill **weekly** in staging.

### 4. Rotating secrets

```bash
# Generate new JWT secret
python -c "import secrets; print(secrets.token_hex(32))"

# Update env.production, redeploy backend; existing tokens become invalid (acceptable
# at 15-min access TTL + 7-day refresh; force logout via /auth/sessions/revoke-all if needed)
```

### 5. Smoke checks after deploy

```bash
# Health pulse
curl -f https://infra.danang.gov.vn/api/v1/../health

# Auth
curl -X POST https://.../api/v1/auth/login -d '{"email":"...","password":"..."}'

# Map data
curl https://.../api/v1/areas | jq '.[].code'
curl 'https://.../api/v1/assets?page_size=10' | jq '.total'
```
