"""Central configuration for the ChronoRoute data pipeline."""

from __future__ import annotations

from pathlib import Path

PIPELINE_VERSION = "0.1.0"
PROJECT_NAME = "ChronoRoute"
TLC_SOURCE_NAME = "NYC TLC Trip Record Data"
TLC_SOURCE_PAGE = "https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page"
TLC_TRIP_DATA_BASE_URL = "https://d37ci6vzurychx.cloudfront.net/trip-data"

SUPPORTED_SERVICES = ("yellow", "green", "fhv", "fhvhv")
SERVICE_DISPLAY_NAMES = {
    "yellow": "Yellow Taxi",
    "green": "Green Taxi",
    "fhv": "For-Hire Vehicle",
    "fhvhv": "High Volume For-Hire Vehicle",
}

ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
BRONZE_DIR = DATA_DIR / "bronze"
SILVER_DIR = DATA_DIR / "silver"
GOLD_DIR = DATA_DIR / "gold"
REFERENCE_DIR = DATA_DIR / "reference"
PUBLIC_DATA_DIR = ROOT_DIR / "public" / "data"
TAXI_ZONE_LOOKUP_PATHS = (
    REFERENCE_DIR / "taxi_zone_lookup.csv",
    DATA_DIR / "taxi_zone_lookup.csv",
)
TAXI_ZONES_GEOJSON_PATHS = (
    REFERENCE_DIR / "taxi_zones.json",
    DATA_DIR / "taxi_zones.json",
)

DEFAULT_INTERACTIVE_RECORDS_PER_SERVICE_MONTH = 30_000
