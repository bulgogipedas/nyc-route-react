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

- `month`: optional `YYYY-MM`; defaults to the latest available TLC month discovered from the official Parquet URLs.
- `services`: list of supported services.
- `overwrite`: redownload existing bronze files when true.
- `download_only`: download available bronze files and reference data, then skip transform/gold/frontend export.
- `require_all_services`: when true, automatic latest-month discovery only selects a month where every requested service is available.

## Design Rule

Airflow orchestrates reusable Python modules only. Ingestion, validation, transformation, aggregation, and export logic live in `src/chronoroute_pipeline`.

The DAG downloads TLC Parquet files automatically into `data/bronze/{service}/YYYY-MM.parquet`; no browser/manual download step is required.

## Troubleshooting

- If no TLC files are available for the target month, the pipeline skips gracefully.
- If one service is unavailable, other available services continue.
- Check `airflow/logs` for task summaries and service availability results.
