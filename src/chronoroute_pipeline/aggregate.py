"""Gold analytics aggregations."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb

from .config import GOLD_DIR, SILVER_DIR
from .tlc_source import validate_service_type


def _literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _json_default(value: Any) -> Any:
    if hasattr(value, "item"):
        return value.item()
    return value


def _silver_path(service_type: str, month: str) -> Path:
    return SILVER_DIR / validate_service_type(service_type) / f"{month}_cleaned.parquet"


def _columns(con: duckdb.DuckDBPyConnection, path: Path) -> set[str]:
    rows = con.sql(f"DESCRIBE SELECT * FROM read_parquet({_literal(str(path))})").fetchall()
    return {row[0] for row in rows}


def _zone_columns(columns: set[str]) -> tuple[str, str]:
    pickup_zone = "pickup_zone" if "pickup_zone" in columns else "pickup_location_id"
    dropoff_zone = "dropoff_zone" if "dropoff_zone" in columns else "dropoff_location_id"
    return pickup_zone, dropoff_zone


def generate_gold_for_service(service_type: str, year: int, month: int) -> dict[str, Any]:
    service = validate_service_type(service_type)
    month_id = f"{int(year):04d}-{int(month):02d}"
    input_path = _silver_path(service, month_id)
    if not input_path.exists():
        raise FileNotFoundError(f"Missing silver file: {input_path}")

    output_dir = GOLD_DIR / service
    output_dir.mkdir(parents=True, exist_ok=True)
    zone_path = output_dir / f"zone_hour_metrics_{month_id}.parquet"
    od_path = output_dir / f"od_zone_hour_{month_id}.parquet"
    kpi_path = output_dir / f"monthly_kpi_{month_id}.json"

    con = duckdb.connect()
    columns = _columns(con, input_path)
    pickup_zone, dropoff_zone = _zone_columns(columns)
    pickup_alias = "pickup_zone" if pickup_zone == "pickup_zone" else "pickup_location_id"
    dropoff_alias = "dropoff_zone" if dropoff_zone == "dropoff_zone" else "dropoff_location_id"
    source = f"read_parquet({_literal(str(input_path))})"

    zone_sql = f"""
        WITH base AS (
            SELECT * FROM {source}
        ),
        pickups AS (
            SELECT month, service_type, pickup_date, day_of_week, day_type, temporal_segment, pickup_hour AS hour,
                {pickup_zone} AS zone_key,
                COUNT(*) AS pickup_count,
                AVG(fare_amount) AS avg_fare,
                AVG(trip_distance) AS avg_distance,
                AVG(duration_minutes) AS avg_duration_minutes
            FROM base
            GROUP BY 1,2,3,4,5,6,7,8
        ),
        dropoffs AS (
            SELECT month, service_type, pickup_date, day_of_week, day_type, temporal_segment, pickup_hour AS hour,
                {dropoff_zone} AS zone_key,
                COUNT(*) AS dropoff_count
            FROM base
            GROUP BY 1,2,3,4,5,6,7,8
        ),
        joined AS (
            SELECT
                COALESCE(p.month, d.month) AS month,
                COALESCE(p.service_type, d.service_type) AS service_type,
                COALESCE(p.pickup_date, d.pickup_date) AS pickup_date,
                COALESCE(p.day_of_week, d.day_of_week) AS day_of_week,
                COALESCE(p.day_type, d.day_type) AS day_type,
                COALESCE(p.temporal_segment, d.temporal_segment) AS temporal_segment,
                COALESCE(p.hour, d.hour) AS hour,
                COALESCE(p.zone_key, d.zone_key) AS {pickup_alias},
                COALESCE(p.pickup_count, 0) AS pickup_count,
                COALESCE(d.dropoff_count, 0) AS dropoff_count,
                p.avg_fare,
                p.avg_distance,
                p.avg_duration_minutes
            FROM pickups p
            FULL OUTER JOIN dropoffs d
            USING (month, service_type, pickup_date, day_of_week, day_type, temporal_segment, hour, zone_key)
        )
        SELECT *,
            pickup_count + dropoff_count AS total_activity,
            CASE WHEN dropoff_count = 0 THEN pickup_count ELSE pickup_count::DOUBLE / dropoff_count END AS pickup_dropoff_ratio,
            CASE WHEN pickup_count + dropoff_count = 0 THEN 0
                ELSE (pickup_count - dropoff_count)::DOUBLE / (pickup_count + dropoff_count)
            END AS normalized_imbalance_score,
            GREATEST(pickup_count - dropoff_count, 0) *
                GREATEST(CASE WHEN pickup_count + dropoff_count = 0 THEN 0
                    ELSE (pickup_count - dropoff_count)::DOUBLE / (pickup_count + dropoff_count)
                END, 0) AS demand_pressure_index,
            GREATEST(dropoff_count - pickup_count, 0) *
                GREATEST(-CASE WHEN pickup_count + dropoff_count = 0 THEN 0
                    ELSE (pickup_count - dropoff_count)::DOUBLE / (pickup_count + dropoff_count)
                END, 0) AS idle_relocation_opportunity_score
        FROM joined
    """
    con.execute(f"COPY ({zone_sql}) TO {_literal(str(zone_path))} (FORMAT PARQUET)")

    od_sql = f"""
        SELECT
            month,
            service_type,
            pickup_date,
            day_type,
            temporal_segment,
            pickup_hour AS hour,
            {pickup_zone} AS {pickup_alias},
            {dropoff_zone} AS {dropoff_alias},
            COUNT(*) AS trip_count,
            AVG(fare_amount) AS avg_fare,
            AVG(trip_distance) AS avg_distance,
            AVG(duration_minutes) AS avg_duration_minutes
        FROM {source}
        GROUP BY 1,2,3,4,5,6,7,8
    """
    con.execute(f"COPY ({od_sql}) TO {_literal(str(od_path))} (FORMAT PARQUET)")

    total_trips = con.sql(f"SELECT COUNT(*) FROM {source}").fetchone()[0]
    stats = con.sql(f"""
        SELECT
            AVG(trip_distance) AS avg_distance,
            AVG(duration_minutes) AS avg_duration_minutes,
            AVG(fare_amount) AS avg_fare
        FROM {source}
    """).fetchone()
    busiest_hour = con.sql(f"""
        SELECT pickup_hour
        FROM {source}
        GROUP BY pickup_hour
        ORDER BY COUNT(*) DESC
        LIMIT 1
    """).fetchone()
    top_pickups = con.sql(f"""
        SELECT {pickup_alias}, SUM(pickup_count) AS pickup_count
        FROM read_parquet({_literal(str(zone_path))})
        GROUP BY 1
        ORDER BY pickup_count DESC
        LIMIT 10
    """).df().to_dict(orient="records")
    top_dropoffs = con.sql(f"""
        SELECT {pickup_alias}, SUM(dropoff_count) AS dropoff_count
        FROM read_parquet({_literal(str(zone_path))})
        GROUP BY 1
        ORDER BY dropoff_count DESC
        LIMIT 10
    """).df().to_dict(orient="records")
    con.close()

    kpi = {
        "month": month_id,
        "service_type": service,
        "total_trips": int(total_trips),
        "avg_distance": None if stats[0] is None else float(stats[0]),
        "avg_duration_minutes": None if stats[1] is None else float(stats[1]),
        "avg_fare": None if stats[2] is None else float(stats[2]),
        "total_revenue": None,
        "busiest_hour": None if busiest_hour is None else int(busiest_hour[0]),
        "top_pickup_zones": top_pickups,
        "top_dropoff_zones": top_dropoffs,
        "generated_at": datetime.now(UTC).isoformat(),
    }
    kpi_path.write_text(json.dumps(kpi, default=_json_default, indent=2))
    return {"service_type": service, "month": month_id, "artifacts": [str(zone_path), str(od_path), str(kpi_path)], "rows": int(total_trips)}


def generate_combined_service_metrics(month: str, services: list[str]) -> dict[str, Any]:
    paths = [_silver_path(service, month) for service in services if _silver_path(service, month).exists()]
    if not paths:
        return {"month": month, "status": "skipped", "message": "No silver data available for combined metrics."}

    output_dir = GOLD_DIR / "all_services"
    output_dir.mkdir(parents=True, exist_ok=True)
    service_hour_path = output_dir / f"service_hour_metrics_{month}.parquet"
    service_zone_path = output_dir / f"service_zone_hour_metrics_{month}.parquet"
    kpi_path = output_dir / f"service_comparison_kpi_{month}.json"
    path_list = "[" + ", ".join(_literal(str(path)) for path in paths) + "]"
    source = f"read_parquet({path_list}, union_by_name=true)"
    con = duckdb.connect()
    columns = _columns(con, paths[0])
    pickup_zone, dropoff_zone = _zone_columns(columns)
    pickup_alias = "pickup_zone" if pickup_zone == "pickup_zone" else "pickup_location_id"

    con.execute(f"""
        COPY (
            SELECT month, service_type, pickup_hour AS hour,
                COUNT(*) AS total_trips,
                AVG(trip_distance) AS avg_distance,
                AVG(duration_minutes) AS avg_duration_minutes,
                AVG(fare_amount) AS avg_fare
            FROM {source}
            GROUP BY 1,2,3
        ) TO {_literal(str(service_hour_path))} (FORMAT PARQUET)
    """)
    con.execute(f"""
        COPY (
            SELECT month, service_type, pickup_hour AS hour, {pickup_zone} AS {pickup_alias},
                COUNT(*) AS pickup_count
            FROM {source}
            GROUP BY 1,2,3,4
        ) TO {_literal(str(service_zone_path))} (FORMAT PARQUET)
    """)
    total_by_service_rows = con.sql(f"""
        SELECT service_type, COUNT(*) AS total_trips
        FROM {source}
        GROUP BY 1
    """).fetchall()
    total_by_service = {service: int(count) for service, count in total_by_service_rows}
    total_trips = sum(total_by_service.values())
    busiest_rows = con.sql(f"""
        SELECT service_type, hour
        FROM (
            SELECT service_type, pickup_hour AS hour, COUNT(*) AS trips,
                ROW_NUMBER() OVER (PARTITION BY service_type ORDER BY COUNT(*) DESC) AS rn
            FROM {source}
            GROUP BY 1,2
        )
        WHERE rn = 1
    """).fetchall()
    kpi = {
        "month": month,
        "available_services": sorted(total_by_service),
        "total_trips_by_service": total_by_service,
        "service_share_by_trip_count": {service: count / total_trips for service, count in total_by_service.items()} if total_trips else {},
        "busiest_hour_by_service": {service: int(hour) for service, hour in busiest_rows},
        "top_pickup_zones_by_service": {},
        "top_dropoff_zones_by_service": {},
        "generated_at": datetime.now(UTC).isoformat(),
    }
    kpi_path.write_text(json.dumps(kpi, default=_json_default, indent=2))
    con.close()
    return {"month": month, "status": "generated", "artifacts": [str(service_hour_path), str(service_zone_path), str(kpi_path)]}
