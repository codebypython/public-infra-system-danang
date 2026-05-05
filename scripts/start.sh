#!/usr/bin/env bash
# =====================================================================
# Đà Nẵng Public Infrastructure System — One-command launcher (Unix)
# =====================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$ROOT_DIR/infra/docker-compose.yml"
ENV_FILE="$ROOT_DIR/.env"
ENV_EXAMPLE="$ROOT_DIR/.env.example"
PROJECT_NAME="danang-infra"

NO_SEED=0
REBUILD=0
FOREGROUND=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --no-seed)    NO_SEED=1; shift ;;
        --rebuild)    REBUILD=1; shift ;;
        --foreground|--fg) FOREGROUND=1; shift ;;
        -h|--help)
            cat <<EOF
Usage: ./scripts/start.sh [--no-seed] [--rebuild] [--foreground]
  --no-seed     Bỏ qua bước seed dữ liệu Đà Nẵng.
  --rebuild     Force docker compose build --no-cache.
  --foreground  Chạy ở chế độ foreground (không detach).
EOF
            exit 0 ;;
        *) echo "Unknown arg: $1"; exit 1 ;;
    esac
done

# --- Helpers ---
c_cyan='\033[0;36m'; c_green='\033[0;32m'; c_yellow='\033[0;33m'; c_red='\033[0;31m'; c_off='\033[0m'
step()  { echo -e "\n${c_cyan}==> $*${c_off}"; }
ok()    { echo -e "    ${c_green}[OK] $*${c_off}"; }
warn()  { echo -e "    ${c_yellow}[WARN] $*${c_off}"; }
err()   { echo -e "    ${c_red}[ERR] $*${c_off}"; }

cat <<EOF

+============================================================+
|   Đà Nẵng Public Infrastructure System  -  DEV Launcher    |
+============================================================+
EOF

# --- 1. Detect Docker ---
step "Kiểm tra Docker"
if ! command -v docker >/dev/null 2>&1; then
    err "Docker chưa cài. Cài Docker Desktop / Docker Engine trước:"
    echo "    https://www.docker.com/products/docker-desktop/"
    exit 1
fi
if ! docker info >/dev/null 2>&1; then
    err "Docker daemon chưa khởi động. Mở Docker Desktop và thử lại."
    exit 1
fi
ok "$(docker --version)"

if ! docker compose version >/dev/null 2>&1; then
    err "Docker Compose plugin không có. Cập nhật Docker Desktop / cài plugin compose."
    exit 1
fi
ok "$(docker compose version | head -n1)"

# --- 2. Bootstrap .env ---
step "Chuẩn bị .env"
if [[ ! -f "$ENV_FILE" ]]; then
    cp "$ENV_EXAMPLE" "$ENV_FILE"
    SECRET=$(LC_ALL=C tr -dc 'a-zA-Z0-9' </dev/urandom | head -c 64)
    if [[ "$(uname)" == "Darwin" ]]; then
        sed -i '' "s|change-me-to-a-random-64-char-hex-string-for-jwt-signing|$SECRET|" "$ENV_FILE"
    else
        sed -i "s|change-me-to-a-random-64-char-hex-string-for-jwt-signing|$SECRET|" "$ENV_FILE"
    fi
    ok ".env tạo từ .env.example (SECRET_KEY auto)"
else
    ok ".env đã tồn tại"
fi

COMPOSE=(docker compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" --env-file "$ENV_FILE")

# --- 3. Build & Up ---
step "Build & start containers"
if [[ "$REBUILD" -eq 1 ]]; then
    "${COMPOSE[@]}" build --no-cache
fi

if [[ "$FOREGROUND" -eq 1 ]]; then
    "${COMPOSE[@]}" up --build
    exit 0
else
    "${COMPOSE[@]}" up --build -d
fi
ok "Containers đã start"

# --- 4. Wait for DB ---
step "Đợi PostgreSQL ready"
for i in $(seq 1 60); do
    if "${COMPOSE[@]}" exec -T db pg_isready -U infra -d danang_infra >/dev/null 2>&1; then
        ok "PostgreSQL ready"
        break
    fi
    sleep 2
    printf '.'
done
echo ''

# --- 5. Migrations ---
step "Alembic migrations"
"${COMPOSE[@]}" exec -T backend alembic upgrade head
ok "Migrations applied"

# --- 6. Seed ---
if [[ "$NO_SEED" -eq 0 ]]; then
    step "Seed dữ liệu Đà Nẵng"
    if "${COMPOSE[@]}" exec -T backend python -m app.scripts.seed_danang; then
        ok "Seed hoàn tất"
    else
        warn "Seed lỗi / đã seed trước đó"
    fi
fi

# --- 7. Done ---
cat <<EOF

${c_green}+============================================================+
|   HỆ THỐNG ĐÃ SẴN SÀNG                                     |
+============================================================+${c_off}

  Frontend (Next.js)        : ${c_cyan}http://localhost:3000${c_off}
  Backend API (FastAPI)     : ${c_cyan}http://localhost:8000${c_off}
  API Docs (Swagger)        : ${c_cyan}http://localhost:8000/docs${c_off}
  AI Service                : ${c_cyan}http://localhost:8001/docs${c_off}
  MinIO Console             : ${c_cyan}http://localhost:9001${c_off}  (minioadmin / minioadmin)
  MailHog                   : ${c_cyan}http://localhost:8025${c_off}
  Meilisearch               : ${c_cyan}http://localhost:7700${c_off}

  ${c_yellow}Demo accounts:${c_off}
    admin@danang.gov.vn      / Admin@123  (admin)
    operator@danang.gov.vn   / Op@12345   (operator)
    tech@danang.gov.vn       / Tech@123   (taskforce)
    citizen@danang.gov.vn    / User@123   (citizen)

  ${c_yellow}Lệnh hữu ích:${c_off}
    ./scripts/logs.sh             -> log tất cả
    ./scripts/logs.sh backend     -> log 1 service
    ./scripts/stop.sh             -> dừng tất cả
    ./scripts/reset.sh            -> dừng và xóa data volumes

EOF
