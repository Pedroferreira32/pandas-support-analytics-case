"""Carga mensal transacional e idempotente com SQL parametrizado."""
from __future__ import annotations

from contextlib import closing
from datetime import datetime
import json
from pathlib import Path
import sqlite3
from typing import Any

import pandas as pd

from .transform import RANKING_DTYPES

SQL_RECONCILIATION = (Path(__file__).resolve().parents[1] / "sql/reconciliar.sql").read_text(encoding="utf-8")
ROW_TYPES = {
    "linha_origem": "INTEGER NOT NULL", "protocolo_raw": "TEXT NOT NULL",
    "protocolo": "TEXT NOT NULL", "protocolo_chave": "TEXT NOT NULL",
    "cliente": "TEXT NOT NULL", "revenda": "TEXT NOT NULL", "atendente_raw": "TEXT NOT NULL",
    "atendente": "TEXT NOT NULL", "inicio_raw": "TEXT NOT NULL", "fim_raw": "TEXT NOT NULL",
    "setores": "TEXT NOT NULL", "transferencias": "TEXT NOT NULL", "avaliacao_raw": "TEXT NOT NULL",
    "inicio": "TEXT", "fim": "TEXT", "competencia_registro": "TEXT",
    "duracao_horas": "REAL", "tma_minutos": "REAL", "avaliacao": "REAL",
    "suspeito_automatico": "INTEGER NOT NULL CHECK (suspeito_automatico IN (0,1))",
    "protocolo_duplicado": "INTEGER NOT NULL CHECK (protocolo_duplicado IN (0,1))",
    "motivo_codigo": "TEXT",
}


class ReconciliationError(RuntimeError):
    """A transação não pode ser confirmada com dados divergentes."""


def initialize_schema(connection: sqlite3.Connection) -> None:
    connection.executescript("""
        CREATE TABLE IF NOT EXISTS execucoes (
          execucao_id TEXT PRIMARY KEY, competencia TEXT NOT NULL,
          origem TEXT NOT NULL, origem_sha256 TEXT NOT NULL, configuracao_json TEXT NOT NULL,
          criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS competencias (
          competencia TEXT PRIMARY KEY, execucao_id TEXT NOT NULL REFERENCES execucoes(execucao_id),
          total_extraido INTEGER NOT NULL CHECK (total_extraido >= 0)
        );
        CREATE TABLE IF NOT EXISTS etapas (
          execucao_id TEXT NOT NULL REFERENCES execucoes(execucao_id), ordem INTEGER NOT NULL,
          etapa TEXT NOT NULL, entrada INTEGER NOT NULL, saida INTEGER NOT NULL,
          excluidos INTEGER NOT NULL, unidade TEXT NOT NULL,
          PRIMARY KEY (execucao_id, ordem)
        );
    """)
    row_columns = ", ".join(f'"{name}" {dtype}' for name, dtype in ROW_TYPES.items())
    for table, checks in (
        ("validos", "CHECK (motivo_codigo IS NULL), UNIQUE (competencia, protocolo_chave)"),
        ("excluidos", "CHECK (motivo_codigo IS NOT NULL)"),
    ):
        connection.execute(f"""CREATE TABLE IF NOT EXISTS {table} (
          competencia TEXT NOT NULL REFERENCES competencias(competencia), {row_columns},
          PRIMARY KEY (competencia, linha_origem), {checks}
        )""")
    ranking_columns = ", ".join(
        f'"{name}" ' + ("TEXT" if dtype == "string" else "INTEGER" if dtype in {"int64", "bool"} else "REAL")
        for name, dtype in RANKING_DTYPES.items()
    )
    connection.execute(f"""CREATE TABLE IF NOT EXISTS ranking (
      competencia TEXT NOT NULL REFERENCES competencias(competencia), {ranking_columns},
      PRIMARY KEY (competencia, atendente), UNIQUE (competencia, posicao)
    )""")


def reconcile_connection(connection: sqlite3.Connection, competencia: str) -> dict[str, Any]:
    cursor = connection.execute(SQL_RECONCILIATION, {"competencia": competencia})
    row = cursor.fetchone()
    if row is None:
        raise ReconciliationError(f"Competência {competencia} ausente no banco.")
    return dict(zip([column[0] for column in cursor.description], row))


def reconcile(database: Path | str, competencia: str) -> dict[str, Any]:
    # mode=ro impede que uma consulta a um caminho incorreto crie um banco vazio.
    with closing(sqlite3.connect(Path(database).resolve().as_uri() + "?mode=ro", uri=True)) as connection:
        return reconcile_connection(connection, competencia)


def _sqlite_value(value: Any) -> Any:
    if pd.isna(value):
        return None
    if isinstance(value, (datetime, pd.Timestamp)):
        return value.isoformat()
    return value.item() if hasattr(value, "item") else value


def _insert_frame(connection: sqlite3.Connection, table: str, competencia: str, frame: pd.DataFrame, columns: list[str]) -> None:
    names = ["competencia", *columns]
    sql_columns = ", ".join(f'"{name}"' for name in names)
    placeholders = ", ".join("?" for _ in names)
    rows = ((competencia, *(_sqlite_value(value) for value in row))
            for row in frame[columns].itertuples(index=False, name=None))
    connection.executemany(f"INSERT INTO {table} ({sql_columns}) VALUES ({placeholders})", rows)


def load(database: Path | str, valid: pd.DataFrame, excluded: pd.DataFrame,
         ranking: pd.DataFrame, metadata: dict[str, Any], stages: list[dict[str, Any]]) -> dict[str, Any]:
    database = Path(database)
    database.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(database, isolation_level=None)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        initialize_schema(connection)
        connection.execute("BEGIN IMMEDIATE")
        try:
            connection.execute("""INSERT INTO execucoes
              (execucao_id, competencia, origem, origem_sha256, configuracao_json) VALUES (?, ?, ?, ?, ?)
              ON CONFLICT(execucao_id) DO NOTHING""", (
                metadata["execucao_id"], metadata["competencia"], metadata["origem"],
                metadata["origem_sha256"], json.dumps(metadata["configuracao"], ensure_ascii=False, sort_keys=True),
            ))
            connection.execute("""INSERT INTO competencias VALUES (?, ?, ?)
              ON CONFLICT(competencia) DO UPDATE SET execucao_id=excluded.execucao_id,
              total_extraido=excluded.total_extraido""",
                (metadata["competencia"], metadata["execucao_id"], metadata["total_extraido"]))
            for table, frame, columns in (
                ("validos", valid, list(ROW_TYPES)), ("excluidos", excluded, list(ROW_TYPES)),
                ("ranking", ranking, list(RANKING_DTYPES)),
            ):
                connection.execute(f"DELETE FROM {table} WHERE competencia = ?", (metadata["competencia"],))
                _insert_frame(connection, table, metadata["competencia"], frame, columns)
            connection.execute("DELETE FROM etapas WHERE execucao_id = ?", (metadata["execucao_id"],))
            connection.executemany("INSERT INTO etapas VALUES (?, ?, ?, ?, ?, ?, ?)", (
                (metadata["execucao_id"], index, stage["etapa"], stage["entrada"], stage["saida"], stage["excluidos"], stage["unidade"])
                for index, stage in enumerate(stages, start=1)
            ))
            report = reconcile_connection(connection, metadata["competencia"])
            if not report["reconciliado"]:
                raise ReconciliationError(f"Reconciliação SQL reprovada: {report}")
            connection.commit()
            return report
        except Exception:
            connection.rollback()
            raise
