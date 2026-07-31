# R2 Warehouse Release Publishing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish idempotent, versioned R2 releases after scheduled Supabase ETL runs.

**Architecture:** Supabase remains the production source of truth. A single publisher
downloads the latest Parquet release, queries only missing or explicitly repaired
dates, performs DuckDB upserts, uploads an immutable Parquet/CSV release, and updates
`v1/latest.json` last.

**Tech Stack:** Python 3.13, SQLAlchemy 2, PyArrow, DuckDB, boto3, PostgreSQL,
Cloudflare R2 S3 API, pytest, GitHub Actions.

## Global Constraints

- Scope is 30 Hanoi districts in the existing `analyst` schema.
- Do not partition R2 data by day or month.
- Preserve default watermark catch-up; reread is opt-in through `--force-republish`.
- Never print credentials or database URLs.
- Display operational timestamps in `Asia/Ho_Chi_Minh`.
- Use immutable releases and activate `latest.json` last.

---

### Task 1: Release contracts and configuration

**Files:**
- Create: `src/r2/__init__.py`
- Create: `src/r2/models.py`
- Create: `src/r2/config.py`
- Test: `tests/unit/test_r2_models.py`

**Interfaces:**
- Produces: `TABLE_SPECS`, `R2Config.from_env()`, `ReleaseManifest`,
  `TableManifest`, `LatestPointer`.

- [ ] Write tests for exact table keys, manifest JSON round-trip, UTC/Vietnam
  timestamps, and missing environment variables.
- [ ] Run focused tests and verify they fail because the module is missing.
- [ ] Implement immutable dataclasses and safe configuration parsing.
- [ ] Run focused tests and Ruff.

### Task 2: PostgreSQL export and DuckDB merge

**Files:**
- Create: `src/r2/exporter.py`
- Test: `tests/unit/test_r2_exporter.py`
- Modify: `pyproject.toml`
- Modify: `poetry.lock`

**Interfaces:**
- Produces: `WarehouseExporter.export_full()`,
  `WarehouseExporter.export_delta()`, `SnapshotMerger.merge()`.

- [ ] Write tests using a temporary DuckDB/Parquet fixture. Verify duplicate source
  keys replace old rows, a second merge is idempotent, and CSV headers stay stable.
- [ ] Run the focused tests and verify RED.
- [ ] Add pinned-compatible `boto3`, `duckdb`, and `pyarrow` dependencies.
- [ ] Implement streaming SQLAlchemy-to-Parquet export and DuckDB merge.
- [ ] Run focused tests and Ruff.

### Task 3: R2 release publisher and CLIs

**Files:**
- Create: `src/r2/publisher.py`
- Create: `scripts/publish_r2_release.py`
- Test: `tests/unit/test_r2_publisher.py`
- Test: `tests/unit/test_r2_cli.py`

**Interfaces:**
- Produces: `R2Publisher.publish_incremental()`, credential-safe CLI exit codes,
  and `--result-json`.

- [ ] Write fake-S3 tests proving objects upload under an immutable release prefix,
  every object is verified, and `latest.json` is written last.
- [ ] Write CLI tests for watermark mode, bounded forced repair, and safe failures.
- [ ] Run tests and verify RED.
- [ ] Implement R2 S3 client, incremental catch-up, repair, verification,
  retention, and result JSON.
- [ ] Run focused tests and Ruff.

### Task 4: Seven-job workflow and Vietnam-time summary

**Files:**
- Create: `.github/actions/setup-python-poetry/action.yml`
- Modify: `.github/workflows/etl.yml`
- Modify: `scripts/github_actions_etl_report.py`
- Test: `tests/unit/test_etl_workflow.py`
- Modify: `tests/unit/test_github_actions_etl_report.py`

**Interfaces:**
- Produces seven visible jobs and a final Vietnamese summary that includes R2 status.

- [ ] Write failing behavioral tests for workflow dependencies and Vietnam timezone.
- [ ] Run tests and verify RED.
- [ ] Split the workflow without transferring warehouse files between jobs.
- [ ] Add `publish-r2` only after the three scheduled collectors succeed.
- [ ] Render start/end/duration, ETL rows, warehouse rows and R2 release in Vietnamese.
- [ ] Run focused tests and Ruff.

### Task 5: Runbook and live verification

**Files:**
- Create: `docs/r2-reporting.md`
- Modify: `.env.example`
- Modify: `docs/etl/automation.md`
- Modify: `docs/etl/demo-runbook.md`

**Interfaces:**
- Produces repeatable R2-only retry, repair, reporting-tool connection, and rollback
  instructions.

- [ ] Document Cloudflare bucket/token/custom-domain setup without credential values.
- [ ] Confirm required environment variable names exist without printing values.
- [ ] Verify `latest.json`, all 12 data objects, hashes, row counts, and max dates.
- [ ] Run full pytest, Ruff and `git diff --check`.
