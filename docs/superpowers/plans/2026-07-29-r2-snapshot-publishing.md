# R2 Snapshot Publishing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bootstrap the complete local weather warehouse into private Cloudflare R2 snapshots, publish new scheduled data incrementally, and present the GitHub Actions pipeline as a detailed multi-job Vietnamese demo.

**Architecture:** Supabase remains the system of record and PostgreSQL Docker remains the manual recovery mirror. A focused snapshot package streams model-aligned CSV partitions, uploads immutable objects to R2, and publishes the active manifest last. GitHub Actions separates validation, database preparation, three ETL modes, R2 publication, and final reporting into visible jobs.

**Tech Stack:** Python 3.13, SQLAlchemy 2.x, psycopg 3, boto3, Pydantic, pytest, PyYAML, GitHub Actions, PostgreSQL 17, Cloudflare R2 S3-compatible API.

## Global Constraints

- Keep Supabase PostgreSQL as the source of truth; R2 is read-only distribution.
- Keep the R2 bucket private during bootstrap.
- Store canonical timestamps in UTC and display workflow timestamps using `Asia/Ho_Chi_Minh`.
- Display time as `DD/MM/YYYY HH:mm:ss (UTC+7)`.
- Upload data objects first and update `v1/manifest.json` last.
- Never put database URLs, access keys, signed URLs, or secrets in logs, manifests, artifacts, or Git diffs.
- Preserve current manual recovery behavior and do not delete Supabase or local PostgreSQL data.
- Use Python 3.13, Black line length 100, and the existing Ruff rules.
- Run tests and Ruff after every code task.
- Use explicit Git paths and imperative English commit subjects of at most 72 characters.

---

## File Structure

- `src/export/__init__.py`: public snapshot interfaces.
- `src/export/r2_snapshot.py`: table specifications, CSV partition export, hashing, manifest models, R2 client creation, and manifest-first safety rules.
- `scripts/bootstrap_r2_history.py`: one-time local PostgreSQL bootstrap CLI.
- `scripts/publish_r2_daily.py`: watermark-aware Supabase daily publisher CLI.
- `scripts/github_actions_job_report.py`: per-job JSON metadata writer.
- `scripts/github_actions_etl_report.py`: final Vietnamese summary, ETL/warehouse queries, R2 summary, and Discord message.
- `.github/actions/setup-python-poetry/action.yml`: shared GitHub Actions Python/Poetry setup.
- `.github/workflows/etl.yml`: seven-job dependency graph.
- `tests/unit/test_r2_snapshot.py`: snapshot, partition, manifest, and uploader unit tests.
- `tests/unit/test_r2_cli.py`: CLI configuration and orchestration tests.
- `tests/unit/test_github_actions_job_report.py`: job metadata and Vietnam-time tests.
- `tests/unit/test_github_actions_etl_report.py`: detailed final Markdown tests.
- `tests/unit/test_etl_workflow.py`: workflow graph and secret-wiring tests.
- `docs/r2-snapshots.md`: concise Vietnamese operator runbook.
- `pyproject.toml` and `poetry.lock`: boto3 runtime and PyYAML development dependencies.

---

### Task 1: Define R2 configuration and snapshot contracts

**Files:**
- Create: `src/export/__init__.py`
- Create: `src/export/r2_snapshot.py`
- Create: `tests/unit/test_r2_snapshot.py`
- Modify: `pyproject.toml`
- Modify: `poetry.lock`

**Interfaces:**
- Consumes: SQLAlchemy tables from `src.database.models`.
- Produces: `R2Config`, `SnapshotTableSpec`, `SnapshotObject`, `SnapshotManifest`, `TABLE_SPECS`, `sha256_file()`, and `month_object_key()`.

- [ ] **Step 1: Add the dependencies**

Run:

```powershell
poetry add boto3
poetry add --group dev pyyaml
```

Expected: `pyproject.toml` contains `boto3` under runtime dependencies and `pyyaml` under development dependencies; `poetry.lock` is refreshed.

- [ ] **Step 2: Write failing contract tests**

Create tests covering exact environment names and deterministic object keys:

```python
def test_r2_config_requires_all_values() -> None:
    with pytest.raises(ValueError, match="R2_ACCOUNT_ID"):
        R2Config.from_environ({})


def test_month_object_key_uses_versioned_hive_partition() -> None:
    assert (
        month_object_key("fact_weather_hourly", date(2026, 7, 1))
        == "v1/history/fact_weather_hourly/year=2026/month=07/data.csv"
    )


def test_manifest_never_serializes_credentials(tmp_path: Path) -> None:
    manifest = SnapshotManifest(
        schema_version=1,
        generated_at_utc=datetime(2026, 7, 29, 15, 15, tzinfo=UTC),
        source="postgresql-docker",
        status="complete",
        min_date=date(2023, 6, 1),
        max_date=date(2026, 7, 28),
        objects=[],
    )
    payload = manifest.to_json()
    assert "secret" not in payload.lower()
    assert "access_key" not in payload.lower()
```

- [ ] **Step 3: Run the tests to verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_r2_snapshot.py -v
```

Expected: FAIL because `src.export.r2_snapshot` does not exist.

- [ ] **Step 4: Implement the immutable contracts**

Implement:

```python
@dataclass(frozen=True)
class R2Config:
    account_id: str
    access_key_id: str
    secret_access_key: str
    bucket_name: str

    @property
    def endpoint_url(self) -> str:
        return f"https://{self.account_id}.r2.cloudflarestorage.com"

    @classmethod
    def from_environ(cls, environ: Mapping[str, str]) -> "R2Config":
        names = (
            "R2_ACCOUNT_ID",
            "R2_ACCESS_KEY_ID",
            "R2_SECRET_ACCESS_KEY",
            "R2_BUCKET_NAME",
        )
        values = {name: environ.get(name, "").strip() for name in names}
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise ValueError(f"Missing R2 configuration: {', '.join(missing)}")
        return cls(
            account_id=values["R2_ACCOUNT_ID"],
            access_key_id=values["R2_ACCESS_KEY_ID"],
            secret_access_key=values["R2_SECRET_ACCESS_KEY"],
            bucket_name=values["R2_BUCKET_NAME"],
        )
```

Define `TABLE_SPECS` for the six `analyst` tables with these conflict keys and partition columns:

```text
dim_district: district_id, unpartitioned
dim_date: date_key, unpartitioned
dim_hour: hour_key, partition by observed_date
fact_weather_daily: district_id + date_key, partition by observed_date
fact_weather_hourly: district_id + hour_key, join dim_hour and partition by observed_date
fact_aqi_hourly: district_id + hour_key, join dim_hour and partition by observed_date
```

- [ ] **Step 5: Run focused verification**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_r2_snapshot.py -v
.\.venv\Scripts\python.exe -m ruff check src/export tests/unit/test_r2_snapshot.py
```

Expected: PASS with no Ruff findings.

- [ ] **Step 6: Commit the contracts**

```powershell
git add -- pyproject.toml poetry.lock src/export/__init__.py src/export/r2_snapshot.py tests/unit/test_r2_snapshot.py
git commit -m "Define R2 snapshot contracts"
```

---

### Task 2: Stream monthly CSV partitions and build the manifest

**Files:**
- Modify: `src/export/r2_snapshot.py`
- Modify: `tests/unit/test_r2_snapshot.py`

**Interfaces:**
- Consumes: `TABLE_SPECS` and a SQLAlchemy `Engine`.
- Produces: `HistoryExporter.export(output_root: Path, generated_at: datetime) -> SnapshotManifest`.

- [ ] **Step 1: Write failing export tests**

Add tests using a recording connection that yields rows in bounded partitions:

```python
def test_history_exporter_writes_stable_csv_and_checksum(export_harness, tmp_path) -> None:
    manifest = export_harness.exporter.export(
        tmp_path,
        generated_at=datetime(2026, 7, 29, 15, 15, tzinfo=UTC),
    )
    daily = next(obj for obj in manifest.objects if obj.table_name == "fact_weather_daily")
    assert daily.object_key.endswith("year=2026/month=07/data.csv")
    assert daily.row_count == 2
    assert len(daily.sha256) == 64
    assert (tmp_path / daily.relative_path).read_text(encoding="utf-8").splitlines()[0] == (
        "district_id,date_key,observed_date,temperature_2m_mean"
    )


def test_exporter_rejects_mismatched_fact_max_dates(export_harness, tmp_path) -> None:
    export_harness.fact_max_dates = {
        "fact_weather_daily": date(2026, 7, 28),
        "fact_weather_hourly": date(2026, 7, 27),
        "fact_aqi_hourly": date(2026, 7, 28),
    }
    with pytest.raises(ValueError, match="Fact tables do not share the same max date"):
        export_harness.exporter.export(tmp_path, generated_at=export_harness.now)
```

- [ ] **Step 2: Run the tests to verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_r2_snapshot.py -k "exporter" -v
```

Expected: FAIL because `HistoryExporter` is missing.

- [ ] **Step 3: Implement streaming export**

Implement `HistoryExporter` with these rules:

1. Query min/max dates before writing.
2. Reject differing max dates across the three fact tables.
3. Export dimensions first.
4. Iterate calendar months from warehouse minimum to maximum date.
5. Execute server-side streaming queries with `stream_results=True`.
6. Write UTF-8 CSV with `newline=""`, stable model column order, ISO dates/timestamps, and empty strings for nulls.
7. Update SHA-256 and row count while writing each file.
8. Exclude zero-row partitions from the manifest.
9. Write the local versioned manifest and active manifest only after every object succeeds.

Use batches of 5,000 rows by default; never call `.all()` for fact exports.

- [ ] **Step 4: Run tests and Ruff**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_r2_snapshot.py -v
.\.venv\Scripts\python.exe -m ruff check src/export tests/unit/test_r2_snapshot.py
```

Expected: PASS.

- [ ] **Step 5: Commit the exporter**

```powershell
git add -- src/export/r2_snapshot.py tests/unit/test_r2_snapshot.py
git commit -m "Export monthly warehouse snapshots"
```

---

### Task 3: Upload snapshots safely and add the bootstrap CLI

**Files:**
- Modify: `src/export/r2_snapshot.py`
- Create: `scripts/bootstrap_r2_history.py`
- Create: `tests/unit/test_r2_cli.py`
- Modify: `tests/unit/test_r2_snapshot.py`

**Interfaces:**
- Consumes: `R2Config`, `SnapshotManifest`, and exported local paths.
- Produces: `create_r2_client(config)`, `R2Publisher.verify_bucket()`, `R2Publisher.publish()`, and bootstrap CLI exit codes.

- [ ] **Step 1: Write failing upload-order tests**

```python
def test_publisher_uploads_active_manifest_last(fake_s3, snapshot_fixture, tmp_path) -> None:
    publisher = R2Publisher(fake_s3, "vwdp-snapshots")
    publisher.publish(snapshot_fixture.manifest, tmp_path)
    keys = [call["Key"] for call in fake_s3.put_calls]
    assert keys[-1] == "v1/manifest.json"
    assert keys[-2].startswith("v1/manifests/bootstrap-")


def test_verify_bucket_uses_head_bucket(fake_s3) -> None:
    R2Publisher(fake_s3, "vwdp-snapshots").verify_bucket()
    assert fake_s3.head_bucket_calls == [{"Bucket": "vwdp-snapshots"}]
```

- [ ] **Step 2: Write failing CLI tests**

```python
def test_bootstrap_requires_local_database_url(monkeypatch) -> None:
    monkeypatch.delenv("LOCAL_DATABASE_URL", raising=False)
    assert main([]) == 1


def test_bootstrap_disposes_engine_and_removes_temp_directory(bootstrap_harness) -> None:
    assert bootstrap_harness.run() == 0
    assert bootstrap_harness.engine.disposed
    assert not bootstrap_harness.temp_directory.exists()
```

- [ ] **Step 3: Run tests to verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_r2_snapshot.py tests/unit/test_r2_cli.py -k "publisher or bootstrap" -v
```

Expected: FAIL because publisher and CLI are missing.

- [ ] **Step 4: Implement the R2 publisher**

Create the boto3 client with:

```python
boto3.client(
    service_name="s3",
    endpoint_url=config.endpoint_url,
    aws_access_key_id=config.access_key_id,
    aws_secret_access_key=config.secret_access_key,
    region_name="auto",
)
```

Upload CSV objects with `ContentType="text/csv; charset=utf-8"` and manifests with
`ContentType="application/json"`. Use immutable versioned object keys. Upload the
timestamped manifest followed by `v1/manifest.json`. Do not catch an exception unless
the CLI can add a credential-safe error category and return exit code 1.

- [ ] **Step 5: Implement the bootstrap CLI**

The CLI must:

1. Parse `--batch-size` with default `5000`.
2. Parse `--verify-only`; this mode reads the active manifest and checks every object
   with `head_object` without exporting or uploading.
3. Require `LOCAL_DATABASE_URL` in bootstrap mode and all four R2 variables in both
   modes.
4. Create a task-specific `TemporaryDirectory`.
5. Verify the bucket before querying PostgreSQL.
6. Export, upload, and print only table name, partition count, rows, bytes, min/max date, and manifest key.
7. Dispose the engine in `finally`.
8. Never print exception messages that can contain a URL; print only exception type and safe stage.

- [ ] **Step 6: Run focused verification**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_r2_snapshot.py tests/unit/test_r2_cli.py -v
.\.venv\Scripts\python.exe -m ruff check src/export scripts/bootstrap_r2_history.py tests/unit/test_r2_snapshot.py tests/unit/test_r2_cli.py
```

Expected: PASS.

- [ ] **Step 7: Commit the uploader and CLI**

```powershell
git add -- src/export/r2_snapshot.py scripts/bootstrap_r2_history.py tests/unit/test_r2_snapshot.py tests/unit/test_r2_cli.py
git commit -m "Upload warehouse history to R2"
```

---

### Task 4: Provision and validate the private R2 bootstrap

**Files:**
- Create: `docs/r2-snapshots.md`

**Interfaces:**
- Consumes: an authenticated Cloudflare Dashboard session, local `.env` values supplied by the user, and `vwdp-postgres`.
- Produces: private bucket `vwdp-snapshots`, a scoped R2 credential pair, and a verified `v1/manifest.json`.

- [ ] **Step 1: Create the private bucket**

In Cloudflare Dashboard:

```text
Storage & databases -> R2 -> Overview -> Create bucket
Name: vwdp-snapshots
Location: Automatic
Storage class: Standard
Public access: Disabled
```

Expected: bucket details show private access.

- [ ] **Step 2: Create scoped S3 credentials**

Create an R2 Account API token with:

```text
Permission: Object Read & Write
Scope: vwdp-snapshots only
```

The user stores the displayed Account ID, Access Key ID, and Secret Access Key in the
local `.env`. Do not copy credential values into chat, terminal output, or repository
files.

- [ ] **Step 3: Verify local warehouse parity**

Run:

```powershell
docker exec vwdp-postgres psql -U vwdp -d vwdp -X -v ON_ERROR_STOP=1 -c "
SELECT 'daily' AS dataset, count(*) AS rows, min(observed_date), max(observed_date)
FROM analyst.fact_weather_daily
UNION ALL
SELECT 'hourly', count(*), min(h.observed_date), max(h.observed_date)
FROM analyst.fact_weather_hourly f JOIN analyst.dim_hour h USING (hour_key)
UNION ALL
SELECT 'aqi', count(*), min(h.observed_date), max(h.observed_date)
FROM analyst.fact_aqi_hourly f JOIN analyst.dim_hour h USING (hour_key);
"
```

Expected: all three datasets have the same maximum date.

- [ ] **Step 4: Run the live bootstrap**

Run from the user's credential-bearing terminal:

```powershell
.\.venv\Scripts\python.exe -m dotenv run -- `
  .\.venv\Scripts\python.exe scripts\bootstrap_r2_history.py
```

Expected: exit code 0 and a credential-safe summary for all six tables.

- [ ] **Step 5: Verify R2 objects without rewriting them**

Run the bootstrap CLI in verification mode:

```powershell
.\.venv\Scripts\python.exe -m dotenv run -- `
  .\.venv\Scripts\python.exe scripts\bootstrap_r2_history.py --verify-only
```

Expected: `v1/manifest.json` is complete; every object exists and matches row count,
byte size, and SHA-256 metadata.

- [ ] **Step 6: Write the Vietnamese runbook**

Document:

- safe environment variable names;
- cloud-to-local sync command;
- bootstrap and verify-only commands;
- expected object layout;
- row-count SQL;
- retry behavior;
- prohibition on `--full` cloud sync unless explicitly accepted;
- no public bucket requirement during bootstrap.

- [ ] **Step 7: Commit the runbook**

```powershell
git add -- docs/r2-snapshots.md
git commit -m "Document R2 snapshot operations"
```

---

### Task 5: Publish only missing daily data

**Files:**
- Modify: `src/export/r2_snapshot.py`
- Create: `scripts/publish_r2_daily.py`
- Modify: `tests/unit/test_r2_snapshot.py`
- Modify: `tests/unit/test_r2_cli.py`

**Interfaces:**
- Consumes: active R2 manifest watermark and Supabase `DATABASE_URL`.
- Produces: `DailyPublisher.publish_missing(end_date: date) -> SnapshotManifest` and daily immutable objects.

- [ ] **Step 1: Write failing watermark tests**

```python
def test_daily_publisher_exports_only_dates_after_watermark(daily_harness) -> None:
    daily_harness.active_manifest.max_date = date(2026, 7, 27)
    result = daily_harness.publisher.publish_missing(date(2026, 7, 29))
    assert daily_harness.exported_dates == [date(2026, 7, 28), date(2026, 7, 29)]
    assert result.max_date == date(2026, 7, 29)


def test_daily_publisher_does_nothing_when_manifest_is_current(daily_harness) -> None:
    daily_harness.active_manifest.max_date = date(2026, 7, 29)
    result = daily_harness.publisher.publish_missing(date(2026, 7, 29))
    assert daily_harness.exported_dates == []
    assert result is daily_harness.active_manifest
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_r2_snapshot.py -k "daily_publisher" -v
```

Expected: FAIL because `DailyPublisher` is missing.

- [ ] **Step 3: Implement daily object keys and catch-up**

Use keys:

```text
v1/daily/fact_weather_daily/date=2026-07-29/data.csv
v1/daily/fact_weather_hourly/date=2026-07-29/data.csv
v1/daily/fact_aqi_hourly/date=2026-07-29/data.csv
v1/daily/dim_hour/date=2026-07-29/data.csv
```

Refresh `dim_district.csv` and `dim_date.csv` only when their checksum changes. Export
dates from `manifest.max_date + 1` through the requested end date. Query only those
dates from Supabase. Publish a new timestamped manifest and update the active manifest
last.

- [ ] **Step 4: Implement the daily CLI**

CLI rules:

- default end date is yesterday in `Asia/Ho_Chi_Minh`;
- optional `--start-date` and `--end-date` force a bounded republish;
- normal mode refuses dates earlier than or equal to the watermark;
- `--force-republish` is required to replace an existing daily date;
- output contains dates, rows, bytes, and manifest key only.

- [ ] **Step 5: Run focused verification**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_r2_snapshot.py tests/unit/test_r2_cli.py -v
.\.venv\Scripts\python.exe -m ruff check src/export scripts/publish_r2_daily.py tests/unit/test_r2_snapshot.py tests/unit/test_r2_cli.py
```

Expected: PASS.

- [ ] **Step 6: Commit the daily publisher**

```powershell
git add -- src/export/r2_snapshot.py scripts/publish_r2_daily.py tests/unit/test_r2_snapshot.py tests/unit/test_r2_cli.py
git commit -m "Publish missing daily snapshots to R2"
```

---

### Task 6: Build per-job reports and Vietnam-time summary

**Files:**
- Create: `scripts/github_actions_job_report.py`
- Create: `tests/unit/test_github_actions_job_report.py`
- Modify: `scripts/github_actions_etl_report.py`
- Modify: `tests/unit/test_github_actions_etl_report.py`

**Interfaces:**
- Consumes: GitHub job identifiers, UTC timestamps, `monitoring.etl_runs`, downloaded job JSON files, and optional R2 publish result JSON.
- Produces: one JSON artifact per job and a detailed Vietnamese `GITHUB_STEP_SUMMARY`.

- [ ] **Step 1: Write failing Vietnam-time tests**

```python
def test_display_dt_uses_ho_chi_minh_timezone() -> None:
    value = datetime(2026, 7, 29, 18, 0, tzinfo=UTC)
    assert _display_dt(value) == "30/07/2026 01:00:00 (UTC+7)"


def test_duration_uses_utc_instants() -> None:
    started = datetime(2026, 7, 29, 18, 0, tzinfo=UTC)
    finished = datetime(2026, 7, 29, 18, 1, 35, tzinfo=UTC)
    assert duration_seconds(started, finished) == 95
```

- [ ] **Step 2: Write failing detailed Markdown tests**

Assert the final Markdown contains:

```text
# Báo cáo ETL thời tiết hằng ngày
Giờ Việt Nam
| Bước | Trạng thái | Bắt đầu | Kết thúc | Thời lượng |
| Run type | ETL run ID | Dòng upsert | Bỏ qua | Từ ngày | Đến ngày |
| Bucket | Manifest | Objects | Bytes | Watermark |
18:00 UTC
01:00 ngày hôm sau (UTC+7)
```

Also assert that database URLs, access keys, and exception connection strings are
redacted.

- [ ] **Step 3: Run tests to verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_github_actions_job_report.py tests/unit/test_github_actions_etl_report.py -v
```

Expected: FAIL because job report functions and Vietnamese rendering are missing.

- [ ] **Step 4: Implement job metadata JSON**

Define:

```python
@dataclass(frozen=True)
class JobReport:
    job_id: str
    display_name: str
    status: str
    started_at_utc: datetime | None
    finished_at_utc: datetime | None
    duration_seconds: int | None
    run_type: str | None = None
    etl_run_id: int | None = None
    rows_upserted: int | None = None
    rows_skipped: int | None = None
    min_date: str | None = None
    max_date: str | None = None
    safe_error: str | None = None
```

Write UTF-8 JSON to `job-reports/{job_id}.json`. Redact URI userinfo and query strings
before serializing errors.

- [ ] **Step 5: Refactor final summary**

Change timezone from `Asia/Bangkok` to `Asia/Ho_Chi_Minh`. Preserve UTC in database
queries, convert only for display, and calculate durations before formatting. Render
Vietnamese job, ETL, warehouse, R2, warning, and recovery sections. Continue sending a
compact Discord message.

- [ ] **Step 6: Run focused verification**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_github_actions_job_report.py tests/unit/test_github_actions_etl_report.py -v
.\.venv\Scripts\python.exe -m ruff check scripts/github_actions_job_report.py scripts/github_actions_etl_report.py tests/unit/test_github_actions_job_report.py tests/unit/test_github_actions_etl_report.py
```

Expected: PASS.

- [ ] **Step 7: Commit reporting**

```powershell
git add -- scripts/github_actions_job_report.py scripts/github_actions_etl_report.py tests/unit/test_github_actions_job_report.py tests/unit/test_github_actions_etl_report.py
git commit -m "Add detailed Vietnam-time workflow reports"
```

---

### Task 7: Split GitHub Actions into visible jobs

**Files:**
- Create: `.github/actions/setup-python-poetry/action.yml`
- Modify: `.github/workflows/etl.yml`
- Create: `tests/unit/test_etl_workflow.py`

**Interfaces:**
- Consumes: existing workflow inputs, ETL CLIs, R2 daily CLI, report scripts, GitHub Secrets, and GitHub Variables.
- Produces: seven named jobs and one final workflow summary.

- [ ] **Step 1: Add a failing workflow structure test**

Parse `.github/workflows/etl.yml` with `yaml.BaseLoader` and assert:

```python
EXPECTED_JOBS = [
    "validate",
    "prepare-database",
    "collect-daily",
    "collect-hourly",
    "collect-aqi",
    "publish-r2",
    "summary",
]

assert list(workflow["jobs"]) == EXPECTED_JOBS
assert workflow["jobs"]["prepare-database"]["needs"] == "validate"
assert workflow["jobs"]["summary"]["if"] == "always()"
assert "R2_SECRET_ACCESS_KEY: ${{ secrets.R2_SECRET_ACCESS_KEY }}" in workflow_text
assert "R2_SECRET_ACCESS_KEY: ${{ vars.R2_SECRET_ACCESS_KEY }}" not in workflow_text
```

- [ ] **Step 2: Run the test to verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_etl_workflow.py -v
```

Expected: FAIL because the workflow still has one `etl` job.

- [ ] **Step 3: Create shared setup action**

The composite action must:

1. Run `actions/setup-python@v5` with Python `3.13` and Poetry cache.
2. Install Poetry with `pipx install poetry`.
3. Run `poetry install`.

Do not put secrets or project-specific ETL commands in the shared action.

- [ ] **Step 4: Split the scheduled graph**

Implement these display names:

```text
1. Kiểm tra mã nguồn
2. Chuẩn bị database
3. Thu thập thời tiết daily
4. Thu thập thời tiết hourly
5. Thu thập AQI hourly
6. Xuất bản snapshot R2
7. Tổng hợp kết quả
```

Scheduled jobs run sequentially. Manual mode runs only the selected ETL mode; conditions
must allow an hourly or AQI manual job when preceding collect jobs are skipped. R2
publication runs for `schedule` only and requires all three scheduled collect jobs to
succeed.

Every job records start time before work, writes a job report with `if: always()`, and
uploads its JSON artifact. The summary job downloads all available report artifacts,
passes `needs.*.result` statuses explicitly, builds `GITHUB_STEP_SUMMARY`, and sends
Discord notification with `continue-on-error: true`.

- [ ] **Step 5: Wire GitHub configuration**

Use:

```text
Secret DATABASE_URL
Secret DISCORD_WEBHOOK_URL
Secret R2_ACCESS_KEY_ID
Secret R2_SECRET_ACCESS_KEY
Variable DISCORD_NOTIFICATIONS_ENABLED
Variable R2_ACCOUNT_ID
Variable R2_BUCKET_NAME
```

Do not expose secrets as job outputs. The publish job receives R2 values only through
its own environment.

- [ ] **Step 6: Run workflow and repository verification**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_etl_workflow.py -v
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
git diff --check
```

Expected: all tests pass, Ruff reports no findings, and Git diff has no whitespace
errors.

- [ ] **Step 7: Commit the workflow graph**

```powershell
git add -- .github/actions/setup-python-poetry/action.yml .github/workflows/etl.yml tests/unit/test_etl_workflow.py
git commit -m "Split ETL workflow into visible stages"
```

---

### Task 8: Validate live automation and handoff

**Files:**
- Modify: `docs/etl/automation.md`
- Modify: `docs/etl/demo-runbook.md`
- Modify: `docs/r2-snapshots.md`

**Interfaces:**
- Consumes: merged implementation, configured GitHub secrets/variables, private R2 bucket, and live Supabase data.
- Produces: live workflow evidence and concise Vietnamese demo instructions.

- [ ] **Step 1: Configure repository credentials interactively**

Confirm these names exist without printing values:

```powershell
gh secret list
gh variable list
```

Expected: all names from Task 7 are present. Add missing values through an interactive
credential-bearing terminal; never place values in command history or chat.

- [ ] **Step 2: Update Vietnamese docs**

Document the seven-node graph, `18:00 UTC = 01:00 UTC+7`, R2 watermark behavior,
summary tables, and recovery distinction:

```text
ETL failed -> run manual catch-up
ETL succeeded and R2 failed -> retry R2 publisher only
```

- [ ] **Step 3: Run local final verification**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
git diff --check
git status --short
```

Expected: tests and Ruff pass; only intended documentation changes remain.

- [ ] **Step 4: Commit documentation**

```powershell
git add -- docs/etl/automation.md docs/etl/demo-runbook.md docs/r2-snapshots.md
git commit -m "Document R2 ETL automation"
```

- [ ] **Step 5: Push and run one manual demo**

After checking the branch:

```powershell
git branch --show-current
git push origin Cuong/dev
gh workflow run "Daily ETL" --ref Cuong/dev -f quick_preset="Demo daily - 2 quận"
```

Expected: the workflow graph displays seven jobs; only the selected manual ETL job runs,
R2 publication is skipped, and the Summary shows Vietnam time.

- [ ] **Step 6: Inspect evidence**

Run:

```powershell
$runId = gh run list --workflow "Daily ETL" --branch Cuong/dev --limit 1 `
  --json databaseId --jq '.[0].databaseId'
gh run view $runId --log
```

Verify job results, ETL row counts, summary timestamps, and recovery guidance. Do not
claim scheduled R2 publication is validated by this manual demo.

- [ ] **Step 7: Validate scheduled-equivalent R2 publication**

Trigger a bounded manual publisher from the credential-bearing terminal:

```powershell
.\.venv\Scripts\python.exe -m dotenv run -- `
  .\.venv\Scripts\python.exe scripts\publish_r2_daily.py --end-date 2026-07-28
```

Expected: no historical reread; either no-op because the watermark is current or one
bounded daily publish with a new complete manifest.
