"""Modelo dimensional, indicadores e verificacoes de qualidade."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import duckdb

SQL_PATH = Path(__file__).resolve().parents[2] / "sql" / "01_model.sql"


def build(raw_file: Path, database: Path, as_of: datetime) -> dict:
    if not raw_file.is_file():
        raise FileNotFoundError(raw_file)
    database.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(database))
    try:
        schema = """{unique_key:'VARCHAR',created_date:'VARCHAR',closed_date:'VARCHAR',
            agency:'VARCHAR',complaint_type:'VARCHAR',descriptor:'VARCHAR',
            status:'VARCHAR',borough:'VARCHAR',incident_zip:'VARCHAR',
            due_date:'VARCHAR',open_data_channel_type:'VARCHAR'}"""
        con.execute(f"CREATE OR REPLACE TABLE raw_requests AS SELECT * FROM read_json(?, format='newline_delimited', columns={schema})", [str(raw_file)])
        raw_count = con.execute("SELECT COUNT(*) FROM raw_requests").fetchone()[0]
        if not raw_count:
            raise ValueError("Fonte vazia")
        con.execute("SET VARIABLE as_of = ?", [as_of.isoformat(sep=" ")])
        # O arquivo SQL e parte versionada da definicao de cada indicador.
        for statement in SQL_PATH.read_text(encoding="utf-8").split(";"):
            if statement.strip():
                con.execute(statement.replace("$as_of", "getvariable('as_of')"))
        rejected = con.execute("SELECT COUNT(*) FROM rejected_requests").fetchone()[0]
        duplicates = con.execute("SELECT COUNT(*) FROM raw_requests").fetchone()[0] - con.execute("SELECT COUNT(*) FROM stg_requests").fetchone()[0]
        accepted = con.execute("SELECT COUNT(*) FROM fact_request").fetchone()[0]
        unknown_borough = con.execute("SELECT COUNT(*) FROM stg_requests WHERE borough IN ('UNKNOWN', 'UNSPECIFIED') AND rejection_reason IS NULL").fetchone()[0]
        closed_without_timestamp = con.execute("SELECT COUNT(*) FROM fact_request WHERE status='CLOSED' AND closed_at IS NULL").fetchone()[0]
        future = con.execute("SELECT COUNT(*) FROM stg_requests WHERE created_at > CAST(getvariable('as_of') AS TIMESTAMP) AND rejection_reason IS NULL").fetchone()[0]
        if accepted + rejected + duplicates + future != raw_count:
            raise AssertionError("A reconciliacao entre origem, rejeicoes e fato falhou")
        if rejected > raw_count * 0.01:
            raise ValueError(f"{rejected} linhas rejeitadas ({rejected/raw_count:.1%}); limite de 1%")
        if duplicates:
            raise ValueError(f"{duplicates} chaves duplicadas na fonte; revise a extracao")
        for table in ("mart_daily", "mart_borough_problem", "mart_case_mix"):
            if con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0:
                raise ValueError(f"Sem registros no indicador {table}")
        return {
            "raw_rows": raw_count, "accepted_rows": accepted, "rejected_rows": rejected,
            "duplicate_rows": duplicates, "future_rows": future,
            "unknown_borough_rows": unknown_borough,
            "closed_without_timestamp_rows": closed_without_timestamp,
            "as_of": as_of.isoformat(sep=" "),
        }
    finally:
        con.close()


def export(database: Path, output: Path, quality: dict) -> None:
    output.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(database), read_only=True)
    try:
        for table in ("mart_daily", "mart_borough_problem", "mart_case_mix", "dim_problem", "dim_borough"):
            con.execute(f"COPY (SELECT * FROM {table}) TO ? (HEADER, DELIMITER ',')", [str(output / f"{table}.csv")])
        (output / "quality.json").write_text(json.dumps(quality, indent=2) + "\n", encoding="utf-8")
    finally:
        con.close()
