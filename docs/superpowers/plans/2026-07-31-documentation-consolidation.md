# Documentation Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate the current project documentation into six accurate Vietnamese files and stop tracking the local codebase-memory artifacts.

**Architecture:** Treat the code, configuration, workflow, CLI help, and tests as authoritative. Keep one clear responsibility per document, link instead of duplicating details, and preserve `docs/superpowers/*` as historical records.

**Tech Stack:** Markdown, Python 3.13, Poetry, FastAPI, SQLAlchemy, Alembic, PostgreSQL/Supabase, GitHub Actions, Cloudflare R2, Power BI, Docker Compose.

## Global Constraints

- Keep documentation concise, complete, and written in Vietnamese.
- Keep commands, paths, identifiers, environment variables, and error text in English.
- Do not edit `.env`, `AGENTS.md`, source code, database schema, or workflows.
- Preserve `.codebase-memory/*` on disk while removing the directory from Git tracking.
- Keep `--lookback-days 0` semantics unchanged and explicit.
- Do not claim live Supabase, R2, GitHub Actions, Power BI, or Docker verification unless it is actually run.

---

### Task 1: Stop Tracking Local Codebase Memory

**Files:**
- Modify: `.gitignore`
- Untrack: `.codebase-memory/.gitattributes`
- Untrack: `.codebase-memory/artifact.json`
- Untrack: `.codebase-memory/graph.db.zst`

**Interfaces:**
- Consumes: current Git index and local `.codebase-memory/` directory.
- Produces: ignored local graph artifacts that remain available to MCP tooling.

- [ ] **Step 1: Add the directory ignore rule**

Add this repository-root rule to `.gitignore`:

```gitignore
/.codebase-memory/
```

- [ ] **Step 2: Remove only the tracked copies from the Git index**

Run:

```powershell
git rm --cached -- .codebase-memory/.gitattributes .codebase-memory/artifact.json .codebase-memory/graph.db.zst
```

- [ ] **Step 3: Verify the local files remain and Git ignores them**

Run:

```powershell
Test-Path .codebase-memory\artifact.json
Test-Path .codebase-memory\graph.db.zst
git check-ignore -v .codebase-memory\artifact.json
git ls-files .codebase-memory
```

Expected: both `Test-Path` calls return `True`, `git check-ignore` reports `.gitignore`, and `git ls-files` returns no paths.

- [ ] **Step 4: Commit the tracking change separately**

```powershell
git add -- .gitignore
git commit -m "Stop tracking codebase memory artifacts"
```

### Task 2: Rewrite the Project Entry Point

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: `pyproject.toml`, `.env.example`, `Dockerfile`, and the five consolidated guides.
- Produces: the only onboarding entry point and documentation index.

- [ ] **Step 1: Replace the README with the approved concise structure**

Use these sections in this order:

```markdown
# Nền Tảng Dữ Liệu Thời Tiết Hà Nội
## Luồng Dữ Liệu
## Thành Phần Chính
## Bắt Đầu Nhanh
## Lệnh Thường Dùng
## Tài Liệu
```

State that the platform covers 30 Hanoi districts, uses six `analyst` tables, exposes FastAPI, publishes R2 CSV/Parquet releases, and serves Power BI from R2. Include the exact install, migration, seed, API, ETL, test, and Ruff commands. Link only the five active files in `docs/`.

- [ ] **Step 2: Check every README command against project configuration**

Run:

```powershell
rg -n "vwdp-etl|vwdp-api|alembic|pytest|ruff" README.md pyproject.toml
```

Expected: every documented command maps to a script or dependency in `pyproject.toml`.

### Task 3: Consolidate Architecture and Data Model

**Files:**
- Create: `docs/architecture.md`
- Create: `docs/data-model.md`

**Interfaces:**
- Consumes: `src/api/`, `src/etl/`, `src/r2/`, `src/sync/`, `src/database/models.py`, and the Alembic chain.
- Produces: one system map and one authoritative warehouse reference.

- [ ] **Step 1: Write `docs/architecture.md`**

Use these sections:

```markdown
# Kiến Trúc Hệ Thống
## Luồng Chính
## Thành Phần
## Cấu Trúc Mã Nguồn
## API
## Ranh Giới Vận Hành
```

The diagram must show `Open-Meteo -> ETL -> Supabase PostgreSQL`, Supabase feeding FastAPI and R2, R2 feeding Power BI, and optional Supabase-to-local PostgreSQL sync. List the nine business GET routes plus `/health`. Explain that the API middleware emits structured logs but does not persist `monitoring.api_requests` rows.

- [ ] **Step 2: Write `docs/data-model.md`**

Use these sections:

```markdown
# Mô Hình Dữ Liệu
## Schema `analyst`
## Quan Hệ
## Schema `monitoring`
## Nguyên Tắc Thiết Kế
## Kiểm Tra Sau Migration
```

Document the six analyst tables and four monitoring tables. State the exact daily and hourly composite keys, route hourly/AQI through `dim_hour.hour_key`, and avoid point-in-time row counts or stale min/max dates.

- [ ] **Step 3: Validate table and route inventories from Python metadata**

Run:

```powershell
.\.venv\Scripts\python.exe -c "from src.database.models import Base; [print(f'{t.schema}.{t.name}') for t in Base.metadata.sorted_tables]"
.\.venv\Scripts\python.exe -c "import os; os.environ['DATABASE_URL']='postgresql+psycopg://test:test@localhost/test'; from src.api.app import create_app; [print(r.path) for r in create_app().routes if hasattr(r, 'methods')]"
```

Expected: ten database tables and the documented FastAPI routes are present.

### Task 4: Consolidate ETL and Automation

**Files:**
- Create: `docs/etl.md`

**Interfaces:**
- Consumes: `src/etl/cli.py`, `.github/workflows/etl.yml`, `scripts/run_manual_catchup.ps1`, and reporting scripts.
- Produces: the authoritative CLI, scheduling, demo, and recovery guide.

- [ ] **Step 1: Write the ETL guide**

Use these sections:

```markdown
# ETL Và Tự Động Hóa
## Luồng Xử Lý
## Run Type Và Khoảng Ngày
## Chạy Local
## GitHub Actions
## Demo
## Manual Catch-Up
## Bằng Chứng Sau Khi Chạy
```

Document all nine run types. State that historical defaults to `2023-06-01` through yesterday, incremental defaults to yesterday only, and forecast defaults to yesterday unless both explicit dates are passed. Use the six exact Vietnamese preset labels from the workflow. State that scheduled runs execute all three collectors and publish R2; manual runs execute only the selected collector and do not publish R2.

- [ ] **Step 2: Document the safe catch-up boundary**

Include this command and explain that R2 publishing occurs only with `-RunType all` unless `-SkipR2` is supplied:

```powershell
.\scripts\run_manual_catchup.ps1 -StartDate 2026-07-28 -EndDate 2026-07-28
```

- [ ] **Step 3: Compare documented flags and workflow labels**

Run:

```powershell
.\.venv\Scripts\python.exe -c "from src.etl.cli import main; raise SystemExit(main())" --help
rg -n "Demo daily|Demo hourly|Demo AQI|Chạy thật" .github/workflows/etl.yml docs/etl.md
```

Expected: every documented flag and preset exists in current code/configuration.

### Task 5: Consolidate Deployment and Local Recovery

**Files:**
- Create: `docs/deployment.md`

**Interfaces:**
- Consumes: `.env.example`, `ops/local/compose.yml`, `Dockerfile`, Alembic, seed scripts, and cloud-to-local sync code.
- Produces: one setup, deployment, Docker, and sync runbook.

- [ ] **Step 1: Write deployment and configuration guidance**

Use these sections:

```markdown
# Triển Khai Và Đồng Bộ Local
## Yêu Cầu
## Cấu Hình
## Khởi Tạo Database
## Chạy API
## GitHub Actions
## PostgreSQL Docker Local
## Đồng Bộ Supabase Về Local
## An Toàn Và Xử Lý Lỗi
```

Describe the Python 3.13/Poetry stack, Session Pooler port `5432` used by the checked-in example, migrations, both seed scripts, API CLI, GitHub secrets/variables, and optional local PostgreSQL at `localhost:5433`.

- [ ] **Step 2: Preserve the sync semantics exactly**

Document required `CLOUD_DATABASE_URL` and `LOCAL_DATABASE_URL`, automatic local migrations, read-only cloud transaction, per-table local transaction, default `--lookback-days 0`, positive reread windows, `--batch-size`, and high-egress `--full`.

- [ ] **Step 3: Compare documented environment variables and flags**

Run:

```powershell
rg -n "^[A-Z][A-Z0-9_]*=" .env.example
.\.venv\Scripts\python.exe scripts\sync_cloud_to_local.py --help
```

Expected: every required documented variable and flag appears in current configuration/code.

### Task 6: Consolidate R2 and Power BI

**Files:**
- Create: `docs/r2-powerbi.md`

**Interfaces:**
- Consumes: `src/r2/`, R2 scripts, workflow R2 job, and the current warehouse model.
- Produces: one publisher, recovery, verification, and reporting guide.

- [ ] **Step 1: Write the R2 lifecycle**

Use these sections:

```markdown
# Cloudflare R2 Và Power BI
## Luồng Release
## Cấu Hình
## Bootstrap Lịch Sử
## Publish Hằng Ngày
## Repair Và Verify
## Retention Và Rollback
## Power BI
## Kiểm Tra
```

Document six Parquet/CSV table pairs under immutable release prefixes, six stable CSV aliases under `v1/current/analyst/`, `v1/latest.json`, SHA-256/size verification, and retention of the active plus two eligible previous releases. State that no rollback CLI exists and changing only `latest.json` is insufficient because Power BI reads current aliases.

- [ ] **Step 2: Correct the Power BI relationships**

Document these relationships exactly:

```text
fact_weather_daily.date_key -> dim_date.date_key
fact_weather_hourly.hour_key -> dim_hour.hour_key
fact_aqi_hourly.hour_key -> dim_hour.hour_key
dim_hour.date_key -> dim_date.date_key
fact_*.district_id -> dim_district.district_id
```

Use `R2BaseUrl` and `LoadR2Table` once, and avoid embedding the current `r2.dev` URL as the production recommendation.

- [ ] **Step 3: Compare documented publisher flags**

Run:

```powershell
.\.venv\Scripts\python.exe scripts\bootstrap_r2_history.py --help
.\.venv\Scripts\python.exe scripts\publish_r2_release.py --help
```

Expected: bootstrap, publish, repair, and verify commands use only supported flags.

### Task 7: Remove Superseded Guides and Repair References

**Files:**
- Delete: `docs/architecture/overview.md`
- Delete: `docs/database/data-cleanup.md`
- Delete: `docs/database/warehouse-design.md`
- Delete: `docs/deployment/guide.md`
- Delete: `docs/etl/automation.md`
- Delete: `docs/etl/demo-runbook.md`
- Delete: `docs/etl/flow.md`
- Delete: `docs/local-cloud-sync.md`
- Delete: `docs/powerbi/guide.md`
- Delete: `docs/r2-snapshots.md`

**Interfaces:**
- Consumes: completed consolidated guides.
- Produces: exactly six active documentation entry points without duplicate instructions.

- [ ] **Step 1: Confirm every old topic exists in the consolidated files**

Check architecture, schema, cleanup rationale, deployment, ETL flow, automation, demo, local sync, R2, and Power BI sections before deleting the old files.

- [ ] **Step 2: Delete the ten superseded files**

Use scoped patches for the exact paths listed above. Remove empty topic directories only if no untracked files remain inside them.

- [ ] **Step 3: Find obsolete references**

Run:

```powershell
rg -n "docs/(architecture/overview|database/(data-cleanup|warehouse-design)|deployment/guide|etl/(flow|automation|demo-runbook)|local-cloud-sync|r2-snapshots|powerbi/guide)\.md" README.md docs --glob "!docs/superpowers/**"
```

Expected: no matches outside the preserved historical plans/specs.

### Task 8: Verify and Commit the Consolidated Documentation

**Files:**
- Verify: `README.md`
- Verify: `docs/architecture.md`
- Verify: `docs/data-model.md`
- Verify: `docs/etl.md`
- Verify: `docs/deployment.md`
- Verify: `docs/r2-powerbi.md`

**Interfaces:**
- Consumes: all consolidated documentation and current repository state.
- Produces: a tested, linted, link-checked documentation commit.

- [ ] **Step 1: Run code verification required after repository changes**

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
```

Expected: all tests and Ruff pass.

- [ ] **Step 2: Validate Markdown links and active file count**

Run a read-only Python link checker over `README.md` and the five active `docs/*.md` files. Exclude `docs/superpowers/*` because those files intentionally preserve historical paths. Confirm exactly five active Markdown files exist directly under `docs/`.

- [ ] **Step 3: Check whitespace and final scope**

```powershell
git diff --check
git status --short
git diff --stat
```

Expected: no whitespace errors; only documentation changes plus the intentional `.gitignore` and codebase-memory index removals are present.

- [ ] **Step 4: Commit the documentation consolidation**

```powershell
git add -- README.md docs
git commit -m "Consolidate project documentation"
```
