"""Preprocessing and leakage-safe temporal features for predictive analysis."""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

TARGET_COLUMNS = {
    "area_mil_ha": ("area_anterior_mil_ha", "area_atual_mil_ha"),
    "produtividade_kg_ha": ("produtividade_anterior_kg_ha", "produtividade_atual_kg_ha"),
    "producao_mil_t": ("producao_anterior_mil_t", "producao_atual_mil_t"),
}


def safra_start(periodo: object) -> int:
    match = re.search(r"(\d{4})", str(periodo))
    if not match:
        return 0
    return int(match.group(1))


def next_safra(periodo: str) -> str:
    start = safra_start(periodo)
    return f"{start + 1}/{str(start + 2)[-2:]}"


def normalize_categories(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in ["produto", "regiao_uf", "tipo_linha"]:
        if col in out.columns:
            out[col] = out[col].astype("string").str.strip().str.upper()
    if "regiao_uf" not in out.columns:
        out["regiao_uf"] = "BRASIL"
    if "produto" not in out.columns:
        out["produto"] = "TODAS"
    return out


def wide_to_long(df: pd.DataFrame, grain: str) -> pd.DataFrame:
    base = normalize_categories(df)
    rows: list[dict[str, object]] = []
    id_cols = [c for c in ["tipo_linha", "produto", "regiao_uf", "fonte", "referencia"] if c in base.columns]
    for _, row in base.iterrows():
        for side, period_col in [("anterior", "periodo_anterior"), ("atual", "periodo_atual")]:
            record = {col: row.get(col) for col in id_cols}
            record["grao"] = grain
            record["safra"] = row.get(period_col)
            record["safra_ordem"] = safra_start(record["safra"])
            for target, pair in TARGET_COLUMNS.items():
                record[target] = pd.to_numeric(row.get(pair[0 if side == "anterior" else 1]), errors="coerce")
            rows.append(record)
    out = pd.DataFrame(rows).dropna(subset=["safra"])
    return out.sort_values(["grao", "produto", "regiao_uf", "safra_ordem"]).reset_index(drop=True)


def prepare_time_series(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    parts = [wide_to_long(df, grain) for grain, df in frames.items()]
    data = pd.concat(parts, ignore_index=True)
    value_cols = list(TARGET_COLUMNS)
    data[value_cols] = data[value_cols].apply(pd.to_numeric, errors="coerce")
    return data.drop_duplicates(["grao", "tipo_linha", "produto", "regiao_uf", "safra"], keep="last")


def add_temporal_features(df: pd.DataFrame) -> pd.DataFrame:
    sort_cols = ["grao", "tipo_linha", "produto", "regiao_uf", "safra_ordem"]
    out = df.sort_values(sort_cols).copy()
    group_cols = ["grao", "tipo_linha", "produto", "regiao_uf"]
    for target in TARGET_COLUMNS:
        grouped = out.groupby(group_cols, dropna=False)[target]
        out[f"{target}_lag_1"] = grouped.shift(1)
        out[f"{target}_lag_2"] = grouped.shift(2)
        out[f"{target}_lag_3"] = grouped.shift(3)
        out[f"{target}_media_movel_3"] = grouped.transform(lambda s: s.shift(1).rolling(3, min_periods=2).mean())
        out[f"{target}_media_movel_5"] = grouped.transform(lambda s: s.shift(1).rolling(5, min_periods=3).mean())
        out[f"{target}_crescimento_pct"] = grouped.pct_change(fill_method=None) * 100
        out[f"{target}_volatilidade"] = grouped.transform(lambda s: s.shift(1).rolling(3, min_periods=2).std())
    out["tendencia_historica"] = out.groupby(group_cols, dropna=False).cumcount()
    out.replace([np.inf, -np.inf], np.nan, inplace=True)
    return out
