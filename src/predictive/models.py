"""Forecasting models with conservative fallbacks for short CONAB series."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .evaluation import regression_metrics

RANDOM_STATE = 42


@dataclass
class ModelResult:
    modelo: str
    prediction: float
    metrics: dict[str, float]
    feature_importance: pd.DataFrame


def naive_forecast(series: pd.Series) -> float:
    values = pd.to_numeric(series, errors="coerce").dropna()
    return float(values.iloc[-1]) if not values.empty else np.nan


def evaluate_available_models(series: pd.Series, min_train: int = 3) -> pd.DataFrame:
    values = pd.to_numeric(series, errors="coerce").dropna().reset_index(drop=True)
    rows: list[dict[str, object]] = []
    if len(values) >= 2:
        y_true = values.iloc[1:]
        y_pred = values.shift(1).dropna()
        rows.append({"modelo": "baseline_ingenuo", **regression_metrics(y_true, y_pred), "observacoes": len(values)})
    for name in ["regressao_linear", "random_forest", "xgboost", "exponential_smoothing"]:
        rows.append({"modelo": name, "MAE": np.nan, "RMSE": np.nan, "MAPE": np.nan, "R2": np.nan, "observacoes": len(values), "status": "historico_insuficiente"})
    return pd.DataFrame(rows)

