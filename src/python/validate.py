"""Validation helpers for processed CONAB datasets."""

from __future__ import annotations

import pandas as pd

NON_NEGATIVE_COLUMNS = [
    "area_anterior_mil_ha",
    "area_atual_mil_ha",
    "produtividade_anterior_kg_ha",
    "produtividade_atual_kg_ha",
    "producao_anterior_mil_t",
    "producao_atual_mil_t",
]


def validate_non_negative(df: pd.DataFrame) -> None:
    """Raise an error when core agronomic measures contain negative values."""
    for column in NON_NEGATIVE_COLUMNS:
        if column in df.columns and (df[column] < 0).any():
            raise ValueError(f"Coluna {column} possui valores negativos")


def validate_required_columns(df: pd.DataFrame, required: set[str]) -> None:
    """Raise an error when required columns are missing."""
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Colunas obrigatorias ausentes: {sorted(missing)}")
