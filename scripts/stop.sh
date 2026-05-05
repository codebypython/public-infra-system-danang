#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$ROOT_DIR/infra/docker-compose.yml"
ENV_FILE="$ROOT_DIR/.env"
PROJECT_NAME="danang-infra"

ARGS=(-f "$COMPOSE_FILE" -p "$PROJECT_NAME")
[[ -f "$ENV_FILE" ]] && ARGS+=(--env-file "$ENV_FILE")

echo "==> Dừng tất cả services..."
docker compose "${ARGS[@]}" down
echo "    [OK] Containers đã dừng. Data volumes vẫn được giữ. Restart bằng ./scripts/start.sh"
