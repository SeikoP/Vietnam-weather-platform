# Metabase Self-Host and ngrok Sharing Design

## Goal

Run Metabase inside this project, connect it to the local `vwdp` PostgreSQL warehouse
with a read-only account, and share the Metabase web application with two trusted
members through an ngrok HTTPS endpoint protected by OAuth.

The cloud-to-local synchronization remains manually invoked. PostgreSQL itself is never
published through ngrok.

## Selected Approach

Use Docker Compose for Metabase and its private application database, and use the
already-installed Windows ngrok CLI for the public tunnel.

This is preferred over:

1. Running ngrok as another Compose service. A container makes a dynamic, per-email
   OAuth allowlist and local credential management more awkward.
2. Using Metabase public links. Public links do not authenticate viewers and cannot
   safely enforce hidden filter values.
3. Exposing PostgreSQL directly. That expands the attack surface and bypasses Metabase
   permissions.

## Components

### `metabase-db`

- Image: `postgres:17-alpine`.
- Stores only Metabase application state: users, sessions, questions, collections, and
  dashboards.
- Uses database/user `metabase`.
- Requires `METABASE_DB_PASSWORD` from the invoking PowerShell environment.
- Has a named persistent volume.
- Is reachable only on the Compose network; it has no host port.

### `metabase`

- Image: `metabase/metabase:v0.63.1`, the latest non-prerelease release verified from
  the official GitHub repository on 2026-07-28.
- Publishes `localhost:3000`.
- Connects to `metabase-db:5432` through `MB_DB_*` environment variables.
- Uses `MB_SITE_URL`, supplied as `http://localhost:3000` for local-only use or the
  stable ngrok HTTPS URL when sharing.
- Disables public sharing and anonymous usage tracking through environment settings.
- Starts only after both PostgreSQL services are healthy.
- Exposes a healthcheck against `/api/health`.

### Warehouse role

An idempotent Python bootstrap command creates or updates `metabase_reader` in the local
warehouse:

- `LOGIN` with the password supplied through `METABASE_WAREHOUSE_PASSWORD`;
- `CONNECT` on database `vwdp`;
- `USAGE` on schema `analyst`;
- `SELECT` on all existing `analyst` tables;
- default `SELECT` privileges for analyst tables created later;
- no write, DDL, monitoring-schema, or superuser privilege.

The command connects with `LOCAL_DATABASE_URL`, which must refer to the local writable
`vwdp` database. It validates that the endpoint is local before executing role DDL.

### Metabase bootstrap

`scripts/setup_metabase.py` is safe to rerun:

1. Validate required environment variables without printing their values.
2. Provision the warehouse read-only role.
3. Wait for `http://localhost:3000/api/health`.
4. If Metabase is new, read its setup token and call `/api/setup` to create the first
   admin and the `VWDP Local Warehouse` PostgreSQL connection.
5. If Metabase is already initialized, authenticate with the supplied admin account and
   create the warehouse connection only when it is missing.
6. Verify the database appears in Metabase and that its connection details use
   `postgres:5432`, database `vwdp`, and user `metabase_reader`.

Required runtime variables:

- `LOCAL_DATABASE_URL`
- `METABASE_DB_PASSWORD`
- `METABASE_WAREHOUSE_PASSWORD`
- `METABASE_ADMIN_EMAIL`
- `METABASE_ADMIN_PASSWORD`
- `METABASE_ADMIN_FIRST_NAME`
- `METABASE_ADMIN_LAST_NAME`
- `METABASE_SITE_URL`

No real values are written to `.env`, `.env.example`, Git, logs, or command output.
`.env.example` receives placeholder names only.

## ngrok Access

`scripts/start_metabase_tunnel.ps1` runs the installed ngrok CLI in the foreground.
It requires:

- `NGROK_AUTHTOKEN`, unless the local ngrok config is already authenticated;
- `NGROK_DOMAIN`, containing the account's assigned development domain;
- `NGROK_OAUTH_ALLOW_EMAILS`, a comma-separated list of exact member emails;
- optional `NGROK_OAUTH_PROVIDER`, defaulting to `google`.

The launcher:

- confirms Metabase health before starting;
- rejects an empty email allowlist;
- invokes one `--oauth-allow-email` flag per normalized email;
- forwards only `https://${NGROK_DOMAIN}` to `http://localhost:3000`;
- never starts a TCP tunnel and never exposes port `5433`;
- stays in the foreground so closing it immediately removes public access.

Each member passes ngrok OAuth and then signs into their own Metabase account. The admin
creates/invites member accounts through the Metabase UI; no shared admin account is
created by automation.

## Data Flow

```text
Supabase PostgreSQL
        |
        | manual scripts/sync_cloud_to_local.py
        v
vwdp-postgres / analyst schema
        |
        | SELECT as metabase_reader (Docker network only)
        v
Metabase :3000
        |
        | ngrok HTTPS + exact-email OAuth
        v
Trusted members
```

Metabase application state follows a separate path:

```text
Metabase -> metabase-db:5432 -> metabase_app_data volume
```

## Manual Operation

The normal sequence is:

1. Export the required local/Metabase/ngrok variables in PowerShell.
2. Run `docker compose up -d postgres metabase-db metabase`.
3. Run `.venv\Scripts\python.exe scripts\setup_metabase.py`.
4. Run `.venv\Scripts\python.exe scripts\sync_cloud_to_local.py` whenever fresh cloud
   data is required.
5. Run `scripts\start_metabase_tunnel.ps1` and leave that terminal open while sharing.

The synchronization is not scheduled and ngrok is not installed as a Windows service.

## Error Handling and Safety

- All commands fail before mutation when required variables are missing.
- Database URLs and passwords are never included in errors or summaries.
- The bootstrap refuses a warehouse URL whose host is not `localhost`, `127.0.0.1`, or
  `::1`.
- A failed Metabase API request does not change warehouse facts.
- A failed cloud sync does not stop Metabase; dashboards keep showing the last
  successfully synchronized local data.
- Public sharing stays disabled even though the ngrok endpoint has OAuth.
- The existing Tiki container/database and the user's unrelated dirty files remain
  untouched.

## Verification

Automated tests cover:

- required-variable validation and credential-safe errors;
- local-host guard;
- read-only role SQL and identifier safety;
- first-run and rerun Metabase API behavior;
- exact warehouse connection details;
- ngrok launcher validation and repeated email flags.

Runtime verification covers:

- `docker compose config --quiet`;
- both PostgreSQL services and Metabase healthy;
- `metabase_reader` can `SELECT` analyst tables but cannot `INSERT`;
- Metabase `/api/health` returns healthy;
- Metabase lists `VWDP Local Warehouse`;
- ngrok endpoint rejects a non-allowlisted identity and accepts an allowlisted identity
  when credentials are supplied;
- the existing cloud sync command completes and local analyst row counts are reviewed.

The real Supabase sync and public ngrok test can run only after the rotated cloud URL,
ngrok token/domain, OAuth email allowlist, and Metabase credentials are available in the
current environment.
