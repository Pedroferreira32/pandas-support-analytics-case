"""Executa testes de contrato e produz evidências das duas amostras fictícias."""
from __future__ import annotations

from importlib.metadata import version
import io
from pathlib import Path
import platform
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from etl import run_pipeline
from etl.pipeline import export_results


def main() -> None:
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    print(stream.getvalue(), end="")
    if not result.wasSuccessful() or not result.testsRun:
        raise SystemExit(1)
    reports = []
    for source, folder in (("atendimentos_ficticios.csv", "etl"), ("cenarios_qualidade.csv", "qualidade")):
        output = ROOT / "resultados" / folder
        run = run_pipeline(ROOT / "dados" / source, output / "suporte.sqlite")
        export_results(run, output)
        reports.append((source, run.manifest))
    lines = ["# Validação da pipeline ETL local", "",
             f"- Python: {platform.python_version()}.",
             f"- pandas: {version('pandas')}; NumPy: {version('numpy')}; xlrd: {version('xlrd')}.",
             f"- Testes novos executados e aprovados: **{result.testsRun}**.",
             "- Os seis testes e os hashes dos oito arquivos originais são conferidos separadamente por `verificar_codigo.py`.", "",
             "| Amostra fictícia | Entrada | Válidos | Excluídos | Avaliações | Cobertura | SQL aprovado |",
             "|---|---:|---:|---:|---:|---:|---|"]
    for source, manifest in reports:
        report = manifest["reconciliacao_sql"]
        lines.append(f"| {source} | {report['total_extraido']} | {report['validos']} | {report['excluidos']} | {report['avaliacoes']} | {manifest['cobertura_avaliacao']:.0f}% | {bool(report['reconciliado'])} |")
    lines.extend(["", "## Contratos verificados", "",
        "- Equivalência dos 18 campos do ranking com o motor original na amostra de referência, com tolerância numérica de 1e-10.",
        "- Schema, CSV malformado, protocolos em branco e quarentena de todas as cópias duplicadas na mesma competência.",
        "- Nota inválida, cobertura, transferência de setor, competência inicial, horários e regras históricas.",
        "- Top 3, desempate, ausência de avaliações, duração zero e base sem atendimentos válidos.",
        "- Carga idempotente, substituição mensal, preservação de outra competência e rollback de dados e metadados.",
        "- Reconciliação SQL, divergência inserida no ranking, CLI e exportação reproduzível.", "",
        "Este relatório registra a execução local que o gerou. A execução remota de CI é comprovada pelos runs do GitHub Actions.", ""])
    (ROOT / "resultados/VALIDACAO_ETL.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Pipeline modular: {result.testsRun} testes aprovados; duas amostras carregadas e reconciliadas no SQLite.")


if __name__ == "__main__":
    main()
