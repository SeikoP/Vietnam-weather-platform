# README Overview And Main Branch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite the root README around the platform overview and rename the repository default branch from `master` to `main` without force-pushing.

**Architecture:** Keep operational commands in the existing focused documentation and make the root README a concise project landing page. Perform the branch rename through GitHub's official branch rename API, then fast-forward the approved documentation commits to the renamed default branch and synchronize local tracking refs.

**Tech Stack:** Markdown, Git, GitHub CLI, GitHub REST API, PowerShell

## Global Constraints

- README prioritizes project purpose, architecture, data, automation, reporting outputs, repository structure, and documentation links.
- README contains no installation, seed, ETL execution, or test command blocks.
- Rename GitHub, remote, and local default branch from `master` to `main`.
- Never force-push and never discard a commit not reachable from the renamed default branch.

---

### Task 1: Rewrite The Root README

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: Current architecture documented in `docs/architecture.md`, `docs/data-model.md`, `docs/etl.md`, `docs/deployment.md`, and `docs/r2-reporting.md`.
- Produces: A concise root landing page whose documentation links remain repository-relative.

- [ ] **Step 1: Run the README acceptance check and confirm the current file fails**

Run:

```powershell
$readme = Get-Content -Raw README.md
if ($readme -match '## Bắt Đầu Nhanh|## Lệnh Thường Dùng') { exit 1 }
```

Expected: exit code `1` because the current README still emphasizes run instructions.

- [ ] **Step 2: Replace README with the approved overview content**

````markdown
# Nền Tảng Dữ Liệu Thời Tiết Hà Nội

## Tổng Quan

Nền tảng thu thập và chuẩn hóa dữ liệu thời tiết, chất lượng không khí cho 30
quận/huyện Hà Nội. Dữ liệu được lưu trong Supabase PostgreSQL, theo dõi chất lượng
qua schema giám sát và phát hành thành snapshot trên Cloudflare R2 cho các công cụ
phân tích, báo cáo.

## Kiến Trúc Dữ Liệu

```text
Open-Meteo -> ETL Python -> Supabase PostgreSQL -> Cloudflare R2 -> Reporting tools
```

Supabase là nguồn dữ liệu chuẩn. ETL chịu trách nhiệm thu thập, biến đổi, kiểm tra và
upsert; R2 là lớp phân phối chỉ đọc qua CSV/Parquet, không thay thế warehouse.

## Khả Năng Chính

- Thu thập weather daily, weather hourly và AQI hourly từ Open-Meteo.
- Chuẩn hóa dữ liệu theo quận/huyện và dimension thời gian dùng chung.
- Kiểm tra dữ liệu trước khi nạp, upsert idempotent và ghi nhận trạng thái ETL.
- Quản lý schema bằng SQLAlchemy/Alembic và tách dữ liệu phân tích khỏi monitoring.
- Phát hành release R2 có manifest, checksum và alias ổn định cho công cụ báo cáo.

## Dữ Liệu Phân Tích

Schema `analyst` tổ chức theo mô hình fact/dimension:

- `dim_district`, `dim_date`, `dim_hour` cung cấp ngữ cảnh địa lý và thời gian.
- `fact_weather_daily`, `fact_weather_hourly`, `fact_aqi_hourly` lưu các chỉ số quan sát.

Snapshot CSV/Parquet giữ cùng cấu trúc bảng để Power BI hoặc công cụ tương thích HTTP
có thể tải dữ liệu mà không truy vấn trực tiếp Supabase.

## Tự Động Hóa Và Phân Phối

GitHub Actions điều phối migration, seed, ba collector và bước publish R2 theo lịch.
Workflow chỉ làm nhiệm vụ orchestration; logic nghiệp vụ nằm trong mã nguồn ETL và R2.
Release chỉ được kích hoạt sau khi dữ liệu vượt qua kiểm tra, sau đó được xuất qua
`v1/current/analyst/` và mô tả bởi manifest phiên bản.

## Cấu Trúc Dự Án

- `src/etl/`: extract, transform, validate, load và orchestration.
- `src/database/`: model, session và Alembic migrations.
- `src/monitoring/`: structured logging và thông báo vận hành.
- `src/r2/`: export, merge, manifest, publish và verify snapshot.
- `scripts/`: seed, catch-up, báo cáo và thao tác vận hành.
- `tests/unit/`: kiểm thử ETL, database, workflow và R2.

## Tài Liệu

- [Kiến trúc hệ thống](docs/architecture.md)
- [Mô hình dữ liệu](docs/data-model.md)
- [ETL và tự động hóa](docs/etl.md)
- [Triển khai](docs/deployment.md)
- [Cloudflare R2 và công cụ báo cáo](docs/r2-reporting.md)
````

- [ ] **Step 3: Verify README content and repository-relative links**

Run:

```powershell
$readme = Get-Content -Raw README.md
if ($readme -match '## Bắt Đầu Nhanh|## Lệnh Thường Dùng|poetry run') { exit 1 }
$required = @(
  'docs/architecture.md',
  'docs/data-model.md',
  'docs/etl.md',
  'docs/deployment.md',
  'docs/r2-reporting.md'
)
foreach ($path in $required) { if (-not (Test-Path -LiteralPath $path)) { exit 1 } }
```

Expected: exit code `0` and all five linked files exist.

- [ ] **Step 4: Check the documentation diff**

Run: `git diff --check; git diff -- README.md`

Expected: no whitespace errors; diff only replaces run-oriented copy with the approved overview.

- [ ] **Step 5: Commit the README**

```powershell
git add README.md
git commit -m "Rewrite README around platform overview"
```

### Task 2: Rename The Default Branch And Push

**Files:**
- No repository file changes.

**Interfaces:**
- Consumes: GitHub repository `SeikoP/Vietnam-weather-platform`, current default branch `master`, and the commits on `agent/readme-main-rename`.
- Produces: GitHub default branch, remote branch, local branch, and `origin/HEAD` consistently named `main`.

- [ ] **Step 1: Verify rename and fast-forward preconditions**

Run:

```powershell
gh repo view SeikoP/Vietnam-weather-platform --json defaultBranchRef
git ls-remote --heads origin master main
git merge-base --is-ancestor origin/master HEAD
git merge-base --is-ancestor master origin/master
```

Expected: default is `master`, remote `main` is absent, and both ancestry checks return `0`.

- [ ] **Step 2: Rename the GitHub branch through the official API**

Run:

```powershell
gh api --method POST repos/SeikoP/Vietnam-weather-platform/branches/master/rename -f new_name=main
```

Expected: response field `name` equals `main`; GitHub updates the default branch.

- [ ] **Step 3: Refresh remote refs and push the documentation commits**

Run:

```powershell
git fetch origin --prune
git remote set-head origin -a
git push origin HEAD:main
```

Expected: a fast-forward update of `origin/main`; no force option is used.

- [ ] **Step 4: Synchronize the local default branch**

Run:

```powershell
git branch -m master main
git fetch origin --prune
git branch -f main origin/main
git branch --set-upstream-to=origin/main main
git switch main
git branch -d agent/readme-main-rename
```

Expected: current local branch is `main`, tracking `origin/main`; the temporary branch deletes only after Git sees it as merged.

- [ ] **Step 5: Verify the final repository state**

Run:

```powershell
git status -sb
git remote show origin
git ls-remote --heads origin master main
gh repo view SeikoP/Vietnam-weather-platform --json defaultBranchRef
git rev-parse HEAD
git rev-parse origin/main
```

Expected: clean `main...origin/main`, GitHub and `origin/HEAD` use `main`, remote `master` is absent, and local/remote SHA values match.
