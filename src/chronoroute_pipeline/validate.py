"""Lightweight validation checks for ChronoRoute pipeline layers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from .config import GOLD_DIR, PUBLIC_DATA_DIR, SILVER_DIR
from .schema import BASE_REQUIRED_CANONICAL, CANONICAL_COLUMNS, required_source_columns
from .tlc_source import get_expected_bronze_path, validate_service_type


def _result(layer: str, path: Path, ok: bool, checks: list[str], errors: list[str]) -> dict[str, Any]:
    return {"layer": layer, "path": str(path), "ok": ok, "checks": checks, "errors": errors}


def _literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def validate_raw_month(service_type: str, year: int, month: int) -> dict[str, Any]:
    service = validate_service_type(service_type)
    path = get_expected_bronze_path(service, year, month)
    checks: list[str] = []
    errors: list[str] = []
    if not path.exists():
        return _result("bronze", path, False, checks, [f"Missing bronze file: {path}"])
    checks.append("file_exists")
    try:
        con = duckdb.connect()
        columns = [row[0] for row in con.sql(f"DESCRIBE SELECT * FROM read_parquet({_literal(str(path))})").fetchall()]
        row_count = con.sql(f"SELECT COUNT(*) FROM read_parquet({_literal(str(path))})").fetchone()[0]
        con.close()
    except Exception as exc:  # noqa: BLE001
        return _result("bronze", path, False, checks, [f"Unable to read parquet: {exc}"])
    checks.append("readable_parquet")
    if row_count == 0:
        errors.append("Raw file has zero rows.")
    else:
        checks.append("row_count_positive")
    missing = required_source_columns(service, columns)
    if missing:
        errors.append(f"Missing required source columns: {', '.join(missing)}")
    else:
        checks.append("required_columns_present")
    return _result("bronze", path, not errors, checks, errors)


def validate_silver_month(service_type: str, year: int, month: int) -> dict[str, Any]:
    service = validate_service_type(service_type)
    month_id = f"{int(year):04d}-{int(month):02d}"
    path = SILVER_DIR / service / f"{month_id}_cleaned.parquet"
    checks: list[str] = []
    errors: list[str] = []
    if not path.exists():
        return _result("silver", path, False, checks, [f"Missing silver file: {path}"])
    checks.append("file_exists")
    con = duckdb.connect()
    columns = [row[0] for row in con.sql(f"DESCRIBE SELECT * FROM read_parquet({_literal(str(path))})").fetchall()]
    row_count = con.sql(f"SELECT COUNT(*) FROM read_parquet({_literal(str(path))})").fetchone()[0]
    checks.append("readable_parquet")
    if row_count == 0:
        errors.append("Silver file has zero rows.")
    else:
        checks.append("row_count_positive")
    missing = [column for column in BASE_REQUIRED_CANONICAL if column not in columns]
    if missing:
        errors.append(f"Missing canonical columns: {', '.join(missing)}")
    else:
        checks.append("canonical_required_columns_present")
    if not set(CANONICAL_COLUMNS).issubset(columns):
        errors.append("Not all canonical columns are present.")
    if "pickup_datetime" in columns and con.sql(f"SELECT COUNT(*) FROM read_parquet({_literal(str(path))}) WHERE pickup_datetime IS NULL").fetchone()[0] > 0:
        errors.append("pickup_datetime contains nulls.")
    if "duration_minutes" in columns:
        if con.sql(f"SELECT COUNT(*) FROM read_parquet({_literal(str(path))}) WHERE duration_minutes IS NOT NULL AND duration_minutes <= 0").fetchone()[0] > 0:
            errors.append("duration_minutes contains non-positive values.")
    con.close()
    return _result("silver", path, not errors, checks, errors)


def validate_gold_month(month: str, services: list[str]) -> dict[str, Any]:
    checks: list[str] = []
    errors: list[str] = []
    for service in services:
        validate_service_type(service)
        service_dir = GOLD_DIR / service
        expected = [
            service_dir / f"zone_hour_metrics_{month}.parquet",
            service_dir / f"od_zone_hour_{month}.parquet",
            service_dir / f"monthly_kpi_{month}.json",
        ]
        for path in expected:
            if not path.exists():
                errors.append(f"Missing gold artifact: {path}")
                continue
            checks.append(f"exists:{path.name}")
            if path.suffix == ".parquet" and len(pd.read_parquet(path)) == 0:
                errors.append(f"Gold parquet has zero rows: {path}")
            if path.suffix == ".json":
                payload = json.loads(path.read_text())
                for key in ("month", "service_type", "total_trips", "generated_at"):
                    if key not in payload:
                        errors.append(f"Missing key {key} in {path}")
    metadata_path = PUBLIC_DATA_DIR / "metadata.json"
    if metadata_path.exists():
        payload = json.loads(metadata_path.read_text())
        for key in ("project", "source", "available_services", "layers", "artifacts"):
            if key not in payload:
                errors.append(f"Missing metadata key: {key}")
        checks.append("metadata_json_present")
    return _result("gold", GOLD_DIR / "all_services", not errors, checks, errors)
