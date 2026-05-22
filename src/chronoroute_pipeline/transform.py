"""Bronze-to-silver transformations."""

from __future__ import annotations

import duckdb

from .config import SILVER_DIR, TAXI_ZONE_LOOKUP_PATHS
from .schema import CANONICAL_COLUMNS, find_column, get_service_mappings
from .tlc_source import get_expected_bronze_path, validate_service_type


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _load_taxi_zone_lookup() -> str | None:
    for path in TAXI_ZONE_LOOKUP_PATHS:
        if path.exists():
            return str(path)
    return None


def _source_columns(con: duckdb.DuckDBPyConnection, source_path: str) -> list[str]:
    rows = con.sql(f"DESCRIBE SELECT * FROM read_parquet({_literal(source_path)})").fetchall()
    return [row[0] for row in rows]


def _mapped_expression(canonical: str, source_columns: list[str], service: str) -> str:
    for mapping in get_service_mappings(service):
        if mapping.canonical == canonical:
            source = find_column(source_columns, mapping.candidates)
            if source:
                return _quote(source)
            break
    if canonical in {"pickup_datetime", "dropoff_datetime"}:
        return "CAST(NULL AS TIMESTAMP)"
    if canonical in {"pickup_location_id", "dropoff_location_id", "pickup_hour"}:
        return "CAST(NULL AS BIGINT)"
    if canonical in {"trip_distance", "fare_amount", "passenger_count", "duration_minutes"}:
        return "CAST(NULL AS DOUBLE)"
    return "CAST(NULL AS VARCHAR)"


def _build_clean_sql(source_path: str, service: str, month_id: str, source_columns: list[str]) -> str:
    pickup_expr = _mapped_expression("pickup_datetime", source_columns, service)
    dropoff_expr = _mapped_expression("dropoff_datetime", source_columns, service)
    pickup_location_expr = _mapped_expression("pickup_location_id", source_columns, service)
    dropoff_location_expr = _mapped_expression("dropoff_location_id", source_columns, service)
    distance_expr = _mapped_expression("trip_distance", source_columns, service)
    fare_expr = _mapped_expression("fare_amount", source_columns, service)
    passenger_expr = _mapped_expression("passenger_count", source_columns, service)
    base_expr = _mapped_expression("base_license_number", source_columns, service)
    dispatch_expr = _mapped_expression("dispatching_base_num", source_columns, service)
    origin_expr = _mapped_expression("originating_base_num", source_columns, service)
    lookup_path = _load_taxi_zone_lookup()

    enrich_select = ""
    enrich_join = ""
    if lookup_path:
        enrich_select = """
            , pickup_lookup.Borough AS pickup_borough
            , pickup_lookup.Zone AS pickup_zone
            , pickup_lookup.service_zone AS pickup_service_zone
            , dropoff_lookup.Borough AS dropoff_borough
            , dropoff_lookup.Zone AS dropoff_zone
            , dropoff_lookup.service_zone AS dropoff_service_zone
        """
        enrich_join = f"""
            LEFT JOIN read_csv_auto({_literal(lookup_path)}) pickup_lookup
                ON canonical.pickup_location_id = pickup_lookup.LocationID
            LEFT JOIN read_csv_auto({_literal(lookup_path)}) dropoff_lookup
                ON canonical.dropoff_location_id = dropoff_lookup.LocationID
        """

    return f"""
        WITH source AS (
            SELECT * FROM read_parquet({_literal(source_path)})
        ),
        canonical AS (
            SELECT
                {_literal(service)} AS service_type,
                CAST({pickup_expr} AS TIMESTAMP) AS pickup_datetime,
                CAST({dropoff_expr} AS TIMESTAMP) AS dropoff_datetime,
                TRY_CAST({pickup_location_expr} AS BIGINT) AS pickup_location_id,
                TRY_CAST({dropoff_location_expr} AS BIGINT) AS dropoff_location_id,
                TRY_CAST({distance_expr} AS DOUBLE) AS trip_distance,
                TRY_CAST({fare_expr} AS DOUBLE) AS fare_amount,
                TRY_CAST({passenger_expr} AS DOUBLE) AS passenger_count,
                CAST({base_expr} AS VARCHAR) AS base_license_number,
                CAST({dispatch_expr} AS VARCHAR) AS dispatching_base_num,
                CAST({origin_expr} AS VARCHAR) AS originating_base_num,
                {_literal(month_id)} AS month,
                CAST(CAST({pickup_expr} AS TIMESTAMP) AS DATE) AS pickup_date,
                EXTRACT('hour' FROM CAST({pickup_expr} AS TIMESTAMP)) AS pickup_hour,
                DAYNAME(CAST({pickup_expr} AS TIMESTAMP)) AS day_of_week,
                CASE
                    WHEN EXTRACT('dow' FROM CAST({pickup_expr} AS TIMESTAMP)) IN (0, 6) THEN 'weekend'
                    ELSE 'weekday'
                END AS day_type,
                CASE
                    WHEN EXTRACT('hour' FROM CAST({pickup_expr} AS TIMESTAMP)) >= 7 AND EXTRACT('hour' FROM CAST({pickup_expr} AS TIMESTAMP)) < 10 THEN 'morning_rush'
                    WHEN EXTRACT('hour' FROM CAST({pickup_expr} AS TIMESTAMP)) >= 10 AND EXTRACT('hour' FROM CAST({pickup_expr} AS TIMESTAMP)) < 16 THEN 'midday'
                    WHEN EXTRACT('hour' FROM CAST({pickup_expr} AS TIMESTAMP)) >= 16 AND EXTRACT('hour' FROM CAST({pickup_expr} AS TIMESTAMP)) < 19 THEN 'evening_rush'
                    WHEN EXTRACT('hour' FROM CAST({pickup_expr} AS TIMESTAMP)) >= 19 THEN 'night'
                    ELSE 'late_night'
                END AS temporal_segment,
                DATE_DIFF('second', CAST({pickup_expr} AS TIMESTAMP), CAST({dropoff_expr} AS TIMESTAMP)) / 60.0 AS duration_minutes
            FROM source
        )
        SELECT canonical.*
            {enrich_select}
        FROM canonical
        {enrich_join}
        WHERE pickup_datetime IS NOT NULL
            AND pickup_location_id IS NOT NULL
            AND dropoff_location_id IS NOT NULL
            AND pickup_hour BETWEEN 0 AND 23
            AND (dropoff_datetime IS NULL OR dropoff_datetime > pickup_datetime)
            AND (trip_distance IS NULL OR trip_distance >= 0)
            AND (fare_amount IS NULL OR fare_amount >= 0)
            AND (passenger_count IS NULL OR passenger_count >= 0)
    """


def clean_month(service_type: str, year: int, month: int) -> dict[str, str | int]:
    service = validate_service_type(service_type)
    month_id = f"{int(year):04d}-{int(month):02d}"
    source_path = get_expected_bronze_path(service, year, month)
    if not source_path.exists():
        raise FileNotFoundError(f"Missing bronze file: {source_path}")

    output_path = SILVER_DIR / service / f"{month_id}_cleaned.parquet"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    source_columns = _source_columns(con, str(source_path))
    sql = _build_clean_sql(str(source_path), service, month_id, source_columns)
    con.execute(f"COPY ({sql}) TO {_literal(str(output_path))} (FORMAT PARQUET)")
    rows = con.sql(f"SELECT COUNT(*) FROM read_parquet({_literal(str(output_path))})").fetchone()[0]
    con.close()
    return {"service_type": service, "month": month_id, "status": "cleaned", "path": str(output_path), "rows": int(rows)}
