# Metabase Self-Host and ngrok Sharing Design

## Goal

Run Metabase inside this project and connect it to the local `vwdp` PostgreSQL warehouse
with a read-only account. Trusted members build dashboards through a tailnet-only
Tailscale endpoint. An ngrok HTTPS endpoint exposes only explicitly published,
view-only dashboards to anyone who has a public dashboard link.

The cloud-to-local synchronization remains manually invoked. PostgreSQL itself is never
published through ngrok.

## Selected Approach

Use Docker Compose for Metabase, its private application database, and a restricted
public reverse proxy. Use the installed Windows Tailscale CLI for collaboration and the
installed Windows ngrok CLI for anonymous dashboard viewing.

This is preferred over:

1. Sending collaborators through ngrok. Tailscale reduces the public attack surface and
   gives members stable tailnet-only access to the complete application.
2. Pointing ngrok directly at Metabase. A restricted reverse proxy prevents the public
   endpoint from forwarding login, admin, query-builder, and private API routes.
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
- Publishes only `127.0.0.1:3000`.
- Connects to `metabase-db:5432` through `MB_DB_*` environment variables.
- Uses `MB_SITE_URL` set to the Tailscale Serve HTTPS URL used by collaborators.
- Enables Metabase public sharing because anonymous ngrok dashboard links require it,
  while anonymous usage tracking remains disabled.
- Starts only after both PostgreSQL services are healthy.
- Exposes a healthcheck against `/api/health`.

### `metabase-public-gateway`

- Image: `nginx:1.29-alpine`.
- Publishes only `127.0.0.1:3001`.
- Proxies to `metabase:3000`.
- Allows the public-dashboard page, Metabase public dashboard/card API, and static asset
  routes required to render that page.
- Returns `404` for `/`, `/auth/*`, `/admin/*`, non-public API routes, query-builder
  routes, and every other path.
- Adds no authentication: knowledge of the unguessable Metabase public dashboard URL is
  the access mechanism selected by the user.

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
- `METABASE_ENCRYPTION_SECRET_KEY`
- `METABASE_WAREHOUSE_PASSWORD`
- `METABASE_ADMIN_EMAIL`
- `METABASE_ADMIN_PASSWORD`
- `METABASE_ADMIN_FIRST_NAME`
- `METABASE_ADMIN_LAST_NAME`
- `METABASE_SITE_URL`

No real values are written to `.env`, `.env.example`, Git, logs, or command output.
`.env.example` receives placeholder names only.
`METABASE_ENCRYPTION_SECRET_KEY` must be a random base64 value of at least 16 characters
and is passed to Metabase as `MB_ENCRYPTION_SECRET_KEY` so stored warehouse credentials
are encrypted at rest.

## Tailscale Collaboration Access

`scripts/start_metabase_tailnet.ps1` validates that Tailscale is authenticated and then
runs:

```powershell
tailscale serve --bg --yes 3000
```

Tailscale Serve provides a stable tailnet-only HTTPS URL for the complete Metabase
application. Each trusted member joins the tailnet and signs in with an individual
Metabase account. The current machine has Tailscale 1.98.8 installed, but its current
backend state is `NoState`; the user must complete `tailscale up` before this launcher
can succeed.

## ngrok Public Dashboard Access

`scripts/start_public_dashboard_tunnel.ps1` runs the installed ngrok CLI in the
foreground.
It requires:

- `NGROK_AUTHTOKEN`, unless the local ngrok config is already authenticated;
- `NGROK_DOMAIN`, containing the account's assigned development domain;
- `METABASE_PUBLIC_DASHBOARD_PATH`, exactly one Metabase path in the form
  `/public/dashboard/{dashboard-uuid}`.

The launcher:

- confirms the restricted gateway is healthy;
- rejects paths outside `/public/dashboard/`;
- forwards `https://${NGROK_DOMAIN}` only to `http://localhost:3001`;
- prints the complete share URL by combining the ngrok domain with the validated
  dashboard path;
- never starts a TCP tunnel and never exposes port `5433`;
- stays in the foreground so closing it immediately removes public access.

Anonymous viewers do not receive Metabase accounts. Anyone who obtains the share URL can
view that published dashboard, so the admin must remove its Metabase public link to
revoke access.

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
Metabase :3000 ---- Tailscale Serve HTTPS ---- Trusted collaborators
        |
        v
restricted gateway :3001 ---- ngrok HTTPS ---- Anonymous dashboard viewers
```

Metabase application state follows a separate path:

```text
Metabase -> metabase-db:5432 -> metabase_app_data volume
```

## Manual Operation

The normal sequence is:

1. Export the required local/Metabase/ngrok variables in PowerShell.
2. Run `docker compose up -d postgres metabase-db metabase metabase-public-gateway`.
3. Run `.venv\Scripts\python.exe scripts\setup_metabase.py`.
4. Run `.venv\Scripts\python.exe scripts\sync_cloud_to_local.py` whenever fresh cloud
   data is required.
5. After `tailscale up`, run `scripts\start_metabase_tailnet.ps1` for collaborators.
6. Publish a selected dashboard in Metabase, export its path as
   `METABASE_PUBLIC_DASHBOARD_PATH`, then run
   `scripts\start_public_dashboard_tunnel.ps1`.

The synchronization is not scheduled and ngrok is not installed as a Windows service.

## Error Handling and Safety

- All commands fail before mutation when required variables are missing.
- Database URLs and passwords are never included in errors or summaries.
- The bootstrap refuses a warehouse URL whose host is not `localhost`, `127.0.0.1`, or
  `::1`.
- A failed Metabase API request does not change warehouse facts.
- A failed cloud sync does not stop Metabase; dashboards keep showing the last
  successfully synchronized local data.
- Public sharing is intentionally enabled. The gateway prevents ngrok from forwarding
  the full Metabase interface, but the dashboard remains accessible to anyone with its
  public URL.
- The existing Tiki container/database and the user's unrelated dirty files remain
  untouched.

## Verification

Automated tests cover:

- required-variable validation and credential-safe errors;
- local-host guard;
- read-only role SQL and identifier safety;
- first-run and rerun Metabase API behavior;
- exact warehouse connection details;
- Tailscale authentication-state and Serve command validation;
- ngrok dashboard-path validation;
- restricted gateway allow/deny behavior.

Runtime verification covers:

- `docker compose config --quiet`;
- both PostgreSQL services and Metabase healthy;
- `metabase_reader` can `SELECT` analyst tables but cannot `INSERT`;
- Metabase `/api/health` returns healthy;
- Metabase lists `VWDP Local Warehouse`;
- Tailscale Serve exposes the full app only inside the tailnet;
- the ngrok dashboard URL renders anonymously while `/`, `/auth/login`, `/admin`, and
  private API endpoints return `404`;
- the existing cloud sync command completes and local analyst row counts are reviewed.

The real Supabase sync and public ngrok test can run only after the rotated cloud URL,
ngrok token/domain, selected public dashboard path, and Metabase credentials are
available in the current environment. Tailscale collaboration also requires the local
client to be authenticated.
