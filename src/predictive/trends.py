"""Trend classification for short agricultural series."""

from __future__ import annotations

import numpy as np
import pandas as pd


def classify_trend(avg_growth: float, volatility: float) -> str:
    if pd.isna(avg_growth):
        return "ESTAVEL"
    if avg_growth >= 12 and volatility < 0.50:
        return "FORTE ALTA"
    if avg_growth >= 3:
        return "ALTA"
    if avg_growth <= -12 and volatility < 0.50:
        return "FORTE QUEDA"
    if avg_growth <= -3:
        return "QUEDA"
    return "ESTAVEL"


def trend_table(df: pd.DataFrame, target: str = "producao_mil_t") -> pd.DataFrame:
    rows = []
    for keys, group in df.groupby(["grao", "tipo_linha", "produto", "regiao_uf"], dropna=False):
        values = group.sort_values("safra_ordem")[target].astype(float)
        growth = values.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan) * 100
        avg_growth = float(growth.mean()) if growth.notna().any() else np.nan
        volatility = float(growth.std() / 100) if growth.notna().sum() >= 2 else 1.0
        rows.append({"grao": keys[0], "tipo_linha": keys[1], "cultura": keys[2], "uf": keys[3], "alvo": target, "crescimento_medio_pct": avg_growth, "volatilidade": volatility, "tendencia": classify_trend(avg_growth, volatility)})
    return pd.DataFrame(rows)

