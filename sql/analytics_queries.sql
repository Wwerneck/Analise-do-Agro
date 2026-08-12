-- Top culturas por producao
WITH produtos_analiticos AS (
    SELECT *
    FROM staging_produtos
    WHERE tipo_linha = 'produto'
      AND produto !~* '(milho|amendoim|feij[aã]o) [123].*safra'
      AND produto !~* '^algodão[[:space:]]*-[[:space:]]*pluma$'
      AND produto !~* '^arroz (sequeiro|irrigado)$'
      AND produto !~* '^(cores|preto|caupi)$'
)
SELECT produto, producao_atual_mil_t,
       DENSE_RANK() OVER (ORDER BY producao_atual_mil_t DESC) AS ranking
FROM produtos_analiticos
ORDER BY producao_atual_mil_t DESC
LIMIT 10;

-- Participacao percentual por produto
WITH produtos_analiticos AS (
    SELECT *
    FROM staging_produtos
    WHERE tipo_linha = 'produto'
      AND produto !~* '(milho|amendoim|feij[aã]o) [123].*safra'
      AND produto !~* '^algodão[[:space:]]*-[[:space:]]*pluma$'
      AND produto !~* '^arroz (sequeiro|irrigado)$'
      AND produto !~* '^(cores|preto|caupi)$'
)
SELECT produto,
       producao_atual_mil_t,
       producao_atual_mil_t / SUM(producao_atual_mil_t) OVER () * 100 AS participacao_pct
FROM produtos_analiticos
ORDER BY participacao_pct DESC;

-- Ranking estadual sem misturar regioes/agregados
WITH ufs AS (
    SELECT * FROM staging_ufs WHERE tipo_linha = 'uf'
)
SELECT regiao_uf, producao_atual_mil_t,
       RANK() OVER (ORDER BY producao_atual_mil_t DESC) AS ranking_uf
FROM ufs;

-- Classificacao por crescimento
WITH produtos_analiticos AS (
    SELECT *
    FROM staging_produtos
    WHERE tipo_linha = 'produto'
      AND produto !~* '(milho|amendoim|feij[aã]o) [123].*safra'
      AND produto !~* '^algodão[[:space:]]*-[[:space:]]*pluma$'
      AND produto !~* '^arroz (sequeiro|irrigado)$'
      AND produto !~* '^(cores|preto|caupi)$'
)
SELECT produto,
       CASE
           WHEN variacao_producao_pct_calc > 0 THEN 'crescimento'
           WHEN variacao_producao_pct_calc < 0 THEN 'queda'
           ELSE 'estavel'
       END AS status_producao,
       variacao_producao_pct_calc
FROM produtos_analiticos;

-- Producao acumulada no ranking
WITH produtos_analiticos AS (
    SELECT *
    FROM staging_produtos
    WHERE tipo_linha = 'produto'
      AND produto !~* '(milho|amendoim|feij[aã]o) [123].*safra'
      AND produto !~* '^algodão[[:space:]]*-[[:space:]]*pluma$'
      AND produto !~* '^arroz (sequeiro|irrigado)$'
      AND produto !~* '^(cores|preto|caupi)$'
)
SELECT produto,
       producao_atual_mil_t,
       SUM(producao_atual_mil_t) OVER (ORDER BY producao_atual_mil_t DESC) AS producao_acumulada
FROM produtos_analiticos;

-- Media de producao por tipo de linha no dataset estadual
SELECT tipo_linha, AVG(producao_atual_mil_t) AS media_producao_atual_mil_t
FROM staging_ufs
GROUP BY tipo_linha
ORDER BY media_producao_atual_mil_t DESC;
