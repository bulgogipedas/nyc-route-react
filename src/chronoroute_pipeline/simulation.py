"""Simple repositioning simulation helpers."""

from __future__ import annotations

import pandas as pd

from .config import GOLD_DIR


def simulate_repositioning(month: str, service_type: str, hour: int, taxi_count: int) -> dict:
    source = GOLD_DIR / service_type / f"zone_hour_metrics_{month}.parquet"
    if not source.exists():
        return {"status": "skipped", "message": f"Missing gold zone metrics: {source}"}
    df = pd.read_parquet(source)
    active = df[df["hour"] == hour].copy()
    before = float(active["normalized_imbalance_score"].abs().mean()) if not active.empty else 0.0
    reducible = min(float(taxi_count), float(active["demand_pressure_index"].sum()))
    after = max(0.0, before - (reducible / max(float(active["total_activity"].sum()), 1.0)))
    return {
        "status": "simulated",
        "month": month,
        "service_type": service_type,
        "hour": hour,
        "taxi_count": taxi_count,
        "before_avg_abs_imbalance": before,
        "after_avg_abs_imbalance": after,
        "estimated_reduction": before - after,
    }
