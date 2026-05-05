#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$ROOT_DIR/infra/docker-compose.yml"
ENV_FILE="$ROOT_DIR/.env"
PROJECT_NAME="danang-infra"

LINES=${LINES:-100}
SERVICE="${1:-}"

ARGS=(-f "$COMPOSE_FILE" -p "$PROJECT_NAME")
[[ -f "$ENV_FILE" ]] && ARGS+=(--env-file "$ENV_FILE")

LOG_ARGS=(logs -f --tail "$LINES")
[[ -n "$SERVICE" ]] && LOG_ARGS+=("$SERVICE")

echo "==> Tailing logs (Ctrl+C để thoát)..."
docker compose "${ARGS[@]}" "${LOG_ARGS[@]}"
