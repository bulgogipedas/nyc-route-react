"""NYC TLC source discovery helpers."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import BRONZE_DIR, SERVICE_DISPLAY_NAMES, SUPPORTED_SERVICES, TLC_TRIP_DATA_BASE_URL


def list_supported_services() -> list[str]:
    return list(SUPPORTED_SERVICES)


def validate_service_type(service_type: str) -> str:
    service = service_type.lower().strip()
    if service not in SUPPORTED_SERVICES:
        raise ValueError(f"Unsupported service_type '{service_type}'. Expected one of: {', '.join(SUPPORTED_SERVICES)}")
    return service


def get_service_display_name(service_type: str) -> str:
    return SERVICE_DISPLAY_NAMES[validate_service_type(service_type)]


def build_tlc_url(service_type: str, year: int, month: int) -> str:
    service = validate_service_type(service_type)
    if not 1 <= int(month) <= 12:
        raise ValueError("month must be between 1 and 12")
    return f"{TLC_TRIP_DATA_BASE_URL}/{service}_tripdata_{int(year):04d}-{int(month):02d}.parquet"


def check_tlc_file_available(service_type: str, year: int, month: int, timeout: int = 12) -> bool:
    url = build_tlc_url(service_type, year, month)
    head_request = Request(url, method="HEAD")
    try:
        with urlopen(head_request, timeout=timeout) as response:
            return 200 <= response.status < 400
    except (HTTPError, URLError, TimeoutError, OSError):
        pass

    get_request = Request(url, headers={"Range": "bytes=0-1023"})
    try:
        with urlopen(get_request, timeout=timeout) as response:
            return 200 <= response.status < 400
    except (HTTPError, URLError, TimeoutError, OSError):
        return False


def get_expected_bronze_path(service_type: str, year: int, month: int) -> Path:
    service = validate_service_type(service_type)
    return BRONZE_DIR / service / f"{int(year):04d}-{int(month):02d}.parquet"


def list_target_months(start_month: str, end_month: str | None = None) -> list[str]:
    start = datetime.strptime(start_month, "%Y-%m")
    end = datetime.strptime(end_month or start_month, "%Y-%m")
    if end < start:
        raise ValueError("end_month must be greater than or equal to start_month")

    months: list[str] = []
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        months.append(f"{year:04d}-{month:02d}")
        month += 1
        if month == 13:
            year += 1
            month = 1
    return months


def shift_month(month: str, offset: int) -> str:
    current = datetime.strptime(month, "%Y-%m")
    year = current.year
    month_num = current.month + offset
    while month_num < 1:
        year -= 1
        month_num += 12
    while month_num > 12:
        year += 1
        month_num -= 12
    return f"{year:04d}-{month_num:02d}"


def find_latest_available_month(
    services: list[str] | None = None,
    end_month: str | None = None,
    lookback_months: int = 12,
    require_all_services: bool = False,
) -> str | None:
    target_services = [validate_service_type(service) for service in (services or list_supported_services())]
    search_end = end_month or datetime.utcnow().strftime("%Y-%m")
    for index in range(lookback_months):
        candidate = shift_month(search_end, -index)
        year, month = (int(part) for part in candidate.split("-"))
        availability = [check_tlc_file_available(service, year, month) for service in target_services]
        if require_all_services and all(availability):
            return candidate
        if not require_all_services and any(availability):
            return candidate
    return None
