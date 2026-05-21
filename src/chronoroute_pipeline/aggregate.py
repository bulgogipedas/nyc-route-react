"""Gold analytics aggregations."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from .config import GOLD_DIR, SILVER_DIR
from .tlc_source import validate_service_type


def _safe_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    return numerator.where(denominator != 0, 0) / denominator.where(denominator != 0, 1)


def _json_default(value: Any) -> Any:
    if hasattr(value, "item"):
        return value.item()
    return value


def _silver_path(service_type: str, month: str) -> Path:
    return SILVER_DIR / validate_service_type(service_type) / f"{month}_cleaned.parquet"


def generate_gold_for_service(service_type: str, year: int, month: int) -> dict[str, Any]:
    service = validate_service_type(service_type)
    month_id = f"{int(year):04d}-{int(month):02d}"
    input_path = _silver_path(service, month_id)
    if not input_path.exists():
        raise FileNotFoundError(f"Missing silver file: {input_path}")
    df = pd.read_parquet(input_path)
    output_dir = GOLD_DIR / service
    output_dir.mkdir(parents=True, exist_ok=True)

    zone_col = "pickup_zone" if "pickup_zone" in df.columns else "pickup_location_id"
    dropoff_zone_col = "dropoff_zone" if "dropoff_zone" in df.columns else "dropoff_location_id"
    zone_keys = ["month", "service_type", "pickup_date", "day_of_week", "day_type", "temporal_segment", "pickup_hour", zone_col]

    pickup_counts = df.groupby(zone_keys, dropna=False).size().rename("pickup_count").reset_index()
    dropoff_keys = ["month", "service_type", "pickup_date", "day_of_week", "day_type", "temporal_segment", "pickup_hour", dropoff_zone_col]
    dropoff_counts = df.groupby(dropoff_keys, dropna=False).size().rename("dropoff_count").reset_index()
    dropoff_counts = dropoff_counts.rename(columns={dropoff_zone_col: zone_col})
    zone_metrics = pickup_counts.merge(dropoff_counts, on=zone_keys, how="outer").fillna({"pickup_count": 0, "dropoff_count": 0})
    zone_metrics = zone_metrics.rename(columns={"pickup_hour": "hour", zone_col: "pickup_zone" if zone_col == "pickup_zone" else "pickup_location_id"})
    zone_metrics["total_activity"] = zone_metrics["pickup_count"] + zone_metrics["dropoff_count"]
    detail_aggs = df.groupby(zone_keys, dropna=False).agg(
        avg_fare=("fare_amount", "mean"),
        avg_distance=("trip_distance", "mean"),
        avg_duration_minutes=("duration_minutes", "mean"),
    ).reset_index().rename(columns={"pickup_hour": "hour", zone_col: "pickup_zone" if zone_col == "pickup_zone" else "pickup_location_id"})
    zone_metrics = zone_metrics.merge(detail_aggs, on=list(detail_aggs.columns[:8]), how="left")
    zone_metrics["pickup_dropoff_ratio"] = _safe_ratio(zone_metrics["pickup_count"], zone_metrics["dropoff_count"])
    zone_metrics["normalized_imbalance_score"] = _safe_ratio(zone_metrics["pickup_count"] - zone_metrics["dropoff_count"], zone_metrics["total_activity"])
    zone_metrics["demand_pressure_index"] = (zone_metrics["pickup_count"] - zone_metrics["dropoff_count"]).clip(lower=0) * zone_metrics["normalized_imbalance_score"].clip(lower=0)
    zone_metrics["idle_relocation_opportunity_score"] = (zone_metrics["dropoff_count"] - zone_metrics["pickup_count"]).clip(lower=0) * (-zone_metrics["normalized_imbalance_score"]).clip(lower=0)

    od_keys = ["month", "service_type", "pickup_date", "day_type", "temporal_segment", "pickup_hour", zone_col, dropoff_zone_col]
    od_metrics = df.groupby(od_keys, dropna=False).agg(
        trip_count=("service_type", "size"),
        avg_fare=("fare_amount", "mean"),
        avg_distance=("trip_distance", "mean"),
        avg_duration_minutes=("duration_minutes", "mean"),
    ).reset_index().rename(columns={
        "pickup_hour": "hour",
        zone_col: "pickup_zone" if zone_col == "pickup_zone" else "pickup_location_id",
        dropoff_zone_col: "dropoff_zone" if dropoff_zone_col == "dropoff_zone" else "dropoff_location_id",
    })

    zone_path = output_dir / f"zone_hour_metrics_{month_id}.parquet"
    od_path = output_dir / f"od_zone_hour_{month_id}.parquet"
    kpi_path = output_dir / f"monthly_kpi_{month_id}.json"
    zone_metrics.to_parquet(zone_path, index=False)
    od_metrics.to_parquet(od_path, index=False)

    hourly = df.groupby("pickup_hour").size()
    kpi = {
        "month": month_id,
        "service_type": service,
        "total_trips": int(len(df)),
        "avg_distance": None if df["trip_distance"].dropna().empty else float(df["trip_distance"].mean()),
        "avg_duration_minutes": None if df["duration_minutes"].dropna().empty else float(df["duration_minutes"].mean()),
        "avg_fare": None if df["fare_amount"].dropna().empty else float(df["fare_amount"].mean()),
        "busiest_hour": None if hourly.empty else int(hourly.sort_values(ascending=False).index[0]),
        "top_pickup_zones": zone_metrics.sort_values("pickup_count", ascending=False).head(10).to_dict(orient="records"),
        "top_dropoff_zones": zone_metrics.sort_values("dropoff_count", ascending=False).head(10).to_dict(orient="records"),
        "generated_at": datetime.now(UTC).isoformat(),
    }
    kpi_path.write_text(json.dumps(kpi, default=_json_default, indent=2))
    return {"service_type": service, "month": month_id, "artifacts": [str(zone_path), str(od_path), str(kpi_path)], "rows": int(len(df))}


def generate_combined_service_metrics(month: str, services: list[str]) -> dict[str, Any]:
    frames = []
    for service in services:
        path = _silver_path(service, month)
        if path.exists():
            frames.append(pd.read_parquet(path))
    if not frames:
        return {"month": month, "status": "skipped", "message": "No silver data available for combined metrics."}

    df = pd.concat(frames, ignore_index=True)
    output_dir = GOLD_DIR / "all_services"
    output_dir.mkdir(parents=True, exist_ok=True)
    service_hour = df.groupby(["month", "service_type", "pickup_hour"], dropna=False).agg(
        total_trips=("service_type", "size"),
        avg_distance=("trip_distance", "mean"),
        avg_duration_minutes=("duration_minutes", "mean"),
        avg_fare=("fare_amount", "mean"),
    ).reset_index().rename(columns={"pickup_hour": "hour"})
    zone_col = "pickup_zone" if "pickup_zone" in df.columns else "pickup_location_id"
    service_zone = df.groupby(["month", "service_type", "pickup_hour", zone_col], dropna=False).size().rename("pickup_count").reset_index().rename(
        columns={"pickup_hour": "hour", zone_col: "pickup_zone" if zone_col == "pickup_zone" else "pickup_location_id"}
    )
    service_hour_path = output_dir / f"service_hour_metrics_{month}.parquet"
    service_zone_path = output_dir / f"service_zone_hour_metrics_{month}.parquet"
    kpi_path = output_dir / f"service_comparison_kpi_{month}.json"
    service_hour.to_parquet(service_hour_path, index=False)
    service_zone.to_parquet(service_zone_path, index=False)

    total_by_service = df.groupby("service_type").size().to_dict()
    total_trips = sum(total_by_service.values())
    kpi = {
        "month": month,
        "available_services": sorted(total_by_service),
        "total_trips_by_service": {key: int(value) for key, value in total_by_service.items()},
        "service_share_by_trip_count": {key: float(value / total_trips) for key, value in total_by_service.items()},
        "busiest_hour_by_service": service_hour.sort_values("total_trips", ascending=False).groupby("service_type").head(1).set_index("service_type")["hour"].to_dict(),
        "top_pickup_zones_by_service": {},
        "top_dropoff_zones_by_service": {},
        "generated_at": datetime.now(UTC).isoformat(),
    }
    kpi_path.write_text(json.dumps(kpi, default=_json_default, indent=2))
    return {"month": month, "status": "generated", "artifacts": [str(service_hour_path), str(service_zone_path), str(kpi_path)]}
