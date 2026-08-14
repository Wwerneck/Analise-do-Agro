# Agroscope

<p align="center">
  <a href="https://wwerneck.github.io/Analise-do-Agro/"><img alt="Dashboard ao vivo" src="https://img.shields.io/badge/Dashboard-GitHub%20Pages-2ea44f?logo=githubpages&logoColor=white"></a>
  <a href="https://github.com/Wwerneck/Analise-do-Agro/actions/workflows/tests.yml"><img alt="Testes" src="https://github.com/Wwerneck/Analise-do-Agro/actions/workflows/tests.yml/badge.svg?branch=main"></a>
  <a href="./CHANGELOG.md"><img alt="Release" src="https://img.shields.io/badge/release-v1.0.0-2ea44f"></a>
</p>

Projeto de analytics com dados oficiais da CONAB para a estimativa da safra 2025/26, comparada a 2024/25. O objetivo e transformar arquivos brutos em bases auditaveis, metricas, visualizacoes, consultas SQL e um dashboard executivo estatico sobre a producao agricola brasileira.

<p align="center">
  <img src="reports/figures/top_10_produtos_producao.png" alt="Top 10 produtos por produção" width="49%"> 
  <img src="reports/figures/pareto_ufs_producao.png" alt="Pareto da produção por UF" width="49%">
</p>

## Avaliação rápida

- [**Abrir dashboard executivo no GitHub Pages**](https://wwerneck.github.io/Analise-do-Agro/)
- Pipeline auditável com extração, tratamento, validação, métricas, visualizações, SQL e análises complementares em R.
- Testes automatizados de qualidade dos dados e da camada preditiva, executados também por CI.

## Destaques

- Producao total Brasil: 353,375.92 mil t.
- Area total Brasil: 83,257.90 mil ha.
- Top cultura por producao: SOJA, com 177,985.00 mil t.
- Top UF por producao: MT, com 109,088.70 mil t.
- Concentracao por produto: CR3 de 92.63%, CR5 de 96.48% e HHI de 4092.07.
- Concentracao estadual: CR3 de 54.56%, CR5 de 72.98% e HHI de 1491.96.
- Apenas 2 produtos respondem por aproximadamente 80% da producao analisada.
- Apenas 7 UFs respondem por aproximadamente 80% da producao estadual analisada.

## Perguntas de negocio

- Quais culturas e UFs concentram producao, area e produtividade?
- Quais produtos e estados cresceram ou recuaram frente a safra anterior?
- A variacao de producao esta mais associada a area, produtividade ou ambos?
- Qual e o nivel de concentracao da producao agricola no recorte analisado?

## Fonte dos dados

- Fonte oficial: CONAB, 5o levantamento da safra de graos 2025/26.
- Referencia: estimativa de fevereiro/2026.
- Comparativo: safra 2025/26 contra 2024/25.
- Dados brutos preservados em `data/raw`.
- O CSV por produto foi extraido da aba `Brasil - Total por Produto` do XLSX oficial.
- Dados por produto e localidade foram extraidos das abas especificas de cada cultura no XLSX oficial.

## Entregaveis

- Dashboard estatico: `reports/dashboard.html`.
- Resumo executivo: `reports/executive_summary.md`.
- Relatorio de qualidade: `reports/data_quality_report.md`.
- Dicionario de dados: `docs/data_dictionary.md`.
- Figuras principais em `reports/figures`.
- Bases tratadas em CSV e Parquet em `data/processed`.
- Exports analiticos em `data/exports`.
- Scripts SQL em `sql`.
- Testes automatizados em `tests`.

## Estrutura

```text
data/
  raw/          Dados originais e extraidos da CONAB
  processed/    Bases tratadas em CSV e Parquet
  exports/      Tabelas analiticas para consumo externo
docs/           Dicionario de dados e imagens
notebooks/      Analises exploratorias em Python e R
reports/        Dashboard, resumo executivo, qualidade e figuras
sql/            Schema, carga e consultas analiticas
src/
  python/       Pipeline, transformacao, metricas e visualizacao
  r/            Analise estatistica complementar
tests/          Testes de qualidade e consistencia
```

## Tecnologias

Python, Pandas, NumPy, PyArrow, Matplotlib, Plotly, SciPy, Statsmodels, Pytest, Jupyter, R, tidyverse, ggplot2 e SQL/PostgreSQL.

## Como executar

No PowerShell:

```powershell
python -m pip install -r requirements.txt
$env:MPLCONFIGDIR=".matplotlib"
python src/python/pipeline.py
python -m pytest -q
```

Depois abra `reports/dashboard.html` no navegador.

## Dashboard

O dashboard `Agroscope` e uma aplicacao HTML/CSS/JavaScript estatica gerada pelo pipeline Python. Ele apresenta uma leitura executiva da safra atual, com filtros por visao, produto, regiao e busca textual.

Versao para GitHub Pages: `https://wwerneck.github.io/Analise-do-Agro/`.

Principais recursos:

- KPIs de producao, area, produtividade e variacao.
- Ranking de culturas e estados por producao.
- Cruzamento Produto x Regiao a partir das abas especificas da planilha oficial.
- Concentracao estadual com CR3, CR5, HHI e Pareto 80%.
- Quadrantes de area x produtividade para leitura dos drivers de variacao.
- Insights deterministicos calculados no navegador.
- Tabela detalhada e download CSV respeitando os filtros ativos.

## Analise Preditiva

A camada preditiva adiciona auditoria automatica, preparacao temporal, features sem vazamento, backtesting, comparacao de modelos, estimativas da proxima safra, tendencias, anomalias, insights e metadados de reproducibilidade.

Dados utilizados: bases oficiais da CONAB ja processadas em `data/processed`, no formato atual de comparativo entre `2024/25` e `2025/26`. A auditoria encontrou somente duas safras historicas no projeto; por isso, o treinamento de modelos complexos e a validacao temporal robusta sao bloqueados e documentados.

Modelos considerados:

- Baseline ingenuo: previsao igual ao ultimo valor conhecido.
- Regressao Linear, Random Forest, XGBoost e Exponential Smoothing ficam registrados na comparacao, mas sao marcados como `historico_insuficiente` quando a serie nao possui observacoes suficientes.

Feature engineering:

- `lag_1`, `lag_2`, `lag_3`.
- medias moveis de 3 e 5 periodos.
- crescimento percentual.
- tendencia historica.
- volatilidade historica.

Todas as features usam `shift`/janelas calculadas somente com safras anteriores, evitando data leakage.

Validacao temporal e backtesting: o pipeline usa walk-forward quando ha historico. No recorte atual, cada serie permite apenas uma comparacao historica basica: usar `2024/25` para estimar `2025/26` e comparar com o valor real.

Metricas calculadas: MAE, RMSE, MAPE e R2. A selecao automatica prioriza MAE/RMSE; MAPE e interpretado com cautela quando valores reais sao proximos de zero.

Score de confianca:

- ALTA CONFIANCA: pelo menos 8 observacoes, MAPE baixo, serie estavel e baixa divergencia entre modelos.
- MEDIA CONFIANCA: pelo menos 5 observacoes, erro moderado e volatilidade aceitavel.
- BAIXA CONFIANCA: historico curto, erro alto, alta volatilidade ou modelos sem suporte suficiente.

Como executar:

```powershell
python -m src.predictive.pipeline
python -m pytest -q
```

Artefatos gerados:

- `data/processed/predictions/forecast_production.csv`
- `data/processed/predictions/forecast_productivity.csv`
- `data/processed/predictions/forecast_area.csv`
- `data/processed/predictions/model_metrics.csv`
- `data/processed/predictions/model_comparison.csv`
- `data/processed/predictions/trends.csv`
- `data/processed/predictions/anomalies.csv`
- `reports/predictive_backtest.md`
- `reports/model_metadata.json`
- `reports/predictive_r_diagnostics.md`, quando `r/predictive_analysis.R` e executado com Rscript.

Camada R complementar:

```powershell
Rscript r/predictive_analysis.R
```

Se `Rscript` nao estiver no PATH no Windows, use o caminho absoluto instalado, por exemplo `C:\Program Files\R\R-4.6.1\bin\Rscript.exe`. O script R consome `data/processed/predictions/features.csv` e gera diagnosticos estatisticos complementares de tendencia, regressao, residuos e intervalos quando houver historico suficiente.

Interpretacao: as previsoes representam estimativas estatisticas baseadas no comportamento historico dos dados e nao constituem previsao oficial da CONAB. Com apenas duas safras, os resultados atuais devem ser lidos como uma estrutura preditiva auditavel e conservadora, nao como uma previsao operacional robusta.

## Metodologia

- Percentuais oficiais sao preservados e tambem recalculados em colunas separadas para auditoria.
- Rankings estaduais usam somente `tipo_linha == "uf"`, sem misturar Brasil, regioes ou agregados regionais.
- Produtos com totais e subcategorias usam regra anti-dupla-contagem: totais como `MILHO TOTAL`, `FEIJAO TOTAL`, `AMENDOIM TOTAL` e `ARROZ` entram no ranking principal; detalhamentos equivalentes ficam fora da base analitica de participacao.
- A decomposicao da variacao usa sinais de area e produtividade para classificar expansoes e quedas.
- O recorte possui apenas dois periodos, portanto nao foram criados forecasts ou tendencias historicas artificiais.

## Qualidade dos dados

O relatorio `reports/data_quality_report.md` documenta colunas, tipos, ausentes, duplicidades, zeros, negativos, infinitos, outliers por IQR, divergencias percentuais e coerencia aproximada entre area, produtividade e producao.

## Figuras

- `reports/figures/top_10_produtos_producao.png`
- `reports/figures/top_10_ufs_producao.png`
- `reports/figures/top_10_produtos_variacao_producao_pct.png`
- `reports/figures/top_10_produtos_area.png`
- `reports/figures/pareto_produtos_producao.png`
- `reports/figures/pareto_ufs_producao.png`
- `reports/figures/area_x_producao_produtos.png`
- `reports/figures/produtividade_x_producao_produtos.png`

## SQL

A pasta `sql` contem:

- `schema.sql`: modelo relacional sugerido.
- `load.sql`: exemplo de carga.
- `analytics_queries.sql`: consultas para rankings, variacoes e concentracao.

## Publicação

O dashboard executivo está disponível em [GitHub Pages](https://wwerneck.github.io/Analise-do-Agro/). A publicação é gerada a partir do conteúdo estático em `docs/`.

Antes de atualizar os artefatos publicados, valide o projeto localmente:

```powershell
python -m pytest -q
```

## Limitacoes

- Os dados representam estimativas de safra.
- A comparacao atual possui somente dois periodos.
- Linhas agregadas existem e nao devem ser misturadas com rankings de UFs ou produtos analiticos.
- Associacoes estatisticas nao devem ser interpretadas como causalidade.

## Proximos passos

- Incorporar series historicas oficiais.
- Criar carga real em PostgreSQL.
- Expandir notebooks com narrativa visual.
- Evoluir a publicação para atualizações automatizadas quando houver novas séries oficiais.
