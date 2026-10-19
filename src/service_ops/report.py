"""Memorando de decisoes e painel HTML gerados a partir do mesmo banco."""

from __future__ import annotations

import json
from pathlib import Path

import duckdb


def _records(con: duckdb.DuckDBPyConnection, query: str) -> list[dict]:
    result = con.execute(query)
    cols = [col[0] for col in result.description]
    return [dict(zip(cols, row)) for row in result.fetchall()]


def generate(database: Path, destination: Path, docs: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    docs.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(database), read_only=True)
    try:
        kpi = _records(con, """SELECT COUNT(*) AS total, SUM(eligible_72h) AS eligible,
              SUM(CASE WHEN eligible_72h = 1 THEN closed_72h ELSE 0 END) AS closed,
              SUM(open_after_72h) AS open_aged, MIN(CAST(created_at AS DATE)) AS start_day,
              MAX(CAST(created_at AS DATE)) AS end_day FROM fact_request""")[0]
        daily = _records(con, """SELECT CAST(created_day AS VARCHAR) AS day,
              SUM(requests) AS requests, SUM(eligible_72h) AS eligible,
              SUM(closed_72h) AS closed FROM mart_daily GROUP BY 1 ORDER BY 1""")
        problems = _records(con, """SELECT borough, agency, problem, eligible_72h,
              closed_72h, open_after_72h, pct_closed_72h, p90_closed_hours
              FROM mart_borough_problem WHERE eligible_72h >= 300 ORDER BY eligible_72h DESC""")
        mix = _records(con, "SELECT * FROM mart_case_mix ORDER BY adjusted_gap_pp")
        top = con.execute("""SELECT agency, problem, SUM(eligible_72h) AS n,
              SUM(closed_72h) AS closed FROM mart_borough_problem
              GROUP BY 1, 2 HAVING SUM(eligible_72h) >= 1000
              ORDER BY SUM(eligible_72h - closed_72h) DESC LIMIT 5""").fetchall()
        poorly = [p for p in problems if p["pct_closed_72h"] is not None]
        poorly.sort(key=lambda p: (p["pct_closed_72h"], -p["eligible_72h"]))
        rate = 100 * kpi["closed"] / kpi["eligible"] if kpi["eligible"] else 0
        raw = con.execute("SELECT COUNT(*) FROM raw_requests").fetchone()[0]
        rejected = con.execute("SELECT COUNT(*) FROM rejected_requests").fetchone()[0]
        unknown_close = con.execute("SELECT COUNT(*) FROM fact_request WHERE status='CLOSED' AND closed_at IS NULL").fetchone()[0]
    finally:
        con.close()

    lead = top[0] if top else None
    slow = poorly[0] if poorly else None
    priority = (
        f"{lead[0]} / {lead[1]}: {lead[2]:,} casos elegíveis; "
        f"{lead[2]-lead[3]:,} não encerrados em 72 horas."
        if lead else "Não há grupo com volume suficiente para priorização."
    )
    diagnostic = (
        f"{slow['borough']} / {slow['agency']} / {slow['problem']}: "
        f"{slow['eligible_72h']:,} casos; {slow['pct_closed_72h']}% encerrados em 72 horas."
        if slow else "Não há grupo comparável com volume suficiente."
    )
    gap = (
        f"{mix[0]['borough']}: diferença ajustada de {mix[0]['adjusted_gap_pp']:+.2f} pontos "
        f"percentuais em {mix[0]['comparable']:,} casos comparáveis ({mix[0]['coverage_pct']}% de cobertura)."
        if mix else "Nenhum bairro atingiu os critérios de cobertura do ajuste."
    )
    memo = f"""# Onde investigar a demora de atendimento no NYC 311

**Recorte:** solicitações criadas entre {kpi['start_day']} e {kpi['end_day']}, extraídas da API pública do NYC Open Data. **Pergunta:** onde concentrar uma investigação operacional para reduzir solicitações que não foram encerradas nas primeiras 72 horas?

## O que os dados mostram

- {raw:,} linhas recebidas; {kpi['total']:,} solicitações válidas no recorte; {rejected:,} rejeitadas por chave ou data inválida.
- {kpi['eligible']:,} solicitações têm janela de observação completa e data de fechamento avaliável; {rate:.1f}% foram encerradas em até 72 horas. {kpi['open_aged']:,} constam com status diferente de `CLOSED` e sem data de fechamento.
- {unknown_close:,} solicitações constam como `CLOSED`, mas sem data de fechamento: permanecem no fato e ficam fora da taxa de 72 horas porque não é possível verificar o prazo.
- Maior volume de casos fora da janela: **{priority}** Volume é critério de priorização, não prova de ineficiência.
- Grupo com menor taxa entre os de pelo menos 300 casos: **{diagnostic}** A comparação direta mistura tipos de demanda e agências.
- Ajuste por agência e tipo, com referência formada somente por outros bairros: **{gap}** Use esse sinal para aprofundar a análise, não para atribuir causalidade.

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
"""
    destination.write_text(memo, encoding="utf-8")

    payload = json.dumps({"kpi": {**{k: str(v) for k, v in kpi.items()}, "unknown_close": unknown_close}, "daily": daily,
                          "problems": problems, "mix": mix}, ensure_ascii=False, default=str)
    # Os nomes de problemas vêm da fonte externa e não podem fechar o script HTML.
    payload = payload.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    template = (Path(__file__).resolve().parents[2] / "docs" / "template.html").read_text(encoding="utf-8")
    docs.write_text(template.replace("/*DATA_PAYLOAD*/", payload), encoding="utf-8")
