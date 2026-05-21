"""Forecast evaluation helpers."""

from __future__ import annotations

import math

import pandas as pd


def evaluate_forecast(actual: pd.Series, forecast: pd.Series) -> dict[str, float]:
    aligned = pd.concat([actual.rename("actual"), forecast.rename("forecast")], axis=1).dropna()
    if aligned.empty:
        return {"mae": math.nan, "rmse": math.nan, "rows": 0}
    errors = aligned["actual"] - aligned["forecast"]
    return {
        "mae": float(errors.abs().mean()),
        "rmse": float((errors.pow(2).mean()) ** 0.5),
        "rows": int(len(aligned)),
    }
