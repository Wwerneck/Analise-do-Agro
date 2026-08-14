# Como contribuir

## Fluxo local

1. Crie uma branch a partir de `main`.
2. Instale `requirements.txt`.
3. Execute `python -m pytest -q` antes de abrir um pull request.
4. Preserve a rastreabilidade: fontes, transformações e métricas devem permanecer documentadas.
5. Não inclua dados sensíveis nem altere dados oficiais sem registrar a fonte e o critério utilizado.

## Padrão de commits

```text
feat: adiciona recurso
fix: corrige comportamento
test: cobre cenário
docs: atualiza documentação
ci: ajusta automação
```

## Pull requests

Explique a alteração, as validações executadas e qualquer efeito no dashboard, nos indicadores ou na interpretação dos dados.
