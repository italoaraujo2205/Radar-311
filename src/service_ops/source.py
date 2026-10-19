"""Extracao paginada da API publica NYC Open Data."""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

URL = "https://data.cityofnewyork.us/resource/erm2-nwe9.json"
FIELDS = (
    "unique_key,created_date,closed_date,agency,complaint_type,descriptor,"
    "status,borough,incident_zip,due_date,open_data_channel_type"
)


def fetch_json(params: dict[str, str | int], retries: int = 4) -> list[dict]:
    url = URL + "?" + urllib.parse.urlencode(params)
    for attempt in range(retries):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "ServiceOpsPortfolio/0.1"})
            with urllib.request.urlopen(request, timeout=180) as response:
                return json.load(response)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            if isinstance(exc, urllib.error.HTTPError) and exc.code not in (429, 500, 502, 503, 504):
                raise
            if attempt == retries - 1:
                raise RuntimeError(f"Falha ao consultar NYC Open Data: {exc}") from exc
            time.sleep(2**attempt)
    raise AssertionError("Tentativas esgotadas")


def download(start: date, end: date, target: Path, page_size: int = 20000) -> dict:
    """Baixa todo o intervalo [start, end); falha se houver pagina faltando."""
    if end <= start or page_size < 1 or page_size > 50000:
        raise ValueError("Intervalo ou tamanho de pagina invalido")
    target.parent.mkdir(parents=True, exist_ok=True)
    where = f"created_date >= '{start}T00:00:00' AND created_date < '{end}T00:00:00'"
    expected = int(fetch_json({"$select": "count(*)", "$where": where})[0]["count"])
    temp = target.with_suffix(target.suffix + ".part")
    digest = hashlib.sha256()
    seen: set[str] = set()
    count = 0
    try:
        with gzip.open(temp, "wt", encoding="utf-8", newline="\n") as output:
            while count < expected:
                rows = fetch_json({
                    "$select": FIELDS, "$where": where, "$order": "unique_key ASC",
                    "$limit": min(page_size, expected - count), "$offset": count,
                })
                if not rows:
                    raise RuntimeError(f"Pagina vazia apos {count} de {expected} registros")
                for row in rows:
                    key = row.get("unique_key")
                    if not key or key in seen:
                        raise RuntimeError(f"Chave ausente ou repetida: {key!r}; fonte mudou durante a extracao?")
                    seen.add(key)
                    line = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
                    digest.update(line.encode("utf-8"))
                    output.write(line)
                count += len(rows)
                print(f"Baixados {count:,}/{expected:,}", flush=True)
        if count != expected:
            raise RuntimeError(f"Esperados {expected} registros; recebidos {count}")
        os.replace(temp, target)
    except BaseException:
        temp.unlink(missing_ok=True)
        raise
    manifest = {
        "source": URL, "start_inclusive": start.isoformat(), "end_exclusive": end.isoformat(),
        "extracted_at_utc": datetime.now(timezone.utc).isoformat(),
        "rows": count, "sha256_jsonl_uncompressed": digest.hexdigest(),
        "raw_file": target.name,
    }
    target.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest
