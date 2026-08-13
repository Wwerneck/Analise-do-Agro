from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.predictive.data_validation import audit_predictive_data
from src.predictive.evaluation import regression_metrics, select_best_model
from src.predictive.forecast import forecast_next
from src.predictive.pipeline import run_pipeline
from src.predictive.preprocessing import add_temporal_features, prepare_time_series
from src.predictive.trends import classify_trend


def sample_wide():
    return pd.DataFrame(
        {
            "tipo_linha": ["produto"],
            "produto": ["SOJA"],
            "periodo_anterior": ["2024/25"],
            "periodo_atual": ["2025/26"],
            "area_anterior_mil_ha": [10.0],
            "area_atual_mil_ha": [11.0],
            "produtividade_anterior_kg_ha": [3000.0],
            "produtividade_atual_kg_ha": [3100.0],
            "producao_anterior_mil_t": [30.0],
            "producao_atual_mil_t": [34.1],
        }
    )


def test_prepare_time_series_creates_two_ordered_periods():
    out = prepare_time_series({"produto": sample_wide()})
    assert list(out["safra"]) == ["2024/25", "2025/26"]
    assert list(out["producao_mil_t"]) == [30.0, 34.1]


def test_lag_uses_only_previous_period():
    out = add_temporal_features(prepare_time_series({"produto": sample_wide()}))
    current = out[out["safra"].eq("2025/26")].iloc[0]
    assert current["producao_mil_t_lag_1"] == 30.0
    assert pd.isna(out[out["safra"].eq("2024/25")].iloc[0]["producao_mil_t_lag_1"])


def test_validation_warns_about_short_history():
    result = audit_predictive_data(prepare_time_series({"produto": sample_wide()}))
    assert result.summary["treinavel"].eq(False).all()
    assert any("Historico insuficiente" in warning for warning in result.warnings)


def test_metrics_and_best_model_selection():
    metrics = regression_metrics([10, 20], [12, 18])
    assert metrics["MAE"] == 2.0
    table = pd.DataFrame([{"modelo": "a", "MAE": 3, "RMSE": 4}, {"modelo": "b", "MAE": 2, "RMSE": 5}])
    assert select_best_model(table) == "b"


def test_forecast_next_uses_baseline_for_short_series():
    long_df = prepare_time_series({"produto": sample_wide()})
    forecast, metrics = forecast_next(long_df, "producao_mil_t")
    assert forecast.iloc[0]["modelo_utilizado"] == "baseline_ingenuo"
    assert forecast.iloc[0]["valor_previsto"] == 34.1
    assert forecast.iloc[0]["confianca"] == "BAIXA CONFIANCA"
    assert "random_forest" in set(metrics["modelo"])


def test_trend_classification():
    assert classify_trend(15, 0.1) == "FORTE ALTA"
    assert classify_trend(-4, 0.8) == "QUEDA"
    assert classify_trend(0.5, 0.1) == "ESTAVEL"


def test_pipeline_exports_prediction_files():
    result = run_pipeline()
    prediction_dir = ROOT / "data" / "processed" / "predictions"
    assert result["safras"] == ["2024/25", "2025/26"]
    assert (prediction_dir / "forecast_production.csv").exists()
    assert (prediction_dir / "model_metrics.csv").exists()
    assert (ROOT / "reports" / "predictive_backtest.md").exists()
    assert (ROOT / "reports" / "model_metadata.json").exists()
