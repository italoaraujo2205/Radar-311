# Dicionário de métricas

**Grão do fato:** uma solicitação (`unique_key`). O intervalo informado na extração filtra `created_date`; não usa a data de fechamento como filtro. Timestamps da API vêm sem fuso; a análise preserva o horário informado e não faz conversão de fuso.

| Métrica | Numerador | Denominador | Observação |
| --- | --- | --- | --- |
| Casos elegíveis 72h | N/A | `created_at <= as_of - 72h` e status `CLOSED` com `closed_at` ausente removido | Sem data não é possível confirmar o prazo |
| Taxa encerrada 72h | Elegíveis com `closed_at` entre criação e criação + 72h | Elegíveis | Abertos com janela completa contam como não encerrados |
| Sem data e não encerrados após 72h | Sem `closed_at`, status diferente de `CLOSED`, criados há mais de 72h | N/A | Status `CLOSED` sem data é contado separadamente |
| Volume fora de 72h | Elegíveis − encerrados em 72h | N/A | Inclui fechamentos posteriores e ainda abertos |
| p90 entre encerrados | Percentil do tempo em horas de registros com `closed_at` | Somente fechados | Interpretar com cuidado se houver muitos abertos |
| Lacuna ajustada (p.p.) | 100 × (encerrados observados − esperados) | Casos comparáveis | Esperados a partir da taxa em outros bairros para agência × problema |

Rejeições: ID ausente, data de criação inválida ou data de fechamento anterior à criação. Bairro ausente vai para `UNKNOWN` e é excluído apenas do ajuste de composição. Uma alteração na base de origem entre páginas pode causar erro de IDs repetidos; a extração descarta o arquivo parcial.

Solicitações com status `CLOSED` e `closed_date` vazia continuam no fato, mas são excluídas dos indicadores de prazo. O total desses registros aparece em `outputs/quality.json` e no memorando.
