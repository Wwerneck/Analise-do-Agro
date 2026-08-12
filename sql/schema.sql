CREATE TABLE dim_produto (
    produto_id SERIAL PRIMARY KEY,
    produto TEXT NOT NULL UNIQUE
);

CREATE TABLE dim_localidade (
    localidade_id SERIAL PRIMARY KEY,
    regiao_uf TEXT NOT NULL UNIQUE,
    tipo_linha TEXT NOT NULL
);

CREATE TABLE dim_periodo (
    periodo_id SERIAL PRIMARY KEY,
    periodo TEXT NOT NULL UNIQUE
);

CREATE TABLE fact_producao_agricola (
    fato_id BIGSERIAL PRIMARY KEY,
    produto_id INTEGER REFERENCES dim_produto(produto_id),
    localidade_id INTEGER REFERENCES dim_localidade(localidade_id),
    periodo_anterior TEXT NOT NULL,
    periodo_atual TEXT NOT NULL,
    area_anterior_mil_ha NUMERIC,
    area_atual_mil_ha NUMERIC,
    produtividade_anterior_kg_ha NUMERIC,
    produtividade_atual_kg_ha NUMERIC,
    producao_anterior_mil_t NUMERIC,
    producao_atual_mil_t NUMERIC,
    variacao_area_pct_calc NUMERIC,
    variacao_produtividade_pct_calc NUMERIC,
    variacao_producao_pct_calc NUMERIC,
    fonte TEXT,
    referencia TEXT
);
