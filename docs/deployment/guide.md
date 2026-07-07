# Deployment Guide

1. Create a Supabase project.
2. Store the direct PostgreSQL connection string in `DATABASE_URL`.
3. Run `poetry run alembic upgrade head`.
4. Run `poetry run python scripts/seed_provinces.py`.
5. Configure GitHub Actions secrets:
   - `DATABASE_URL`
   - `DISCORD_WEBHOOK_URL` only when notifications are enabled later.
6. Keep `DISCORD_NOTIFICATIONS_ENABLED=false` until failure notifications are approved.
