"""Explainable repositioning recommendations."""

from __future__ import annotations

import pandas as pd

from .config import GOLD_DIR


def generate_repositioning_recommendations(month: str, service_type: str, top_n: int = 25) -> dict:
    source = GOLD_DIR / service_type / f"zone_hour_metrics_{month}.parquet"
    if not source.exists():
        return {"status": "skipped", "message": f"Missing gold zone metrics: {source}"}
    df = pd.read_parquet(source)
    zone_col = "pickup_zone" if "pickup_zone" in df.columns else "pickup_location_id"
    demand = df[df["demand_pressure_index"] > 0].sort_values("demand_pressure_index", ascending=False)
    surplus = df[df["idle_relocation_opportunity_score"] > 0].sort_values("idle_relocation_opportunity_score", ascending=False)
    recommendations = []
    for rank, ((_, from_row), (_, to_row)) in enumerate(zip(surplus.iterrows(), demand.iterrows()), start=1):
        confidence = min(1.0, float((from_row["idle_relocation_opportunity_score"] + to_row["demand_pressure_index"]) / max(df["total_activity"].max(), 1)))
        recommendations.append({
            "rank": rank,
            "month": month,
            "service_type": service_type,
            "hour": int(to_row["hour"]),
            "from_zone": from_row[zone_col],
            "to_zone": to_row[zone_col],
            "confidence_score": confidence,
            "reason": "Move idle vehicles from dropoff-surplus zones toward pickup-pressure zones.",
        })
        if rank >= top_n:
            break
    output_df = pd.DataFrame(recommendations)
    output = GOLD_DIR / service_type / f"repositioning_recommendations_{month}.parquet"
    output_df.to_parquet(output, index=False)
    return {"status": "generated", "path": str(output), "rows": int(len(output_df))}
