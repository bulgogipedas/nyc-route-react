"""Baseline demand forecasting utilities."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .config import GOLD_DIR


def baseline_demand_forecast(month: str, service_type: str, window: int = 3) -> dict:
    source = GOLD_DIR / service_type / f"zone_hour_metrics_{month}.parquet"
    if not source.exists():
        return {"status": "skipped", "message": f"Missing gold zone metrics: {source}"}
    df = pd.read_parquet(source)
    forecast = df.sort_values(["pickup_location_id" if "pickup_location_id" in df.columns else "pickup_zone", "hour"]).copy()
    forecast["forecast_pickup_count"] = forecast.groupby("hour")["pickup_count"].transform(lambda s: s.rolling(window, min_periods=1).mean())
    output = GOLD_DIR / service_type / f"demand_forecast_{month}.parquet"
    forecast.to_parquet(output, index=False)
    return {"status": "generated", "path": str(output), "rows": int(len(forecast))}
