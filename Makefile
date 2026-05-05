# Đà Nẵng Public Infrastructure System — Make targets
# Usage:  make start  | make stop  | make logs SERVICE=backend  | make reset

PROJECT     := danang-infra
COMPOSE     := docker compose -f infra/docker-compose.yml -p $(PROJECT) --env-file .env

.DEFAULT_GOAL := help

.PHONY: help start stop restart logs ps shell-backend shell-db migrate seed reset rebuild status

help:
	@echo "Available targets:"
	@echo "  make start       Khởi động toàn bộ hệ thống (1 lệnh duy nhất)"
	@echo "  make stop        Dừng tất cả services (giữ data)"
	@echo "  make restart     stop + start"
	@echo "  make logs        Tail log tất cả (LINES=200 SERVICE=backend để filter)"
	@echo "  make ps          Liệt kê containers"
	@echo "  make migrate     Chạy alembic upgrade head"
	@echo "  make seed        Re-seed dữ liệu Đà Nẵng"
	@echo "  make shell-backend  Mở bash shell trong backend container"
	@echo "  make shell-db    Mở psql shell"
	@echo "  make rebuild     Rebuild images không cache"
	@echo "  make reset       Dừng + XÓA toàn bộ data volumes (cẩn thận!)"

start:
	@bash ./scripts/start.sh

stop:
	@bash ./scripts/stop.sh

restart: stop start

logs:
	@bash ./scripts/logs.sh $(SERVICE)

ps:
	$(COMPOSE) ps

migrate:
	$(COMPOSE) exec -T backend alembic upgrade head

seed:
	$(COMPOSE) exec -T backend python -m app.scripts.seed_danang

shell-backend:
	$(COMPOSE) exec backend bash

shell-db:
	$(COMPOSE) exec db psql -U infra -d danang_infra

rebuild:
	$(COMPOSE) build --no-cache

status:
	$(COMPOSE) ps
	@echo ''
	@echo 'Health checks:'
	@curl -fs http://localhost:8000/health 2>/dev/null && echo ' - backend OK' || echo ' - backend DOWN'
	@curl -fs http://localhost:8001/health 2>/dev/null && echo ' - ai-service OK' || echo ' - ai-service DOWN'
	@curl -fs http://localhost:3000        2>/dev/null >/dev/null && echo ' - frontend OK' || echo ' - frontend DOWN'

reset:
	@bash ./scripts/reset.sh
