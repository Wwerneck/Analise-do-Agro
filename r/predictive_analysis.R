# Complementary statistical diagnostics for Agroscope predictive analysis.

library(stats)

`%||%` <- function(x, y) if (is.null(x) || length(x) == 0 || is.na(x)) y else x
args_file <- sub("^--file=", "", commandArgs(FALSE)[grepl("^--file=", commandArgs(FALSE))][1])
script_file <- args_file %||% file.path(getwd(), "r", "predictive_analysis.R")
root <- normalizePath(file.path(dirname(script_file), ".."), mustWork = FALSE)
features_path <- file.path(root, "data", "processed", "predictions", "features.csv")
output_path <- file.path(root, "reports", "predictive_r_diagnostics.md")

if (!file.exists(features_path)) {
  dir.create(dirname(output_path), recursive = TRUE, showWarnings = FALSE)
  writeLines(c(
    "# Diagnostico Estatistico Preditivo em R",
    "",
    "Arquivo de features nao encontrado. Execute primeiro: `python -m src.predictive.pipeline`."
  ), output_path)
  quit(save = "no")
}

df <- read.csv(features_path, stringsAsFactors = FALSE)
targets <- c("producao_mil_t", "produtividade_kg_ha", "area_mil_ha")
lines <- c(
  "# Diagnostico Estatistico Preditivo em R",
  "",
  "Camada complementar baseada nos artefatos calculados em Python. Nao substitui a validacao temporal principal."
)

for (target in targets) {
  values <- df[[target]]
  values <- values[!is.na(values)]
  lines <- c(lines, "", paste0("## ", target), "")
  if (length(values) < 3) {
    lines <- c(lines, "Historico insuficiente para decomposicao temporal, regressao estatistica robusta e diagnostico de residuos.")
    next
  }
  fit <- lm(values ~ seq_along(values))
  residuals_summary <- summary(residuals(fit))
  conf <- confint(fit)
  lines <- c(
    lines,
    paste0("- Coeficiente de tendencia: ", round(coef(fit)[2], 4)),
    paste0("- R2: ", round(summary(fit)$r.squared, 4)),
    paste0("- Intervalo de confianca da tendencia: [", round(conf[2, 1], 4), ", ", round(conf[2, 2], 4), "]"),
    paste0("- Residuos: min=", round(residuals_summary[1], 4), "; mediana=", round(residuals_summary[3], 4), "; max=", round(residuals_summary[6], 4))
  )
}

dir.create(dirname(output_path), recursive = TRUE, showWarnings = FALSE)
writeLines(lines, output_path)
