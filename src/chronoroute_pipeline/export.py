"""Export gold and silver artifacts into frontend-compatible public data files."""

from __future__ import annotations

import json
from calendar import month_name
from pathlib import Path

import pandas as pd

from .config import DEFAULT_INTERACTIVE_RECORDS_PER_SERVICE_MONTH, GOLD_DIR, PUBLIC_DATA_DIR, SILVER_DIR, TAXI_ZONES_GEOJSON_PATHS, TLC_SOURCE_PAGE
from .metadata import write_metadata
from .tlc_source import get_service_display_name, validate_service_type


def _silver_path(service_type: str, month: str) -> Path:
    return SILVER_DIR / service_type / f"{month}_cleaned.parquet"


def _load_centroids() -> dict[int, list[float]]:
    for path in TAXI_ZONES_GEOJSON_PATHS:
        if not path.exists():
            continue
        payload = json.loads(path.read_text())
        centroids: dict[int, list[float]] = {}
        for feature in payload.get("features", []):
            props = feature.get("properties", {})
            loc_id = props.get("location_id") or props.get("LocationID") or props.get("objectid")
            if loc_id is None:
                continue
            geom = feature.get("geometry", {})
            coords = geom.get("coordinates", [])
            if geom.get("type") == "Polygon" and coords:
                ring = coords[0]
            elif geom.get("type") == "MultiPolygon" and coords and coords[0]:
                ring = coords[0][0]
            else:
                continue
            if not ring:
                continue
            lon = sum(point[0] for point in ring) / len(ring)
            lat = sum(point[1] for point in ring) / len(ring)
            centroids[int(loc_id)] = [lon, lat]
        return centroids
    return {}


def _build_path(row: pd.Series, centroids: dict[int, list[float]]) -> str | None:
    try:
        pickup_id = int(row["pickup_location_id"])
        dropoff_id = int(row["dropoff_location_id"])
    except (TypeError, ValueError):
        return None
    pickup = centroids.get(pickup_id)
    dropoff = centroids.get(dropoff_id)
    if not pickup or not dropoff:
        return None
    pickup_dt = pd.to_datetime(row["pickup_datetime"], errors="coerce")
    dropoff_dt = pd.to_datetime(row["dropoff_datetime"], errors="coerce")
    if pd.isna(pickup_dt):
        return None
    start = int(pickup_dt.hour * 3600 + pickup_dt.minute * 60 + pickup_dt.second)
    if pd.isna(dropoff_dt):
        end = start + 600
    else:
        end = int(dropoff_dt.hour * 3600 + dropoff_dt.minute * 60 + dropoff_dt.second)
        if end <= start:
            end = start + 600
    return json.dumps([[pickup[0], pickup[1], start], [dropoff[0], dropoff[1], end]])


def _export_trip_paths(months: list[str], services: list[str]) -> str | None:
    centroids = _load_centroids()
    if not centroids:
        return None
    frames: list[pd.DataFrame] = []
    for service in services:
        for month in months:
            path = _silver_path(service, month)
            if not path.exists():
                continue
            df = pd.read_parquet(path)
            if df.empty:
                continue
            sample_size = min(DEFAULT_INTERACTIVE_RECORDS_PER_SERVICE_MONTH, len(df))
            sample = df.sample(sample_size, random_state=int(month.replace("-", "")) + len(service)).copy()
            sample["path"] = sample.apply(lambda row: _build_path(row, centroids), axis=1)
            sample = sample.dropna(subset=["path"])
            if sample.empty:
                continue
            export_df = pd.DataFrame({
                "service_type": sample["service_type"],
                "month": sample["month"],
                "vendor": sample.get("base_license_number", pd.Series([0] * len(sample))).fillna(0),
                "hour": sample["pickup_hour"].astype(int),
                "trip_distance": sample["trip_distance"],
                "fare": sample["fare_amount"],
                "path": sample["path"],
            })
            frames.append(export_df)
    if not frames:
        return None
    output = pd.concat(frames, ignore_index=True)
    output_path = PUBLIC_DATA_DIR / "trip_paths.parquet"
    output.to_parquet(output_path, index=False)
    return str(output_path)


def _export_month_and_hourly_files(months: list[str], services: list[str]) -> list[str]:
    months_payload = []
    hourly_by_service_month: dict[str, dict[str, list[dict]]] = {}
    monthly_stats: dict[str, dict[str, dict]] = {}
    written: list[str] = []
    for service in services:
        hourly_by_service_month[service] = {}
        monthly_stats[service] = {}
        for month in months:
            kpi_path = GOLD_DIR / service / f"monthly_kpi_{month}.json"
            hourly_path = GOLD_DIR / "all_services" / f"service_hour_metrics_{month}.parquet"
            if not kpi_path.exists():
                continue
            kpi = json.loads(kpi_path.read_text())
            year, month_num = month.split("-")
            months_payload.append({
                "id": month,
                "service_type": service,
                "label": f"{month_name[int(month_num)]} {year}",
                "source": f"NYC Taxi & Limousine Commission {get_service_display_name(service)} Trip Records",
                "source_url": TLC_SOURCE_PAGE,
                "source_file": f"{service}_tripdata_{month}.parquet",
                "total_trips": kpi.get("total_trips", 0),
                "avg_distance": kpi.get("avg_distance") or 0,
                "peak_hour": kpi.get("busiest_hour") or 0,
                "total_revenue": kpi.get("total_revenue") or 0,
            })
            monthly_stats[service][month] = {
                "total_trips": kpi.get("total_trips", 0),
                "avg_distance": kpi.get("avg_distance") or 0,
                "peak_hour": kpi.get("busiest_hour") or 0,
                "total_revenue": kpi.get("total_revenue") or 0,
            }
            if hourly_path.exists():
                hourly_df = pd.read_parquet(hourly_path)
                active = hourly_df[(hourly_df["service_type"] == service) & (hourly_df["month"] == month)]
                hourly_by_service_month[service][month] = [
                    {
                        "hour": int(row.hour),
                        "count": int(row.total_trips),
                        "total_distance": float((row.avg_distance or 0) * row.total_trips),
                        "total_revenue": float((row.avg_fare or 0) * row.total_trips),
                    }
                    for row in active.itertuples(index=False)
                ]
    if months_payload:
        (PUBLIC_DATA_DIR / "months_by_service.json").write_text(json.dumps(months_payload))
        (PUBLIC_DATA_DIR / "hourly_volume_by_service_month.json").write_text(json.dumps(hourly_by_service_month))
        (PUBLIC_DATA_DIR / "monthly_stats_by_service.json").write_text(json.dumps(monthly_stats))
        written.extend([
            str(PUBLIC_DATA_DIR / "months_by_service.json"),
            str(PUBLIC_DATA_DIR / "hourly_volume_by_service_month.json"),
            str(PUBLIC_DATA_DIR / "monthly_stats_by_service.json"),
        ])
    return written


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

    generated = []
    trip_paths = _export_trip_paths(months, valid_services)
    if trip_paths:
        generated.append(trip_paths)
    generated.extend(_export_month_and_hourly_files(months, valid_services))

    metadata = write_metadata(available_months_by_service)
    for filename in ("trip_paths.parquet", "months.json", "hourly_volume_by_month.json", "stats.json", "h3_deadhead.json", "od_flows.json"):
        path = PUBLIC_DATA_DIR / filename
        if path.exists():
            copied.append(str(path))
    return {"metadata": metadata, "generated_frontend_artifacts": generated, "preserved_frontend_artifacts": copied}


def list_public_artifacts(public_data_dir: Path = PUBLIC_DATA_DIR) -> list[str]:
    return [str(path) for path in sorted(public_data_dir.glob("*")) if path.is_file()]
