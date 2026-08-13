"""Metrics and model comparison helpers."""

from __future__ import annotations

import numpy as np
import pandas as pd


def regression_metrics(y_true, y_pred) -> dict[str, float]:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    mask = ~(np.isnan(y_true) | np.isnan(y_pred))
    y_true, y_pred = y_true[mask], y_pred[mask]
    if len(y_true) == 0:
        return {"MAE": np.nan, "RMSE": np.nan, "MAPE": np.nan, "R2": np.nan}
    err = y_true - y_pred
    mae = float(np.mean(np.abs(err)))
    rmse = float(np.sqrt(np.mean(err**2)))
    pct_mask = np.abs(y_true) > 1e-9
    mape = float(np.mean(np.abs(err[pct_mask] / y_true[pct_mask])) * 100) if pct_mask.any() else np.nan
    denom = float(np.sum((y_true - y_true.mean()) ** 2))
    r2 = float(1 - np.sum(err**2) / denom) if denom > 0 else np.nan
    return {"MAE": mae, "RMSE": rmse, "MAPE": mape, "R2": r2}


def select_best_model(metrics: pd.DataFrame) -> str | None:
    valid = metrics.dropna(subset=["MAE", "RMSE"], how="all")
    if valid.empty:
        return None
    return str(valid.sort_values(["MAE", "RMSE"], na_position="last").iloc[0]["modelo"])

