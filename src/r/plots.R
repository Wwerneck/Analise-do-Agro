library(readr)
library(ggplot2)

ufs <- read_csv("data/processed/conab_ufs_clean.csv", show_col_types = FALSE)

ggplot(subset(ufs, tipo_linha == "uf"), aes(reorder(regiao_uf, producao_atual_mil_t), producao_atual_mil_t)) +
  geom_col(fill = "#596f2f") +
  coord_flip() +
  labs(
    title = "Producao por UF",
    x = "UF",
    y = "Producao atual (mil t)"
  )
