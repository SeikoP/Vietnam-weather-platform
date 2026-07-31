# Repository Guidelines

## Project Structure & Module Organization

This repository is a Python data platform for Hanoi weather and AQI data. Core source code lives in `src/`. Database models and migrations are in `src/database/`, ETL components are in `src/etl/`, and R2 publishing code is in `src/r2/`.

Operational scripts live in `scripts/`. Tests live under `tests/unit/`. Alembic migrations are stored in `src/database/migrations/versions/`.

## Build, Test, and Development Commands

- `poetry install`: install runtime and development dependencies.
- `poetry run pytest`: run the full test suite.
- `poetry run ruff check .`: lint imports, style, bug-prone patterns, and modernization rules.
- `poetry run black .`: format Python files with the repository line length.
- `poetry run alembic upgrade head`: apply database migrations.
- `poetry run vwdp-etl --run-type incremental-daily`: run an ETL mode through the CLI.

## Coding Style & Naming Conventions

Use Python 3.13 syntax. Format with Black using a 100-character line length. Ruff enforces `E`, `F`, `I`, `B`, `UP`, and `SIM` rules, so keep imports sorted, remove unused code, and prefer modern Python idioms.

Use `snake_case` for modules, functions, variables, and database-oriented fields. Use `PascalCase` for classes and Pydantic models. Keep API route modules focused by resource, for example `districts.py` and `weather.py`.

## Testing Guidelines

Use pytest. Place unit tests in `tests/unit/`. Name test files `test_*.py` and test functions `test_*`.

When changing ETL logic, cover transformer, validator, loader, or CLI behavior as appropriate. Run `poetry run pytest` before opening a PR.

## Commit & Pull Request Guidelines

Recent commits use short imperative subjects, for example `Add district AQI ETL flow` and `Fix rows_loaded: use len(records) instead of rowcount for upsert`. Keep subjects concise and focused on one change.

Pull requests should include a clear summary, verification commands run, and any database migration or operational impact. Link related issues when available. Include screenshots only for user-facing visual changes.

## Security & Configuration Tips

Do not commit `.env`, credentials, database URLs, tokens, or local password files. Use `.env.example` for documented configuration only. Treat migrations and seed scripts as production-impacting changes; review schema names, constraints, and idempotency before merging.
