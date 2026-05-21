# ChronoRoute Airflow

This folder contains the monthly orchestration layer for the ChronoRoute TLC pipeline.

The DAG imports reusable modules from `src/chronoroute_pipeline`; it should not contain heavy transformation logic.

Run locally:

```bash
podman compose -f docker-compose.airflow.yml up
```

UI: `http://localhost:8080`

Login: `airflow` / `airflow`
