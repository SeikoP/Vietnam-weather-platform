# Architecture Overview

VWDP is organized as a layered data platform:

1. Open-Meteo extractors collect historical and forecast data.
2. ETL validators reject impossible values and persist validation errors.
3. Transformers normalize API payloads into typed domain records.
4. Loaders upsert records into Supabase PostgreSQL warehouse tables.
5. FastAPI exposes curated warehouse data to applications.
6. Power BI connects directly to PostgreSQL star schema tables and analytics views.

The current implementation focuses on the first production slice: daily historical weather, 63-province dimension data, warehouse schema, monitoring tables, and API scaffolding.
