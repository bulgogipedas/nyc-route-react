"""Monthly ChronoRoute TLC pipeline DAG."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from airflow.decorators import dag, task

SRC_DIR = Path("/opt/airflow/src")
if SRC_DIR.exists() and str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from chronoroute_pipeline.aggregate import generate_combined_service_metrics, generate_gold_for_service
from chronoroute_pipeline.config import SUPPORTED_SERVICES
from chronoroute_pipeline.export import export_frontend_artifacts
from chronoroute_pipeline.ingest import download_month
from chronoroute_pipeline.tlc_source import check_tlc_file_available
from chronoroute_pipeline.transform import clean_month
from chronoroute_pipeline.validate import validate_gold_month, validate_raw_month, validate_silver_month


def _previous_calendar_month(logical_date: datetime) -> str:
    year = logical_date.year
    month = logical_date.month - 1
    if month == 0:
        year -= 1
        month = 12
    return f"{year:04d}-{month:02d}"


def _split_month(month: str) -> tuple[int, int]:
    year, month_num = month.split("-")
    return int(year), int(month_num)


@dag(
    dag_id="chronoroute_monthly_pipeline",
    schedule="0 6 5 * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["chronoroute", "nyc-tlc", "geospatial"],
    params={"month": "", "services": list(SUPPORTED_SERVICES), "overwrite": False},
)
def chronoroute_monthly_pipeline():
    @task
    def determine_target_month(**context) -> str:
        requested = context["params"].get("month")
        return requested or _previous_calendar_month(context["logical_date"])

    @task
    def determine_services(**context) -> list[str]:
        requested = context["params"].get("services") or list(SUPPORTED_SERVICES)
        return [service for service in requested if service in SUPPORTED_SERVICES]

    @task
    def check_availability_per_service(month: str, services: list[str]) -> list[str]:
        year, month_num = _split_month(month)
        available = []
        for service in services:
            if check_tlc_file_available(service, year, month_num):
                available.append(service)
        return available

    @task
    def download_available_services(month: str, services: list[str], **context) -> list[dict]:
        year, month_num = _split_month(month)
        overwrite = bool(context["params"].get("overwrite", False))
        return [download_month(service, year, month_num, overwrite=overwrite) for service in services]

    @task
    def validate_raw_per_service(month: str, services: list[str]) -> list[dict]:
        year, month_num = _split_month(month)
        return [validate_raw_month(service, year, month_num) for service in services]

    @task
    def transform_to_silver_per_service(month: str, services: list[str]) -> list[dict]:
        year, month_num = _split_month(month)
        return [clean_month(service, year, month_num) for service in services]

    @task
    def validate_silver_per_service(month: str, services: list[str]) -> list[dict]:
        year, month_num = _split_month(month)
        return [validate_silver_month(service, year, month_num) for service in services]

    @task
    def generate_gold_per_service(month: str, services: list[str]) -> list[dict]:
        year, month_num = _split_month(month)
        return [generate_gold_for_service(service, year, month_num) for service in services]

    @task
    def generate_combined_service_metrics_task(month: str, services: list[str]) -> dict:
        return generate_combined_service_metrics(month, services)

    @task
    def validate_gold(month: str, services: list[str]) -> dict:
        return validate_gold_month(month, services)

    @task
    def export_frontend_artifacts_task(month: str, services: list[str]) -> dict:
        return export_frontend_artifacts([month], services)

    @task
    def summarize(month: str, requested_services: list[str], available_services: list[str]) -> dict:
        skipped = sorted(set(requested_services) - set(available_services))
        return {
            "target_month": month,
            "requested_services": requested_services,
            "available_services": available_services,
            "skipped_services": skipped,
            "processed_services": available_services,
            "failed_services": [],
        }

    month = determine_target_month()
    services = determine_services()
    available = check_availability_per_service(month, services)
    download_available_services(month, available)
    validate_raw_per_service(month, available)
    transform_to_silver_per_service(month, available)
    validate_silver_per_service(month, available)
    generate_gold_per_service(month, available)
    generate_combined_service_metrics_task(month, available)
    validate_gold(month, available)
    export_frontend_artifacts_task(month, available)
    summarize(month, services, available)


chronoroute_monthly_pipeline()
