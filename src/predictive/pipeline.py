"""Central predictive pipeline for Agroscope."""

from __future__ import annotations

import json
from datetime import datetime
from html import escape
from pathlib import Path

import pandas as pd

from .anomaly_detection import detect_anomalies
from .backtesting import run_backtest, write_backtest_report
from .data_validation import audit_predictive_data
from .forecast import forecast_next
from .insights import generate_insights
from .preprocessing import add_temporal_features, prepare_time_series
from .trends import trend_table

ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data" / "processed"
PREDICTIONS = PROCESSED / "predictions"
REPORTS = ROOT / "reports"


def load_processed_frames() -> dict[str, pd.DataFrame]:
    return {
        "produto": pd.read_csv(PROCESSED / "conab_produtos_clean.csv"),
        "uf": pd.read_csv(PROCESSED / "conab_ufs_clean.csv"),
        "produto_uf": pd.read_csv(PROCESSED / "conab_produto_localidade_clean.csv"),
    }


def export_csv_parquet(df: pd.DataFrame, name: str) -> None:
    csv_path = PREDICTIONS / f"{name}.csv"
    df.to_csv(csv_path, index=False, encoding="utf-8")
    if not df.empty:
        df.to_parquet(PREDICTIONS / f"{name}.parquet", index=False)


def write_dashboard_section(forecasts: pd.DataFrame, metrics: pd.DataFrame, insights: list[str]) -> None:
    dashboard = REPORTS / "dashboard.html"
    if not dashboard.exists() or forecasts.empty:
        return
    production = forecasts[forecasts["alvo"].eq("producao_mil_t")].copy()
    top_growth = production.sort_values("variacao_prevista_pct", ascending=False).head(10)
    best = metrics[metrics["modelo"].eq("baseline_ingenuo")]
    mae = best["MAE"].mean() if not best.empty else float("nan")
    rmse = best["RMSE"].mean() if not best.empty else float("nan")
    mape = best["MAPE"].mean() if not best.empty else float("nan")
    total_rows = production[production["tipo_linha"].eq("TOTAL_BRASIL") & production["cultura"].eq("TODAS")]
    if total_rows.empty:
        total_rows = production[production["tipo_linha"].eq("TOTAL_BRASIL") & ~production["cultura"].str.contains("SAFRA|IRRIGADO|SEQUEIRO|CORES|PRETO|CAUPI", na=False)]
    if total_rows.empty:
        total_rows = production[production["tipo_linha"].eq("UF")]
    total_prev = total_rows["valor_previsto"].sum()
    total_var = total_rows["variacao_prevista_pct"].mean()
    rows = "\n".join(
        f"<tr><td>{escape(str(r.cultura))}</td><td>{escape(str(r.uf))}</td><td>{r.valor_anterior:,.2f}</td><td>{r.valor_previsto:,.2f}</td><td>{r.variacao_prevista_pct:,.2f}%</td><td>{escape(str(r.confianca))}</td></tr>"
        for r in top_growth.itertuples()
    )
    insight_html = "".join(f"<div class=\"panel\"><p class=\"lead\">{escape(text)}</p></div>" for text in insights[:3])
    section = f"""
    <h2>ANALISE PREDITIVA</h2>
    <p class="lead">As previsoes representam estimativas estatisticas baseadas no comportamento historico dos dados e nao constituem previsao oficial da CONAB. Como o recorte atual possui somente duas safras, modelos complexos foram bloqueados e os resultados abaixo usam baseline ingenuo com baixa confianca.</p>
    <section class="kpis" id="predictiveKpis">
      <div class="card"><span class="label">PRODUCAO PREVISTA</span><strong class="value">{total_prev:,.1f} mil t</strong><small class="note">Cenario esperado do modelo</small></div>
      <div class="card"><span class="label">PRODUTIVIDADE PREVISTA</span><strong class="value">baseline</strong><small class="note">Ultimo valor conhecido por serie</small></div>
      <div class="card"><span class="label">VARIACAO ESPERADA</span><strong class="value">{total_var:,.2f}%</strong><small class="note">Proxima safra estimada</small></div>
      <div class="card"><span class="label">MODELO MAIS PRECISO</span><strong class="value">Baseline</strong><small class="note">MAE medio {mae:,.2f} | RMSE {rmse:,.2f} | MAPE {mape:,.2f}%</small></div>
    </section>
    <h2>QUALIDADE DAS PREVISOES</h2>
    <section class="panel"><p class="lead">MAPE representa o erro percentual medio das previsoes. Quanto menor, melhor. A confianca foi classificada por quantidade de historico, erro medio, estabilidade da serie e diferenca entre modelos.</p></section>
    <h2>TOP CULTURAS COM MAIOR CRESCIMENTO PREVISTO</h2>
    <section class="panel"><div style="overflow:auto"><table><thead><tr><th>Cultura</th><th>UF</th><th>Producao atual</th><th>Producao prevista</th><th>Variacao</th><th>Confianca</th></tr></thead><tbody>{rows}</tbody></table></div></section>
    <h2>Insights Preditivos</h2>
    <section class="insights">{insight_html}</section>
"""
    html = dashboard.read_text(encoding="utf-8")
    marker_start = "<!-- predictive-section-start -->"
    marker_end = "<!-- predictive-section-end -->"
    block = f"{marker_start}{section}{marker_end}"
    if marker_start in html and marker_end in html:
        html = html.split(marker_start)[0] + block + html.split(marker_end)[1]
    else:
        html = html.replace("  </main>", block + "\n  </main>")
    dashboard.write_text(html, encoding="utf-8")


def run_pipeline() -> dict[str, object]:
    PREDICTIONS.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    frames = load_processed_frames()
    long_df = prepare_time_series(frames)
    features = add_temporal_features(long_df)
    validation = audit_predictive_data(long_df)
    export_csv_parquet(validation.summary, "data_audit")
    export_csv_parquet(features, "features")
    all_forecasts, all_metrics = [], []
    for target, name in [("producao_mil_t", "forecast_production"), ("produtividade_kg_ha", "forecast_productivity"), ("area_mil_ha", "forecast_area")]:
        fc, metrics = forecast_next(long_df, target)
        export_csv_parquet(fc, name)
        all_forecasts.append(fc)
        all_metrics.append(metrics)
    forecasts = pd.concat(all_forecasts, ignore_index=True)
    metrics = pd.concat(all_metrics, ignore_index=True)
    export_csv_parquet(metrics, "model_metrics")
    export_csv_parquet(metrics, "model_comparison")
    trends = pd.concat([trend_table(long_df, t) for t in ["producao_mil_t", "produtividade_kg_ha", "area_mil_ha"]], ignore_index=True)
    anomalies = pd.concat([detect_anomalies(long_df, t) for t in ["producao_mil_t", "produtividade_kg_ha", "area_mil_ha"]], ignore_index=True)
    export_csv_parquet(trends, "trends")
    export_csv_parquet(anomalies, "anomalies")
    backtest = pd.concat([run_backtest(long_df, t) for t in ["producao_mil_t", "produtividade_kg_ha", "area_mil_ha"]], ignore_index=True)
    export_csv_parquet(backtest, "backtest")
    write_backtest_report(backtest, REPORTS / "predictive_backtest.md")
    insights = generate_insights(forecasts, trends)
    (PREDICTIONS / "insights.txt").write_text("\n".join(insights), encoding="utf-8")
    write_dashboard_section(forecasts, metrics, insights)
    metadata = {
        "executed_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "modelos": ["baseline_ingenuo", "regressao_linear", "random_forest", "xgboost", "exponential_smoothing"],
        "modelo_efetivamente_usado": "baseline_ingenuo",
        "motivo": "Historico oficial disponivel possui somente duas safras; modelos complexos foram bloqueados por insuficiencia de dados.",
        "features": [c for c in features.columns if "lag" in c or "media_movel" in c or "crescimento" in c or "volatilidade" in c],
        "warnings": validation.warnings,
    }
    (REPORTS / "model_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"warnings": validation.warnings, "safras": sorted(long_df["safra"].unique()), "forecasts": len(forecasts), "metrics": len(metrics)}


def main() -> None:
    result = run_pipeline()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
