"""Bronze-to-silver transformations."""

from __future__ import annotations

import pandas as pd

from .config import SILVER_DIR, TAXI_ZONE_LOOKUP_PATHS
from .schema import normalize_trip_schema
from .tlc_source import get_expected_bronze_path, validate_service_type


def _load_taxi_zone_lookup() -> pd.DataFrame | None:
    for path in TAXI_ZONE_LOOKUP_PATHS:
        if path.exists():
            lookup = pd.read_csv(path)
            lookup.columns = [column.strip() for column in lookup.columns]
            return lookup
    return None


def _enrich_zones(df: pd.DataFrame) -> pd.DataFrame:
    lookup = _load_taxi_zone_lookup()
    if lookup is None or "LocationID" not in lookup.columns:
        return df
    columns = [column for column in ("LocationID", "Borough", "Zone", "service_zone") if column in lookup.columns]
    lookup = lookup[columns].copy()

    pickup_lookup = lookup.rename(columns={
        "LocationID": "pickup_location_id",
        "Borough": "pickup_borough",
        "Zone": "pickup_zone",
        "service_zone": "pickup_service_zone",
    })
    dropoff_lookup = lookup.rename(columns={
        "LocationID": "dropoff_location_id",
        "Borough": "dropoff_borough",
        "Zone": "dropoff_zone",
        "service_zone": "dropoff_service_zone",
    })
    df = df.merge(pickup_lookup, on="pickup_location_id", how="left")
    df = df.merge(dropoff_lookup, on="dropoff_location_id", how="left")
    return df


def clean_month(service_type: str, year: int, month: int) -> dict[str, str | int]:
    service = validate_service_type(service_type)
    month_id = f"{int(year):04d}-{int(month):02d}"
    source_path = get_expected_bronze_path(service, year, month)
    if not source_path.exists():
        raise FileNotFoundError(f"Missing bronze file: {source_path}")

    raw = pd.read_parquet(source_path)
    cleaned = normalize_trip_schema(raw, service, month_id)
    cleaned = cleaned.dropna(subset=["pickup_datetime", "pickup_location_id", "dropoff_location_id"])

    if cleaned["dropoff_datetime"].notna().any():
        cleaned = cleaned[(cleaned["dropoff_datetime"].isna()) | (cleaned["dropoff_datetime"] > cleaned["pickup_datetime"])]
    for optional_positive in ("trip_distance", "fare_amount", "passenger_count"):
        values = cleaned[optional_positive]
        cleaned = cleaned[(values.isna()) | (values >= 0)]

    cleaned = cleaned[(cleaned["pickup_hour"].notna()) & (cleaned["pickup_hour"].between(0, 23))]
    cleaned = _enrich_zones(cleaned)

    output_path = SILVER_DIR / service / f"{month_id}_cleaned.parquet"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cleaned.to_parquet(output_path, index=False)
    return {"service_type": service, "month": month_id, "status": "cleaned", "path": str(output_path), "rows": int(len(cleaned))}
