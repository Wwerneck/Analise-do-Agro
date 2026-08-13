"""Automatic data audit for predictive modelling readiness."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class ValidationResult:
    summary: pd.DataFrame
    warnings: list[str]


def audit_predictive_data(df: pd.DataFrame, min_periods: int = 5) -> ValidationResult:
    group_cols = ["grao", "tipo_linha", "produto", "regiao_uf"]
    periods = sorted(df["safra"].dropna().astype(str).unique(), key=lambda x: int(str(x)[:4]))
    counts = df.groupby(group_cols, dropna=False).agg(
        observacoes=("safra", "nunique"),
        periodo_min=("safra_ordem", "min"),
        periodo_max=("safra_ordem", "max"),
        ausentes=("producao_mil_t", lambda s: int(s.isna().sum())),
    ).reset_index()
    counts["treinavel"] = counts["observacoes"] >= min_periods
    warnings: list[str] = []
    if len(periods) < min_periods:
        warnings.append(
            f"Historico insuficiente para Machine Learning temporal: {len(periods)} safras encontradas ({', '.join(periods)}); minimo recomendado: {min_periods}."
        )
    if not counts["treinavel"].any():
        warnings.append("Nenhuma serie possui observacoes suficientes para treinamento preditivo robusto.")
    duplicate_count = int(df.duplicated(["grao", "tipo_linha", "produto", "regiao_uf", "safra"]).sum())
    if duplicate_count:
        warnings.append(f"Foram encontradas {duplicate_count} duplicidades por serie/safra.")
    return ValidationResult(counts, warnings)

