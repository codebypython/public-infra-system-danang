# Setup Roadmap — Đà Nẵng Public Infrastructure System

> **Mục tiêu**: chạy được toàn bộ hệ thống bằng `.\start.cmd` trên máy Windows 11 Home Single Language hiện đang gặp lỗi DISM/CBS build mismatch + có Vanguard cài.
>
> **Yêu cầu**: giữ nguyên dữ liệu trên D:, E:, F:; cho phép gỡ + cài lại Vanguard sau này khi muốn chơi Valorant.
>
> **Tổng thời gian**: ~115 phút (chủ yếu chờ Windows Update download + install). Bạn có thể làm việc khác trong lúc chờ.

---

## Tổng quan 6 Phase

| Phase | Tên | Thời gian | Bắt buộc reboot? |
| ----- | --- | --------- | ---------------- |
| 1     | Backup quick + Bitlocker check                   | 15 phút      | Không  |
| 2     | Switch Beta channel + update Windows build 26220 | 60 phút      | 1 lần  |
| 3     | Uninstall Vanguard                                | 1 phút       | Không  |
| 4     | Cài WSL2                                          | 10 phút      | 1 lần  |
| 5     | Cài Docker Desktop                                | 10 phút      | 1 lần  |
| 6     | Chạy hệ thống với `.\start.cmd`                   | 15 phút      | Không  |

> Mở **PowerShell as Administrator** (chuột phải Start → Terminal (Admin)) và giữ nó open xuyên suốt. Mọi lệnh dưới đây paste vào đó.

---

## ✅ Phase 1 — Backup quick + Bitlocker check (15 phút)

### Bước 1.1 — Chạy script tự động backup

```powershell
cd D:\Development\projects\public-infra-system-for-Danangcity
.\scripts\backup-pre-update.ps1
```

Script sẽ tự làm:
- Tạo restore point Windows
- Check Bitlocker status, lưu recovery key (nếu có)
- Zip project folder vào `D:\Development\backup-danang-<timestamp>.zip`
- In ra danh sách 20 file lớn nhất trên D:/E:/F: để bạn review

### Bước 1.2 — Verify backup OK

```powershell
# Kiểm tra restore point đã tạo
Get-ComputerRestorePoint | Select-Object -Last 1 | Format-List Description, CreationTime

# Kiểm tra file zip backup
Get-ChildItem "D:\Development\backup-danang-*.zip" | Select-Object Name, Length, LastWriteTime
```

Output mong đợi: 1 restore point có description "Pre-Beta-Channel-Switch" và 1 file zip ~10-50MB.

### Bước 1.3 — Backup data Tier 1 (nếu có)

Nếu bạn có ảnh, code chưa push, tài liệu quan trọng trên D:/E:/F: → copy thủ công lên USB ngoài hoặc cloud (Google Drive, OneDrive). Đây là best practice 3-2-1, không liên quan trực tiếp tới Windows update.

---

## ✅ Phase 2 — Switch Beta channel + update Windows (60 phút)

### Bước 2.1 — Mở dialog Insider Program

```powershell
start ms-settings:windowsinsider
```

### Bước 2.2 — Enroll Beta channel

Trong dialog wizard:
1. Click **Get started**
2. Step 1/4 — Link Microsoft account → click **Continue**
3. Step 2/4 — Choose channel → click **Beta Channel** (highlight) → **Continue**
4. Step 3/4 — Confirm switch → **Continue**
5. Step 4/4 — Tick agree terms → **Continue**
6. Click **Restart now**

### Bước 2.3 — Sau khi máy khởi động lại, mở Windows Update

```powershell
start ms-settings:windowsupdate
```

→ Click **Check for updates**.

### Bước 2.4 — Download + install build Beta

Bạn sẽ thấy build `26220.xxxx` (hoặc cao hơn) bắt đầu download (~3-5GB).

| Tình huống | Hành động |
| ---------- | --------- |
| Build Beta đang download tự động | Đợi 30-60 phút → click **Restart now** khi hỏi |
| Không thấy build mới, chỉ thấy "You're up to date" | Đợi 5 phút rồi check lại; nếu vẫn không có → xem **Troubleshooting Phase 2** ở cuối file |

### Bước 2.5 — Verify build mới đã cài

Sau khi máy khởi động lại lần 2:

```powershell
[System.Environment]::OSVersion.Version
Get-ComputerInfo | Select-Object WindowsProductName, WindowsVersion, OsBuildNumber
```

Output mong đợi:
```
Major  Minor  Build  Revision
-----  -----  -----  --------
10     0      26220  ????

OsBuildNumber : 26220 (hoặc cao hơn)
```

### Bước 2.6 — Verify DISM đã sync

```powershell
dism.exe /online /get-featureinfo /featurename:VirtualMachinePlatform
```

Output mong đợi:
```
Feature Name : VirtualMachinePlatform
State : Disabled
```

**Quan trọng**: bạn phải thấy `State : Disabled` (không phải `Error 1168`). Nếu vẫn `Error 1168` → DISM chưa sync, đợi thêm Windows Update hoặc xem Troubleshooting.

---

## ✅ Phase 3 — Uninstall Vanguard (1 phút)

### Bước 3.1 — Stop services trước khi uninstall

```powershell
sc.exe stop vgc 2>$null
sc.exe stop vgk 2>$null
```

### Bước 3.2 — Mở Settings để uninstall

```powershell
start ms-settings:appsfeatures
```

→ Trong ô Search, gõ **"Vanguard"** → click 3 chấm bên cạnh **Riot Vanguard** → **Uninstall** → confirm.

### Bước 3.3 — Verify đã gỡ

```powershell
Get-Service vgc, vgk -ErrorAction SilentlyContinue
```

Phải trả về empty / "Cannot find any service".

> **Lưu ý**: Khi nào muốn chơi Valorant lại, mở launcher Valorant — nó tự download + install Vanguard trong 5 phút. Nhưng lúc đó Docker sẽ STOP work. Để switch giữa 2 mode dễ dàng, dùng `dev-mode.ps1` / `game-mode.ps1` (xem dưới).

---

## ✅ Phase 4 — Cài WSL2 (10 phút)

### Bước 4.1 — Enable VMP + Linux Subsystem

```powershell
wsl --install --no-distribution
```

Output mong đợi:
```
Installing Windows optional component: VirtualMachinePlatform
The operation completed successfully.
Installing Windows optional component: Microsoft-Windows-Subsystem-Linux
The operation completed successfully.
```

### Bước 4.2 — Set WSL2 default + update kernel

```powershell
wsl --set-default-version 2
wsl --update
```

### Bước 4.3 — Restart máy lần 3

```powershell
Restart-Computer
```

### Bước 4.4 — Sau reboot, cài Ubuntu

```powershell
wsl --install -d Ubuntu
```

Một cửa sổ Ubuntu sẽ tự bật → khi thấy prompt:
```
Enter new UNIX username:
```
→ gõ username (ví dụ `kien`) → Enter → nhập password Linux (gõ tùy ý, **nhớ password**) → Enter lại để confirm.

Khi thấy prompt `kien@HOSTNAME:~$` → gõ `exit` → đóng cửa sổ.

### Bước 4.5 — Verify WSL2 chạy

```powershell
wsl --status
wsl --list --verbose
```

Output mong đợi:
```
Default Distribution: Ubuntu
Default Version: 2

NAME      STATE        VERSION
Ubuntu    Stopped      2
```

---

## ✅ Phase 5 — Cài Docker Desktop (10 phút)

### Bước 5.1 — Cài qua winget

```powershell
winget install -e --id Docker.DockerDesktop --accept-package-agreements --accept-source-agreements
```

UAC prompt sẽ hiện → click **Yes**. Đợi installer chạy ~3-5 phút.

### Bước 5.2 — Restart máy lần 4

```powershell
Restart-Computer
```

### Bước 5.3 — Sau reboot, mở Docker Desktop

- Start menu → tìm **Docker Desktop** → click mở
- Wizard hiện:
  - Tick **Use WSL 2 instead of Hyper-V** (đã default trên Home edition)
  - Click **Accept** terms of service
  - Click **Continue without signing in** (skip Docker account)
- Đợi Docker Desktop start: icon con cá voi ở taskbar tray sẽ chuyển từ animate → static (mất ~1-2 phút)

### Bước 5.4 — Verify Docker hoạt động

```powershell
docker --version
docker compose version
docker run --rm hello-world
```

Lệnh `hello-world` phải print:
```
Hello from Docker!
This message shows that your installation appears to be working correctly.
```

---

## ✅ Phase 6 — Chạy hệ thống Đà Nẵng (15 phút)

### Bước 6.1 — Vào project folder

```powershell
cd D:\Development\projects\public-infra-system-for-Danangcity
```

### Bước 6.2 — Chạy 1 lệnh duy nhất

```powershell
.\start.cmd
```

### Bước 6.3 — Đợi build + up (~5-15 phút lần đầu)

Script sẽ:
1. Verify Docker running
2. Tạo `.env` từ `.env.example` với SECRET_KEY auto-gen
3. Pull images: postgis, redis, minio, meilisearch, mailhog (~600MB)
4. Build images: backend (FastAPI + GDAL), ai-service, frontend Next.js
5. Wait DB ready
6. Run alembic migrations
7. Seed data Đà Nẵng (8 quận, 4 demo user, ~200 assets)

### Bước 6.4 — Khi script print "SYSTEM READY"

Mở browser → <http://localhost:3000> → đăng nhập:

| Vai trò | Email | Password |
| ------- | ----- | -------- |
| Admin | `admin@danang.gov.vn` | `Admin@123` |
| Operator | `operator@danang.gov.vn` | `Op@12345` |
| TaskForce | `tech@danang.gov.vn` | `Tech@123` |
| Citizen | `citizen@danang.gov.vn` | `User@123` |

### Bước 6.5 — Verify 11 containers up

```powershell
docker compose -f .\infra\docker-compose.yml -p danang-infra ps
```

Phải thấy 11 containers status `Up` hoặc `healthy`:

```
NAME                          STATUS
danang-infra-ai-service-1     Up
danang-infra-backend-1        Up (healthy)
danang-infra-beat-1           Up
danang-infra-db-1             Up (healthy)
danang-infra-frontend-1       Up
danang-infra-mailhog-1        Up
danang-infra-meilisearch-1    Up
danang-infra-minio-1          Up (healthy)
danang-infra-minio-init-1     Exited (0)
danang-infra-redis-1          Up (healthy)
danang-infra-worker-1         Up
```

`minio-init` Exited (0) là bình thường — nó là one-shot job tạo bucket rồi exit.

### URLs hệ thống

- **Web app**: <http://localhost:3000>
- **API docs**: <http://localhost:8000/docs>
- **AI service docs**: <http://localhost:8001/docs>
- **MinIO console**: <http://localhost:9001> (`minioadmin` / `minioadmin`)
- **MailHog**: <http://localhost:8025>
- **Meilisearch**: <http://localhost:7700>

---

## 🎮 Sử dụng hằng ngày sau khi setup xong

### Khi muốn dev (Docker mode)

```powershell
cd D:\Development\projects\public-infra-system-for-Danangcity
.\start.cmd       # khởi động hệ thống (~30 giây nếu image đã cache)
.\stop.cmd        # dừng tất cả (giữ data)
.\scripts\logs.ps1 backend    # xem log 1 service
```

### Khi muốn chuyển sang chơi Valorant

```powershell
.\scripts\game-mode.ps1
```

Script sẽ:
- Stop Docker Desktop
- Set Vanguard services về Auto (nếu còn cài Vanguard)
- HOẶC nhắc bạn mở Valorant launcher để cài lại Vanguard (nếu đã uninstall)
- Yêu cầu reboot

### Khi quay lại dev

```powershell
.\scripts\dev-mode.ps1
```

Script sẽ:
- Stop + disable Vanguard services
- Yêu cầu reboot
- Sau reboot → chạy `.\start.cmd` để dev

### Check current mode

```powershell
.\scripts\mode-status.ps1
```

Script in trạng thái hiện tại: Vanguard ON/OFF, Docker running/stopped, WSL2 status, project containers.

---

## 🛠 Troubleshooting

### Phase 2: Build Beta không tự download

**Triệu chứng**: sau khi switch Beta channel + restart, Windows Update vẫn báo "You're up to date" trên build 26200.

**Nguyên nhân**: Microsoft hold bạn lại nếu build hiện tại > build Beta latest. Hiếm khi xảy ra với build 26200 vì Beta đã ở 26220, nhưng có thể nếu bạn ở build 26200 cao hơn 26220 cụ thể.

**Fix**:
```powershell
# Force Windows Update detect lại
wuauclt /resetauthorization /detectnow

# Reset Windows Update components
net stop wuauserv
net stop cryptSvc
net stop bits
net stop msiserver
ren C:\Windows\SoftwareDistribution SoftwareDistribution.old
ren C:\Windows\System32\catroot2 catroot2.old
net start wuauserv
net start cryptSvc
net start bits
net start msiserver

# Check lại
start ms-settings:windowsupdate
```

Nếu vẫn fail → tải ISO Beta channel từ <https://www.microsoft.com/en-us/software-download/windowsinsiderpreviewISO> → mount ISO → chạy `setup.exe` → chọn **Keep personal files and apps** → đây là in-place upgrade, giữ data + apps. Mất ~30-45 phút.

### Phase 4: `wsl --install` vẫn báo Error 1168

**Triệu chứng**: dù đã update build 26220, lệnh `wsl --install --no-distribution` vẫn báo `Error 1168`.

**Nguyên nhân**: SSU (Servicing Stack Update) chưa cập nhật theo build mới.

**Fix**:
```powershell
# Force reset DISM cache
DISM /Online /Cleanup-Image /StartComponentCleanup /ResetBase
# Cài SSU mới nhất (Microsoft Update Catalog)
wuauclt /detectnow /updatenow
# Đợi 15 phút rồi thử lại wsl --install
```

### Phase 5: Docker Desktop không start (whale icon mãi animate)

**Triệu chứng**: mở Docker Desktop, icon con cá voi ở tray quay tròn không dừng.

**Nguyên nhân**: WSL2 backend chưa init xong hoặc conflict với residue Vanguard driver.

**Fix**:
```powershell
# Restart Docker service
Restart-Service com.docker.service

# Hoặc reset Docker Desktop hoàn toàn
& "C:\Program Files\Docker\Docker\Docker Desktop.exe" --reset-to-factory-defaults
```

Verify không còn Vanguard driver:
```powershell
driverquery /v | findstr -i "vgk vanguard"
# Phải trả về empty
```

Nếu vẫn thấy `vgk` driver → Vanguard chưa uninstall sạch. Reboot rồi uninstall lại từ Settings.

### Phase 6: `start.cmd` fail "port 5432 already in use"

**Triệu chứng**: container `db` không start được, log báo "port 5432 is already allocated".

**Nguyên nhân**: bạn có Postgres native chạy sẵn trên máy.

**Fix**:
```powershell
# Tìm và stop Postgres native
Get-Service | Where-Object { $_.Name -like "*postgres*" } | Stop-Service
# Hoặc đổi port DB trong .env:
notepad .\.env
# Đổi POSTGRES_PORT=5432 thành POSTGRES_PORT=5433
.\start.cmd
```

### Phase 6: container nào đó báo `unhealthy`

```powershell
.\scripts\logs.ps1 <service-name>
# Ví dụ:
.\scripts\logs.ps1 backend
.\scripts\logs.ps1 db
```

Đọc error message; thường gặp:
- DB schema chưa migrate → `docker compose -f .\infra\docker-compose.yml -p danang-infra exec backend alembic upgrade head`
- Permission denied trên MinIO → `.\scripts\reset.ps1` để xóa volume rồi `.\start.cmd` lại

---

## 📌 Sau khi hoàn thành — Kiểm tra cuối

```powershell
# 1. Windows build
Get-ComputerInfo | Select-Object OsBuildNumber

# 2. WSL2 ready
wsl --status

# 3. Docker ready
docker run --rm hello-world

# 4. Project running
cd D:\Development\projects\public-infra-system-for-Danangcity
docker compose -f .\infra\docker-compose.yml -p danang-infra ps

# 5. Login web
start http://localhost:3000
```

Nếu cả 5 bước trên work → bạn đã hoàn thành setup. Mỗi lần dev sau này chỉ cần `.\start.cmd`.

---

## 📚 Tài liệu liên quan

- `README.md` — overview project + tech stack
- `docs/architecture.md` — kiến trúc tổng thể
- `docs/runbook.md` — runbook vận hành
- `infra/docker-compose.yml` — định nghĩa 11 services
- `scripts/start.ps1` — main launcher
- `scripts/dev-mode.ps1` — switch sang Dev mode (Vanguard OFF)
- `scripts/game-mode.ps1` — switch sang Game mode (Vanguard ON)
- `scripts/mode-status.ps1` — check current mode
- `scripts/backup-pre-update.ps1` — backup trước khi update Windows
