library(readr)
library(dplyr)

produtos <- read_csv("data/processed/conab_produtos_clean.csv", show_col_types = FALSE)

base_cor <- produtos |>
  select(area_atual_mil_ha, produtividade_atual_kg_ha, producao_atual_mil_t,
         variacao_area_pct_calc, variacao_produtividade_pct_calc, variacao_producao_pct_calc) |>
  na.omit()

if (nrow(base_cor) >= 10) {
  print(cor(base_cor, method = "spearman"))
} else {
  message("Observacoes insuficientes para uma analise de correlacao robusta.")
}
