"""Reference data ingestion helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from .config import REFERENCE_DIR, TAXI_ZONE_LOOKUP_URL


@dataclass
class ReferenceStatus:
    artifact: str
    status: str
    path: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def download_taxi_zone_lookup(overwrite: bool = False) -> dict[str, str]:
    """Download the TLC taxi zone lookup CSV into the reference layer."""
    path = REFERENCE_DIR / "taxi_zone_lookup.csv"
    if path.exists() and not overwrite:
        return ReferenceStatus("taxi_zone_lookup", "skipped", str(path), "Reference lookup already exists.").to_dict()

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = Path(f"{path}.tmp")
    try:
        with urlopen(TAXI_ZONE_LOOKUP_URL, timeout=30) as response, tmp_path.open("wb") as handle:
            handle.write(response.read())
        tmp_path.replace(path)
        return ReferenceStatus("taxi_zone_lookup", "downloaded", str(path), f"Downloaded {TAXI_ZONE_LOOKUP_URL}").to_dict()
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        if tmp_path.exists():
            tmp_path.unlink()
        return ReferenceStatus("taxi_zone_lookup", "failed", str(path), str(exc)).to_dict()
