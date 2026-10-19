import gzip
import json
from datetime import date, datetime
from pathlib import Path

import duckdb
import pytest

from service_ops.model import build, export
from service_ops.report import generate
from service_ops.source import download


def row(key, borough, closed="2025-01-01T12:00:00.000", created="2025-01-01T00:00:00.000"):
    return {"unique_key": str(key), "created_date": created, "closed_date": closed,
            "agency": "NYPD", "complaint_type": "Illegal Parking", "descriptor": "Test",
            "borough": borough, "status": "Closed" if closed else "Open", "open_data_channel_type": "ONLINE"}


def test_censored_window_and_case_mix(tmp_path):
    raw = tmp_path / "sample.jsonl.gz"
    rows = [row(i, "BRONX", None if i % 10 == 0 else "2025-01-01T12:00:00.000") for i in range(600)]
    rows += [row(i, "QUEENS", None if i % 2 == 0 else "2025-01-01T12:00:00.000") for i in range(600, 1200)]
    rows += [row(1200, "BRONX", created="2025-01-04T23:00:00.000", closed=None)]
    rows += [row(1201, "BRONX", created="2025-01-01T12:00:00.000", closed="2025-01-01T10:00:00.000")]
    uncertain = row(1202, "BRONX", closed=None)
    uncertain["status"] = "Closed"
    rows += [uncertain]
    with gzip.open(raw, "wt", encoding="utf-8") as target:
        for item in rows:
            target.write(json.dumps(item) + "\n")
    db = tmp_path / "case.duckdb"
    quality = build(raw, db, datetime(2025, 1, 5, 0, 0))
    assert (quality["raw_rows"], quality["accepted_rows"], quality["rejected_rows"], quality["closed_without_timestamp_rows"]) == (1203, 1202, 1, 1)
    with duckdb.connect(str(db), read_only=True) as con:
        bronx = con.execute("""SELECT eligible_72h, closed_72h, open_after_72h
            FROM mart_borough_problem WHERE borough='BRONX'""").fetchone()
        assert bronx == (600, 540, 60)
        gaps = dict(con.execute("SELECT borough, adjusted_gap_pp FROM mart_case_mix").fetchall())
        assert gaps["BRONX"] == 40.0 and gaps["QUEENS"] == -40.0
    export(db, tmp_path / "out", quality)
    generate(db, tmp_path / "memo.md", tmp_path / "docs" / "index.html")
    assert "72 horas" in (tmp_path / "memo.md").read_text()
    assert 'const d={"kpi"' in (tmp_path / "docs" / "index.html").read_text()


def test_download_rejects_changed_pagination(monkeypatch, tmp_path):
    responses = [[{"count": "3"}], [row("1", "BRONX"), row("2", "BRONX")],
                 [row("2", "BRONX")]]
    monkeypatch.setattr("service_ops.source.fetch_json", lambda *args, **kwargs: responses.pop(0))
    dest = tmp_path / "data.jsonl.gz"
    with pytest.raises(RuntimeError, match="repetida"):
        download(date(2025, 1, 1), date(2025, 1, 2), dest, page_size=2)
    assert not dest.exists() and not dest.with_suffix(dest.suffix + ".part").exists()
