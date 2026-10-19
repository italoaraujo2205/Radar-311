"""Comandos para reproduzir o estudo e atualizar seus resultados."""

import argparse
import json
from datetime import date, datetime
from pathlib import Path

from service_ops.model import build, export
from service_ops.report import generate
from service_ops.source import download


def main() -> None:
    parser = argparse.ArgumentParser(description="NYC 311: analise operacional")
    parser.add_argument("action", choices=("download", "build", "report", "all"))
    parser.add_argument("--start", type=date.fromisoformat, default=date(2025, 1, 1))
    parser.add_argument("--end", type=date.fromisoformat, default=date(2025, 2, 1))
    parser.add_argument("--as-of", type=datetime.fromisoformat, default=datetime.now().replace(microsecond=0))
    parser.add_argument("--page-size", type=int, default=20000)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = args.root.resolve()
    raw = root / "data" / "raw" / f"nyc311_{args.start}_{args.end}.jsonl.gz"
    database = root / "data" / "service_ops.duckdb"
    if args.action in ("download", "all"):
        print(download(args.start, args.end, raw, args.page_size))
    if args.action in ("build", "all"):
        quality = build(raw, database, args.as_of)
        export(database, root / "outputs", quality)
        manifest = json.loads(raw.with_suffix(".manifest.json").read_text(encoding="utf-8"))
        (root / "reports").mkdir(parents=True, exist_ok=True)
        (root / "reports" / "run_manifest.json").write_text(
            json.dumps({"extraction": manifest, "quality": quality}, indent=2) + "\n",
            encoding="utf-8",
        )
        print(quality)
    if args.action in ("report", "all"):
        generate(database, root / "reports" / "decision_memo.md", root / "docs" / "index.html")
        print("Painel em docs/index.html; memorando em reports/decision_memo.md")


if __name__ == "__main__":
    main()
