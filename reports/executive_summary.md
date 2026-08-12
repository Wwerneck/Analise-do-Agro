# Executive Summary

## Contexto

Projeto analitico reproduzivel com dados oficiais da CONAB para a estimativa da safra 2025/26, comparada a 2024/25.

## Principais KPIs

- Producao total Brasil informada no dataset estadual: 353,375.92 mil t.
- Area total Brasil informada no dataset estadual: 83,257.90 mil ha.
- Top cultura por producao: SOJA (177,985.00 mil t).
- Top UF por producao: MT (109,088.70 mil t).
- CR3 produtos: 92.63% | CR5 produtos: 96.48% | HHI produtos: 4092.07.
- CR3 UFs: 54.56% | CR5 UFs: 72.98% | HHI UFs: 1491.96.
- Produtos ate aproximadamente 80% da producao: 2.
- UFs ate aproximadamente 80% da producao: 7.

## Principais Descobertas

- Soja representa 50.37% da producao no recorte por produto.
- Milho Total representa 39.18% da producao no recorte por produto; linhas de safra do milho foram tratadas como detalhamento para evitar dupla contagem.
- Linhas detalhadas de milho identificadas: nao disponivel.
- A decomposicao classifica expansoes e quedas por sinais de area e produtividade; a leitura e associativa, nao causal.

## Insights

### Concentracao por produto

Insight: a producao analisada e concentrada em poucas culturas.
Evidencia: 2 produtos alcancam cerca de 80% da producao; CR3 = 92.63%.
Interpretacao: decisoes sobre soja, milho e demais culturas lideres tendem a explicar grande parte do movimento agregado.
Limitacao: linhas de produto podem conter agregacoes e detalhamentos; o pipeline marca agregados explicitos e evita dupla contagem evidente.

### Variacao de producao

Insight: SOJA foi o maior aumento absoluto de producao, enquanto MILHO TOTAL teve a maior queda absoluta.
Evidencia: crescimento de 6,504.50 mil t e queda de -2,709.40 mil t.
Interpretacao: a classificacao de decomposicao indica expansao combinada no maior crescimento e queda por produtividade na maior queda.
Limitacao: a decomposicao usa sinais e diferencas entre dois periodos; nao estabelece causalidade.

### Concentracao estadual

Insight: a producao estadual tambem e concentrada.
Evidencia: 7 UFs alcancam cerca de 80% da producao; CR5 = 72.98%.
Interpretacao: os principais estados sustentam uma parcela relevante da oferta nacional no recorte.
Limitacao: rankings estaduais filtram apenas `tipo_linha = uf`; regioes e total Brasil nao entram no ranking.

### Movimento estadual

Insight: RS teve o maior aumento absoluto entre UFs, enquanto MT teve a maior queda.
Evidencia: variacoes absolutas de 3,019.30 mil t e -3,307.00 mil t.
Interpretacao: esses movimentos ajudam a localizar onde a mudanca agregada se concentra geograficamente.
Limitacao: o dataset estadual nao esta aberto por cultura nesta etapa.

## Limitacoes

- O recorte atual compara apenas dois periodos; nao foram criados forecasts, ARIMA, Prophet ou tendencias historicas artificiais.
- A planilha pode conter categorias agregadas de produto; somas devem respeitar a hierarquia para evitar dupla contagem.

## Proximos passos

- Incorporar serie historica oficial para analise temporal adequada.
- Adicionar dados por produto e UF quando disponiveis.
- Carregar os dados processados em PostgreSQL e publicar dashboard.
