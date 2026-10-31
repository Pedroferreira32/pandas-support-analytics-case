"""Orquestração explícita: extrair, validar, transformar e carregar."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import logging
from pathlib import Path
from typing import Any

import pandas as pd

from .config import PipelineConfig
from .extract import extract
from .load import load
from .transform import transform
from .validate import validate

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PipelineResult:
    valid: pd.DataFrame
    excluded: pd.DataFrame
    ranking: pd.DataFrame
    manifest: dict[str, Any]


def run_pipeline(source: Path | str, database: Path | str, config: PipelineConfig | None = None) -> PipelineResult:
    config = config or PipelineConfig()
    extracted = extract(source)
    checked = validate(extracted.frame, config)
    ranking = transform(checked.valid, config)
    stages = [
        {"etapa": "extract", "entrada": len(extracted.frame), "saida": len(extracted.frame), "excluidos": 0, "unidade": "atendimentos"},
        {"etapa": "validate", "entrada": len(extracted.frame), "saida": len(checked.valid), "excluidos": len(checked.excluded), "unidade": "atendimentos"},
        {"etapa": "transform", "entrada": len(checked.valid), "saida": len(ranking), "excluidos": 0, "unidade": "atendimentos -> atendentes"},
        {"etapa": "load", "entrada": len(extracted.frame) + len(ranking), "saida": len(extracted.frame) + len(ranking), "excluidos": 0, "unidade": "linhas: validos + excluidos + ranking"},
    ]
    for stage in stages[:3]:
        logger.info("%s | entrada=%s saida=%s excluidos=%s | %s",
                    stage["etapa"], stage["entrada"], stage["saida"], stage["excluidos"], stage["unidade"])
    fingerprint = json.dumps({"source": extracted.source_sha256, "config": config.to_dict()}, sort_keys=True)
    metadata = {
        "execucao_id": sha256(fingerprint.encode()).hexdigest(), "competencia": config.competencia,
        "origem": extracted.source_name, "origem_sha256": extracted.source_sha256,
        "configuracao": config.to_dict(), "total_extraido": len(extracted.frame),
    }
    reconciliation = load(database, checked.valid, checked.excluded, ranking, metadata, stages)
    logger.info("load | linhas persistidas=%s | reconciliado=%s", stages[-1]["saida"], bool(reconciliation["reconciliado"]))
    manifest = {
        **metadata, "etapas": stages, "regras": checked.rule_counts, "reconciliacao_sql": reconciliation,
        "avaliacoes_validas": int(checked.valid["avaliacao"].count()),
        "cobertura_avaliacao": float(checked.valid["avaliacao"].count() / len(checked.valid) * 100) if len(checked.valid) else 0.0,
    }
    return PipelineResult(checked.valid, checked.excluded, ranking, manifest)


def export_results(result: PipelineResult, output_dir: Path | str) -> None:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    for name, frame in (("validos", result.valid), ("excluidos", result.excluded), ("ranking", result.ranking)):
        frame.to_csv(output / f"{name}.csv", sep=";", index=False, encoding="utf-8-sig", float_format="%.10g", lineterminator="\n")
    (output / "manifesto.json").write_text(
        json.dumps(result.manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
    report = result.manifest["reconciliacao_sql"]
    lines = ["# Execução da pipeline ETL local", "", "Dados exclusivamente fictícios.", "",
             "| Etapa | Entrada | Saída | Excluídos | Unidade |", "|---|---:|---:|---:|---|"]
    lines.extend(f"| {s['etapa']} | {s['entrada']} | {s['saida']} | {s['excluidos']} | {s['unidade']} |" for s in result.manifest["etapas"])
    lines.extend(["", f"Reconciliação SQL: **{report['total_extraido']} = {report['validos']} válidos + {report['excluidos']} excluídos**.",
                  f"Avaliações válidas: **{result.manifest['avaliacoes_validas']}**. Cobertura: **{result.manifest['cobertura_avaliacao']:.2f}%**.",
                  f"Controles SQL aprovados: **{bool(report['reconciliado'])}**.", "",
                  "A saída de transform está no grão de atendente. A carga conta linhas das três tabelas, sem contar os metadados.", "",
                  "A consulta SQL confere contagens, exclusividade das linhas de origem, protocolos válidos únicos e contagens por atendente; não prova qualidade operacional.", ""])
    (output / "RESUMO.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")
