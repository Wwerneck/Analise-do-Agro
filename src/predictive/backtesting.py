"""Walk-forward backtesting for available series."""

from __future__ import annotations

import pandas as pd

from .evaluation import regression_metrics


def run_backtest(df: pd.DataFrame, target: str = "producao_mil_t") -> pd.DataFrame:
    rows = []
    for keys, group in df.groupby(["grao", "tipo_linha", "produto", "regiao_uf"], dropna=False):
        group = group.sort_values("safra_ordem").reset_index(drop=True)
        values = group[target].astype(float)
        if values.notna().sum() < 2:
            continue
        predicted = values.shift(1)
        for i in range(1, len(group)):
            metrics = regression_metrics([values.iloc[i]], [predicted.iloc[i]])
            rows.append({"grao": keys[0], "tipo_linha": keys[1], "cultura": keys[2], "uf": keys[3], "alvo": target, "safra_teste": group.loc[i, "safra"], "previsto": predicted.iloc[i], "real": values.iloc[i], "erro_pct": metrics["MAPE"], "modelo": "baseline_ingenuo"})
    return pd.DataFrame(rows)


def write_backtest_report(backtest: pd.DataFrame, path) -> None:
    if backtest.empty:
        text = "# Backtest Preditivo\n\nNao houve observacoes suficientes para executar backtest.\n"
    else:
        summary = backtest.groupby(["alvo", "modelo"]).agg(MAPE_medio=("erro_pct", "mean"), observacoes=("erro_pct", "count")).reset_index()
        text = "# Backtest Preditivo\n\nBacktest walk-forward disponivel com baseline ingenuo: cada safra e prevista pelo ultimo valor conhecido.\n\n"
        text += "| alvo | modelo | MAPE_medio | observacoes |\n|---|---|---:|---:|\n"
        for row in summary.itertuples(index=False):
            text += f"| {row.alvo} | {row.modelo} | {row.MAPE_medio:.4f} | {row.observacoes} |\n"
        text += "\n\nObservacao: o recorte atual tem somente duas safras, portanto existe apenas uma dobra historica por serie.\n"
    path.write_text(text, encoding="utf-8")
