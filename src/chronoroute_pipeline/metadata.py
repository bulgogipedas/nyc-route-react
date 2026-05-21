"""Metadata generation for frontend and pipeline observability."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from .config import PIPELINE_VERSION, PROJECT_NAME, PUBLIC_DATA_DIR, TLC_SOURCE_NAME


def discover_artifacts(public_data_dir: Path = PUBLIC_DATA_DIR) -> list[dict[str, str | int]]:
    if not public_data_dir.exists():
        return []
    artifacts = []
    for path in sorted(public_data_dir.iterdir()):
        if path.is_file():
            artifacts.append({"name": path.name, "path": f"/data/{path.name}", "bytes": path.stat().st_size})
    return artifacts


def build_metadata(available_months_by_service: dict[str, list[str]], artifacts: list[dict[str, str | int]] | None = None) -> dict:
    available_services = [service for service, months in available_months_by_service.items() if months]
    return {
        "project": PROJECT_NAME,
        "source": TLC_SOURCE_NAME,
        "generated_at": datetime.now(UTC).isoformat(),
        "pipeline_version": PIPELINE_VERSION,
        "available_services": available_services,
        "available_months_by_service": available_months_by_service,
        "layers": {
            "bronze": "Raw TLC parquet files",
            "silver": "Cleaned normalized trip records",
            "gold": "Dashboard-ready analytics aggregates",
        },
        "airflow": {
            "dag_id": "chronoroute_monthly_pipeline",
            "schedule": "monthly",
        },
        "artifacts": artifacts if artifacts is not None else discover_artifacts(),
    }


def write_metadata(available_months_by_service: dict[str, list[str]], output_path: Path = PUBLIC_DATA_DIR / "metadata.json") -> dict:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    metadata = build_metadata(available_months_by_service)
    output_path.write_text(json.dumps(metadata, indent=2))
    return metadata
