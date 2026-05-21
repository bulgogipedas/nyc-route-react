# Airflow Orchestration

The DAG `chronoroute_monthly_pipeline` runs monthly on the 5th day and defaults to the previous calendar month.

## Local Run

```bash
podman compose -f docker-compose.airflow.yml up
```

Open `http://localhost:8080`.

Default login:

```text
airflow / airflow
```

## DAG Params

- `month`: optional `YYYY-MM`; defaults to previous calendar month.
- `services`: list of supported services.
- `overwrite`: redownload existing bronze files when true.

## Design Rule

Airflow orchestrates reusable Python modules only. Ingestion, validation, transformation, aggregation, and export logic live in `src/chronoroute_pipeline`.

## Troubleshooting

- If no TLC files are available for the target month, the pipeline skips gracefully.
- If one service is unavailable, other available services continue.
- Check `airflow/logs` for task summaries and service availability results.
