"""Demonstração com dados sintéticos; executa a função original do projeto."""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.pipeline.engine import process_upload


EXPECTED_REASONS = {
    'FORA_SUPORTE', 'SEM_ATENDENTE', 'ATENDENTE_EXCLUIDO', 'DATA_INVALIDA',
    'SEM_FINALIZACAO', 'DURACAO_NEGATIVA', 'ACIMA_H', 'PERIODO',
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    source = ROOT / 'dados/atendimentos_ficticios.csv'
    result = process_upload(source.read_bytes(), source.name, '08/2026', 'Diego Demo')
    stats = result['estatisticas']
    valid = {row['protocolo']: row for row in result['validos']}
    excluded = {row['protocolo']: row for row in result['excluidos']}
    reasons = Counter(row['motivoCodigo'] for row in result['excluidos'])

    require(stats['TOTAL'] == 18, 'A amostra deve ter 18 registros.')
    require(stats['VALIDOS'] == 10 and stats['EXCLUIDOS'] == 8, 'A amostra deve gerar 10 válidos e 8 exclusões.')
    require(stats['TOTAL'] == stats['VALIDOS'] + stats['EXCLUIDOS'], 'A reconciliação não fechou.')
    require(set(reasons) == EXPECTED_REASONS and all(n == 1 for n in reasons.values()), 'Os oito motivos devem aparecer uma vez cada.')
    require(excluded['E001']['motivoCodigo'] == 'FORA_SUPORTE', 'Deve prevalecer o primeiro motivo de exclusão.')
    require(valid['V004']['fim'].startswith('2026-09-01') and result['competencia'] == '2026-08', 'A competência deve considerar o início.')
    require('V006' in valid, 'A transferência para Suporte deve ser aceita.')
    require(valid['V007']['avaliacao'] is None, 'Nota 8 deve ser desconsiderada na escala 0–5.')
    require(stats['AVALIACOES_VALIDAS'] == 9, 'Devem restar nove avaliações válidas.')
    require(abs(result['operacao']['coberturaAvaliacao'] - 90.0) < 1e-9, 'A cobertura deve ser 90%.')

    output = ROOT / 'resultados'
    output.mkdir(exist_ok=True)
    # O timestamp é metadado da execução; removê-lo torna a saída didática estável.
    result.pop('processadoEm', None)
    (output / 'resultado.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    for field, filename in [('ranking', 'ranking.csv'), ('validos', 'validos.csv'), ('excluidos', 'excluidos.csv')]:
        pd.DataFrame(result[field]).to_csv(output / filename, sep=';', index=False, encoding='utf-8-sig')

    summary = [
        '# Resultado da demonstração com dados fictícios', '',
        '| Controle | Resultado |', '|---|---:|',
        f"| Total importado | {stats['TOTAL']} |",
        f"| Válidos | {stats['VALIDOS']} |",
        f"| Excluídos | {stats['EXCLUIDOS']} |",
        f"| Avaliações válidas | {stats['AVALIACOES_VALIDAS']} |",
        f"| Cobertura de avaliação | {result['operacao']['coberturaAvaliacao']:.0f}% |",
        '', 'Reconciliação conferida: **18 = 10 + 8**.', '',
        '## Exclusões', '', '| Motivo | Quantidade |', '|---|---:|',
    ]
    summary.extend(f'| {code} | {count} |' for code, count in sorted(reasons.items()))
    summary.extend(['', '## Indicadores por atendente fictício', '',
        '| Atendente | Atendimentos | TMA médio (min) | Mediana (min) | P90 (min) | Avaliação média | Cobertura |',
        '|---|---:|---:|---:|---:|---:|---:|'])
    for row in result['ranking']:
        summary.append(f"| {row['atendente']} | {row['atendimentos']} | {row['tmaMedioMin']:.2f} | {row['tmaMedianoMin']:.2f} | {row['tmaP90Min']:.2f} | {row['avaliacaoMedia']:.2f} | {row['coberturaAvaliacao']:.2f}% |")
    summary.extend(['', 'Números exclusivamente sintéticos. Não representam o desempenho real da equipe.', '',
        'TMA: tempo médio de atendimento. P90: percentil 90 das durações. Cobertura: avaliações válidas / atendimentos válidos.', ''])
    (output / 'RESUMO.md').write_text('\n'.join(summary), encoding='utf-8')
    print('Reconciliação: 18 = 10 válidos + 8 excluídos.')
    print('Avaliações: 9 válidas; cobertura de 90%.')
    print('Verificações da amostra: aprovadas.')
    columns = ['atendente', 'atendimentos', 'tmaMedioMin', 'tmaP90Min', 'avaliacaoMedia', 'coberturaAvaliacao']
    print(pd.DataFrame(result['ranking'])[columns].to_string(index=False, float_format=lambda value: f'{value:.2f}'))
    print(f'Resultados: {output}')


if __name__ == '__main__':
    main()
