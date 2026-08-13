"""Next-season forecast exports."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .models import evaluate_available_models, naive_forecast
from .preprocessing import next_safra


def confidence_label(n_obs: int, mape: float, volatility: float, model_spread: float = 0) -> str:
    if n_obs >= 8 and (pd.isna(mape) or mape < 12) and volatility < 0.20 and model_spread < 0.10:
        return "ALTA CONFIANCA"
    if n_obs >= 5 and (pd.isna(mape) or mape < 25) and volatility < 0.35:
        return "MEDIA CONFIANCA"
    return "BAIXA CONFIANCA"


def forecast_next(df: pd.DataFrame, target: str, allowed_types: set[str] | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, object]] = []
    metric_rows: list[pd.DataFrame] = []
    allowed_types = allowed_types or {"PRODUTO", "UF", "REGIAO", "TOTAL_BRASIL"}
    for keys, group in df[df["tipo_linha"].isin(allowed_types)].groupby(["grao", "tipo_linha", "produto", "regiao_uf"], dropna=False):
        group = group.sort_values("safra_ordem")
        series = group[target]
        metrics = evaluate_available_models(series)
        if not metrics.empty:
            metric_rows.append(metrics.assign(grao=keys[0], tipo_linha=keys[1], produto=keys[2], regiao_uf=keys[3], alvo=target))
        current = pd.to_numeric(series, errors="coerce").dropna()
        if current.empty:
            continue
        predicted = naive_forecast(series)
        previous = float(current.iloc[-1])
        pct = ((predicted - previous) / previous * 100) if previous else np.nan
        resid = current.diff().dropna()
        sigma = float(resid.std()) if len(resid) >= 2 else np.nan
        margin = 1.96 * sigma if pd.notna(sigma) else np.nan
        vol = float(current.pct_change(fill_method=None).std()) if len(current) >= 3 else 1.0
        mape = metrics.loc[metrics["modelo"].eq("baseline_ingenuo"), "MAPE"].mean() if "modelo" in metrics else np.nan
        rows.append({
            "safra_prevista": next_safra(str(group["safra"].iloc[-1])),
            "cultura": keys[2],
            "uf": keys[3],
            "tipo_linha": keys[1],
            "alvo": target,
            "valor_anterior": previous,
            "valor_previsto": predicted,
            "variacao_prevista_pct": pct,
            "limite_inferior": predicted - margin if pd.notna(margin) else np.nan,
            "limite_superior": predicted + margin if pd.notna(margin) else np.nan,
            "modelo_utilizado": "baseline_ingenuo",
            "MAE": metrics.loc[metrics["modelo"].eq("baseline_ingenuo"), "MAE"].mean() if "modelo" in metrics else np.nan,
            "RMSE": metrics.loc[metrics["modelo"].eq("baseline_ingenuo"), "RMSE"].mean() if "modelo" in metrics else np.nan,
            "MAPE": mape,
            "confianca": confidence_label(len(current), float(mape) if pd.notna(mape) else np.nan, vol),
            "observacoes": len(current),
            "status": "estimativa_baseline_com_historico_curto" if len(current) < 5 else "estimativa_modelo",
        })
    return pd.DataFrame(rows), pd.concat(metric_rows, ignore_index=True) if metric_rows else pd.DataFrame()
