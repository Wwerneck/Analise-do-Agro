from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/python"))

from pipeline import analytical_rows


def test_processed_files_exist():
    assert (ROOT / "data/processed/conab_produtos_clean.csv").exists()
    assert (ROOT / "data/processed/conab_ufs_clean.csv").exists()
    assert (ROOT / "data/processed/conab_produto_localidade_clean.csv").exists()


def test_core_measures_are_non_negative():
    base_cols = [
        "area_anterior_mil_ha",
        "area_atual_mil_ha",
        "produtividade_anterior_kg_ha",
        "produtividade_atual_kg_ha",
        "producao_anterior_mil_t",
        "producao_atual_mil_t",
    ]
    for file_name in ["conab_produtos_clean.csv", "conab_ufs_clean.csv"]:
        df = pd.read_csv(ROOT / "data/processed" / file_name)
        assert (df[base_cols] >= 0).all().all()


def test_product_location_missing_productivity_only_when_no_area_or_production():
    df = pd.read_csv(ROOT / "data/processed/conab_produto_localidade_clean.csv")
    productivity_cols = ["produtividade_anterior_kg_ha", "produtividade_atual_kg_ha"]
    other_base_cols = [
        "area_anterior_mil_ha",
        "area_atual_mil_ha",
        "producao_anterior_mil_t",
        "producao_atual_mil_t",
    ]
    assert (df[other_base_cols] >= 0).all().all()
    missing_productivity = df[df[productivity_cols].isna().any(axis=1)]
    assert (
        missing_productivity[["area_anterior_mil_ha", "area_atual_mil_ha", "producao_anterior_mil_t", "producao_atual_mil_t"]]
        .eq(0)
        .all(axis=1)
        .all()
    )


def test_state_rankings_filter_only_ufs():
    df = pd.read_csv(ROOT / "data/processed/conab_ufs_clean.csv")
    assert {"uf", "regiao", "agregado_regional", "total_brasil"}.issubset(set(df["tipo_linha"]))
    assert len(df[df["tipo_linha"].eq("uf")]) == 27


def test_percentage_recalculation_is_close():
    df = pd.read_csv(ROOT / "data/processed/conab_produtos_clean.csv")
    diff = (df["producao_variacao_pct"] - df["variacao_producao_pct_calc"]).abs()
    assert (diff.dropna() <= 0.2).mean() >= 0.9


def test_product_analytical_rows_do_not_double_count_total_production():
    products = pd.read_csv(ROOT / "data/processed/conab_produtos_clean.csv")
    states = pd.read_csv(ROOT / "data/processed/conab_ufs_clean.csv")
    product_total = analytical_rows(products, "produto")["producao_atual_mil_t"].sum()
    brazil_total = states.loc[states["tipo_linha"].eq("total_brasil"), "producao_atual_mil_t"].iloc[0]
    assert abs(product_total - brazil_total) <= 0.1


def test_analytical_exports_exist_and_are_valid():
    concentration = pd.read_csv(ROOT / "data/exports/indicadores_concentracao.csv")
    product_pareto = pd.read_csv(ROOT / "data/exports/pareto_produtos_producao.csv")
    state_pareto = pd.read_csv(ROOT / "data/exports/pareto_ufs_producao.csv")

    assert {"produto", "uf"}.issubset(set(concentration["dimensao"]))
    assert (concentration[["cr3_pct", "cr5_pct", "hhi"]] > 0).all().all()
    assert product_pareto["participacao_acumulada_pct"].is_monotonic_increasing
    assert state_pareto["participacao_acumulada_pct"].is_monotonic_increasing
    assert product_pareto["atinge_80_pct"].any()
    assert state_pareto["atinge_80_pct"].any()


def test_dashboard_exists():
    dashboard = ROOT / "reports/dashboard.html"
    assert dashboard.exists()
    html = dashboard.read_text(encoding="utf-8")
    assert "Agroscope" in html
    assert "Vis\u00e3o Geral" in html
    assert "Concentra\u00e7\u00e3o da produ\u00e7\u00e3o" in html
    assert "downloadCsv" in html
    assert "productsData" in html
    assert "productLocationData" in html
    assert "Content-Security-Policy" in html
    assert "escapeHtml" in html
    assert "csvCell" in html
    assert "withActiveShare" in html
    assert "regionSelect.disabled" not in html
    assert "produ\u00c3" not in html
    assert "eval(" not in html
    assert "document.write" not in html
    assert "fetch(" not in html
    assert "Vis\u00c3" not in html
    assert "produ\u00c3" not in html


def test_product_region_data_supports_cross_filter():
    df = pd.read_csv(ROOT / "data/processed/conab_produto_localidade_clean.csv")
    soja_centro_oeste = df[
        df["produto"].eq("SOJA")
        & df["tipo_linha"].eq("regiao")
        & df["regiao_uf"].eq("CENTRO-OESTE")
    ]
    assert not soja_centro_oeste.empty
    assert soja_centro_oeste.iloc[0]["producao_atual_mil_t"] > 0
    soja_mt = df[
        df["produto"].eq("SOJA")
        & df["tipo_linha"].eq("uf")
        & df["regiao_uf"].eq("MT")
    ]
    assert not soja_mt.empty
    assert soja_mt.iloc[0]["producao_atual_mil_t"] > 0

