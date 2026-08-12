"""Reusable KPI calculations."""

from __future__ import annotations

import pandas as pd


def concentration_ratio(df: pd.DataFrame, value_col: str, n: int) -> float:
    """Return CRn concentration ratio as percentage."""
    total = df[value_col].sum()
    if total <= 0:
        return float("nan")
    return float(df.nlargest(n, value_col)[value_col].sum() / total * 100)


def pareto_table(df: pd.DataFrame, entity_col: str, value_col: str) -> pd.DataFrame:
    """Create a Pareto table with individual and cumulative shares."""
    out = df[[entity_col, value_col]].sort_values(value_col, ascending=False).reset_index(drop=True)
    total = out[value_col].sum()
    out["ranking"] = out.index + 1
    out["participacao_pct"] = out[value_col] / total * 100
    out["participacao_acumulada_pct"] = out["participacao_pct"].cumsum()
    return out
