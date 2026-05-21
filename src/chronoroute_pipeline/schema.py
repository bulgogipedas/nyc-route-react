"""Schema normalization rules for TLC services."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd

from .tlc_source import validate_service_type

CANONICAL_COLUMNS = [
    "service_type",
    "pickup_datetime",
    "dropoff_datetime",
    "pickup_location_id",
    "dropoff_location_id",
    "trip_distance",
    "fare_amount",
    "passenger_count",
    "base_license_number",
    "dispatching_base_num",
    "originating_base_num",
    "month",
    "pickup_date",
    "pickup_hour",
    "day_of_week",
    "day_type",
    "temporal_segment",
    "duration_minutes",
]

BASE_REQUIRED_CANONICAL = ["service_type", "pickup_datetime", "pickup_location_id", "dropoff_location_id", "month", "pickup_hour"]


@dataclass(frozen=True)
class ColumnMapping:
    canonical: str
    candidates: tuple[str, ...]
    required: bool = False


SERVICE_COLUMN_MAPPINGS: dict[str, tuple[ColumnMapping, ...]] = {
    "yellow": (
        ColumnMapping("pickup_datetime", ("tpep_pickup_datetime",), True),
        ColumnMapping("dropoff_datetime", ("tpep_dropoff_datetime",), True),
        ColumnMapping("pickup_location_id", ("PULocationID",), True),
        ColumnMapping("dropoff_location_id", ("DOLocationID",), True),
        ColumnMapping("trip_distance", ("trip_distance",)),
        ColumnMapping("fare_amount", ("fare_amount", "total_amount")),
        ColumnMapping("passenger_count", ("passenger_count",)),
    ),
    "green": (
        ColumnMapping("pickup_datetime", ("lpep_pickup_datetime",), True),
        ColumnMapping("dropoff_datetime", ("lpep_dropoff_datetime",), True),
        ColumnMapping("pickup_location_id", ("PULocationID",), True),
        ColumnMapping("dropoff_location_id", ("DOLocationID",), True),
        ColumnMapping("trip_distance", ("trip_distance",)),
        ColumnMapping("fare_amount", ("fare_amount", "total_amount")),
        ColumnMapping("passenger_count", ("passenger_count",)),
    ),
    "fhv": (
        ColumnMapping("pickup_datetime", ("pickup_datetime",), True),
        ColumnMapping("dropoff_datetime", ("dropOff_datetime", "dropoff_datetime")),
        ColumnMapping("pickup_location_id", ("PUlocationID", "PULocationID"), True),
        ColumnMapping("dropoff_location_id", ("DOlocationID", "DOLocationID"), True),
        ColumnMapping("dispatching_base_num", ("dispatching_base_num",)),
        ColumnMapping("base_license_number", ("affiliated_base_number", "Affiliated_base_number")),
    ),
    "fhvhv": (
        ColumnMapping("pickup_datetime", ("pickup_datetime",), True),
        ColumnMapping("dropoff_datetime", ("dropoff_datetime",), True),
        ColumnMapping("pickup_location_id", ("PULocationID", "PUlocationID"), True),
        ColumnMapping("dropoff_location_id", ("DOLocationID", "DOlocationID"), True),
        ColumnMapping("trip_distance", ("trip_miles", "trip_distance")),
        ColumnMapping("fare_amount", ("base_passenger_fare",)),
        ColumnMapping("base_license_number", ("hvfhs_license_num",)),
        ColumnMapping("dispatching_base_num", ("dispatching_base_num",)),
        ColumnMapping("originating_base_num", ("originating_base_num",)),
    ),
}


def get_service_mappings(service_type: str) -> tuple[ColumnMapping, ...]:
    return SERVICE_COLUMN_MAPPINGS[validate_service_type(service_type)]


def find_column(columns: Iterable[str], candidates: Iterable[str]) -> str | None:
    available = {column.lower(): column for column in columns}
    for candidate in candidates:
        match = available.get(candidate.lower())
        if match:
            return match
    return None


def required_source_columns(service_type: str, available_columns: Iterable[str] | None = None) -> list[str]:
    mappings = get_service_mappings(service_type)
    if available_columns is None:
        return [mapping.candidates[0] for mapping in mappings if mapping.required]
    missing = []
    for mapping in mappings:
        if mapping.required and find_column(available_columns, mapping.candidates) is None:
            missing.append("/".join(mapping.candidates))
    return missing


def normalize_trip_schema(df: pd.DataFrame, service_type: str, month: str) -> pd.DataFrame:
    service = validate_service_type(service_type)
    output = pd.DataFrame(index=df.index)
    output["service_type"] = service

    for mapping in get_service_mappings(service):
        source = find_column(df.columns, mapping.candidates)
        output[mapping.canonical] = df[source] if source else pd.NA

    for column in CANONICAL_COLUMNS:
        if column not in output:
            output[column] = pd.NA

    output["pickup_datetime"] = pd.to_datetime(output["pickup_datetime"], errors="coerce")
    output["dropoff_datetime"] = pd.to_datetime(output["dropoff_datetime"], errors="coerce")
    output["pickup_location_id"] = pd.to_numeric(output["pickup_location_id"], errors="coerce").astype("Int64")
    output["dropoff_location_id"] = pd.to_numeric(output["dropoff_location_id"], errors="coerce").astype("Int64")

    for numeric_column in ("trip_distance", "fare_amount", "passenger_count"):
        output[numeric_column] = pd.to_numeric(output[numeric_column], errors="coerce")

    output["month"] = month
    output["pickup_date"] = output["pickup_datetime"].dt.date.astype("string")
    output["pickup_hour"] = output["pickup_datetime"].dt.hour.astype("Int64")
    output["day_of_week"] = output["pickup_datetime"].dt.day_name()
    output["day_type"] = output["pickup_datetime"].dt.dayofweek.map(lambda day: "weekend" if day >= 5 else "weekday")
    output["temporal_segment"] = output["pickup_hour"].map(classify_temporal_segment)
    output["duration_minutes"] = (output["dropoff_datetime"] - output["pickup_datetime"]).dt.total_seconds() / 60
    return output[CANONICAL_COLUMNS]


def classify_temporal_segment(hour: int | float | None) -> str | None:
    if pd.isna(hour):
        return None
    hour_int = int(hour)
    if 7 <= hour_int < 10:
        return "morning_rush"
    if 10 <= hour_int < 16:
        return "midday"
    if 16 <= hour_int < 19:
        return "evening_rush"
    if 19 <= hour_int <= 23:
        return "night"
    return "late_night"
