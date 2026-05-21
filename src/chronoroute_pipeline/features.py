"""Feature engineering helpers for analytics and modeling."""

from __future__ import annotations

import pandas as pd


def add_service_zone_hour_key(df: pd.DataFrame) -> pd.DataFrame:
    output = df.copy()
    zone_col = "pickup_zone" if "pickup_zone" in output.columns else "pickup_location_id"
    output["service_zone_hour_key"] = (
        output["service_type"].astype(str)
        + "|"
        + output[zone_col].astype(str)
        + "|"
        + output["pickup_hour"].astype(str)
    )
    return output
