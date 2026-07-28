# Metabase and Restricted ngrok Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run a persistent Metabase instance over the local weather warehouse, give collaborators tailnet-only full access, and expose only anonymous public dashboards through a restricted ngrok gateway.

**Architecture:** Docker Compose adds a private PostgreSQL application database, pinned Metabase, and an Nginx public-dashboard gateway on loopback port 3001. Python bootstrap code provisions a read-only warehouse role and idempotently initializes Metabase through its API. Tested command builders drive Tailscale Serve and ngrok without exposing PostgreSQL.

**Tech Stack:** Python 3.13, SQLAlchemy 2.x, HTTPX 0.28, PostgreSQL 17, Metabase 0.63.1, Nginx 1.29, Docker Compose, Tailscale 1.98.8, ngrok 3.33.1, pytest, Ruff.

## Global Constraints

- Work directly on `Cuong/dev`; the user declined a worktree.
- Do not edit `.env`, real secret files, `.codebase-memory/*`, or the user's existing `.gitignore` changes.
- Never print database URLs, passwords, ngrok tokens, or Metabase session tokens.
- Bind Metabase and its public gateway only to `127.0.0.1`.
- Never expose PostgreSQL port `5433` through ngrok or Tailscale Funnel.
- Tailscale Serve is the only full-application remote access path.
- ngrok forwards only the restricted public gateway and has no OAuth by user choice.
- Anyone with a Metabase public dashboard URL can view it; revocation means removing that public link.
- Cloud synchronization remains manual and must not read `.env`.
- Preserve all existing cloud-to-local sync behavior and tests.

---

## File Structure

- `docker-compose.yml`: add `metabase-db`, `metabase`, and `metabase-public-gateway`.
- `.env.example`: add non-secret variable names and example values.
- `config/metabase-public-nginx.conf`: allow public dashboard rendering routes and deny all other routes.
- `src/metabase/__init__.py`: export bootstrap interfaces.
- `src/metabase/bootstrap.py`: settings validation, local guard, warehouse role grants, Metabase API setup.
- `scripts/setup_metabase.py`: credential-safe bootstrap CLI.
- `scripts/metabase_access.py`: tested Tailscale/ngrok command construction and execution.
- `scripts/start_metabase_tailnet.ps1`: thin Windows wrapper for tailnet access.
- `scripts/start_public_dashboard_tunnel.ps1`: thin Windows wrapper for ngrok.
- `tests/unit/test_metabase_bootstrap.py`: bootstrap unit tests.
- `tests/unit/test_metabase_access.py`: access command unit tests.
- `docs/metabase-self-host.md`: Vietnamese runbook.

---

### Task 1: Add the persistent Metabase stack and restricted gateway

**Files:**
- Modify: `docker-compose.yml`
- Modify: `.env.example`
- Create: `config/metabase-public-nginx.conf`
- Create: `docs/metabase-self-host.md`

**Interfaces:**
- Consumes: `VWDP_POSTGRES_PASSWORD`, `METABASE_DB_PASSWORD`,
  `METABASE_ENCRYPTION_SECRET_KEY`, `METABASE_SITE_URL`.
- Produces:
  - `metabase-db:5432` on the Compose network only.
  - Metabase at `127.0.0.1:3000`.
  - Restricted gateway at `127.0.0.1:3001`.

- [ ] **Step 1: Add Compose services**

Add:

```yaml
  metabase-db:
    image: postgres:17-alpine
    container_name: vwdp-metabase-db
    environment:
      POSTGRES_DB: metabase
      POSTGRES_USER: metabase
      POSTGRES_PASSWORD: ${METABASE_DB_PASSWORD:?Set METABASE_DB_PASSWORD}
    volumes:
      - metabase_app_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U metabase -d metabase"]
      interval: 5s
      timeout: 5s
      retries: 20

  metabase:
    image: metabase/metabase:v0.63.1
    container_name: vwdp-metabase
    depends_on:
      postgres:
        condition: service_healthy
      metabase-db:
        condition: service_healthy
    environment:
      MB_DB_TYPE: postgres
      MB_DB_DBNAME: metabase
      MB_DB_PORT: 5432
      MB_DB_USER: metabase
      MB_DB_PASS: ${METABASE_DB_PASSWORD:?Set METABASE_DB_PASSWORD}
      MB_DB_HOST: metabase-db
      MB_SITE_URL: ${METABASE_SITE_URL:-http://localhost:3000}
      MB_SITE_NAME: VWDP Metabase
      MB_ANON_TRACKING_ENABLED: "false"
      MB_ENABLE_PUBLIC_SHARING: "true"
      MB_ENCRYPTION_SECRET_KEY: ${METABASE_ENCRYPTION_SECRET_KEY:?Set METABASE_ENCRYPTION_SECRET_KEY}
      JAVA_TIMEZONE: Asia/Ho_Chi_Minh
    ports:
      - "127.0.0.1:3000:3000"
    healthcheck:
      test: ["CMD-SHELL", "curl --fail --silent http://localhost:3000/api/health || exit 1"]
      interval: 15s
      timeout: 5s
      retries: 40

  metabase-public-gateway:
    image: nginx:1.29-alpine
    container_name: vwdp-metabase-public
    depends_on:
      metabase:
        condition: service_healthy
    ports:
      - "127.0.0.1:3001:80"
    volumes:
      - ./config/metabase-public-nginx.conf:/etc/nginx/conf.d/default.conf:ro
    healthcheck:
      test: ["CMD-SHELL", "wget -q -O /dev/null http://localhost/healthz"]
      interval: 10s
      timeout: 5s
      retries: 10
```

Add `metabase_app_data:` under the top-level `volumes`.

- [ ] **Step 2: Add the Nginx route policy**

Create this exact initial configuration:

```nginx
server {
    listen 80;
    server_name _;

    location = /healthz {
        access_log off;
        add_header Content-Type text/plain;
        return 200 "ok\n";
    }

    location ~ ^/public/dashboard/[0-9a-fA-F-]+$ {
        proxy_pass http://metabase:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location ^~ /api/public/ {
        proxy_pass http://metabase:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location ^~ /app/ {
        proxy_pass http://metabase:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto https;
    }

    location = /api/session/properties {
        proxy_pass http://metabase:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto https;
    }

    location / {
        return 404;
    }
}
```

Do not broaden the gateway unless browser verification proves another render-only route
is required. Any added route must receive a regression assertion that `/`,
`/auth/login`, `/admin`, and `/api/user/current` remain blocked.

- [ ] **Step 3: Document placeholders**

Append to `.env.example`:

```dotenv
# Metabase self-hosting. Keep real values outside Git.
METABASE_DB_PASSWORD=replace-with-metabase-app-db-secret
METABASE_ENCRYPTION_SECRET_KEY=replace-with-random-base64-secret
METABASE_WAREHOUSE_PASSWORD=replace-with-readonly-warehouse-secret
METABASE_ADMIN_EMAIL=admin@example.com
METABASE_ADMIN_PASSWORD=replace-with-metabase-admin-secret
METABASE_ADMIN_FIRST_NAME=VWDP
METABASE_ADMIN_LAST_NAME=Admin
METABASE_SITE_URL=http://localhost:3000
NGROK_DOMAIN=assigned-domain.ngrok-free.app
METABASE_PUBLIC_DASHBOARD_PATH=/public/dashboard/00000000-0000-0000-0000-000000000000
```

- [ ] **Step 4: Write the initial Vietnamese runbook**

Document:

```powershell
$env:METABASE_DB_PASSWORD = Read-Host "Metabase DB password"
$env:METABASE_ENCRYPTION_SECRET_KEY = Read-Host "Metabase encryption key"
$env:METABASE_WAREHOUSE_PASSWORD = Read-Host "Warehouse reader password"
$env:METABASE_ADMIN_EMAIL = "admin@example.com"
$env:METABASE_ADMIN_PASSWORD = Read-Host "Metabase admin password"
$env:METABASE_ADMIN_FIRST_NAME = "VWDP"
$env:METABASE_ADMIN_LAST_NAME = "Admin"
$env:METABASE_SITE_URL = "http://localhost:3000"
docker compose up -d postgres metabase-db metabase metabase-public-gateway
```

Also state that `Read-Host` above returns plain strings for process environment use, the
terminal must remain private, and secrets are not persisted by the project.

- [ ] **Step 5: Validate Compose without rendering secrets**

Run:

```powershell
$env:VWDP_POSTGRES_PASSWORD = "compose-check-only"
$env:METABASE_DB_PASSWORD = "compose-check-only"
$env:METABASE_ENCRYPTION_SECRET_KEY = "Y29tcG9zZS1jaGVjay1vbmx5"
docker compose config --quiet
```

Expected: exit code 0. Never run plain `docker compose config`, because the existing
`api.env_file` expands secrets in output.

- [ ] **Step 6: Commit the stack**

```powershell
git branch --show-current
git add -- docker-compose.yml .env.example config/metabase-public-nginx.conf docs/metabase-self-host.md
git commit -m "Add self-hosted Metabase stack"
```

---

### Task 2: Provision a safe warehouse reader

**Files:**
- Create: `src/metabase/__init__.py`
- Create: `src/metabase/bootstrap.py`
- Create: `tests/unit/test_metabase_bootstrap.py`

**Interfaces:**
- Produces:
  - `MetabaseSettings.from_environ(environ: Mapping[str, str]) -> MetabaseSettings`
  - `validate_local_warehouse_url(url: str) -> None`
  - `provision_warehouse_reader(engine: Engine, password: str) -> None`
- Consumes: SQLAlchemy engine for the local `vwdp` database.

- [ ] **Step 1: Write failing settings and local-guard tests**

```python
def test_settings_require_named_environment_values() -> None:
    with pytest.raises(ValueError, match="METABASE_DB_PASSWORD"):
        MetabaseSettings.from_environ({})


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+psycopg://vwdp:secret@db.example.com/vwdp",
        "postgresql+psycopg://vwdp:secret@10.0.0.5/vwdp",
    ],
)
def test_local_guard_rejects_non_loopback_hosts(url: str) -> None:
    with pytest.raises(ValueError, match="local"):
        validate_local_warehouse_url(url)
```

Use a complete valid mapping in a positive test and assert parsed values without ever
placing them in assertion failure messages.

- [ ] **Step 2: Confirm RED**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/test_metabase_bootstrap.py -k "settings or local_guard" -v
```

Expected: collection failure because `src.metabase.bootstrap` does not exist.

- [ ] **Step 3: Implement settings and the loopback guard**

Use:

```python
@dataclass(frozen=True)
class MetabaseSettings:
    local_database_url: str
    warehouse_password: str
    admin_email: str
    admin_password: str
    admin_first_name: str
    admin_last_name: str
    metabase_url: str = "http://localhost:3000"

    @classmethod
    def from_environ(cls, environ: Mapping[str, str]) -> "MetabaseSettings":
        names = (
            "LOCAL_DATABASE_URL",
            "METABASE_WAREHOUSE_PASSWORD",
            "METABASE_ADMIN_EMAIL",
            "METABASE_ADMIN_PASSWORD",
            "METABASE_ADMIN_FIRST_NAME",
            "METABASE_ADMIN_LAST_NAME",
        )
        values = {name: environ.get(name, "").strip() for name in names}
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise ValueError(f"{missing[0]} is required")
        return cls(
            local_database_url=values["LOCAL_DATABASE_URL"],
            warehouse_password=values["METABASE_WAREHOUSE_PASSWORD"],
            admin_email=values["METABASE_ADMIN_EMAIL"],
            admin_password=values["METABASE_ADMIN_PASSWORD"],
            admin_first_name=values["METABASE_ADMIN_FIRST_NAME"],
            admin_last_name=values["METABASE_ADMIN_LAST_NAME"],
            metabase_url=environ.get("METABASE_URL", "http://localhost:3000").rstrip("/"),
        )


def validate_local_warehouse_url(url: str) -> None:
    parsed = make_url(url)
    if parsed.host not in {"localhost", "127.0.0.1", "::1"} or parsed.database != "vwdp":
        raise ValueError("LOCAL_DATABASE_URL must target the local vwdp database")
```

- [ ] **Step 4: Write failing warehouse grant tests**

Use a recording engine/connection implementing `begin`, `execute`, and context manager
methods. Assert:

```python
def test_reader_provisioning_grants_only_analyst_select(recording_engine) -> None:
    provision_warehouse_reader(recording_engine, "reader-secret")
    sql = "\n".join(recording_engine.statements).lower()
    assert "create role metabase_reader" in sql
    assert "grant usage on schema analyst" in sql
    assert "grant select on all tables in schema analyst" in sql
    assert "alter default privileges in schema analyst grant select" in sql
    assert "grant insert" not in sql
    assert "monitoring" not in sql
    assert "reader-secret" not in sql
    assert recording_engine.parameters_contain("reader-secret")
```

Test both the role-missing and role-existing result branches.

- [ ] **Step 5: Confirm RED**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/test_metabase_bootstrap.py -k reader -v
```

Expected: failure because `provision_warehouse_reader` is undefined.

- [ ] **Step 6: Implement idempotent reader provisioning**

Within one `engine.begin()`, bind the password only through `set_config` and keep the
role DDL text constant:

```python
connection.execute(
    text("SELECT set_config('vwdp.metabase_reader_password', :password, true)"),
    {"password": password},
)
connection.execute(
    text(
        """
        DO $block$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'metabase_reader') THEN
                EXECUTE format(
                    'ALTER ROLE metabase_reader WITH LOGIN PASSWORD %L',
                    current_setting('vwdp.metabase_reader_password')
                );
            ELSE
                EXECUTE format(
                    'CREATE ROLE metabase_reader WITH LOGIN PASSWORD %L',
                    current_setting('vwdp.metabase_reader_password')
                );
            END IF;
        END
        $block$;
        """
    )
)
connection.execute(text("GRANT CONNECT ON DATABASE vwdp TO metabase_reader"))
connection.execute(text("GRANT USAGE ON SCHEMA analyst TO metabase_reader"))
connection.execute(
    text("GRANT SELECT ON ALL TABLES IN SCHEMA analyst TO metabase_reader")
)
connection.execute(
    text(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA analyst "
        "GRANT SELECT ON TABLES TO metabase_reader"
    )
)
```

The role name and database/schema names are fixed constants, never user input. Passwords
remain bound parameters.

- [ ] **Step 7: Verify and commit**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/test_metabase_bootstrap.py -v
.venv\Scripts\python.exe -m ruff check src/metabase tests/unit/test_metabase_bootstrap.py
git branch --show-current
git add -- src/metabase/__init__.py src/metabase/bootstrap.py tests/unit/test_metabase_bootstrap.py
git commit -m "Provision Metabase warehouse reader"
```

---

### Task 3: Initialize Metabase and attach the local warehouse

**Files:**
- Modify: `src/metabase/bootstrap.py`
- Modify: `src/metabase/__init__.py`
- Modify: `tests/unit/test_metabase_bootstrap.py`
- Create: `scripts/setup_metabase.py`

**Interfaces:**
- Produces:
  - `MetabaseClient(base_url: str, client: httpx.Client)`
  - `MetabaseClient.wait_until_healthy(timeout_seconds: int = 180) -> None`
  - `MetabaseClient.ensure_setup(settings: MetabaseSettings) -> None`
  - `bootstrap_metabase(settings: MetabaseSettings) -> None`
  - CLI `main() -> int`
- Consumes: `provision_warehouse_reader`, Metabase REST API.

- [ ] **Step 1: Write failing API lifecycle tests**

Use `httpx.MockTransport` with deterministic handlers.

For a new instance, return:

```json
{"setup-token": "setup-token-value"}
```

from `/api/session/properties`, capture `/api/setup`, then assert the submitted database
details are exactly:

```python
{
    "engine": "postgres",
    "name": "VWDP Local Warehouse",
    "details": {
        "host": "postgres",
        "port": 5432,
        "dbname": "vwdp",
        "user": "metabase_reader",
        "password": settings.warehouse_password,
        "ssl": False,
    },
}
```

For an initialized instance, return a null setup token, accept
`POST /api/session`, return `{"id": "session-id"}`, return an existing database from
`GET /api/database`, and assert no duplicate `POST /api/database` occurs.

- [ ] **Step 2: Confirm RED**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/test_metabase_bootstrap.py -k "new_instance or initialized_instance" -v
```

Expected: failure because `MetabaseClient` is undefined.

- [ ] **Step 3: Implement the API client**

Implement credential-safe `_request`:

```python
def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
    response = self.client.request(method, f"{self.base_url}{path}", **kwargs)
    if response.is_error:
        raise RuntimeError(
            f"Metabase request failed: {method} {path} returned {response.status_code}"
        )
    return response
```

`ensure_setup` must:

1. Read `setup-token`.
2. Call `/api/setup` with admin, preferences, and warehouse details when the token is
   present.
3. Otherwise authenticate, list databases, and add `VWDP Local Warehouse` only if its
   name is absent.
4. Never log request bodies, responses, session IDs, or exception response bodies.

- [ ] **Step 4: Test health waiting and safe timeout**

Use an injected `sleep_fn` and mock transport that returns two unhealthy responses then
healthy. Add a timeout case and assert its message contains no base URL or credentials.

- [ ] **Step 5: Implement orchestration and CLI**

`bootstrap_metabase`:

```python
validate_local_warehouse_url(settings.local_database_url)
engine = create_engine(settings.local_database_url, pool_pre_ping=True)
try:
    provision_warehouse_reader(engine, settings.warehouse_password)
finally:
    engine.dispose()
with httpx.Client(timeout=30.0) as http_client:
    client = MetabaseClient(settings.metabase_url, http_client)
    client.wait_until_healthy()
    client.ensure_setup(settings)
```

The CLI loads only `os.environ`, prints `Metabase setup completed.` on success, and on
failure prints only `f"Metabase setup failed ({type(exc).__name__})."` to stderr.

- [ ] **Step 6: Verify and commit**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/test_metabase_bootstrap.py -v
.venv\Scripts\python.exe -m ruff check src/metabase scripts/setup_metabase.py tests/unit/test_metabase_bootstrap.py
git branch --show-current
git add -- src/metabase/__init__.py src/metabase/bootstrap.py scripts/setup_metabase.py tests/unit/test_metabase_bootstrap.py
git commit -m "Initialize Metabase warehouse connection"
```

---

### Task 4: Add tested Tailscale and ngrok launchers

**Files:**
- Create: `scripts/metabase_access.py`
- Create: `scripts/start_metabase_tailnet.ps1`
- Create: `scripts/start_public_dashboard_tunnel.ps1`
- Create: `tests/unit/test_metabase_access.py`

**Interfaces:**
- Produces:
  - `build_tailscale_command(status: Mapping[str, object]) -> list[str]`
  - `validate_public_dashboard_path(path: str) -> str`
  - `build_ngrok_command(environ: Mapping[str, str]) -> tuple[list[str], str]`
  - CLI subcommands `tailnet` and `public-dashboard`.

- [ ] **Step 1: Write failing command-builder tests**

```python
def test_tailscale_requires_running_backend() -> None:
    with pytest.raises(ValueError, match="tailscale up"):
        build_tailscale_command({"BackendState": "NoState"})


def test_tailscale_builds_tailnet_only_serve_command() -> None:
    assert build_tailscale_command({"BackendState": "Running"}) == [
        "tailscale",
        "serve",
        "--bg",
        "--yes",
        "3000",
    ]


def test_ngrok_forwards_only_public_gateway() -> None:
    command, share_url = build_ngrok_command(
        {
            "NGROK_DOMAIN": "weather.ngrok-free.app",
            "NGROK_AUTHTOKEN": "token-value",
            "METABASE_PUBLIC_DASHBOARD_PATH": (
                "/public/dashboard/123e4567-e89b-12d3-a456-426614174000"
            ),
        }
    )
    assert command[:3] == ["ngrok", "http", "http://localhost:3001"]
    assert "--oauth" not in command
    assert "5433" not in command
    assert share_url.endswith("/public/dashboard/123e4567-e89b-12d3-a456-426614174000")
```

Add invalid cases for `/`, `/dashboard/1`, query strings, fragments, whitespace, and
non-UUID suffixes.

- [ ] **Step 2: Confirm RED**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/test_metabase_access.py -v
```

Expected: collection failure because `scripts.metabase_access` does not exist.

- [ ] **Step 3: Implement validation and command construction**

Use:

```python
PUBLIC_DASHBOARD_PATTERN = re.compile(
    r"^/public/dashboard/[0-9a-fA-F]{8}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
```

The ngrok command is:

```python
[
    "ngrok",
    "http",
    "http://localhost:3001",
    "--url",
    f"https://{domain}",
    "--authtoken",
    token,
    "--host-header",
    "rewrite",
]
```

If `NGROK_AUTHTOKEN` is absent, omit only the two authtoken arguments so ngrok can use
its local authenticated config. Validate the domain as a hostname and never include the
token in printed output.

- [ ] **Step 4: Implement command execution and wrappers**

The Python CLI:

- obtains Tailscale JSON using `tailscale status --json`;
- checks `http://localhost:3000/api/health` before `tailscale serve`;
- checks `http://localhost:3001/healthz` before ngrok;
- prints the share URL, then runs ngrok in the foreground;
- prints credential-safe exception types on failure.

PowerShell wrappers contain only:

```powershell
$repoRoot = Split-Path -Parent $PSScriptRoot
& "$repoRoot\.venv\Scripts\python.exe" "$repoRoot\scripts\metabase_access.py" tailnet
exit $LASTEXITCODE
```

and the equivalent `public-dashboard` subcommand.

- [ ] **Step 5: Verify and commit**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/test_metabase_access.py -v
.venv\Scripts\python.exe -m ruff check scripts/metabase_access.py tests/unit/test_metabase_access.py
git branch --show-current
git add -- scripts/metabase_access.py scripts/start_metabase_tailnet.ps1 scripts/start_public_dashboard_tunnel.ps1 tests/unit/test_metabase_access.py
git commit -m "Add restricted Metabase access launchers"
```

---

### Task 5: Deploy locally and verify security boundaries

**Files:**
- Modify only if verification finds a tested defect:
  - `config/metabase-public-nginx.conf`
  - `src/metabase/bootstrap.py`
  - `scripts/metabase_access.py`
  - their corresponding tests
- Modify: `docs/metabase-self-host.md`

**Interfaces:**
- Consumes all previous tasks and runtime environment variables.
- Produces a healthy local Metabase stack and reviewed warehouse connection.

- [ ] **Step 1: Run the complete automated suite**

```powershell
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m compileall -q src scripts
```

Expected: all commands exit 0.

- [ ] **Step 2: Check runtime prerequisites without printing values**

```powershell
$names = @(
  "VWDP_POSTGRES_PASSWORD",
  "LOCAL_DATABASE_URL",
  "METABASE_DB_PASSWORD",
  "METABASE_ENCRYPTION_SECRET_KEY",
  "METABASE_WAREHOUSE_PASSWORD",
  "METABASE_ADMIN_EMAIL",
  "METABASE_ADMIN_PASSWORD",
  "METABASE_ADMIN_FIRST_NAME",
  "METABASE_ADMIN_LAST_NAME"
)
$names | ForEach-Object {
  [pscustomobject]@{ Name = $_; Set = [bool](Get-Item "Env:$_" -ErrorAction SilentlyContinue) }
}
```

If any are absent, do not fabricate or persist them. Complete code verification and
report the exact missing variable names as the runtime blocker.

- [ ] **Step 3: Start and inspect services when prerequisites exist**

```powershell
docker compose up -d postgres metabase-db metabase metabase-public-gateway
docker compose ps postgres metabase-db metabase metabase-public-gateway
.venv\Scripts\python.exe scripts\setup_metabase.py
```

Wait at most five minutes for Metabase migrations. Inspect `docker compose logs
--no-log-prefix --tail 100 metabase` only if health fails; do not print Compose-rendered
environment.

- [ ] **Step 4: Verify PostgreSQL privilege boundary**

Use SQLAlchemy with a URL assembled in process from the supplied reader password.
Verify:

```sql
select count(*) from analyst.dim_district;
```

succeeds and this transaction:

```sql
insert into analyst.dim_district
  (district_id, district_name, latitude, longitude)
values (-999, 'denied', 21.0, 105.8);
```

fails with `InsufficientPrivilege`. Roll back and verify district `-999` does not exist.

- [ ] **Step 5: Verify public gateway**

```powershell
Invoke-WebRequest http://localhost:3001/healthz -UseBasicParsing
```

Assert HTTP 404 for:

```text
/
/auth/login
/admin
/api/user/current
```

After creating one disposable public dashboard through the Metabase UI/API, verify its
public path and `/api/public/*` requests pass. Remove the disposable public link after
testing.

- [ ] **Step 6: Configure Tailscale when authenticated**

If `tailscale status --json` reports `Running`, execute:

```powershell
scripts\start_metabase_tailnet.ps1
tailscale serve status
```

If it reports `NoState`, stop this runtime step and report that `tailscale up` requires
interactive user authentication.

- [ ] **Step 7: Start ngrok only when its runtime values and a dashboard path exist**

```powershell
scripts\start_public_dashboard_tunnel.ps1
```

This is intentionally foreground and long-running. Report the public share URL without
any token. If the user has not yet created a dashboard/public link, do not create a
meaningless tunnel.

- [ ] **Step 8: Run manual cloud synchronization only with the rotated URL**

Confirm `CLOUD_DATABASE_URL` and `LOCAL_DATABASE_URL` are present without printing them,
then run:

```powershell
.venv\Scripts\python.exe scripts\sync_cloud_to_local.py
```

Do not substitute the old credential exposed earlier. If the rotated cloud variable is
absent, report the blocker and leave existing local data unchanged.

- [ ] **Step 9: Review local row counts**

Query exact local counts:

```sql
select count(*) from analyst.dim_district;
select count(*) from analyst.dim_date;
select count(*) from analyst.dim_hour;
select count(*) from analyst.fact_weather_daily;
select count(*) from analyst.fact_weather_hourly;
select count(*) from analyst.fact_aqi_hourly;
```

Report counts only, never connection details.

- [ ] **Step 10: Commit verification-driven documentation or fixes**

```powershell
git branch --show-current
git add -- docs/metabase-self-host.md config/metabase-public-nginx.conf src/metabase/bootstrap.py scripts/metabase_access.py tests/unit/test_metabase_bootstrap.py tests/unit/test_metabase_access.py
git commit -m "Verify local Metabase deployment"
```

Stage only paths actually modified by verification. Do not stage `.codebase-memory/*`
or `.gitignore`.
