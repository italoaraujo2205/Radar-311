# Service Ops 311 · onde investigar a demora de atendimento?

Estudo de análise de dados sobre solicitações públicas de atendimento de Nova York. A pergunta não é “qual bairro é pior?”, e sim **em quais filas uma equipe operacional deveria investigar primeiro para reduzir solicitações não encerradas em 72 horas?** O projeto combina volume, taxa, casos ainda abertos e comparação por tipo de problema. Usa solicitações reais criadas em janeiro de 2025, fornecidas pelo [NYC Open Data](https://data.cityofnewyork.us/Social-Services/311-Service-Requests-from-2020-to-Present/erm2-nwe9).

**Abra o [painel interativo](docs/index.html) e o [memorando de decisões](reports/decision_memo.md).** No GitHub, use *Download raw* para abrir o HTML localmente; ele não depende de servidor. Os dois arquivos são produzidos pela mesma base e incluem os números da execução registrada neste repositório.

Na extração analisada, **348.180** linhas resultaram em **348.081** solicitações válidas; **75,8%** dos casos com prazo verificável foram encerrados em 72 horas. O grupo `HPD / HEAT/HOT WATER` concentrou **14.597** solicitações não encerradas nesse intervalo. Outro achado de qualidade: **1.051** solicitações tinham status `CLOSED`, mas não traziam data de fechamento; elas foram excluídas da taxa para evitar uma classificação falsa.

## Pergunta e entrega

| O que avaliar | Como foi definido | Decisão apoiada |
| --- | --- | --- |
| Encerramento em 72h | `closed_date` até 72h após `created_date`; só casos com janela completa e fechamento verificável | Monitorar velocidade sem distorcer o último dia |
| Sem data de fechamento | Status diferente de `CLOSED`, sem `closed_date` e com mais de 72h | Identificar fila pendente |
| Volume fora de 72h | Casos elegíveis menos casos encerrados na janela | Priorizar onde uma melhoria alcançaria mais pessoas |
| Comparação ajustada | Agência e problema iguais; referência calculada em *outros* bairros | Reduzir confusão pela composição de solicitações |
| p90 de fechados | Percentil 90 do tempo de casos já encerrados | Diagnóstico auxiliar, sempre junto da taxa e dos abertos |

O projeto trata a janela de 72 horas como **indicador analítico**, não como SLA oficial. Na fonte, `due_date` se refere ao prazo para a agência **atualizar** o chamado, não ao prazo de encerramento. A comparação entre bairros não isola complexidade, acesso aos canais ou propensão de moradores a registrar ocorrências.

## Arquitetura

1. `src/service_ops/source.py` consulta a API oficial em páginas, guarda apenas 11 campos úteis, remove endereço e coordenadas, registra hash e contagem, e rejeita páginas duplicadas.
2. `data/raw/*.jsonl.gz` mantém a extração bruta local. `sql/01_model.sql` tipa, isola registros inválidos, cria dimensões, fato e três tabelas analíticas em DuckDB.
3. `src/service_ops/report.py` usa o banco para gerar uma página HTML filtrável e o memorando com achados e limites.
4. `outputs/*.csv` exporta tabelas para Power BI. Uma receita do modelo e das medidas está em [powerbi/README.md](powerbi/README.md).

Os dados brutos e o banco não entram no Git: qualquer pessoa pode baixar novamente a fonte, enquanto o painel e o memorando ficam disponíveis sem instalar nada. Como a API é atualizada diariamente, o [manifesto da execução](reports/run_manifest.json) registra contagem, hash e data da extração usada nos resultados; uma reexecução posterior pode produzir números diferentes.

## Executar

Python 3.11+; na pasta do repositório:

```bash
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows: .venv\Scripts\activate
pip install -e '.[test]'
service-ops all --start 2025-01-01 --end 2025-02-01 --page-size 20000
python -m pytest -q
```

A extração mensal reúne centenas de milhares de linhas; a API pode limitar requisições sem token. Se a extração falhar, a cópia parcial é descartada e o comando deve ser executado novamente. Para conhecer o fluxo com menos dados, use `--end 2025-01-03` e, após a inspeção, rode o mês completo para comparar os bairros. `service-ops build` e `service-ops report` executam apenas as etapas posteriores, usando o mesmo intervalo de datas. É possível fixar o instante de observação com `--as-of '2025-02-05 00:00:00'`.

## Modelo e validação

`fact_request` tem uma linha por `unique_key`; as dimensões são `dim_problem` (agência + tipo) e `dim_borough`. Os marts são `mart_daily`, `mart_borough_problem` e `mart_case_mix`. A cobertura do ajuste exige pelo menos 30 casos da mesma agência e problema em outros bairros, 500 casos comparáveis no bairro e cobertura de 80% dos elegíveis. Grupos não comparáveis ficam de fora do indicador ajustado.

O pipeline reconcilia o total bruto com aceitos, rejeitados, repetidos e fora da janela; rejeita extrações com IDs duplicados e falha quando dados inválidos ultrapassam 1%. Os testes exercitam censura temporal, data incoerente, comparação ajustada e paginação inconsistente. O [dicionário de métricas](docs/metricas.md) descreve os campos, filtros e interpretações.

## Limites para a discussão

Encerrar uma solicitação não comprova que o problema foi resolvido, e a taxa de 72 horas não traduz satisfação do cidadão. A base cobre chamados dirigidos a agências específicas, não toda a demanda por serviços urbanos. Uma recomendação de mudança operacional precisaria de entrevistas com as agências e avaliação antes/depois com grupos comparáveis.

Fonte: [311 Service Requests from 2020 to Present, NYC Open Data](https://data.cityofnewyork.us/Social-Services/311-Service-Requests-from-2020-to-Present/erm2-nwe9). As definições de campos e a atualização da base estão nas [notas oficiais](https://www.nyc.gov/opendata/news/all-news/311-Service-Requests-Updates).
