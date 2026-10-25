"""Confere a integridade e executa os testes originais usando a biblioteca padrão."""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
from pathlib import Path
import platform
import runpy
import sys
import unittest

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> None:
    manifest = json.loads((ROOT / 'docs/origem_codigo.json').read_text(encoding='utf-8'))
    for entry in manifest['source_files']:
        data = (ROOT / entry['path']).read_bytes()
        blob_sha = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        if blob_sha != entry['git_blob_sha'] or hashlib.sha256(data).hexdigest() != entry['sha256']:
            raise AssertionError(f"Arquivo diferente da origem: {entry['path']}")

    functions = runpy.run_path(str(ROOT / 'backend/tests/test_pipeline.py'))
    cases = [(name, fn) for name, fn in functions.items() if name.startswith('test_') and callable(fn)]
    suite = unittest.TestSuite(unittest.FunctionTestCase(fn, description=name) for name, fn in cases)
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    log = stream.getvalue()
    print(log, end='')
    if not result.wasSuccessful() or result.testsRun != 6:
        raise SystemExit(1)

    # Verifica também o cenário sintético pela execução de ponta a ponta do recorte.
    demo_output = io.StringIO()
    with contextlib.redirect_stdout(demo_output):
        runpy.run_path(str(ROOT / 'scripts/demo_pandas.py'), run_name='__main__')

    report = [
        '# Verificação do recorte pandas', '',
        'Data de preparação deste material: 25/10/2026.', '',
        f'- Origem: {manifest["repository"]}',
        f'- Commit: {manifest["commit"]}',
        f'- Python desta execução: {platform.python_version()}',
        f'- pandas desta execução: {pd.__version__}',
        f'- Arquivos de origem conferidos por hashes Git e SHA-256: {len(manifest["source_files"])}.',
        f'- Testes originais de pipeline executados: {result.testsRun}.',
        '- Resultado: todos aprovados.',
        '- Amostra sintética: reconciliação, oito motivos, avaliação inválida, cobertura, transferência e mês de início conferidos.',
        '', '## Testes originais executados', '',
    ]
    report.extend(f'- {name}' for name, _ in cases)
    report.extend(['', 'Os testes foram executados com unittest.FunctionTestCase sobre as funções originais. API, banco, frontend e implantação estão fora desta verificação.', ''])
    (ROOT / 'resultados/VALIDACAO.md').write_text('\n'.join(report), encoding='utf-8')
    print(f"Integridade: {len(manifest['source_files'])} arquivos originais conferidos.")
    print('Amostra sintética: aprovada.')


if __name__ == '__main__':
    main()
