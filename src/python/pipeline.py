"""End-to-end pipeline for the Agroscope portfolio project."""

from __future__ import annotations

import logging
import math
import json
import os
import re
from html import escape
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
EXPORTS_DIR = ROOT / "data" / "exports"
REPORTS_DIR = ROOT / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"
DOCS_DIR = ROOT / "docs"
MATPLOTLIB_CACHE_DIR = ROOT / ".matplotlib"

UF_FILE = RAW_DIR / "conab_brasil_por_uf_fev_2026.csv"
XLSX_FILE = RAW_DIR / "conab_safra_graos_fev_2026.xlsx"
PRODUCT_RAW_FILE = RAW_DIR / "conab_brasil_por_produto_fev_2026.csv"

SOURCE_URL = "https://www.gov.br/conab/pt-br/atuacao/informacoes-agropecuarias/safras/safra-de-graos/boletim-da-safra-de-graos/5o-levantamento-safra-2025-26/site_previsao_de_safra-por-produto-fev-2026.xlsx"
REFERENCE = "Estimativa em fevereiro/2026"
PREVIOUS_PERIOD = "2024/25"
CURRENT_PERIOD = "2025/26"
NUMERIC_COLUMNS = [
    "area_anterior_mil_ha",
    "area_atual_mil_ha",
    "area_variacao_pct",
    "produtividade_anterior_kg_ha",
    "produtividade_atual_kg_ha",
    "produtividade_variacao_pct",
    "producao_anterior_mil_t",
    "producao_atual_mil_t",
    "producao_variacao_pct",
]
UF_CODES = {
    "AC",
    "AL",
    "AM",
    "AP",
    "BA",
    "CE",
    "DF",
    "ES",
    "GO",
    "MA",
    "MG",
    "MS",
    "MT",
    "PA",
    "PB",
    "PE",
    "PI",
    "PR",
    "RJ",
    "RN",
    "RO",
    "RR",
    "RS",
    "SC",
    "SE",
    "SP",
    "TO",
}
REGION_NAMES = {"NORTE", "NORDESTE", "CENTRO-OESTE", "SUDESTE", "SUL"}
PRODUCT_SHEETS = {
    "ALGODÃO - CAROÇO (1)": "Caro\u00e7o de Algod\u00e3o",
    "ALGODÃO - PLUMA": "Algodao em Pluma",
    "AMENDOIM TOTAL": "Amendoim Total",
    "ARROZ": "Arroz Total",
    "FEIJÃO TOTAL": "Feij\u00e3o Total",
    "GERGELIM": "Gergelim",
    "GIRASSOL": "Girassol",
    "MAMONA": "Mamona",
    "MILHO TOTAL": "Milho Total",
    "SOJA": "Soja",
    "SORGO": "Sorgo",
    "AVEIA": "Aveia",
    "CANOLA": "Canola",
    "CENTEIO": "Centeio",
    "CEVADA": "Cevada",
    "TRIGO": "Trigo",
    "TRITICALE": "Triticale",
}


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")


def ensure_dirs() -> None:
    for path in [
        PROCESSED_DIR,
        EXPORTS_DIR,
        REPORTS_DIR,
        FIGURES_DIR,
        DOCS_DIR,
        DOCS_DIR / "images",
        MATPLOTLIB_CACHE_DIR,
    ]:
        path.mkdir(parents=True, exist_ok=True)


def snake_case(value: str) -> str:
    value = re.sub(r"[^0-9a-zA-Z]+", "_", str(value).strip().lower())
    return re.sub(r"_+", "_", value).strip("_")


def normalize_text(value: object) -> object:
    """Fix known encoding artifacts without changing the analytical meaning."""
    if pd.isna(value):
        return value
    text = str(value).strip()
    replacements = {
        "Ã‚Âª": "Âª",
        "Ã‚Âº": "Âº",
        "Ãƒâ€¡": "Ã‡",
        "ÃƒÂ£": "Ã£",
        "ÃƒÂ¡": "Ã¡",
        "ÃƒÂ©": "Ã©",
        "ÃƒÂ­": "Ã­",
        "ÃƒÂ³": "Ã³",
        "ÃƒÂº": "Ãº",
        "ÃƒÂ¢": "Ã¢",
        "ÃƒÂª": "Ãª",
        "ÃƒÂ´": "Ã´",
        "ÃƒÂ§": "Ã§",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return text


def pct_change(current: pd.Series, previous: pd.Series) -> pd.Series:
    previous = pd.to_numeric(previous, errors="coerce")
    current = pd.to_numeric(current, errors="coerce")
    return np.where(previous.eq(0) | previous.isna(), np.nan, ((current - previous) / previous) * 100)


def classify_decomposition(row: pd.Series) -> str:
    prod_delta = row["producao_atual_mil_t"] - row["producao_anterior_mil_t"]
    area_delta = row["area_atual_mil_ha"] - row["area_anterior_mil_ha"]
    yield_delta = row["produtividade_atual_kg_ha"] - row["produtividade_anterior_kg_ha"]
    if math.isclose(prod_delta, 0, abs_tol=0.05):
        return "estabilidade aproximada"
    direction = "expansao" if prod_delta > 0 else "queda"
    area_supports = (area_delta > 0 and prod_delta > 0) or (area_delta < 0 and prod_delta < 0)
    yield_supports = (yield_delta > 0 and prod_delta > 0) or (yield_delta < 0 and prod_delta < 0)
    if area_supports and yield_supports:
        return f"{direction} combinada"
    if area_supports:
        return f"{direction} por area"
    if yield_supports:
        return f"{direction} por produtividade"
    return f"{direction} com efeitos compensatorios"


def analytical_rows(df: pd.DataFrame, kind: str) -> pd.DataFrame:
    """Return rows suitable for rankings, avoiding aggregate lines."""
    if kind == "produto":
        rows = df[df["tipo_linha"].eq("produto")].copy()
        product = rows["produto"].astype("string")
        detail_mask = (
            product.str.contains(r"milho\s+[123].*safra", case=False, regex=True, na=False)
            | product.str.contains(r"amendoim\s+[12].*safra", case=False, regex=True, na=False)
            | product.str.contains(r"feij[aã]o\s+[123].*safra", case=False, regex=True, na=False)
            | product.str.fullmatch(r"(?i)(cores|preto|caupi)", na=False)
            | product.str.contains(r"arroz\s+(?:sequeiro|irrigado)", case=False, regex=True, na=False)
            | product.str.fullmatch(r"(?i)algodão\s*-\s*pluma", na=False)
        )
        return rows[~detail_mask].copy()
    if kind == "uf":
        return df[df["tipo_linha"].eq("uf")].copy()
    return df.copy()


def pareto_table(df: pd.DataFrame, entity_col: str, value_col: str) -> pd.DataFrame:
    """Build a Pareto table with individual and cumulative shares."""
    out = df[[entity_col, value_col]].sort_values(value_col, ascending=False).reset_index(drop=True)
    total = out[value_col].sum()
    out["ranking"] = out.index + 1
    out["participacao_pct"] = np.where(total > 0, out[value_col] / total * 100, np.nan)
    out["participacao_acumulada_pct"] = out["participacao_pct"].cumsum()
    out["atinge_80_pct"] = out["participacao_acumulada_pct"].ge(80)
    return out


def concentration_ratio(df: pd.DataFrame, value_col: str, n: int) -> float:
    """Return the share held by the n largest observations."""
    total = df[value_col].sum()
    if total <= 0:
        return float("nan")
    return float(df.nlargest(n, value_col)[value_col].sum() / total * 100)


def hhi(df: pd.DataFrame, value_col: str) -> float:
    """Return HHI using percentage shares."""
    total = df[value_col].sum()
    if total <= 0:
        return float("nan")
    shares = df[value_col] / total * 100
    return float((shares**2).sum())


def extract_product_csv() -> pd.DataFrame:
    logging.info("Extraindo aba Brasil - Total por Produto do XLSX oficial")
    raw = pd.read_excel(XLSX_FILE, sheet_name="Brasil - Total por Produto", header=None)
    records: list[dict[str, object]] = []
    for _, row in raw.iterrows():
        product = row.iloc[0]
        values = row.iloc[1:10].tolist()
        if pd.isna(product) or not isinstance(product, str):
            continue
        if product.strip().lower() in {"produto", "total"}:
            continue
        nums = pd.to_numeric(pd.Series(values), errors="coerce")
        if nums.notna().sum() < 6:
            continue
        records.append(
            {
                "tipo_linha": "agregado_produto"
                if product.strip().upper() in {"BRASIL (2)", "SUBTOTAL"}
                else "produto",
                "produto": product.strip(),
                "periodo_anterior": PREVIOUS_PERIOD,
                "periodo_atual": CURRENT_PERIOD,
                "area_anterior_mil_ha": nums.iloc[0],
                "area_atual_mil_ha": nums.iloc[1],
                "area_variacao_pct": nums.iloc[2],
                "produtividade_anterior_kg_ha": nums.iloc[3],
                "produtividade_atual_kg_ha": nums.iloc[4],
                "produtividade_variacao_pct": nums.iloc[5],
                "producao_anterior_mil_t": nums.iloc[6],
                "producao_atual_mil_t": nums.iloc[7],
                "producao_variacao_pct": nums.iloc[8],
                "fonte": "Conab",
                "referencia": REFERENCE,
                "source_url": SOURCE_URL,
            }
        )
    df = pd.DataFrame(records)
    df.to_csv(PRODUCT_RAW_FILE, index=False, encoding="utf-8")
    logging.info("%s registros por produto extraidos", len(df))
    return df


def classify_location(value: object) -> str:
    text = str(value).strip().upper()
    if text in UF_CODES:
        return "uf"
    if text in REGION_NAMES:
        return "regiao"
    if text == "BRASIL":
        return "total_brasil"
    if text in {"NORTE/NORDESTE", "CENTRO-SUL"}:
        return "agregado_regional"
    return "outro"


def extract_product_location_data() -> pd.DataFrame:
    """Extract product x region/UF data from product-specific CONAB sheets."""
    records: list[dict[str, object]] = []
    xlsx = pd.ExcelFile(XLSX_FILE)
    for product, sheet in PRODUCT_SHEETS.items():
        if sheet not in xlsx.sheet_names:
            logging.warning("Aba nao encontrada para produto %s: %s", product, sheet)
            continue
        raw = pd.read_excel(XLSX_FILE, sheet_name=sheet, header=None)
        for _, row in raw.iloc[7:].iterrows():
            location = row.iloc[0]
            if pd.isna(location):
                continue
            location_text = str(normalize_text(location)).strip()
            line_type = classify_location(location_text)
            if line_type == "outro":
                continue
            nums = pd.to_numeric(row.iloc[1:10], errors="coerce")
            if nums.notna().sum() < 6:
                continue
            records.append(
                {
                    "tipo_linha": line_type,
                    "produto": product,
                    "regiao_uf": location_text,
                    "periodo_anterior": PREVIOUS_PERIOD,
                    "periodo_atual": CURRENT_PERIOD,
                    "area_anterior_mil_ha": nums.iloc[0],
                    "area_atual_mil_ha": nums.iloc[1],
                    "area_variacao_pct": nums.iloc[2],
                    "produtividade_anterior_kg_ha": nums.iloc[3],
                    "produtividade_atual_kg_ha": nums.iloc[4],
                    "produtividade_variacao_pct": nums.iloc[5],
                    "producao_anterior_mil_t": nums.iloc[6],
                    "producao_atual_mil_t": nums.iloc[7],
                    "producao_variacao_pct": nums.iloc[8],
                    "fonte": "Conab",
                    "referencia": REFERENCE,
                    "source_url": SOURCE_URL,
                }
            )
    df = pd.DataFrame(records)
    logging.info("Dataset produto x localidade extraido: %s linhas", len(df))
    return df


def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    if PRODUCT_RAW_FILE.exists():
        products = pd.read_csv(PRODUCT_RAW_FILE)
        if "tipo_linha" not in products.columns:
            products = extract_product_csv()
    else:
        products = extract_product_csv()
    states = pd.read_csv(UF_FILE)
    logging.info("Dataset por produto carregado: %s linhas", len(products))
    logging.info("Dataset por UF carregado: %s linhas", len(states))
    return products, states


def clean_frame(df: pd.DataFrame) -> pd.DataFrame:
    cleaned = df.copy()
    cleaned.columns = [snake_case(col) for col in cleaned.columns]
    for col in cleaned.select_dtypes(include=["object", "string"]).columns:
        cleaned[col] = cleaned[col].map(normalize_text).astype("string").str.strip()
        cleaned[col] = cleaned[col].replace({"": pd.NA})
    for col in NUMERIC_COLUMNS:
        if col in cleaned.columns:
            cleaned[col] = pd.to_numeric(cleaned[col], errors="coerce")
    return cleaned


def add_metrics(df: pd.DataFrame, entity_col: str) -> pd.DataFrame:
    out = df.copy()
    out["variacao_area_pct_calc"] = pct_change(out["area_atual_mil_ha"], out["area_anterior_mil_ha"])
    out["variacao_produtividade_pct_calc"] = pct_change(
        out["produtividade_atual_kg_ha"], out["produtividade_anterior_kg_ha"]
    )
    out["variacao_producao_pct_calc"] = pct_change(out["producao_atual_mil_t"], out["producao_anterior_mil_t"])
    denominator_base = out
    if "tipo_linha" in out.columns:
        if "produto" in out.columns:
            denominator_base = analytical_rows(out, "produto")
        elif "regiao_uf" in out.columns:
            denominator_base = analytical_rows(out, "uf")
        else:
            denominator_base = out[~out["tipo_linha"].astype("string").str.contains("agregado|total_brasil", na=False)]
    total = denominator_base["producao_atual_mil_t"].sum()
    out["participacao_producao_pct"] = np.where(total > 0, out["producao_atual_mil_t"] / total * 100, np.nan)
    if "tipo_linha" in out.columns:
        aggregate_mask = out["tipo_linha"].astype("string").str.contains("agregado|total_brasil", na=False)
        out.loc[aggregate_mask, "participacao_producao_pct"] = np.nan
    out["crescimento_producao_mil_t"] = out["producao_atual_mil_t"] - out["producao_anterior_mil_t"]
    out["crescimento_area_mil_ha"] = out["area_atual_mil_ha"] - out["area_anterior_mil_ha"]
    out["crescimento_produtividade_kg_ha"] = (
        out["produtividade_atual_kg_ha"] - out["produtividade_anterior_kg_ha"]
    )
    out["classificacao_decomposicao"] = out.apply(classify_decomposition, axis=1)
    out[f"ranking_{entity_col}_producao"] = out["producao_atual_mil_t"].rank(ascending=False, method="dense")
    return out


def audit_frame(name: str, df: pd.DataFrame) -> str:
    numeric = df.select_dtypes(include=[np.number])
    missing = df.isna().sum()
    duplicate_count = int(df.duplicated().sum())
    negative_counts = (numeric < 0).sum()
    zero_counts = (numeric == 0).sum()
    infinite_counts = np.isinf(numeric).sum()
    pct_issues = {}
    pairs = [
        ("area_variacao_pct", "variacao_area_pct_calc"),
        ("produtividade_variacao_pct", "variacao_produtividade_pct_calc"),
        ("producao_variacao_pct", "variacao_producao_pct_calc"),
    ]
    metric_df = add_metrics(df, "item")
    for original, calculated in pairs:
        if original in metric_df.columns:
            diff = (metric_df[original] - metric_df[calculated]).abs()
            pct_issues[original] = int((diff > 0.15).fillna(False).sum())
    production_calc = (df["area_atual_mil_ha"] * df["produtividade_atual_kg_ha"]) / 1000
    production_diff = (production_calc - df["producao_atual_mil_t"]).abs()
    outlier_counts = {}
    for col in numeric.columns:
        q1, q3 = numeric[col].quantile([0.25, 0.75])
        iqr = q3 - q1
        outlier_counts[col] = int(((numeric[col] < q1 - 1.5 * iqr) | (numeric[col] > q3 + 1.5 * iqr)).sum())
    return f"""
### {name}

- Linhas: {len(df)}
- Colunas: {len(df.columns)}
- Colunas existentes: {", ".join(df.columns)}
- Tipos: `{df.dtypes.astype(str).to_dict()}`
- Valores ausentes: `{missing[missing > 0].to_dict()}`
- Duplicidades: {duplicate_count}
- Valores negativos por coluna numerica: `{negative_counts[negative_counts > 0].to_dict()}`
- Zeros por coluna numerica: `{zero_counts[zero_counts > 0].to_dict()}`
- Valores infinitos: `{infinite_counts[infinite_counts > 0].to_dict()}`
- Categorias unicas relevantes: `{ {c: int(df[c].nunique(dropna=True)) for c in df.select_dtypes(include=['string', 'object']).columns} }`
- Percentuais divergentes acima de 0,15 p.p.: `{pct_issues}`
- Divergencias area x produtividade x producao acima de 0,5 mil t: {int((production_diff > 0.5).sum())}
- Possiveis outliers por IQR: `{outlier_counts}`

Estatisticas descritivas:

```text
{numeric.describe().round(3).to_string()}
```
"""


def write_reports(products: pd.DataFrame, states: pd.DataFrame) -> None:
    state_ufs = states[states["tipo_linha"].eq("uf")].copy()
    report = "# Relatorio de Qualidade dos Dados\n\n"
    report += "Fonte oficial: CONAB. Unidades validadas: area em mil hectares, produtividade em kg/ha e producao em mil toneladas. A coerencia matematica usa area * produtividade / 1000 ~= producao.\n"
    report += audit_frame("Brasil por produto", products)
    report += audit_frame("Brasil por UF/regiao", states)
    report += "\n## Observacoes tecnicas\n\n"
    report += "- O arquivo por UF contem linhas de UF, regiao, agregados regionais e total Brasil; rankings estaduais devem filtrar `tipo_linha == 'uf'`.\n"
    report += "- O CSV por produto nao estava na raiz; foi extraido da aba `Brasil - Total por Produto` do XLSX oficial e salvo em `data/raw`.\n"
    report += "- Valores extremos foram apenas sinalizados por IQR; nenhum registro foi removido automaticamente.\n"
    report += "- Percentuais foram recalculados e mantidos em colunas separadas para auditoria.\n"
    (REPORTS_DIR / "data_quality_report.md").write_text(report, encoding="utf-8")

    product_rows = analytical_rows(products, "produto")
    top_products = product_rows.sort_values("producao_atual_mil_t", ascending=False).head(10)
    top_states = state_ufs.sort_values("producao_atual_mil_t", ascending=False).head(10)
    pareto_products = pareto_table(product_rows, "produto", "producao_atual_mil_t")
    pareto_states = pareto_table(state_ufs, "regiao_uf", "producao_atual_mil_t")
    products_to_80 = int(pareto_products.loc[pareto_products["atinge_80_pct"], "ranking"].min())
    states_to_80 = int(pareto_states.loc[pareto_states["atinge_80_pct"], "ranking"].min())
    cr3_products = concentration_ratio(product_rows, "producao_atual_mil_t", 3)
    cr5_products = concentration_ratio(product_rows, "producao_atual_mil_t", 5)
    cr3_states = concentration_ratio(state_ufs, "producao_atual_mil_t", 3)
    cr5_states = concentration_ratio(state_ufs, "producao_atual_mil_t", 5)
    hhi_products = hhi(product_rows, "producao_atual_mil_t")
    hhi_states = hhi(state_ufs, "producao_atual_mil_t")
    soja = product_rows[product_rows["produto"].str.contains("soja", case=False, na=False)]
    milho_total = product_rows[product_rows["produto"].str.fullmatch("MILHO TOTAL", case=False, na=False)]
    milho_detail = product_rows[
        product_rows["produto"].str.contains("milho", case=False, na=False)
        & ~product_rows["produto"].str.fullmatch("MILHO TOTAL", case=False, na=False)
    ]
    milho_share = (
        milho_total["participacao_producao_pct"].sum()
        if not milho_total.empty
        else product_rows[product_rows["produto"].str.contains("milho", case=False, na=False)][
            "participacao_producao_pct"
        ].sum()
    )
    biggest_growth = product_rows.sort_values("crescimento_producao_mil_t", ascending=False).iloc[0]
    biggest_drop = product_rows.sort_values("crescimento_producao_mil_t").iloc[0]
    biggest_state_growth = state_ufs.sort_values("crescimento_producao_mil_t", ascending=False).iloc[0]
    biggest_state_drop = state_ufs.sort_values("crescimento_producao_mil_t").iloc[0]
    summary = f"""# Executive Summary

## Contexto

Projeto analitico reproduzivel com dados oficiais da CONAB para a estimativa da safra 2025/26, comparada a 2024/25.

## Principais KPIs

- Producao total Brasil informada no dataset estadual: {states.loc[states['tipo_linha'].eq('total_brasil'), 'producao_atual_mil_t'].sum():,.2f} mil t.
- Area total Brasil informada no dataset estadual: {states.loc[states['tipo_linha'].eq('total_brasil'), 'area_atual_mil_ha'].sum():,.2f} mil ha.
- Top cultura por producao: {top_products.iloc[0]['produto']} ({top_products.iloc[0]['producao_atual_mil_t']:,.2f} mil t).
- Top UF por producao: {top_states.iloc[0]['regiao_uf']} ({top_states.iloc[0]['producao_atual_mil_t']:,.2f} mil t).
- CR3 produtos: {cr3_products:.2f}% | CR5 produtos: {cr5_products:.2f}% | HHI produtos: {hhi_products:.2f}.
- CR3 UFs: {cr3_states:.2f}% | CR5 UFs: {cr5_states:.2f}% | HHI UFs: {hhi_states:.2f}.
- Produtos ate aproximadamente 80% da producao: {products_to_80}.
- UFs ate aproximadamente 80% da producao: {states_to_80}.

## Principais Descobertas

- Soja representa {soja['participacao_producao_pct'].sum():.2f}% da producao no recorte por produto.
- Milho Total representa {milho_share:.2f}% da producao no recorte por produto; linhas de safra do milho foram tratadas como detalhamento para evitar dupla contagem.
- Linhas detalhadas de milho identificadas: {", ".join(milho_detail['produto'].tolist()) if not milho_detail.empty else "nao disponivel"}.
- A decomposicao classifica expansoes e quedas por sinais de area e produtividade; a leitura e associativa, nao causal.

## Insights

### Concentracao por produto

Insight: a producao analisada e concentrada em poucas culturas.
Evidencia: {products_to_80} produtos alcancam cerca de 80% da producao; CR3 = {cr3_products:.2f}%.
Interpretacao: decisoes sobre soja, milho e demais culturas lideres tendem a explicar grande parte do movimento agregado.
Limitacao: linhas de produto podem conter agregacoes e detalhamentos; o pipeline marca agregados explicitos e evita dupla contagem evidente.

### Variacao de producao

Insight: {biggest_growth['produto']} foi o maior aumento absoluto de producao, enquanto {biggest_drop['produto']} teve a maior queda absoluta.
Evidencia: crescimento de {biggest_growth['crescimento_producao_mil_t']:,.2f} mil t e queda de {biggest_drop['crescimento_producao_mil_t']:,.2f} mil t.
Interpretacao: a classificacao de decomposicao indica {biggest_growth['classificacao_decomposicao']} no maior crescimento e {biggest_drop['classificacao_decomposicao']} na maior queda.
Limitacao: a decomposicao usa sinais e diferencas entre dois periodos; nao estabelece causalidade.

### Concentracao estadual

Insight: a producao estadual tambem e concentrada.
Evidencia: {states_to_80} UFs alcancam cerca de 80% da producao; CR5 = {cr5_states:.2f}%.
Interpretacao: os principais estados sustentam uma parcela relevante da oferta nacional no recorte.
Limitacao: rankings estaduais filtram apenas `tipo_linha = uf`; regioes e total Brasil nao entram no ranking.

### Movimento estadual

Insight: {biggest_state_growth['regiao_uf']} teve o maior aumento absoluto entre UFs, enquanto {biggest_state_drop['regiao_uf']} teve a maior queda.
Evidencia: variacoes absolutas de {biggest_state_growth['crescimento_producao_mil_t']:,.2f} mil t e {biggest_state_drop['crescimento_producao_mil_t']:,.2f} mil t.
Interpretacao: esses movimentos ajudam a localizar onde a mudanca agregada se concentra geograficamente.
Limitacao: o dataset estadual nao esta aberto por cultura nesta etapa.

## Limitacoes

- O recorte atual compara apenas dois periodos; nao foram criados forecasts, ARIMA, Prophet ou tendencias historicas artificiais.
- A planilha pode conter categorias agregadas de produto; somas devem respeitar a hierarquia para evitar dupla contagem.

## Proximos passos

- Incorporar serie historica oficial para analise temporal adequada.
- Adicionar dados por produto e UF quando disponiveis.
- Carregar os dados processados em PostgreSQL e publicar dashboard.
"""
    (REPORTS_DIR / "executive_summary.md").write_text(summary, encoding="utf-8")


def make_figures(products: pd.DataFrame, states: pd.DataFrame) -> None:
    os.environ.setdefault("MPLCONFIGDIR", str(MATPLOTLIB_CACHE_DIR))
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    product_rows = analytical_rows(products, "produto")
    state_ufs = analytical_rows(states, "uf")
    figure_titles = {
        "top_10_produtos_producao": "Top 10 Produtos por Producao",
        "top_10_ufs_producao": "Top 10 UFs por Producao",
        "top_10_produtos_variacao_producao_pct": "Top 10 Produtos por Variacao da Producao",
        "top_10_produtos_area": "Top 10 Produtos por Area",
        "pareto_produtos_producao": "Pareto da Producao por Produto",
        "pareto_ufs_producao": "Pareto da Producao por UF",
        "area_x_producao_produtos": "Area x Producao por Produto",
        "produtividade_x_producao_produtos": "Produtividade x Producao por Produto",
    }
    for df, label, col in [
        (
            product_rows.sort_values("producao_atual_mil_t", ascending=False).head(10),
            "top_10_produtos_producao",
            "produto",
        ),
        (
            state_ufs.sort_values("producao_atual_mil_t", ascending=False).head(10),
            "top_10_ufs_producao",
            "regiao_uf",
        ),
        (
            product_rows.sort_values("variacao_producao_pct_calc", ascending=False).head(10),
            "top_10_produtos_variacao_producao_pct",
            "produto",
        ),
        (
            product_rows.sort_values("area_atual_mil_ha", ascending=False).head(10),
            "top_10_produtos_area",
            "produto",
        ),
    ]:
        fig, ax = plt.subplots(figsize=(10, 6))
        value_col = "variacao_producao_pct_calc" if "variacao" in label else (
            "area_atual_mil_ha" if label.endswith("_area") else "producao_atual_mil_t"
        )
        ax.barh(df[col], df[value_col], color="#2f6f73")
        ax.invert_yaxis()
        ax.set_title(figure_titles[label])
        ax.set_xlabel(value_col)
        fig.tight_layout()
        fig.savefig(FIGURES_DIR / f"{label}.png", dpi=160)
        plt.close(fig)

    for df, entity_col, label in [
        (product_rows, "produto", "pareto_produtos_producao"),
        (state_ufs, "regiao_uf", "pareto_ufs_producao"),
    ]:
        pareto = pareto_table(df, entity_col, "producao_atual_mil_t")
        fig, ax1 = plt.subplots(figsize=(11, 6))
        ax1.bar(pareto[entity_col].head(15), pareto["participacao_pct"].head(15), color="#596f2f")
        ax1.set_ylabel("Participacao individual (%)")
        ax1.tick_params(axis="x", rotation=70)
        ax2 = ax1.twinx()
        ax2.plot(pareto[entity_col].head(15), pareto["participacao_acumulada_pct"].head(15), color="#9b4d2e", marker="o")
        ax2.axhline(80, color="#444444", linestyle="--", linewidth=1)
        ax2.set_ylabel("Participacao acumulada (%)")
        ax1.set_title(figure_titles[label])
        fig.tight_layout()
        fig.savefig(FIGURES_DIR / f"{label}.png", dpi=160)
        plt.close(fig)

    for x_col, label in [
        ("area_atual_mil_ha", "area_x_producao_produtos"),
        ("produtividade_atual_kg_ha", "produtividade_x_producao_produtos"),
    ]:
        fig, ax = plt.subplots(figsize=(9, 6))
        ax.scatter(product_rows[x_col], product_rows["producao_atual_mil_t"], color="#2f6f73", alpha=0.8)
        ax.set_title(figure_titles[label])
        ax.set_xlabel(x_col)
        ax.set_ylabel("producao_atual_mil_t")
        fig.tight_layout()
        fig.savefig(FIGURES_DIR / f"{label}.png", dpi=160)
        plt.close(fig)


def export_data(products: pd.DataFrame, states: pd.DataFrame, product_locations: pd.DataFrame | None = None) -> None:
    products.to_csv(PROCESSED_DIR / "conab_produtos_clean.csv", index=False, encoding="utf-8")
    states.to_csv(PROCESSED_DIR / "conab_ufs_clean.csv", index=False, encoding="utf-8")
    products.to_parquet(PROCESSED_DIR / "conab_produtos_clean.parquet", index=False)
    states.to_parquet(PROCESSED_DIR / "conab_ufs_clean.parquet", index=False)
    if product_locations is not None and not product_locations.empty:
        product_locations.to_csv(PROCESSED_DIR / "conab_produto_localidade_clean.csv", index=False, encoding="utf-8")
        product_locations.to_parquet(PROCESSED_DIR / "conab_produto_localidade_clean.parquet", index=False)
    product_rows = analytical_rows(products, "produto")
    state_ufs = analytical_rows(states, "uf")
    pareto_table(product_rows, "produto", "producao_atual_mil_t").to_csv(
        EXPORTS_DIR / "pareto_produtos_producao.csv", index=False, encoding="utf-8"
    )
    pareto_table(state_ufs, "regiao_uf", "producao_atual_mil_t").to_csv(
        EXPORTS_DIR / "pareto_ufs_producao.csv", index=False, encoding="utf-8"
    )
    pd.DataFrame(
        [
            {
                "dimensao": "produto",
                "cr3_pct": concentration_ratio(product_rows, "producao_atual_mil_t", 3),
                "cr5_pct": concentration_ratio(product_rows, "producao_atual_mil_t", 5),
                "hhi": hhi(product_rows, "producao_atual_mil_t"),
            },
            {
                "dimensao": "uf",
                "cr3_pct": concentration_ratio(state_ufs, "producao_atual_mil_t", 3),
                "cr5_pct": concentration_ratio(state_ufs, "producao_atual_mil_t", 5),
                "hhi": hhi(state_ufs, "producao_atual_mil_t"),
            },
        ]
    ).to_csv(EXPORTS_DIR / "indicadores_concentracao.csv", index=False, encoding="utf-8")


def write_dictionary(df: pd.DataFrame) -> None:
    lines = ["# Data Dictionary\n"]
    units = {
        "area": "mil hectares",
        "produtividade": "kg/ha",
        "producao": "mil toneladas",
        "pct": "percentual",
    }
    for col in df.columns:
        unit = next((v for k, v in units.items() if k in col), "nao aplicavel")
        lines.append(f"## {col}\n\n- Tipo: {df[col].dtype}\n- Unidade: {unit}\n- Origem: CONAB/pipeline\n- Regra: preservar ausentes; numericos nao devem ser negativos quando aplicavel.\n")
    (DOCS_DIR / "data_dictionary.md").write_text("\n".join(lines), encoding="utf-8")


DISPLAY_TEXT_REPLACEMENTS = {
    "ÃƒO": "ÃO",
    "Ãƒo": "ÃO",
    "Ãƒ‡": "Ç",
    "Ã‡": "Ç",
    "Ã¡": "á",
    "Ã¢": "â",
    "Ã£": "ã",
    "Ã§": "ç",
    "Ã©": "é",
    "Ãª": "ê",
    "Ã­": "í",
    "Ã³": "ó",
    "Ãµ": "õ",
    "Ãº": "ú",
    "Ã": "Á",
    "Â·": "·",
    "â–²": "▲",
    "â–¼": "▼",
    "â“˜": "ⓘ",
}


def fix_display_text(text: str) -> str:
    """Repair known mojibake artifacts before writing user-facing HTML."""
    for _ in range(2):
        for old, new in DISPLAY_TEXT_REPLACEMENTS.items():
            text = text.replace(old, new)
    return text


def write_dashboard(products: pd.DataFrame, states: pd.DataFrame, product_locations: pd.DataFrame | None = None) -> None:
    """Create an executive static dashboard with deterministic analytics."""
    product_rows = analytical_rows(products, "produto").copy()
    state_ufs = analytical_rows(states, "uf").copy()
    total_row = states.loc[states["tipo_linha"].eq("total_brasil")].iloc[0]
    total_production = float(total_row["producao_atual_mil_t"])
    total_area = float(total_row["area_atual_mil_ha"])
    productivity = total_production * 1000 / total_area if total_area else np.nan
    production_delta = pct_change(pd.Series([total_production]), pd.Series([total_row["producao_anterior_mil_t"]]))[0]
    area_delta = pct_change(pd.Series([total_area]), pd.Series([total_row["area_anterior_mil_ha"]]))[0]
    pareto_states = pareto_table(state_ufs, "regiao_uf", "producao_atual_mil_t")
    states_to_80 = int(pareto_states.loc[pareto_states["atinge_80_pct"], "ranking"].min())
    cr3_states = concentration_ratio(state_ufs, "producao_atual_mil_t", 3)
    cr5_states = concentration_ratio(state_ufs, "producao_atual_mil_t", 5)
    hhi_states = hhi(state_ufs, "producao_atual_mil_t")
    top_product = product_rows.nlargest(1, "producao_atual_mil_t").iloc[0]
    top_state = state_ufs.nlargest(1, "producao_atual_mil_t").iloc[0]
    top_growth = state_ufs.nlargest(1, "crescimento_producao_mil_t").iloc[0]
    top_drop = state_ufs.nsmallest(1, "crescimento_producao_mil_t").iloc[0]
    regions = {
        "RR": "Norte", "RO": "Norte", "AC": "Norte", "AM": "Norte", "AP": "Norte", "PA": "Norte", "TO": "Norte",
        "MA": "Nordeste", "PI": "Nordeste", "CE": "Nordeste", "RN": "Nordeste", "PB": "Nordeste", "PE": "Nordeste",
        "AL": "Nordeste", "SE": "Nordeste", "BA": "Nordeste", "MT": "Centro-Oeste", "MS": "Centro-Oeste",
        "GO": "Centro-Oeste", "DF": "Centro-Oeste", "MG": "Sudeste", "ES": "Sudeste", "RJ": "Sudeste",
        "SP": "Sudeste", "PR": "Sul", "SC": "Sul", "RS": "Sul",
    }
    state_ufs["regiao"] = state_ufs["regiao_uf"].map(regions)
    product_locations = product_locations.copy() if product_locations is not None else pd.DataFrame()
    if not product_locations.empty:
        product_locations["regiao"] = np.where(
            product_locations["tipo_linha"].eq("regiao"),
            product_locations["regiao_uf"].astype("string").str.title(),
            product_locations["regiao_uf"].map(regions),
        )
        product_locations["participacao_producao_pct"] = np.nan
        for _, group_index in product_locations.groupby(["tipo_linha", "regiao"])["producao_atual_mil_t"].groups.items():
            total_group = product_locations.loc[group_index, "producao_atual_mil_t"].sum()
            if total_group > 0:
                product_locations.loc[group_index, "participacao_producao_pct"] = (
                    product_locations.loc[group_index, "producao_atual_mil_t"] / total_group * 100
                )

    def number(value: float, decimals: int = 1) -> str:
        if pd.isna(value):
            return "-"
        formatted = f"{float(value):,.{decimals}f}"
        return formatted.replace(",", "X").replace(".", ",").replace("X", ".")

    def compact_mil_t(value: float) -> str:
        return f"{number(value / 1000, 1)} milhÃµes t" if abs(value) >= 1000 else f"{number(value, 1)} mil t"

    def delta(value: float) -> str:
        symbol = "â–²" if value >= 0 else "â–¼"
        sign = "+" if value >= 0 else ""
        return f"{symbol} {sign}{number(value, 1)}%"

    def records(df: pd.DataFrame, cols: list[str]) -> str:
        return json.dumps(df[cols].replace({np.nan: None}).to_dict(orient="records"), ensure_ascii=False)

    product_json = records(product_rows, [
        "produto", "producao_atual_mil_t", "producao_anterior_mil_t", "area_atual_mil_ha",
        "produtividade_atual_kg_ha", "variacao_area_pct_calc", "variacao_produtividade_pct_calc",
        "variacao_producao_pct_calc", "crescimento_producao_mil_t", "crescimento_area_mil_ha", "participacao_producao_pct",
        "classificacao_decomposicao",
    ])
    state_json = records(state_ufs, [
        "regiao_uf", "regiao", "producao_atual_mil_t", "producao_anterior_mil_t", "area_atual_mil_ha",
        "produtividade_atual_kg_ha", "variacao_area_pct_calc", "variacao_produtividade_pct_calc",
        "variacao_producao_pct_calc", "crescimento_producao_mil_t", "crescimento_area_mil_ha", "participacao_producao_pct",
        "classificacao_decomposicao",
    ])
    product_location_json = records(product_locations, [
        "tipo_linha", "produto", "regiao_uf", "regiao", "producao_atual_mil_t", "producao_anterior_mil_t",
        "area_atual_mil_ha", "produtividade_atual_kg_ha", "variacao_area_pct_calc",
        "variacao_produtividade_pct_calc", "variacao_producao_pct_calc", "crescimento_producao_mil_t", "crescimento_area_mil_ha",
        "participacao_producao_pct", "classificacao_decomposicao",
    ]) if not product_locations.empty else "[]"
    pareto_json = records(pareto_states, ["regiao_uf", "producao_atual_mil_t", "participacao_pct", "participacao_acumulada_pct", "ranking"])
    html = f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Agroscope</title>
  <meta http-equiv="Content-Security-Policy" content="default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; object-src 'none'; base-uri 'none'; form-action 'none'">
  <style>
    :root {{ --bg:#0b1214; --surface:#111b1d; --surface-2:#172426; --surface-3:#0f181a; --border:#253638; --primary:#5ee0bf; --primary-2:#20b896; --secondary:#87a7a0; --text:#eef8f5; --muted:#9fb0ab; --positive:#64d99f; --negative:#f07f73; --warning:#d8b456; --gold:#d8b456; --blue:#78b8ce; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:radial-gradient(circle at 18% 0%, rgba(94,224,191,.16), transparent 32%), linear-gradient(180deg, #0b1214 0%, #0f1719 48%, #0b1214 100%); color:var(--text); font-family:Inter, Segoe UI, Arial, sans-serif; }}
    header {{ background:transparent; color:white; border-bottom:1px solid rgba(135,167,160,.16); }}
    .wrap {{ max-width:980px; margin:0 auto; padding:0 24px; }}
    .hero {{ min-height:188px; padding:34px 0 28px; display:grid; grid-template-columns:1fr; gap:18px; align-items:end; }}
    .eyebrow {{ margin:0 0 10px; color:var(--gold); font-size:12px; text-transform:uppercase; letter-spacing:.12em; }}
    h1 {{ margin:0; font-size:44px; line-height:1.02; }}
    .subtitle {{ margin:12px 0 0; color:#c8d8d4; line-height:1.42; max-width:820px; font-size:17px; }}
    .meta {{ display:flex; flex-wrap:wrap; gap:10px; align-items:center; justify-content:flex-start; }}
    .pill {{ border:1px solid rgba(216,180,86,.32); border-radius:999px; padding:8px 12px; color:#fff0bd; background:rgba(216,180,86,.10); font-size:13px; white-space:nowrap; }}
    main {{ padding:24px 0 48px; }}
    .toolbar {{ margin-top:-1px; padding:14px 0; background:rgba(17,27,29,.88); border-top:1px solid rgba(135,167,160,.10); border-bottom:1px solid var(--border); box-shadow:0 18px 50px rgba(0,0,0,.30); position:sticky; top:0; z-index:3; backdrop-filter:saturate(140%) blur(10px); }}
    .filters {{ display:grid; grid-template-columns:1fr 1fr 1fr .9fr; gap:12px; align-items:end; }}
    label {{ display:grid; gap:6px; color:#aebfba; font-size:12px; font-weight:700; text-transform:uppercase; letter-spacing:.06em; }}
    select,input {{ width:100%; border:1px solid #314447; border-radius:8px; padding:11px 14px; background:#0d1517; color:var(--text); font:inherit; min-height:48px; box-shadow:inset 0 1px 0 rgba(255,255,255,.03); }}
    select:focus,input:focus {{ outline:2px solid rgba(35,112,75,.18); border-color:var(--secondary); }}
    h2 {{ margin:32px 0 10px; font-size:22px; color:#f2fbf8; }}
    .lead {{ margin:0 0 14px; color:var(--muted); line-height:1.45; }}
    .context-strip {{ display:flex; flex-wrap:wrap; gap:10px; margin:0 0 14px; }}
    .context-chip {{ border:1px solid var(--border); border-radius:999px; padding:7px 10px; background:#0d1517; color:#cbdad6; font-size:12px; }}
    .kpis {{ display:grid; grid-template-columns:repeat(4, minmax(0, 1fr)); gap:14px; margin-top:2px; }}
    .card,.chart,.panel {{ background:linear-gradient(180deg, rgba(24,38,40,.98) 0%, rgba(15,24,26,.98) 100%); border:1px solid var(--border); border-radius:8px; box-shadow:0 18px 48px rgba(0,0,0,.34); }}
    .card {{ padding:17px 17px 15px; min-height:126px; display:flex; flex-direction:column; justify-content:space-between; position:relative; overflow:hidden; }}
    .card::after {{ content:""; position:absolute; inset:auto 0 0 0; height:3px; background:linear-gradient(90deg, rgba(30,107,92,.22), rgba(201,168,74,.18)); }}
    .card:nth-child(1) {{ border-left:4px solid var(--primary); }}
    .card:nth-child(2) {{ border-left:4px solid var(--gold); }}
    .card:nth-child(3) {{ border-left:4px solid var(--blue); }}
    .card:nth-child(4) {{ border-left:4px solid #8d7660; }}
    .label {{ color:#a8bab5; font-size:12px; font-weight:700; text-transform:uppercase; letter-spacing:.06em; }}
    .value {{ display:block; margin-top:10px; font-size:clamp(23px, 2.1vw, 27px); line-height:1.08; font-weight:800; white-space:normal; overflow-wrap:break-word; }}
    .note {{ display:block; margin-top:8px; color:var(--muted); font-size:13px; line-height:1.35; }}
    .leader-list {{ display:grid; gap:10px; margin-top:10px; }}
    .leader-row {{ display:flex; align-items:baseline; justify-content:space-between; gap:12px; }}
    .leader-row strong {{ font-size:28px; line-height:1; }}
    .leader-row span {{ color:var(--muted); font-size:13px; text-align:right; }}
    .up {{ color:var(--positive); }} .down {{ color:var(--negative); }}
    .grid {{ display:grid; grid-template-columns:minmax(0, 1.45fr) minmax(360px, .85fr); gap:18px; }}
    .grid-even {{ display:grid; grid-template-columns:1fr 1fr; gap:18px; }}
    .chart {{ padding:20px; min-height:320px; }}
    .chart h3,.panel h3 {{ margin:0 0 6px; font-size:18px; }}
    .bars {{ display:grid; gap:10px; margin-top:14px; }}
    .bar-row {{ display:grid; grid-template-columns:minmax(130px, 230px) 1fr minmax(110px, auto); gap:12px; align-items:center; font-size:13px; padding:2px 0; }}
    .bar-row b {{ overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
    .bar-track {{ height:14px; background:#233336; border-radius:999px; overflow:hidden; }}
    .bar-fill {{ height:100%; background:linear-gradient(90deg, #20b896, #8de6cd); border-radius:999px; }}
    .bar-fill.neg {{ background:var(--negative); }}
    .scatter {{ height:320px; position:relative; border:1px solid var(--border); background:linear-gradient(90deg, transparent 49.8%, #33484b 50%, transparent 50.2%), linear-gradient(0deg, transparent 49.8%, #33484b 50%, transparent 50.2%), #0d1517; border-radius:8px; margin-top:12px; overflow:hidden; }}
    .dot {{ position:absolute; width:11px; height:11px; border-radius:50%; background:#5ee0bf; transform:translate(-50%, -50%); outline:2px solid #0d1517; box-shadow:0 0 18px rgba(94,224,191,.34); }}
    .panel {{ padding:20px; }}
    .concentration {{ display:grid; grid-template-columns:repeat(3, 1fr); gap:10px; margin-top:12px; }}
    .mini {{ background:#0d1517; border:1px solid var(--border); border-radius:8px; padding:12px; }}
    table {{ width:100%; border-collapse:collapse; font-size:13px; }}
    th,td {{ padding:10px; border-bottom:1px solid var(--border); text-align:right; }}
    th {{ color:#cbdad6; background:#172426; }}
    th:first-child,td:first-child {{ text-align:left; }}
    .insights {{ display:grid; grid-template-columns:repeat(3, 1fr); gap:12px; }}
    .actions {{ display:flex; gap:10px; flex-wrap:wrap; margin-top:12px; }}
    button {{ border:1px solid var(--border); border-radius:8px; padding:10px 12px; background:#142123; color:var(--text); cursor:pointer; font:inherit; }}
    footer {{ color:var(--muted); padding:0 0 34px; font-size:13px; }}
    @media (max-width:1180px) {{ .kpis {{ grid-template-columns:repeat(2, 1fr); }} .hero {{ grid-template-columns:1fr; }} .meta {{ justify-content:flex-start; }} }}
    @media (max-width:980px) {{ .grid,.grid-even,.insights {{ grid-template-columns:1fr; }} .filters {{ grid-template-columns:1fr 1fr; }} }}
    @media (max-width:640px) {{ .wrap {{ padding:0 18px; }} h1 {{ font-size:30px; }} .subtitle {{ font-size:16px; }} .kpis,.filters {{ grid-template-columns:1fr; }} .bar-row {{ grid-template-columns:1fr; gap:6px; }} .value {{ white-space:normal; }} }}
  </style>
</head>
<body>
  <header><div class="wrap hero"><div><p class="eyebrow">Dados oficiais de safra</p><h1>Agroscope</h1><p class="subtitle">InteligÃªncia de dados sobre a produÃ§Ã£o agrÃ­cola brasileira, com rankings, variaÃ§Ãµes, produtividade e concentraÃ§Ã£o da safra analisada.</p></div><div class="meta"><span class="pill">Safra {CURRENT_PERIOD}</span><span class="pill">Comparativo {PREVIOUS_PERIOD}</span><span class="pill">{REFERENCE}</span></div></div></header>
  <div class="toolbar"><div class="wrap filters"><label>VisÃ£o<select id="view"><option value="states">Estados</option><option value="products">Culturas</option></select></label><label>Produto<select id="productFilter"></select></label><label>RegiÃ£o<select id="regionFilter"></select></label><label><span id="searchLabel">Estado</span><input id="search" type="search" placeholder="Buscar UF"></label></div></div>
  <main class="wrap">
    <div id="contextStrip" class="context-strip"></div>
    <section class="kpis">
      <div class="card"><span class="label">ProduÃ§Ã£o total</span><strong class="value" id="kpiProduction">{number(total_production / 1000, 1)} mi t</strong><small class="note" id="kpiProductionDelta">{delta(production_delta)} vs. safra anterior</small></div>
      <div class="card"><span class="label">Ãrea plantada</span><strong class="value" id="kpiArea">{number(total_area / 1000, 1)} mi ha</strong><small class="note" id="kpiAreaDelta">{delta(area_delta)} vs. safra anterior</small></div>
      <div class="card"><span class="label">Produtividade mÃ©dia</span><strong class="value" id="kpiProductivity">{number(productivity, 0)} kg/ha</strong><small class="note">ProduÃ§Ã£o / Ã¡rea cultivada</small></div>
      <div class="card"><span class="label">LideranÃ§as</span><div class="leader-list" id="kpiLeaders"><div class="leader-row"><strong>{escape(str(top_product['produto']))}</strong><span>{compact_mil_t(top_product['producao_atual_mil_t'])}</span></div><div class="leader-row"><strong>{escape(str(top_state['regiao_uf']))}</strong><span>{compact_mil_t(top_state['producao_atual_mil_t'])}</span></div></div></div>
    </section>
    <h2>VisÃ£o Geral</h2><p class="lead" id="scopeNote"></p>
    <section class="grid"><div class="chart"><h3 id="rankingTitle"></h3><p class="lead">Barras ordenadas por produÃ§Ã£o atual. Tooltips do navegador mostram Ã¡rea, produtividade, participaÃ§Ã£o e variaÃ§Ã£o.</p><div id="rankingBars" class="bars"></div></div><div class="panel"><h3>ConcentraÃ§Ã£o da produÃ§Ã£o <span title="CR3/CR5 medem a participaÃ§Ã£o dos 3 e 5 maiores; HHI soma as participaÃ§Ãµes percentuais ao quadrado, em escala 0-10.000.">â“˜</span></h3><div class="concentration"><div class="mini"><span class="label">CR3</span><strong class="value">{number(cr3_states, 1)}%</strong></div><div class="mini"><span class="label">CR5</span><strong class="value">{number(cr5_states, 1)}%</strong></div><div class="mini"><span class="label">HHI</span><strong class="value">{number(hhi_states, 0)}</strong></div></div><p class="lead" style="margin-top:12px">{states_to_80} estados respondem por aproximadamente 80% da produÃ§Ã£o estadual analisada.</p><div id="paretoBars" class="bars"></div></div></section>
    <h2>Ãrea x Produtividade x ProduÃ§Ã£o</h2><section class="grid-even"><div class="chart"><h3>Quadrantes de variaÃ§Ã£o</h3><p class="lead">X = variaÃ§Ã£o da Ã¡rea, Y = variaÃ§Ã£o da produtividade, tamanho visual aproximado pela produÃ§Ã£o.</p><div id="scatter" class="scatter"></div></div><div class="chart"><h3>Crescimentos e quedas</h3><p class="lead">Maiores movimentos absolutos de produÃ§Ã£o no recorte selecionado.</p><div id="movementBars" class="bars"></div></div></section>
    <h2>Principais Insights</h2><section id="insights" class="insights"></section>
    <h2>Dados</h2><section class="panel"><div class="actions"><button id="downloadCsv" type="button">Baixar dados filtrados CSV</button></div><div style="overflow:auto; margin-top:12px"><table><thead><tr><th>Item</th><th>Producao</th><th>Area</th><th>Produtividade</th><th>Variacao</th><th>Participacao</th></tr></thead><tbody id="dataTable"></tbody></table></div></section>
  </main>
  <footer class="wrap">Dados oficiais preservados em data/raw. Rankings estaduais usam somente tipo_linha == uf; regiÃµes, agregados regionais e Brasil nÃ£o entram nos rankings.</footer>
  <script>
    const productsData = {product_json};
    const statesData = {state_json};
    const productLocationData = {product_location_json};
    const paretoStates = {pareto_json};
    const productSelect = document.getElementById("productFilter");
    const regionSelect = document.getElementById("regionFilter");
    const escapeHtml = value => String(value ?? "").replace(/[&<>"']/g, char => {{
      switch (char) {{
        case "&": return "&amp;";
        case "<": return "&lt;";
        case ">": return "&gt;";
        case String.fromCharCode(34): return "&quot;";
        case "'": return "&#39;";
        default: return char;
      }}
    }});
    const csvCell = value => {{
      const text = String(value ?? "");
      const safe = /^[=+@-]/.test(text) ? `'${{text}}` : text;
      return `"${{safe.replace(/"/g, '""')}}"`;
    }};
    const fmt = (v, d=1) => v === null || Number.isNaN(Number(v)) ? "-" : Number(v).toLocaleString("pt-BR", {{minimumFractionDigits:d, maximumFractionDigits:d}});
    const mt = v => Math.abs(v) >= 1000 ? `${{fmt(v/1000,1)}} milhÃµes t` : `${{fmt(v,1)}} mil t`;
    const compactT = v => Math.abs(v) >= 1000 ? `${{fmt(v/1000,1)}} mi t` : `${{fmt(v,1)}} mil t`;
    const compactHa = v => Math.abs(v) >= 1000 ? `${{fmt(v/1000,1)}} mi ha` : `${{fmt(v,1)}} mil ha`;
    const pct = v => v === null || Number.isNaN(Number(v)) ? "-" : `${{v >= 0 ? "â–² +" : "â–¼ "}}${{fmt(v,1)}}%`;
    const nameOf = (row, view) => view === "products" ? row.produto : row.regiao_uf;
    const shareOf = row => row.participacao_ativa_pct ?? row.participacao_producao_pct;
    const deltaClass = value => value === null || Number.isNaN(Number(value)) ? "note" : `note ${{value >= 0 ? "up" : "down"}}`;
    function withActiveShare(rows) {{
      const total = rows.reduce((sum, row) => sum + (Number(row.producao_atual_mil_t) || 0), 0);
      return rows.map(row => ({{...row, participacao_ativa_pct: total > 0 ? (Number(row.producao_atual_mil_t) || 0) / total * 100 : null}}));
    }}
    function setupFilters() {{
      productSelect.innerHTML = `<option value="Todos">Todos</option>` + productsData.map(r => `<option value="${{escapeHtml(r.produto)}}">${{escapeHtml(r.produto)}}</option>`).join("");
      const regions = [...new Set(statesData.map(r => r.regiao))].sort();
      regionSelect.innerHTML = `<option value="Todos">Todos</option>` + regions.map(r => `<option value="${{escapeHtml(r)}}">${{escapeHtml(r)}}</option>`).join("");
    }}
    function filteredRows() {{
      const view = document.getElementById("view").value;
      const q = document.getElementById("search").value.trim().toLowerCase();
      const selectedRegion = regionSelect.value;
      const selectedProduct = productSelect.value;
      let rows = view === "products"
        ? (selectedRegion === "Todos" ? [...productsData] : productLocationData.filter(r => r.tipo_linha === "regiao" && r.regiao === selectedRegion))
        : (selectedProduct === "Todos" ? [...statesData] : productLocationData.filter(r => r.tipo_linha === "uf"));
      if (selectedProduct !== "Todos") rows = rows.filter(r => r.produto === selectedProduct);
      if (view === "states" && regionSelect.value !== "Todos") rows = rows.filter(r => r.regiao === regionSelect.value);
      if (q) rows = rows.filter(r => nameOf(r, view).toLowerCase().includes(q));
      return rows;
    }}
    function renderBars(id, rows, view, valueCol="producao_atual_mil_t", limit=10) {{
      const sorted = [...rows].sort((a,b) => b[valueCol] - a[valueCol]).slice(0, limit);
      const max = Math.max(...sorted.map(r => Math.abs(r[valueCol] || 0)), 1);
      document.getElementById(id).innerHTML = sorted.map(r => {{
        const label = escapeHtml(nameOf(r, view));
        const title = escapeHtml(`${{nameOf(r, view)}} | Producao: ${{mt(r.producao_atual_mil_t)}} | Area: ${{fmt(r.area_atual_mil_ha,1)}} mil ha | Produtividade: ${{fmt(r.produtividade_atual_kg_ha,0)}} kg/ha | Participacao: ${{fmt(shareOf(r),1)}}% | Variacao: ${{fmt(r.variacao_producao_pct_calc,1)}}%`);
        return `<div class="bar-row" title="${{title}}"><b>${{label}}</b><div class="bar-track"><div class="bar-fill${{r[valueCol] < 0 ? " neg" : ""}}" style="width:${{Math.max(Math.abs(r[valueCol] || 0)/max*100,1)}}%"></div></div><span>${{valueCol.includes("pct") ? fmt(r[valueCol],1)+"%" : mt(r[valueCol])}}</span></div>`;
      }}).join("") || "<p class='lead'>Nenhum dado encontrado para os filtros selecionados.</p>";
    }}
    function renderScatter(rows, view) {{
      const xs = rows.map(r => r.variacao_area_pct_calc || 0), ys = rows.map(r => r.variacao_produtividade_pct_calc || 0);
      const maxX = Math.max(...xs.map(Math.abs), 1), maxY = Math.max(...ys.map(Math.abs), 1);
      document.getElementById("scatter").innerHTML = rows.map(r => {{
        const left = 50 + (r.variacao_area_pct_calc || 0) / maxX * 45;
        const top = 50 - (r.variacao_produtividade_pct_calc || 0) / maxY * 45;
        const size = Math.min(24, 8 + Math.sqrt(Math.max(r.producao_atual_mil_t, 0)) / 28);
        const title = escapeHtml(`${{nameOf(r, view)}} | Area: ${{fmt(r.variacao_area_pct_calc,1)}}% | Produtividade: ${{fmt(r.variacao_produtividade_pct_calc,1)}}% | Producao: ${{mt(r.producao_atual_mil_t)}}`);
        return `<span class="dot" style="left:${{left}}%;top:${{top}}%;width:${{size}}px;height:${{size}}px" title="${{title}}"></span>`;
      }}).join("");
    }}
    function renderTable(rows, view) {{
      document.getElementById("dataTable").innerHTML = [...rows].sort((a,b) => b.producao_atual_mil_t - a.producao_atual_mil_t).map(r => `<tr><td>${{escapeHtml(nameOf(r, view))}}</td><td>${{mt(r.producao_atual_mil_t)}}</td><td>${{fmt(r.area_atual_mil_ha,1)}} mil ha</td><td>${{fmt(r.produtividade_atual_kg_ha,0)}} kg/ha</td><td>${{pct(r.variacao_producao_pct_calc)}}</td><td>${{fmt(shareOf(r),1)}}%</td></tr>`).join("");
    }}
    function renderKpis(rows, view) {{
      const totalProduction = rows.reduce((sum, r) => sum + (Number(r.producao_atual_mil_t) || 0), 0);
      const totalPrevious = rows.reduce((sum, r) => sum + (Number(r.producao_anterior_mil_t) || 0), 0);
      const totalArea = rows.reduce((sum, r) => sum + (Number(r.area_atual_mil_ha) || 0), 0);
      const areaPrevious = rows.reduce((sum, r) => sum + ((Number(r.area_atual_mil_ha) || 0) - (Number(r.crescimento_area_mil_ha) || 0)), 0);
      const productivity = totalArea > 0 ? totalProduction * 1000 / totalArea : null;
      const prodDelta = totalPrevious > 0 ? (totalProduction - totalPrevious) / totalPrevious * 100 : null;
      const areaDelta = areaPrevious > 0 ? (totalArea - areaPrevious) / areaPrevious * 100 : null;
      const sorted = [...rows].sort((a,b) => b.producao_atual_mil_t - a.producao_atual_mil_t);
      const leader = sorted[0];
      const runnerUp = sorted[1];
      document.getElementById("kpiProduction").textContent = compactT(totalProduction);
      document.getElementById("kpiArea").textContent = compactHa(totalArea);
      document.getElementById("kpiProductivity").textContent = productivity ? `${{fmt(productivity,0)}} kg/ha` : "-";
      document.getElementById("kpiProductionDelta").textContent = `${{pct(prodDelta)}} vs. safra anterior`;
      document.getElementById("kpiProductionDelta").className = deltaClass(prodDelta);
      document.getElementById("kpiAreaDelta").textContent = `${{pct(areaDelta)}} vs. safra anterior`;
      document.getElementById("kpiAreaDelta").className = deltaClass(areaDelta);
      document.getElementById("kpiLeaders").innerHTML = leader ? [leader, runnerUp].filter(Boolean).map(row => `<div class="leader-row"><strong>${{escapeHtml(nameOf(row, view))}}</strong><span>${{compactT(row.producao_atual_mil_t)}}</span></div>`).join("") : "<span class='note'>Sem dados no recorte</span>";
    }}
    function renderInsights(rows, view) {{
      const sorted = [...rows].sort((a,b) => b.producao_atual_mil_t - a.producao_atual_mil_t);
      const growth = [...rows].sort((a,b) => b.crescimento_producao_mil_t - a.crescimento_producao_mil_t)[0];
      const drop = [...rows].sort((a,b) => a.crescimento_producao_mil_t - b.crescimento_producao_mil_t)[0];
      const top = sorted[0];
      document.getElementById("insights").innerHTML = top ? [`${{nameOf(top, view)}} lidera com ${{mt(top.producao_atual_mil_t)}} e ${{fmt(shareOf(top),1)}}% do recorte.`,`${{nameOf(growth, view)}} teve o maior aumento absoluto: ${{mt(growth.crescimento_producao_mil_t)}}.`,`${{nameOf(drop, view)}} teve a maior queda absoluta: ${{mt(drop.crescimento_producao_mil_t)}}.`].map(t => `<div class="panel"><p class="lead">${{escapeHtml(t)}}</p></div>`).join("") : "<div class='panel'><p class='lead'>Nenhum dado encontrado para os filtros selecionados.</p></div>";
    }}
    function renderPareto() {{
      const max = Math.max(...paretoStates.slice(0,10).map(r => r.producao_atual_mil_t), 1);
      document.getElementById("paretoBars").innerHTML = paretoStates.slice(0,10).map(r => `<div class="bar-row"><b>${{r.ranking}}. ${{escapeHtml(r.regiao_uf)}}</b><div class="bar-track"><div class="bar-fill" style="width:${{r.producao_atual_mil_t/max*100}}%"></div></div><span>${{fmt(r.participacao_acumulada_pct,1)}}% acum.</span></div>`).join("");
    }}
    function render() {{
      const view = document.getElementById("view").value;
      const rows = withActiveShare(filteredRows());
      document.getElementById("searchLabel").textContent = view === "products" ? "Cultura" : "Estado";
      document.getElementById("search").placeholder = view === "products" ? "Buscar cultura" : "Buscar UF";
      const regionText = regionSelect.value === "Todos" ? "Brasil" : regionSelect.value;
      const productText = productSelect.value === "Todos" ? "" : ` Â· ${{productSelect.value}}`;
      document.getElementById("contextStrip").innerHTML = [`VisÃ£o: ${{view === "products" ? "Culturas" : "Estados"}}`, `Produto: ${{productSelect.value}}`, `RegiÃ£o: ${{regionSelect.value}}`].map(item => `<span class="context-chip">${{escapeHtml(item)}}</span>`).join("");
      document.getElementById("rankingTitle").textContent = view === "products"
        ? `Top culturas por produÃ§Ã£o Â· ${{regionText}}`
        : `Estados com maior produÃ§Ã£o${{productText}}`;
      document.getElementById("scopeNote").textContent = view === "products"
        ? `Culturas calculadas para ${{regionText}} a partir das abas oficiais por produto da planilha-base.`
        : `Rankings estaduais consideram somente as 27 UFs vÃ¡lidas${{productText}}.`;
      renderBars("rankingBars", rows, view);
      renderKpis(rows, view);
      renderBars("movementBars", [...rows].sort((a,b) => Math.abs(b.crescimento_producao_mil_t) - Math.abs(a.crescimento_producao_mil_t)), view, "crescimento_producao_mil_t", 8);
      renderScatter(rows, view);
      renderTable(rows, view);
      renderInsights(rows, view);
      renderPareto();
    }}
    document.getElementById("downloadCsv").addEventListener("click", () => {{
      const view = document.getElementById("view").value;
      const rows = withActiveShare(filteredRows());
      const headers = ["item","producao_mil_t","area_mil_ha","produtividade_kg_ha","variacao_producao_pct","participacao_pct"];
      const csv = [headers.map(csvCell).join(","), ...rows.map(r => [nameOf(r, view), r.producao_atual_mil_t, r.area_atual_mil_ha, r.produtividade_atual_kg_ha, r.variacao_producao_pct_calc, shareOf(r)].map(csvCell).join(","))].join("\\n");
      const blob = new Blob([csv], {{type:"text/csv;charset=utf-8"}});
      const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = "agroscope_dados_filtrados.csv"; a.click(); URL.revokeObjectURL(a.href);
    }});
    setupFilters();
    ["view","productFilter","regionFilter","search"].forEach(id => document.getElementById(id).addEventListener("input", render));
    ["view","productFilter","regionFilter"].forEach(id => document.getElementById(id).addEventListener("change", render));
    render();
  </script>
</body>
</html>
"""
    (REPORTS_DIR / "dashboard.html").write_text(fix_display_text(html), encoding="utf-8")


def main() -> None:
    configure_logging()
    ensure_dirs()
    products_raw, states_raw = load_data()
    products = add_metrics(clean_frame(products_raw), "produto")
    states = add_metrics(clean_frame(states_raw), "localidade")
    product_locations = add_metrics(clean_frame(extract_product_location_data()), "produto_localidade")
    write_reports(products, states)
    export_data(products, states, product_locations)
    write_dictionary(products)
    make_figures(products, states)
    write_dashboard(products, states, product_locations)
    logging.info("Pipeline concluido")


if __name__ == "__main__":
    main()


