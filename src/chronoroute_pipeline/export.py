"""Export gold and silver artifacts into frontend-compatible public data files."""

from __future__ import annotations

import json
import math
from calendar import month_name
from pathlib import Path

import duckdb

from .config import DEFAULT_INTERACTIVE_RECORDS_PER_SERVICE_MONTH, GOLD_DIR, PUBLIC_DATA_DIR, SILVER_DIR, TAXI_ZONES_GEOJSON_PATHS, TLC_SOURCE_PAGE
from .metadata import write_metadata
from .tlc_source import get_service_display_name, validate_service_type


def _silver_path(service_type: str, month: str) -> Path:
    return SILVER_DIR / service_type / f"{month}_cleaned.parquet"


def _literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _finite_number(value: object, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


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


def _centroid_values_sql(centroids: dict[int, list[float]]) -> str:
    rows = [
        f"({location_id}, {coords[0]}, {coords[1]})"
        for location_id, coords in sorted(centroids.items())
    ]
    return "(VALUES " + ", ".join(rows) + ")"


def _export_trip_paths(months: list[str], services: list[str]) -> str | None:
    centroids = _load_centroids()
    if not centroids:
        return None
    centroid_sql = _centroid_values_sql(centroids)
    queries: list[str] = []
    con = duckdb.connect()
    for service in services:
        for month in months:
            path = _silver_path(service, month)
            if not path.exists():
                continue
            queries.append(f"""
                SELECT
                    service_type,
                    month,
                    COALESCE(CAST(base_license_number AS VARCHAR), 'unknown') AS vendor,
                    CAST(pickup_hour AS INTEGER) AS hour,
                    trip_distance,
                    fare_amount AS fare,
                    '[[' || pickup_lon || ',' || pickup_lat || ',' || start_second || '],[' ||
                        dropoff_lon || ',' || dropoff_lat || ',' || end_second || ']]' AS path
                FROM (
                    SELECT
                        service_type,
                        month,
                        base_license_number,
                        pickup_hour,
                        trip_distance,
                        fare_amount,
                        pickup_lon,
                        pickup_lat,
                        dropoff_lon,
                        dropoff_lat,
                        EXTRACT('hour' FROM pickup_datetime) * 3600
                            + EXTRACT('minute' FROM pickup_datetime) * 60
                            + EXTRACT('second' FROM pickup_datetime) AS start_second,
                        CASE
                            WHEN dropoff_datetime IS NULL THEN
                                EXTRACT('hour' FROM pickup_datetime) * 3600
                                + EXTRACT('minute' FROM pickup_datetime) * 60
                                + EXTRACT('second' FROM pickup_datetime) + 600
                            WHEN (
                                EXTRACT('hour' FROM dropoff_datetime) * 3600
                                + EXTRACT('minute' FROM dropoff_datetime) * 60
                                + EXTRACT('second' FROM dropoff_datetime)
                            ) <= (
                                EXTRACT('hour' FROM pickup_datetime) * 3600
                                + EXTRACT('minute' FROM pickup_datetime) * 60
                                + EXTRACT('second' FROM pickup_datetime)
                            ) THEN
                                EXTRACT('hour' FROM pickup_datetime) * 3600
                                + EXTRACT('minute' FROM pickup_datetime) * 60
                                + EXTRACT('second' FROM pickup_datetime) + 600
                            ELSE
                                EXTRACT('hour' FROM dropoff_datetime) * 3600
                                + EXTRACT('minute' FROM dropoff_datetime) * 60
                                + EXTRACT('second' FROM dropoff_datetime)
                        END AS end_second
                    FROM (
                        SELECT
                            trips.*,
                            pickup_centroids.lon AS pickup_lon,
                            pickup_centroids.lat AS pickup_lat,
                            dropoff_centroids.lon AS dropoff_lon,
                            dropoff_centroids.lat AS dropoff_lat
                        FROM (
                            SELECT *
                            FROM read_parquet({_literal(str(path))})
                            LIMIT {DEFAULT_INTERACTIVE_RECORDS_PER_SERVICE_MONTH}
                        ) trips
                        JOIN {centroid_sql} AS pickup_centroids(location_id, lon, lat)
                            ON trips.pickup_location_id = pickup_centroids.location_id
                        JOIN {centroid_sql} AS dropoff_centroids(location_id, lon, lat)
                            ON trips.dropoff_location_id = dropoff_centroids.location_id
                    ) AS filtered
                ) AS sampled
            """)
    if not queries:
        con.close()
        return None
    output_path = PUBLIC_DATA_DIR / "trip_paths.parquet"
    con.execute(f"COPY ({' UNION ALL '.join(queries)}) TO {_literal(str(output_path))} (FORMAT PARQUET)")
    con.close()
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
                "total_trips": int(_finite_number(kpi.get("total_trips"), 0)),
                "avg_distance": _finite_number(kpi.get("avg_distance"), 0),
                "peak_hour": int(_finite_number(kpi.get("busiest_hour"), 0)),
                "total_revenue": _finite_number(kpi.get("total_revenue"), 0),
            })
            monthly_stats[service][month] = {
                "total_trips": int(_finite_number(kpi.get("total_trips"), 0)),
                "avg_distance": _finite_number(kpi.get("avg_distance"), 0),
                "peak_hour": int(_finite_number(kpi.get("busiest_hour"), 0)),
                "total_revenue": _finite_number(kpi.get("total_revenue"), 0),
            }
            if hourly_path.exists():
                con = duckdb.connect()
                active = con.sql(f"""
                    SELECT hour, total_trips, avg_distance, avg_fare
                    FROM read_parquet({_literal(str(hourly_path))})
                    WHERE service_type = {_literal(service)}
                        AND month = {_literal(month)}
                    ORDER BY hour
                """).fetchall()
                con.close()
                hourly_by_service_month[service][month] = [
                    {
                        "hour": int(hour),
                        "count": int(_finite_number(total_trips, 0)),
                        "total_distance": _finite_number(avg_distance, 0) * _finite_number(total_trips, 0),
                        "total_revenue": _finite_number(avg_fare, 0) * _finite_number(total_trips, 0),
                    }
                    for hour, total_trips, avg_distance, avg_fare in active
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
