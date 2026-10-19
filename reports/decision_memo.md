# Onde investigar a demora de atendimento no NYC 311

**Recorte:** solicitações criadas entre 2025-01-01 e 2025-01-31, extraídas da API pública do NYC Open Data. **Pergunta:** onde concentrar uma investigação operacional para reduzir solicitações que não foram encerradas nas primeiras 72 horas?

## O que os dados mostram

- 348,180 linhas recebidas; 348,081 solicitações válidas no recorte; 99 rejeitadas por chave ou data inválida.
- 347,030 solicitações têm janela de observação completa e data de fechamento avaliável; 75.8% foram encerradas em até 72 horas. 1,543 constam com status diferente de `CLOSED` e sem data de fechamento.
- 1,051 solicitações constam como `CLOSED`, mas sem data de fechamento: permanecem no fato e ficam fora da taxa de 72 horas porque não é possível verificar o prazo.
- Maior volume de casos fora da janela: **HPD / HEAT/HOT WATER: 67,229 casos elegíveis; 14,597 não encerrados em 72 horas.** Volume é critério de priorização, não prova de ineficiência.
- Grupo com menor taxa entre os de pelo menos 300 casos: **MANHATTAN / TLC / For Hire Vehicle Complaint: 947 casos; 0.0% encerrados em 72 horas.** A comparação direta mistura tipos de demanda e agências.
- Ajuste por agência e tipo, com referência formada somente por outros bairros: **MANHATTAN: diferença ajustada de -6.15 pontos percentuais em 60,364 casos comparáveis (99.7% de cobertura).** Use esse sinal para aprofundar a análise, não para atribuir causalidade.

## Proposta para a equipe operacional

1. Revisar com a agência responsável o fluxo do grupo de maior volume; separar fila de triagem, dependência de terceiros e data efetiva do serviço.
2. Investigar os grupos de menor taxa com amostras de casos e entrevistas; para reclamações formais, validar primeiro se 72 horas é uma janela operacional plausível. Segmentar horários e canais antes de propor mudança.
3. Acompanhar semanalmente taxa em 72 horas, volume, abertos há mais de 72 horas e a cobertura do ajuste. Validar impacto com comparação temporal e controles antes/depois de qualquer intervenção.

## Definições e limites

- **Encerrado em 72 horas:** `closed_date` entre criação e criação + 72 horas. Apenas casos criados há mais de 72 horas e sem fechamento impossível de verificar entram no denominador. Não é SLA oficial.
- `due_date` indica prazo para atualização da solicitação na fonte, não promessa de fechamento. Não foi usado como prazo de resolução.
- Tempo p90 considera apenas casos encerrados: pode parecer menor em grupos com muitos casos ainda abertos. O indicador principal inclui esses casos no denominador quando elegíveis.
- O ajuste usa, para cada agência e problema, a taxa observada em outros bairros, com pelo menos 30 casos; exige pelo menos 500 casos comparáveis e cobertura de 80%. Diferenças residuais podem refletir complexidade, registro e acesso ao canal.
- As solicitações dependem da propensão a reportar problemas; volume por bairro não mede incidência real, qualidade geral do serviço nem desigualdade sem dados adicionais.
- A base pública é atualizada; reexecuções posteriores podem mudar dados de fechamento do mesmo mês. O manifesto da extração registra data, contagem e hash da cópia local.

**Fonte:** https://data.cityofnewyork.us/Social-Services/311-Service-Requests-from-2020-to-Present/erm2-nwe9
