#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$ROOT_DIR/infra/docker-compose.yml"
ENV_FILE="$ROOT_DIR/.env"
PROJECT_NAME="danang-infra"

FORCE=0
[[ "${1:-}" == "--force" || "${1:-}" == "-f" ]] && FORCE=1

if [[ "$FORCE" -eq 0 ]]; then
    echo ''
    echo '!!! CẢNH BÁO: Sẽ XÓA TOÀN BỘ DATA của hệ thống !!!'
    echo '    - PostgreSQL DB'
    echo '    - MinIO objects'
    echo '    - Redis cache'
    echo '    - Meilisearch index'
    echo ''
    read -p 'Gõ "RESET" để xác nhận: ' reply
    if [[ "$reply" != "RESET" ]]; then
        echo 'Huỷ bỏ.'
        exit 0
    fi
fi

ARGS=(-f "$COMPOSE_FILE" -p "$PROJECT_NAME")
[[ -f "$ENV_FILE" ]] && ARGS+=(--env-file "$ENV_FILE")

echo "==> Dừng và xóa volumes..."
docker compose "${ARGS[@]}" down -v --remove-orphans
echo "    [OK] Volumes đã xóa. Chạy ./scripts/start.sh để init lại."
