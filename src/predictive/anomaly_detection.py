"""Anomaly flags for CONAB time series."""

from __future__ import annotations

import numpy as np
import pandas as pd


def detect_anomalies(df: pd.DataFrame, target: str = "producao_mil_t") -> pd.DataFrame:
    rows = []
    for keys, group in df.groupby(["grao", "tipo_linha", "produto", "regiao_uf"], dropna=False):
        values = group.sort_values("safra_ordem")[target].astype(float)
        if values.notna().sum() < 4:
            continue
        z = (values - values.mean()) / values.std(ddof=0)
        for idx, score in z.items():
            if pd.notna(score) and abs(score) >= 2.5:
                row = group.loc[idx]
                rows.append({"grao": keys[0], "tipo_linha": keys[1], "cultura": keys[2], "uf": keys[3], "safra": row["safra"], "alvo": target, "valor": row[target], "metodo": "z_score", "score": float(score)})
    return pd.DataFrame(rows, columns=["grao", "tipo_linha", "cultura", "uf", "safra", "alvo", "valor", "metodo", "score"])

