# ChronoRoute Data Pipeline

ChronoRoute uses a batch-first data engineering layout so large TLC files are processed outside the browser and only compact artifacts are shipped with the static frontend.

## Layers

- Bronze: raw TLC Parquet files downloaded by service and month.
- Silver: cleaned canonical trip records with consistent column names and time features.
- Gold: aggregate datasets for dashboards, service comparison, and data science workflows.
- Public data: compact frontend artifacts and `metadata.json`.

## Monthly Flow

1. Build the TLC URL for each requested service and month.
2. Check file availability with HTTP HEAD and a lightweight GET fallback.
3. Download available services into `data/bronze/{service}/YYYY-MM.parquet`.
4. Validate raw files.
5. Normalize schemas into `data/silver/{service}/YYYY-MM_cleaned.parquet`.
6. Validate silver outputs.
7. Generate per-service and combined gold metrics.
8. Export frontend metadata while preserving the existing dashboard artifacts.

If a service is unavailable, the pipeline skips that service and continues with the available ones.

## No Manual Download Required

Use the CLI to download TLC Parquet files directly from the official CloudFront URLs:

```bash
python scripts/run_pipeline.py --start-month 2026-01 --end-month 2026-03 --services yellow green fhv fhvhv --download-only
```

The same download step is part of the Airflow DAG. Raw files land in `data/bronze/{service}/YYYY-MM.parquet` and remain ignored by git.

The CLI also downloads `data/reference/taxi_zone_lookup.csv` unless `--skip-reference-data` is provided.

To process the newest available TLC month without hardcoding the month:

```bash
python scripts/run_pipeline.py --latest-available --services yellow green fhv fhvhv
```
