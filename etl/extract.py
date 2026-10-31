"""Extração do contrato CSV da amostra, sem inferência destrutiva de tipos."""
from __future__ import annotations

import csv
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO, StringIO
from pathlib import Path

import pandas as pd

COLUMNS = {
    "Protocolo": "protocolo",
    "Contact ID": "cliente",
    "Revenda": "revenda",
    "User ID": "atendente",
    "Iniciado": "inicio_raw",
    "Fim": "fim_raw",
    "Setores": "setores",
    "Setores Transfers": "transferencias",
    "Rating": "avaliacao_raw",
}


class SchemaError(ValueError):
    """Arquivo incompatível com o contrato explícito deste case."""


def validate_schema(headers: list[str]) -> None:
    if len(headers) != len(set(headers)):
        raise SchemaError("Schema inválido: cabeçalhos duplicados.")
    missing = sorted(set(COLUMNS) - set(headers))
    extra = sorted(set(headers) - set(COLUMNS))
    if missing or extra:
        raise SchemaError(f"Schema inválido. Ausentes: {missing}; inesperados: {extra}.")


@dataclass(frozen=True)
class Extraction:
    frame: pd.DataFrame
    source_name: str
    source_sha256: str


def extract(source: Path | str) -> Extraction:
    source = Path(source)
    if source.suffix.lower() != ".csv":
        raise SchemaError("Esta pipeline recebe CSV UTF-8 delimitado por ponto e vírgula.")
    content = source.read_bytes()
    # A pré-checagem evita que o parser renomeie cabeçalhos ou complete linhas curtas.
    reader = csv.reader(StringIO(content.decode("utf-8-sig")), delimiter=";", strict=True)
    try:
        headers = next(reader)
        validate_schema(headers)
        count = 0
        for record_number, row in enumerate(reader, start=2):
            if len(row) != len(headers):
                raise SchemaError(f"Registro {record_number}: esperado {len(headers)} campos, recebido {len(row)}.")
            count += 1
    except StopIteration as exc:
        raise SchemaError("O arquivo está vazio.") from exc
    except csv.Error as exc:
        raise SchemaError(f"CSV malformado: {exc}") from exc
    if not count:
        raise SchemaError("O arquivo contém cabeçalho, mas nenhum registro.")
    frame = pd.read_csv(
        BytesIO(content), sep=";", encoding="utf-8-sig", dtype="string",
        keep_default_na=False, skip_blank_lines=False,
    ).rename(columns=COLUMNS)
    frame.insert(0, "linha_origem", range(2, len(frame) + 2))
    return Extraction(frame, source.name, sha256(content).hexdigest())
