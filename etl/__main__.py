"""CLI: python -m etl --help."""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import sqlite3
import sys

from .config import PipelineConfig
from .load import ReconciliationError, reconcile
from .pipeline import export_results, run_pipeline

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="ETL local com pandas, SQLite e reconciliação SQL.")
    parser.add_argument("--source", type=Path, default=ROOT / "dados/atendimentos_ficticios.csv")
    parser.add_argument("--database", type=Path, default=ROOT / "resultados/etl/suporte.sqlite")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "resultados/etl")
    parser.add_argument("--competencia", default="2026-08")
    parser.add_argument("--exclude-attendant", action="append", help="Nome parcial a excluir; repetível. Padrão da amostra: Diego Demo.")
    parser.add_argument("--reconcile-only", action="store_true", help="Consulta o banco existente em modo somente leitura.")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        config = PipelineConfig(
            competencia=args.competencia,
            excluded_attendants=tuple(args.exclude_attendant) if args.exclude_attendant is not None else ("Diego Demo",),
        )
        if args.reconcile_only:
            report = reconcile(args.database, config.competencia)
        else:
            result = run_pipeline(args.source, args.database, config)
            export_results(result, args.output_dir)
            report = result.manifest["reconciliacao_sql"]
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["reconciliado"] else 1
    except (OSError, UnicodeError, ValueError, sqlite3.Error, ReconciliationError) as exc:
        print(f"Falha: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
