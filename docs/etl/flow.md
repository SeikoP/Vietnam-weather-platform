# ETL Flow

1. Extract Open-Meteo data by province and date range.
2. Validate coordinates and weather measures.
3. Transform Open-Meteo arrays into normalized records.
4. Load records with PostgreSQL upsert semantics.
5. Verify affected row counts and log rejected records.
6. Commit only after a province batch succeeds.

Historical backfill starts at `2023-06-01`. Incremental daily runs load through yesterday to avoid partial current-day data.
