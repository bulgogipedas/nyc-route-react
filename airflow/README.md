# ChronoRoute Airflow

This folder contains the monthly orchestration layer for the ChronoRoute TLC pipeline.

The DAG imports reusable modules from `src/chronoroute_pipeline`; it should not contain heavy transformation logic.

The monthly DAG downloads TLC Parquet files automatically into the mounted `data/bronze` folder before validation and transformation. Set `download_only=true` in DAG params when you only want to populate bronze files.

Run locally:

```bash
podman compose -f docker-compose.airflow.yml up
```

UI: `http://localhost:8080`

Login: `airflow` / `airflow`
