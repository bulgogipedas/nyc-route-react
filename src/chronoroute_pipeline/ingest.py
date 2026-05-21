"""Bronze ingestion for TLC Parquet files."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from .tlc_source import build_tlc_url, check_tlc_file_available, get_expected_bronze_path, validate_service_type


@dataclass
class IngestStatus:
    service_type: str
    month: str
    status: str
    path: str | None
    message: str

    def to_dict(self) -> dict[str, str | None]:
        return asdict(self)


def download_month(service_type: str, year: int, month: int, overwrite: bool = False) -> dict[str, str | None]:
    service = validate_service_type(service_type)
    month_id = f"{int(year):04d}-{int(month):02d}"
    path = get_expected_bronze_path(service, year, month)
    url = build_tlc_url(service, year, month)

    if path.exists() and not overwrite:
        return IngestStatus(service, month_id, "skipped", str(path), "Bronze file already exists.").to_dict()

    if not check_tlc_file_available(service, year, month):
        return IngestStatus(service, month_id, "unavailable", str(path), f"TLC file is unavailable: {url}").to_dict()

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = Path(f"{path}.tmp")
    try:
        with urlopen(url, timeout=60) as response, tmp_path.open("wb") as handle:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
        tmp_path.replace(path)
        return IngestStatus(service, month_id, "downloaded", str(path), f"Downloaded {url}").to_dict()
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        if tmp_path.exists():
            tmp_path.unlink()
        return IngestStatus(service, month_id, "failed", str(path), str(exc)).to_dict()
