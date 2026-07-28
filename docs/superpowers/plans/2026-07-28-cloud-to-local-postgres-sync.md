# Cloud-to-Local PostgreSQL Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build one manually invoked, idempotent command that provisions an isolated local PostgreSQL target and incrementally copies the current weather warehouse from Supabase into it.

**Architecture:** Add a dedicated PostgreSQL 17 Compose service on host port 5433. A SQLAlchemy Core sync service reads exact model columns from a read-only cloud transaction, computes local high-water marks per district, re-reads a configurable recent window, and applies PostgreSQL upserts to the local database in bounded batches. A thin script validates configuration, migrates the local target in a subprocess, runs the service, and prints a credential-safe summary.

**Tech Stack:** Python 3.13, SQLAlchemy 2.x Core, psycopg 3, Alembic, PostgreSQL 17, Docker Compose, pytest, Ruff.

## Global Constraints

- Do not edit `.env`, cloud ETL code, GitHub Actions, or the unrelated Tiki container/database.
- Preserve the user's existing changes in `.codebase-memory/*` and `.gitignore`.
- Never log database URLs, passwords, or connection-string representations.
- `CLOUD_DATABASE_URL` is read-only; `LOCAL_DATABASE_URL` is the only writable target.
- The default command is manual; do not add a scheduler, watcher, or background process.
- Default `--lookback-days` is 0 and default `--batch-size` is 1000.
- Default mode reads all rows newer than the local watermark without re-reading old
  rows; a positive lookback adds a recheck window, and `--full` is the only
  full-history mode.
- Sync dimensions before facts in this exact order: district, date, hour, daily, hourly, AQI.
- Use `(district_id, date_key)` for daily conflicts and `(district_id, hour_key)` for hourly/AQI conflicts.
- Use `.venv\Scripts\python.exe -m pytest` and `.venv\Scripts\python.exe -m ruff check .` when Poetry is unavailable.
- Do not run a real full Supabase sync while the organization has only about 0.47 GB egress remaining; verify with local fixtures until quota resets or the user explicitly accepts the egress cost.

---

## File Structure

- `docker-compose.yml`: add the isolated `vwdp-postgres` service and persistent volume.
- `.env.example`: document placeholders for the two sync URLs and required local Docker password.
- `src/sync/__init__.py`: export the sync service's public types.
- `src/sync/cloud_to_local.py`: table specifications, URL safety, query construction, streaming, upsert, and summary.
- `scripts/sync_cloud_to_local.py`: CLI parsing, environment validation, local Alembic migration, engine lifecycle, and output.
- `tests/unit/test_cloud_to_local_sync.py`: core query and orchestration tests.
- `tests/unit/test_cloud_to_local_cli.py`: CLI/config/migration-command tests.
- `docs/local-cloud-sync.md`: Vietnamese operator runbook and Power BI connection guidance.

---

### Task 1: Add the isolated local PostgreSQL service

**Files:**
- Modify: `docker-compose.yml`
- Modify: `.env.example`
- Create: `docs/local-cloud-sync.md`

**Interfaces:**
- Consumes: PowerShell environment variable `VWDP_POSTGRES_PASSWORD`.
- Produces: PostgreSQL endpoint `localhost:5433`, database/user `vwdp`, persistent volume `vwdp_postgres_data`.

- [ ] **Step 1: Extend Compose with a required password and healthcheck**

Add this service alongside the existing `api` service:

```yaml
  postgres:
    image: postgres:17-alpine
    container_name: vwdp-postgres
    environment:
      POSTGRES_DB: vwdp
      POSTGRES_USER: vwdp
      POSTGRES_PASSWORD: ${VWDP_POSTGRES_PASSWORD:?Set VWDP_POSTGRES_PASSWORD}
    ports:
      - "5433:5432"
    volumes:
      - vwdp_postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U vwdp -d vwdp"]
      interval: 5s
      timeout: 5s
      retries: 10

volumes:
  vwdp_postgres_data:
```

- [ ] **Step 2: Document non-secret sync placeholders**

Append only placeholders to `.env.example`:

```dotenv
# Manual Supabase -> local PostgreSQL synchronization.
CLOUD_DATABASE_URL=postgresql+psycopg://cloud_readonly:password@pooler.example.com:6543/postgres
LOCAL_DATABASE_URL=postgresql+psycopg://vwdp:password@localhost:5433/vwdp
VWDP_POSTGRES_PASSWORD=replace-with-a-local-secret
```

- [ ] **Step 3: Write the initial operator runbook**

Create `docs/local-cloud-sync.md` with these exact operational commands and cautions:

```powershell
$env:VWDP_POSTGRES_PASSWORD = "<local-secret>"
docker compose up -d postgres
docker compose ps postgres

$env:CLOUD_DATABASE_URL = "<read-only-supabase-url>"
$env:LOCAL_DATABASE_URL = "postgresql+psycopg://vwdp:<url-encoded-password>@localhost:5433/vwdp"
.venv\Scripts\python.exe scripts\sync_cloud_to_local.py
```

Explain that the first run is full, subsequent runs are incremental, `--lookback-days`
is a recheck window rather than a schedule, and members should connect Power BI to port
5433 with a separate read-only role.

- [ ] **Step 4: Validate the Compose model**

Run:

```powershell
$env:VWDP_POSTGRES_PASSWORD = "compose-validation-only"
docker compose config --quiet
docker compose config
```

Expected: exit code 0, `vwdp-postgres` maps `5433:5432`, and no reference to the Tiki
container appears.

- [ ] **Step 5: Commit the infrastructure slice**

```powershell
git branch --show-current
git add -- docker-compose.yml .env.example docs/local-cloud-sync.md
git commit -m "Add local weather PostgreSQL service"
```

---

### Task 2: Define sync contracts and configuration safety

**Files:**
- Create: `src/sync/__init__.py`
- Create: `src/sync/cloud_to_local.py`
- Create: `tests/unit/test_cloud_to_local_sync.py`

**Interfaces:**
- Produces:
  - `SyncOptions(lookback_days: int = 0, batch_size: int = 1000, full: bool = False)`
  - `TableSpec(name, table, conflict_columns, key_column, time_column, time_join)`
  - `SyncTableResult(table_name: str, rows_read: int, rows_upserted: int)`
  - `validate_distinct_databases(cloud_url: str, local_url: str) -> None`
  - `TABLE_SPECS: tuple[TableSpec, ...]`
- Consumes: existing ORM tables from `src.database.models`.

- [ ] **Step 1: Write failing option and URL tests**

Add tests:

```python
import pytest

from src.sync.cloud_to_local import SyncOptions, validate_distinct_databases


def test_sync_options_reject_negative_lookback() -> None:
    with pytest.raises(ValueError, match="lookback_days"):
        SyncOptions(lookback_days=-1)


def test_sync_options_reject_non_positive_batch_size() -> None:
    with pytest.raises(ValueError, match="batch_size"):
        SyncOptions(batch_size=0)


def test_validate_distinct_databases_rejects_same_endpoint_without_leaking_password() -> None:
    url = "postgresql+psycopg://user:secret@localhost:5433/vwdp"
    with pytest.raises(ValueError) as exc_info:
        validate_distinct_databases(url, url)
    assert "secret" not in str(exc_info.value)


def test_validate_distinct_databases_rejects_same_database_with_different_users() -> None:
    cloud_url = "postgresql+psycopg://cloud:one@localhost:5433/vwdp"
    local_url = "postgresql+psycopg://local:two@localhost:5433/vwdp"
    with pytest.raises(ValueError):
        validate_distinct_databases(cloud_url, local_url)
```

- [ ] **Step 2: Run the tests and confirm RED**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/test_cloud_to_local_sync.py -v
```

Expected: collection fails because `src.sync.cloud_to_local` does not exist.

- [ ] **Step 3: Implement validated dataclasses and URL comparison**

Implement:

```python
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy.engine import make_url


@dataclass(frozen=True)
class SyncOptions:
    lookback_days: int = 0
    batch_size: int = 1000
    full: bool = False

    def __post_init__(self) -> None:
        if self.lookback_days < 0:
            raise ValueError("lookback_days must be non-negative")
        if self.batch_size <= 0:
            raise ValueError("batch_size must be positive")

    @property
    def lookback(self) -> timedelta:
        return timedelta(days=self.lookback_days)


def _database_identity(url: str) -> tuple[str | None, int | None, str | None]:
    parsed = make_url(url)
    return parsed.host, parsed.port, parsed.database


def validate_distinct_databases(cloud_url: str, local_url: str) -> None:
    if _database_identity(cloud_url) == _database_identity(local_url):
        raise ValueError("cloud and local database endpoints must be different")
```

Define `TableSpec`, `SyncTableResult`, and `TABLE_SPECS` using the six model tables in
the approved order. Also expose `DAILY_SPEC`, `HOURLY_SPEC`, and `AQI_SPEC` by looking
them up once from `TABLE_SPECS`. Use explicit conflict/key columns and represent hourly
time filters with `DimHour.__table__`; do not duplicate model column names as raw
strings except in the table-spec declarations.

- [ ] **Step 4: Test the table order and conflict contracts**

Add:

```python
from src.sync.cloud_to_local import TABLE_SPECS


def test_table_specs_preserve_foreign_key_order_and_conflict_keys() -> None:
    assert [spec.name for spec in TABLE_SPECS] == [
        "dim_district",
        "dim_date",
        "dim_hour",
        "fact_weather_daily",
        "fact_weather_hourly",
        "fact_aqi_hourly",
    ]
    conflicts = {spec.name: spec.conflict_columns for spec in TABLE_SPECS}
    assert conflicts["fact_weather_daily"] == ("district_id", "date_key")
    assert conflicts["fact_weather_hourly"] == ("district_id", "hour_key")
    assert conflicts["fact_aqi_hourly"] == ("district_id", "hour_key")
```

- [ ] **Step 5: Run focused tests and confirm GREEN**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/test_cloud_to_local_sync.py -v
```

Expected: all Task 2 tests pass.

- [ ] **Step 6: Commit the contracts**

```powershell
git branch --show-current
git add -- src/sync/__init__.py src/sync/cloud_to_local.py tests/unit/test_cloud_to_local_sync.py
git commit -m "Define cloud sync contracts"
```

---

### Task 3: Build incremental source queries

**Files:**
- Modify: `src/sync/cloud_to_local.py`
- Modify: `tests/unit/test_cloud_to_local_sync.py`

**Interfaces:**
- Produces:
  - `Watermarks = dict[int, int] | int | None`
  - `load_watermarks(connection, spec: TableSpec) -> Watermarks`
  - `load_local_district_ids(connection) -> tuple[int, ...]`
  - `build_source_statement(spec, watermarks, district_ids, cutoff, full) -> Select`
- Consumes: SQLAlchemy `Connection`, `TableSpec`, UTC cutoff datetime.

- [ ] **Step 1: Write failing watermark tests**

Use a lightweight fake result that returns mapping rows, while executing the real
SQLAlchemy statement through an injected recording connection:

```python
class RecordingMappings:
    def __init__(self, rows: list[dict[str, int]]) -> None:
        self.rows = rows

    def mappings(self):
        return self

    def all(self) -> list[dict[str, int]]:
        return self.rows


class RecordingConnection:
    def __init__(self, rows: list[dict[str, int]]) -> None:
        self.rows = rows
        self.statement = None

    def execute(self, statement):
        self.statement = statement
        return RecordingMappings(self.rows)


def test_load_watermarks_returns_max_key_per_district() -> None:
    connection = RecordingConnection([
        {"district_id": 1, "last_key": 2026072801},
        {"district_id": 2, "last_key": 2026072802},
    ])
    result = load_watermarks(connection, HOURLY_SPEC)
    assert result == {1: 2026072801, 2: 2026072802}
    compiled = str(connection.statement.compile(dialect=postgresql.dialect()))
    assert "max" in compiled.lower()
    assert "group by" in compiled.lower()
```

Also test that dimension specs use a scalar watermark rather than a district mapping,
and that `load_local_district_ids` returns all local district IDs in stable order.

- [ ] **Step 2: Run focused tests and confirm RED**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/test_cloud_to_local_sync.py -k watermark -v
```

Expected: failure because `load_watermarks` is undefined.

- [ ] **Step 3: Implement local watermark queries**

For fact tables, select:

```sql
select district_id, max(date_key or hour_key) as last_key
from analyst.fact_...
group by district_id
```

For `dim_date` and `dim_hour`, select one scalar maximum. `dim_district` has no
watermark because it is always small/full.

- [ ] **Step 4: Write failing source-query tests**

Compile actual SQLAlchemy statements with the PostgreSQL dialect and assert behavior,
not formatting:

```python
def test_hourly_statement_combines_per_district_watermark_and_lookback() -> None:
    cutoff = datetime(2026, 7, 25, tzinfo=UTC)
    statement = build_source_statement(
        HOURLY_SPEC,
        watermarks={1: 2026072500, 2: 2026072400},
        district_ids=(1, 2, 3),
        cutoff=cutoff,
        full=False,
    )
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "fact_weather_hourly.district_id" in sql
    assert "fact_weather_hourly.hour_key" in sql
    assert "dim_hour.observed_at" in sql
    assert " OR " in sql


def test_full_statement_has_no_incremental_where_clause() -> None:
    statement = build_source_statement(
        HOURLY_SPEC,
        watermarks={1: 123},
        district_ids=(1,),
        cutoff=datetime(2026, 7, 25, tzinfo=UTC),
        full=True,
    )
    assert "WHERE" not in str(statement.compile(dialect=postgresql.dialect()))
```

Add cases for empty local watermarks, daily `observed_date`, incremental `dim_date`,
and incremental `dim_hour`.

- [ ] **Step 5: Run source-query tests and confirm RED**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/test_cloud_to_local_sync.py -k statement -v
```

Expected: failure because `build_source_statement` is undefined.

- [ ] **Step 6: Implement exact-column incremental statements**

Build `select(*spec.table.columns)` and:

- join `dim_hour` only for hourly/AQI cutoff filtering;
- filter daily facts directly on `observed_date`;
- construct one district/key branch per ID returned by `load_local_district_ids`;
- use `key > -1` for a district missing from the watermark mapping so its history is fetched;
- combine new-key branches with the lookback predicate using `or_`;
- order facts by district then key and dimensions by primary key;
- omit `WHERE` only when `full=True` or the target table is completely empty.

Never use `select(spec.table)` followed by accessing ORM relationships, and never add
cloud-only audit columns absent from current models.

- [ ] **Step 7: Run focused tests and confirm GREEN**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/test_cloud_to_local_sync.py -v
```

Expected: all query-selection tests pass.

- [ ] **Step 8: Commit incremental query planning**

```powershell
git branch --show-current
git add -- src/sync/cloud_to_local.py tests/unit/test_cloud_to_local_sync.py
git commit -m "Build incremental cloud sync queries"
```

---

### Task 4: Stream rows and upsert the local warehouse

**Files:**
- Modify: `src/sync/cloud_to_local.py`
- Modify: `tests/unit/test_cloud_to_local_sync.py`

**Interfaces:**
- Produces:
  - `build_upsert_statement(spec: TableSpec, rows: Sequence[Mapping]) -> Insert`
  - `CloudToLocalSync(cloud_engine, local_engine, options, now_fn)`
  - `CloudToLocalSync.run() -> tuple[SyncTableResult, ...]`
- Consumes: SQLAlchemy `Engine` instances and Task 3 query builders.

- [ ] **Step 1: Write failing upsert tests**

Compile the real PostgreSQL insert:

```python
def test_build_upsert_statement_updates_non_key_columns() -> None:
    rows = [{"district_id": 1, "date_key": 20260728, "temperature_2m_mean": 30.0}]
    statement = build_upsert_statement(DAILY_SPEC, rows)
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "ON CONFLICT (district_id, date_key) DO UPDATE" in sql
    assert "temperature_2m_mean" in sql
```

Add a dimension case and assert key columns are not present in the update assignment
mapping.

- [ ] **Step 2: Run upsert tests and confirm RED**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/test_cloud_to_local_sync.py -k upsert -v
```

Expected: failure because `build_upsert_statement` is undefined.

- [ ] **Step 3: Implement PostgreSQL upsert generation**

Use:

```python
from sqlalchemy.dialects.postgresql import insert

base = insert(spec.table).values(list(rows))
update_columns = {
    column.name: getattr(base.excluded, column.name)
    for column in spec.table.columns
    if column.name not in spec.conflict_columns
}
return base.on_conflict_do_update(
    index_elements=[spec.table.c[name] for name in spec.conflict_columns],
    set_=update_columns,
)
```

- [ ] **Step 4: Write failing orchestration tests**

Use dependency-injected recording connections/results to verify public behavior. Define
the `sync_harness` pytest fixture in the same test module; it must expose `service`,
`cloud_rows_by_table`, `local_upsert_order`, and `read_only_count`, and its fake
connection/result classes must implement the context-manager and
`mappings().partitions(batch_size)` methods used by production:

```python
def test_run_syncs_tables_in_foreign_key_order_and_batches_rows(sync_harness) -> None:
    sync_harness.cloud_rows_by_table = {
        spec.name: [{"synthetic": spec.name}] for spec in TABLE_SPECS
    }
    results = sync_harness.service.run()
    assert [result.table_name for result in results] == [spec.name for spec in TABLE_SPECS]
    assert sync_harness.local_upsert_order == [spec.name for spec in TABLE_SPECS]


def test_run_uses_one_read_only_cloud_transaction_per_table(sync_harness) -> None:
    sync_harness.service.run()
    assert sync_harness.read_only_count == len(TABLE_SPECS)
```

Add tests that:

- batches 2,500 rows as 1,000/1,000/500;
- rolls back the failing table transaction;
- retains results for tables committed before the failure;
- does not include URL strings in raised/logged messages;
- computes cutoff from the injected `now_fn`, not local naive time.

- [ ] **Step 5: Run orchestration tests and confirm RED**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/test_cloud_to_local_sync.py -k "run or batch or rollback" -v
```

Expected: failure because `CloudToLocalSync` is undefined.

- [ ] **Step 6: Implement streaming and per-table transactions**

For each `TableSpec`:

1. Open a local connection and load its watermark.
2. Open a cloud connection and transaction.
3. Execute `SET TRANSACTION READ ONLY`.
4. Execute the Task 3 select with `stream_results=True`.
5. Open one local transaction for the table.
6. Iterate `result.mappings().partitions(options.batch_size)`.
7. Execute one Task 4 upsert per non-empty partition.
8. Commit the local table transaction only after all batches succeed.
9. Return exact read/upsert counts.

Use `datetime.now(UTC)` through injectable `now_fn`. Close connections/results in
`finally`/context managers. Do not store all source rows in memory.

- [ ] **Step 7: Run core tests and confirm GREEN**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/test_cloud_to_local_sync.py -v
```

Expected: all core sync tests pass.

- [ ] **Step 8: Commit the sync engine**

```powershell
git branch --show-current
git add -- src/sync/cloud_to_local.py tests/unit/test_cloud_to_local_sync.py
git commit -m "Stream cloud data into local PostgreSQL"
```

---

### Task 5: Add the manual CLI and local migration step

**Files:**
- Create: `scripts/sync_cloud_to_local.py`
- Create: `tests/unit/test_cloud_to_local_cli.py`
- Modify: `src/sync/__init__.py`
- Modify: `docs/local-cloud-sync.md`

**Interfaces:**
- Produces:
  - `parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace`
  - `load_database_urls(environ: Mapping[str, str]) -> tuple[str, str]`
  - `run_local_migrations(local_url: str) -> None`
  - `main() -> int`
- Consumes: `CloudToLocalSync`, `SyncOptions`, and SQLAlchemy `create_engine`.

- [ ] **Step 1: Write failing CLI validation tests**

Add:

```python
def test_load_database_urls_requires_both_values() -> None:
    with pytest.raises(ValueError, match="CLOUD_DATABASE_URL"):
        load_database_urls({"LOCAL_DATABASE_URL": "postgresql+psycopg://local/db"})


def test_parse_args_uses_safe_defaults() -> None:
    args = parse_args([])
    assert args.lookback_days == 0
    assert args.batch_size == 1000
    assert args.full is False
```

Test invalid negative/zero values through `parse_args` and assert argparse exits with
code 2.

- [ ] **Step 2: Run CLI tests and confirm RED**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/test_cloud_to_local_cli.py -v
```

Expected: collection fails because the script module does not exist.

- [ ] **Step 3: Implement parsing and environment loading**

Use custom argparse types:

```python
def non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be non-negative")
    return parsed


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed
```

Read only `CLOUD_DATABASE_URL` and `LOCAL_DATABASE_URL` from the provided environment
mapping. Do not call `load_dotenv` and do not print either value.

- [ ] **Step 4: Write failing migration subprocess test**

```python
def test_run_local_migrations_passes_local_url_only_to_child_environment(monkeypatch) -> None:
    captured = {}

    def fake_run(command, *, check, env, cwd):
        captured.update(command=command, check=check, env=env, cwd=cwd)

    monkeypatch.setattr(subprocess, "run", fake_run)
    run_local_migrations("postgresql+psycopg://vwdp:secret@localhost:5433/vwdp")
    assert captured["command"][-3:] == ["alembic", "upgrade", "head"]
    assert captured["env"]["DATABASE_URL"].endswith("@localhost:5433/vwdp")
```

- [ ] **Step 5: Run migration test and confirm RED**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/test_cloud_to_local_cli.py -k migration -v
```

Expected: failure because `run_local_migrations` is undefined.

- [ ] **Step 6: Implement isolated Alembic execution**

Run:

```python
subprocess.run(
    [sys.executable, "-m", "alembic", "upgrade", "head"],
    check=True,
    cwd=REPOSITORY_ROOT,
    env={**os.environ, "DATABASE_URL": local_url},
)
```

This intentionally uses a child process so cached application settings cannot redirect
Alembic to the cloud database.

- [ ] **Step 7: Write and implement the main lifecycle test-first**

Test that `main()`:

- validates distinct URLs before migration;
- migrates local before constructing the sync service;
- creates cloud/local engines with `pool_pre_ping=True`;
- disposes both engines in `finally`;
- prints one line per table plus totals;
- returns 0 on success and a non-zero code with credential-safe text on failure.

Implement the minimal lifecycle to satisfy those assertions. The cloud engine must
not reuse application `SessionLocal`.

- [ ] **Step 8: Run CLI and core tests**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/test_cloud_to_local_cli.py tests/unit/test_cloud_to_local_sync.py -v
```

Expected: all focused tests pass.

- [ ] **Step 9: Complete the runbook**

Add:

- first-run/full-egress warning;
- default incremental command;
- optional positive `--lookback-days` recheck command;
- `--full` recovery command;
- Power BI connection fields (`localhost`, `5433`, `vwdp`);
- row-count verification SQL for all six tables;
- instructions to create a separate read-only member role manually, without embedding
  its password in the document.

- [ ] **Step 10: Commit the CLI slice**

```powershell
git branch --show-current
git add -- scripts/sync_cloud_to_local.py tests/unit/test_cloud_to_local_cli.py src/sync/__init__.py docs/local-cloud-sync.md
git commit -m "Add manual cloud sync command"
```

---

### Task 6: Verify with an isolated local fixture

**Files:**
- Modify only if verification reveals a tested defect:
  - `src/sync/cloud_to_local.py`
  - `scripts/sync_cloud_to_local.py`
  - corresponding test file

**Interfaces:**
- Consumes: the completed Docker service and CLI.
- Produces: evidence that first-run and second-run behavior are idempotent without using Supabase egress.

- [ ] **Step 1: Start the isolated target**

Run:

```powershell
$env:VWDP_POSTGRES_PASSWORD = "<task-specific-local-secret>"
docker compose up -d postgres
docker compose ps postgres
```

Expected: only `vwdp-postgres` is created by this project; the Tiki container remains
unchanged and healthy.

- [ ] **Step 2: Create isolated source and target fixture databases**

Inside `vwdp-postgres`, create `vwdp_sync_source_test` and
`vwdp_sync_target_test`. Apply existing Alembic migrations to both by setting
`DATABASE_URL` separately in the current PowerShell process. Seed:

- two districts;
- five date/hour rows;
- daily/hourly/AQI rows for both districts.

Use explicit SQL fixtures with non-secret local credentials. Do not point either URL
at Supabase.

- [ ] **Step 3: Run first sync and capture counts**

Set:

```powershell
$env:CLOUD_DATABASE_URL = "postgresql+psycopg://vwdp:<encoded-secret>@localhost:5433/vwdp_sync_source_test"
$env:LOCAL_DATABASE_URL = "postgresql+psycopg://vwdp:<encoded-secret>@localhost:5433/vwdp_sync_target_test"
.venv\Scripts\python.exe scripts\sync_cloud_to_local.py
```

Expected: all fixture rows are copied and all six table summaries are printed.

- [ ] **Step 4: Run second sync without source changes**

Run the same command again.

Expected: no duplicates and no old rows are re-read because the default lookback is
zero. Local row counts remain identical.

- [ ] **Step 5: Add one new and one recently corrected source row**

Insert a new latest hour/fact and update one older fact in the source fixture. Run the
default sync, then run with an explicit positive lookback to verify both behaviors.

Expected: the new row appears locally and the corrected local value matches the source.

- [ ] **Step 6: Verify strict incremental mode**

Update an existing recent source row and add another new row, then run:

```powershell
.venv\Scripts\python.exe scripts\sync_cloud_to_local.py --lookback-days 0
```

Expected: the new row is copied; the existing corrected row is not re-read. This
documents the deliberate trade-off of strict mode.

- [ ] **Step 7: Run repository verification**

Run:

```powershell
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m ruff check .
$env:VWDP_POSTGRES_PASSWORD = "compose-validation-only"
docker compose config --quiet
git diff --check
git status --short
```

Expected: pytest and Ruff pass, Compose validates, no whitespace errors, and only
intentional files plus pre-existing user changes are present.

- [ ] **Step 8: Run Supabase advisors only if remote DDL was changed**

No remote DDL is planned. Do not call migration tools against Supabase. If scope
changes and remote DDL is introduced, stop, list tables, run security/performance
advisors, and obtain user confirmation before applying it.

- [ ] **Step 9: Commit any verification-driven fixes**

Only if Step 7 required tested code changes:

```powershell
git branch --show-current
git add -- src/sync/cloud_to_local.py scripts/sync_cloud_to_local.py tests/unit/test_cloud_to_local_sync.py tests/unit/test_cloud_to_local_cli.py
git commit -m "Fix local sync verification issues"
```

Do not stage `.codebase-memory/*` or `.gitignore`.
