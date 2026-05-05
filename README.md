# Đà Nẵng Public Infrastructure System

> Hệ thống quản lý hạ tầng công cộng thành phố Đà Nẵng — production-grade web platform với GIS 3D, AI báo cáo sự cố, và command center điều phối.

## Tổng quan

Platform web responsive dành cho 4 vai trò người dùng:

- **Citizen**: tra cứu hạ tầng 3D, báo cáo sự cố tích hợp AI YOLOv8, theo dõi tiến độ ticket realtime, xem các lớp cảnh báo công cộng (thi công, ngập, AQI).
- **Operator**: command center điều phối thông minh, AI verification, dispatch theo proximity.
- **TaskForce**: nhận task, GPS check-in, upload ảnh before/after có watermark, tối ưu route.
- **Admin**: quản lý digital twin, camera surveillance AI, analytics & BI, user management.

Phạm vi địa lý: 8 quận/huyện thành phố Đà Nẵng (Hải Châu, Sơn Trà, Thanh Khê, Liên Chiểu, Cẩm Lệ, Ngũ Hành Sơn, Hòa Vang, Hoàng Sa). Bbox `15.95-16.20°N, 107.95-108.45°E`.

## Kiến trúc

```
┌─────────────────────────────────────────────────────────┐
│  Next.js 16 Web (Citizen / Operator / TaskForce / Admin)│
└────────────────────────┬────────────────────────────────┘
                         │ HTTPS + WebSocket
                ┌────────▼─────────┐
                │  Nginx (gateway) │
                └────────┬─────────┘
                         │
         ┌───────────────┼─────────────────┐
         ▼               ▼                 ▼
    ┌─────────┐    ┌──────────┐     ┌──────────────┐
    │ FastAPI │◄──►│ AI Svc   │     │ Celery Worker│
    │ Backend │    │ (YOLOv8) │     │ + Beat       │
    └────┬────┘    └────┬─────┘     └───────┬──────┘
         │              │                   │
    ┌────▼──────────────▼───────────────────▼──────┐
    │ PostgreSQL 16 + PostGIS │ Redis │ MinIO │ Meili│
    └───────────────────────────────────────────────┘
```

Chi tiết kế hoạch tại `docs/architecture.md`.

## Tech stack

- **Frontend**: Next.js 16 (App Router) · React 19 · TypeScript 5 · Tailwind 4 · shadcn/ui · MapLibre GL JS · Zustand · TanStack Query · react-hook-form + zod
- **Backend**: Python 3.12 · FastAPI · SQLAlchemy 2 (async) · GeoAlchemy2 · Pydantic v2 · Alembic · Celery · python-socketio
- **AI**: ultralytics YOLOv8 · OpenCV · scikit-learn (predictive maintenance)
- **Data**: PostgreSQL 16 + PostGIS 3.4 · Redis 7 · MinIO · Meilisearch
- **Observability**: OpenTelemetry · Prometheus · Grafana · Loki · Sentry
- **DevOps**: Docker Compose · Nginx · GitHub Actions · k6 · Trivy/Semgrep/Bandit

## Cấu trúc thư mục

```
public-infra-system-for-Danangcity/
├── frontend/        Next.js 16 app
├── backend/         FastAPI monolith modular
├── ai-service/      FastAPI YOLOv8 inference
├── infra/           docker-compose, nginx, prometheus, seed data
├── docs/            ADRs + runbook + architecture
└── .github/         CI/CD workflows
```

## Khởi động — 1 LỆNH DUY NHẤT

Chỉ cần Docker Desktop cài sẵn (nếu chưa, script sẽ tự cài qua winget).

> **Lần đầu setup máy?** Đọc [`SETUP-ROADMAP.md`](./SETUP-ROADMAP.md) — checklist chi tiết 6 phase, gồm xử lý Vanguard, Windows Insider, WSL2, Docker Desktop. Đặc biệt cần nếu máy bạn đang ở Insider Canary build hoặc có Riot Vanguard cài.

### Windows (PowerShell)

```powershell
.\start.cmd
# hoặc
.\scripts\start.ps1
```

### macOS / Linux / WSL

```bash
./scripts/start.sh
# hoặc
make start
```

Script sẽ tự động:

1. Kiểm tra Docker (offer cài Docker Desktop nếu thiếu).
2. Tạo `.env` từ `.env.example` (auto-generate `SECRET_KEY`).
3. Build và khởi động **toàn bộ** stack: PostgreSQL+PostGIS · Redis · MinIO · Meilisearch · MailHog · Backend FastAPI · AI Service · Frontend Next.js · Celery worker + beat.
4. Đợi PostgreSQL ready, chạy Alembic migrations.
5. Seed dữ liệu Đà Nẵng (8 quận, 4 tài khoản demo, ~200 assets, 20 sample reports).
6. In ra URLs và demo accounts.

### Lệnh phụ trợ

| Lệnh                              | Tác dụng                                                     |
| --------------------------------- | ------------------------------------------------------------ |
| `.\scripts\start.ps1`             | Khởi động hệ thống (Windows)                                 |
| `.\scripts\stop.ps1`              | Dừng tất cả (giữ data)                                       |
| `.\scripts\logs.ps1 [svc]`        | Tail log (tất cả hoặc 1 service)                             |
| `.\scripts\reset.ps1`             | Dừng + XÓA toàn bộ data volumes                              |
| `.\scripts\start.ps1 -Rebuild`    | Rebuild Docker images không cache                            |
| `.\scripts\start.ps1 -NoSeed`     | Bỏ qua seed dữ liệu                                          |
| `.\scripts\backup-pre-update.ps1` | Restore point + Bitlocker key + zip project (trước update Windows) |
| `.\scripts\dev-mode.ps1`          | Switch sang Dev mode (Vanguard OFF, Docker work)             |
| `.\scripts\game-mode.ps1`         | Switch sang Game mode (Vanguard ON, chơi Valorant)           |
| `.\scripts\mode-status.ps1`       | Kiểm tra trạng thái Vanguard / Docker / WSL / containers     |
| `make start / stop / logs`        | Tương đương cho macOS/Linux                                  |

### URLs

- **Web app**: <http://localhost:3000>
- **API docs**: <http://localhost:8000/docs>
- **AI service docs**: <http://localhost:8001/docs>
- **MinIO console**: <http://localhost:9001> (`minioadmin` / `minioadmin`)
- **MailHog (catch-all email)**: <http://localhost:8025>
- **Meilisearch**: <http://localhost:7700>

## Phát triển native (tuỳ chọn, không Docker)

<details>
<summary>Click để xem hướng dẫn chạy native từng service</summary>

```bash
docker compose -f infra/docker-compose.yml up -d db redis minio meilisearch  # data layer

cd backend && pip install -e .[dev] && alembic upgrade head
python -m app.scripts.seed_danang
uvicorn app.main:app --port 8000 --reload

cd ../ai-service && pip install -e .
uvicorn app.main:app --port 8001 --reload

cd ../frontend && npm install && npm run dev
```

</details>

## Demo accounts (sau khi seed)

| Role      | Email                    | Password    |
| --------- | ------------------------ | ----------- |
| Admin     | `admin@danang.gov.vn`    | `Admin@123` |
| Operator  | `operator@danang.gov.vn` | `Op@12345`  |
| TaskForce | `tech@danang.gov.vn`     | `Tech@123`  |
| Citizen   | `citizen@danang.gov.vn`  | `User@123`  |

## Yêu cầu hệ thống

- **Docker Desktop** (Windows / macOS) hoặc **Docker Engine + Compose plugin** (Linux). Nếu chưa cài, script `start.ps1` sẽ tự cài qua winget.
- RAM ≥ 8 GB (khuyến nghị 16 GB), Disk ≥ 10 GB free cho images + data.
- Cổng yêu cầu rảnh: `3000, 5432, 6379, 7700, 8000, 8001, 8025, 9000, 9001, 1025`.

## License

Internal — Đà Nẵng Smart City Project.
