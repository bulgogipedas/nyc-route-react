"""Export gold artifacts into frontend-compatible public data files."""

from __future__ import annotations

from pathlib import Path

from .config import GOLD_DIR, PUBLIC_DATA_DIR
from .metadata import write_metadata
from .tlc_source import validate_service_type


def export_frontend_artifacts(months: list[str], services: list[str]) -> dict:
    valid_services = [validate_service_type(service) for service in services]
    PUBLIC_DATA_DIR.mkdir(parents=True, exist_ok=True)

    available_months_by_service: dict[str, list[str]] = {service: [] for service in valid_services}
    copied: list[str] = []
    for service in valid_services:
        service_gold_dir = GOLD_DIR / service
        for month in months:
            if (service_gold_dir / f"monthly_kpi_{month}.json").exists():
                available_months_by_service[service].append(month)

    metadata = write_metadata(available_months_by_service)
    for filename in ("trip_paths.parquet", "months.json", "hourly_volume_by_month.json", "stats.json", "h3_deadhead.json", "od_flows.json"):
        path = PUBLIC_DATA_DIR / filename
        if path.exists():
            copied.append(str(path))
    return {"metadata": metadata, "preserved_frontend_artifacts": copied}


def list_public_artifacts(public_data_dir: Path = PUBLIC_DATA_DIR) -> list[str]:
    return [str(path) for path in sorted(public_data_dir.glob("*")) if path.is_file()]
