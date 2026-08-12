library(readr)
library(dplyr)
library(ggplot2)
library(scales)

produtos <- read_csv("data/processed/conab_produtos_clean.csv", show_col_types = FALSE)

descritiva <- produtos |>
  summarise(
    media_producao = mean(producao_atual_mil_t, na.rm = TRUE),
    mediana_producao = median(producao_atual_mil_t, na.rm = TRUE),
    desvio_padrao_producao = sd(producao_atual_mil_t, na.rm = TRUE),
    q1_producao = quantile(producao_atual_mil_t, 0.25, na.rm = TRUE),
    q3_producao = quantile(producao_atual_mil_t, 0.75, na.rm = TRUE),
    coeficiente_variacao = desvio_padrao_producao / media_producao
  )

print(descritiva)

ggplot(produtos, aes(producao_atual_mil_t)) +
  geom_histogram(bins = 20, fill = "#2f6f73", color = "white") +
  scale_x_continuous(labels = label_number()) +
  labs(
    title = "Distribuicao da producao por produto",
    x = "Producao atual (mil t)",
    y = "Frequencia",
    caption = "Fonte: CONAB"
  )

