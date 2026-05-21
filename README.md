# ChronoRoute

ChronoRoute is an end-to-end geospatial data engineering and analytics platform for analyzing NYC taxi and for-hire vehicle mobility patterns across Yellow Taxi, Green Taxi, FHV, and High Volume FHV trip records.

The current frontend remains a browser-based Manhattan mobility dashboard powered by DuckDB-WASM, Deck.gl, MapLibre, H3, and precomputed TLC-derived artifacts. The project now also includes a reusable batch pipeline, Airflow orchestration, bronze/silver/gold data layers, validation checks, and a data science foundation for forecasting, repositioning recommendations, and simulation.

## Problem

NYC TLC trip records are large monthly Parquet datasets with different schemas across services. A useful mobility product needs to ingest them reliably, normalize the fields that can be compared, validate data quality, and publish compact artifacts that remain fast enough for a static web deployment.

## Goal

ChronoRoute turns official TLC Parquet files into:

- Bronze raw monthly files.
- Silver canonical trip records.
- Gold analytics datasets for zone-hour activity, OD flows, service comparisons, and KPI summaries.
- Browser-ready public artifacts for the existing React dashboard.
- Lightweight data science outputs for forecasting and repositioning analysis.

## Architecture

```text
NYC TLC Parquet files
  -> data/bronze/{service}/YYYY-MM.parquet
  -> data/silver/{service}/YYYY-MM_cleaned.parquet
  -> data/gold/{service}/zone_hour_metrics_YYYY-MM.parquet
  -> data/gold/all_services/service_comparison_kpi_YYYY-MM.json
  -> public/data/* dashboard artifacts and metadata.json
```

Airflow orchestrates the monthly run. The DAG calls reusable Python modules under `src/chronoroute_pipeline`; transformation logic does not live inside the DAG.

## Multi-Service TLC Pipeline

Supported `service_type` values:

- `yellow`
- `green`
- `fhv`
- `fhvhv`

The source data comes from the official [NYC TLC Trip Record Data](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page) page. TLC publishes monthly Parquet files using these patterns:

```text
https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_YYYY-MM.parquet
https://d37ci6vzurychx.cloudfront.net/trip-data/green_tripdata_YYYY-MM.parquet
https://d37ci6vzurychx.cloudfront.net/trip-data/fhv_tripdata_YYYY-MM.parquet
https://d37ci6vzurychx.cloudfront.net/trip-data/fhvhv_tripdata_YYYY-MM.parquet
```

Yellow and Green taxi data have richer fare, passenger, and trip distance fields. FHV and HVFHV schemas differ, so cross-service comparisons should focus first on trip volume, time, location, and spatial flow. Fare comparisons may be incomplete or invalid across all services.

## Bronze, Silver, Gold

- Bronze stores raw TLC Parquet files and is ignored by git.
- Silver stores cleaned canonical records with normalized timestamps, location IDs, service type, day type, temporal segment, and duration.
- Gold stores dashboard-ready aggregates such as zone-hour metrics, OD zone-hour flows, monthly KPIs, combined service-hour metrics, and service comparison KPIs.

Optional reference data can be placed in `data/reference/taxi_zone_lookup.csv`. If it is present, the pipeline enriches LocationIDs with zone and borough labels. If it is missing, LocationID-based outputs still work.

## Airflow Monthly Orchestration

The DAG `chronoroute_monthly_pipeline` runs monthly on the 5th day to give TLC files time to appear. It defaults to the previous calendar month and supports manual params:

- `month`
- `services`
- `overwrite`

Run Airflow locally:

```bash
podman compose -f docker-compose.airflow.yml up
```

Open `http://localhost:8080` and log in with `airflow` / `airflow`.

## Data Quality Checks

Validation covers:

- Raw file existence, readability, row counts, and service-specific source columns.
- Silver canonical columns, timestamps, duration, month, hour, and service type.
- Gold artifact existence, non-empty outputs, and required JSON metadata keys.

Checks are intentionally lightweight and use pandas/pyarrow-compatible reads.

## Gold Analytics Datasets

Per-service outputs:

- `zone_hour_metrics_YYYY-MM.parquet`
- `od_zone_hour_YYYY-MM.parquet`
- `monthly_kpi_YYYY-MM.json`

Combined outputs:

- `service_hour_metrics_YYYY-MM.parquet`
- `service_zone_hour_metrics_YYYY-MM.parquet`
- `service_comparison_kpi_YYYY-MM.json`

The metrics include pickup/dropoff counts, total activity, average distance, average duration, average fare when available, pickup/dropoff ratio, normalized imbalance score, demand pressure index, and idle relocation opportunity score.

## Data Science Roadmap

The first data science layer is deliberately explainable:

- Baseline demand forecast using rolling/service-zone-hour averages.
- Repositioning recommendations from dropoff-surplus zones to pickup-pressure zones.
- Simple simulation for estimated imbalance reduction.
- MAE/RMSE evaluation helpers when actuals are available.

These outputs are not forced into the frontend yet.

## Running Locally

Install frontend dependencies:

```bash
bun install
```

Run the dashboard:

```bash
bun run dev
```

Build for production:

```bash
bun run build
```

Run pipeline checks:

```bash
python scripts/run_pipeline.py --month 2026-03 --services yellow green fhv fhvhv --check-only
```

Run a local batch pipeline:

```bash
python scripts/run_pipeline.py --month 2026-03 --services yellow
```

## Deployment

This remains a Vite static app and can be deployed to Vercel or Netlify.

Vercel:

- Framework preset: Vite
- Build command: `bun run build`
- Output directory: `dist`
- SPA rewrites and cache headers are configured in `vercel.json`.

Netlify:

- Build command: `bun run build`
- Publish directory: `dist`
- SPA redirects and cache headers are configured in `netlify.toml` and `public/_redirects`.

Do not hardcode temporary preview domains as canonical URLs. After the final domain is chosen, set a `SITE_URL` deployment variable and add sitemap/canonical generation.

## Future Roadmap

- Service-aware frontend filters once multi-service artifacts are generated.
- Borough/zone enrichment using the TLC taxi zone lookup.
- H3-based imbalance gold outputs for broader spatial modeling.
- GitHub Actions for frontend build, lint, and pipeline import checks.
- Google Search Console and final-domain SEO polish.
