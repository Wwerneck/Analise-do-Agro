"""Deterministic insight generation from predictive outputs."""

from __future__ import annotations

import pandas as pd


def generate_insights(forecasts: pd.DataFrame, trends: pd.DataFrame) -> list[str]:
    insights: list[str] = []
    prod = forecasts[forecasts["alvo"].eq("producao_mil_t")].copy()
    if not prod.empty:
        top = prod.sort_values("valor_previsto", ascending=False).iloc[0]
        insights.append(f"{top['cultura']} em {top['uf']} apresenta maior producao prevista no recorte calculado: {top['valor_previsto']:.2f} mil t, com {top['confianca'].lower()}.")
        growth = prod.sort_values("variacao_prevista_pct", ascending=False).iloc[0]
        insights.append(f"O maior crescimento percentual previsto aparece em {growth['cultura']} / {growth['uf']}: {growth['variacao_prevista_pct']:.2f}% segundo a estimativa do modelo.")
    if not trends.empty:
        trend = trends[trends["alvo"].eq("producao_mil_t")].sort_values("crescimento_medio_pct", ascending=False).iloc[0]
        insights.append(f"A tendencia historica mais favoravel no recorte e {trend['tendencia']} para {trend['cultura']} / {trend['uf']}.")
    if not insights:
        insights.append("Historico insuficiente para gerar insights preditivos robustos sem incorporar novas safras oficiais.")
    return insights

