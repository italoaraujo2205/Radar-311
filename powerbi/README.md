# Modelo para Power BI

Após executar `service-ops all`, importe os CSVs da pasta `outputs/`. Para uma apresentação leve, comece por `mart_borough_problem.csv`, `mart_case_mix.csv` e `mart_daily.csv` (os três já são agregados). Não crie relação entre os marts; cada um tem grão diferente. Se precisar de navegação detalhada e drill-through, conecte o DuckDB por uma exportação do `fact_request` e use `dim_problem` e `dim_borough` com cardinalidade 1:N.

## Página 1: diagnóstico

- Cartões: solicitações elegíveis, taxa de encerramento 72h, casos fora da janela.
- Série diária: soma de `requests` de `mart_daily` por `created_day`.
- Matriz: agência, problema, bairro; volume e taxa de 72h. Ordene por casos fora da janela, não apenas pela pior taxa.
- Segmentações: agência, bairro e problema. Mostre ao lado da matriz a cobertura dos grupos usados no ajuste.

## Página 2: composição

- Barras divergentes: `adjusted_gap_pp` por bairro, com zero no centro.
- Tabela de apoio: `comparable`, `coverage_pct`, `observed` e `expected`.
- Texto fixo: a diferença ajusta somente agência e tipo de solicitação e não estima efeito causal.

## Medidas DAX no mart agregado

```dax
Casos Elegíveis = SUM(mart_borough_problem[eligible_72h])

Encerrados 72h = SUM(mart_borough_problem[closed_72h])

Taxa 72h = DIVIDE([Encerrados 72h], [Casos Elegíveis])

Fora de 72h = [Casos Elegíveis] - [Encerrados 72h]

Sem Data e Não Encerrados = SUM(mart_borough_problem[open_after_72h])
```

Formate `Taxa 72h` como porcentagem. A soma desses indicadores respeita filtros por bairro/agência/tipo; não tire média simples de `pct_closed_72h`. O ajuste `adjusted_gap_pp` já é calculado no SQL sobre os casos comparáveis e não deve ser agregado ou cruzado livremente com outros filtros.
