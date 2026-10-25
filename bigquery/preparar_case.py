"""Gera um case GoogleSQL a partir da amostra do projeto, sem acessar a nuvem.

Os resultados de referência são calculados pelo motor Python/pandas original.
Este script não executa SQL nem produz evidência de execução no BigQuery.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import sys
import textwrap

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / 'bigquery'
sys.path.insert(0, str(ROOT))
from backend.app.pipeline.engine import process_upload

T = chr(96)
PROJECT_TOKEN = '__PROJECT_ID__'
DATASET = f'{PROJECT_TOKEN}.support_analytics_portfolio'
MARKER = 'portfolio_bigquery_case_v1'
FIELD_MAP = [
    ('protocolo', 'Protocolo'), ('cliente', 'Contact ID'), ('revenda', 'Revenda'),
    ('atendente', 'User ID'), ('inicio_raw', 'Iniciado'), ('fim_raw', 'Fim'),
    ('setores', 'Setores'), ('transferencias', 'Setores Transfers'), ('avaliacao_raw', 'Rating'),
]


def sql_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def source_select(rows: list[dict[str, str]]) -> str:
    records = []
    for line_number, row in enumerate(rows, start=2):
        fields = [f'{line_number} AS linha_origem']
        fields.extend(f'{sql_string(row[source])} AS {field}' for field, source in FIELD_MAP)
        records.append('  STRUCT(' + ', '.join(fields) + ')')
    return 'SELECT * FROM UNNEST([\n' + ',\n'.join(records) + '\n])'


def transform_ctes(source: str) -> str:
    return textwrap.dedent('''\
    raw AS (
    __SOURCE__
    ),
    tipado AS (
      SELECT
        *,
        SAFE.PARSE_DATETIME('%d/%m/%Y %H:%M', NULLIF(TRIM(inicio_raw), '')) AS inicio_dt,
        SAFE.PARSE_DATETIME('%d/%m/%Y %H:%M', NULLIF(TRIM(fim_raw), '')) AS fim_dt,
        SAFE_CAST(REPLACE(NULLIF(TRIM(avaliacao_raw), ''), ',', '.') AS FLOAT64) AS avaliacao_num,
        REGEXP_REPLACE(UPPER(NORMALIZE(TRIM(atendente), NFD)), r'\\pM', '') AS atendente_normalizado
      FROM raw
    ),
    preparado AS (
      SELECT
        *,
        DATETIME_DIFF(fim_dt, inicio_dt, SECOND) / 3600.0 AS duracao_horas,
        IF(avaliacao_num BETWEEN 0 AND 5, avaliacao_num, NULL) AS avaliacao_valida,
        DATE(inicio_dt) AS data_inicio,
        DATE_TRUNC(DATE(inicio_dt), MONTH) AS competencia
      FROM tipado
    ),
    classificados AS (
      SELECT
        *,
        CASE
          WHEN NOT (
            STRPOS(UPPER(setores), 'SUPORTE') > 0
            OR STRPOS(UPPER(transferencias), 'SUPORTE') > 0
          ) THEN 'FORA_SUPORTE'
          WHEN atendente_normalizado IN (
            '', '-', 'NAN', 'NAT', 'NONE', 'NULL', 'PENDENTE',
            'SEM ATENDENTE', 'NAO INFORMADO'
          ) THEN 'SEM_ATENDENTE'
          WHEN STRPOS(atendente_normalizado, 'DIEGO DEMO') > 0 THEN 'ATENDENTE_EXCLUIDO'
          WHEN inicio_dt IS NULL THEN 'DATA_INVALIDA'
          WHEN fim_dt IS NULL THEN 'SEM_FINALIZACAO'
          WHEN duracao_horas < 0 THEN 'DURACAO_NEGATIVA'
          WHEN duracao_horas > 9 THEN 'ACIMA_H'
          WHEN EXTRACT(DAYOFWEEK FROM inicio_dt) = 1
            OR TIME(inicio_dt) < TIME '08:00:00'
            OR TIME(inicio_dt) >= TIME '20:00:00' THEN 'PERIODO'
          ELSE NULL
        END AS motivo_codigo
      FROM preparado
    )''').replace('__SOURCE__', textwrap.indent(source, '  '))


def metric_ctes(source: str) -> str:
    return textwrap.dedent('''\
    validos AS (
      SELECT *
      FROM __SOURCE__
      WHERE motivo_codigo IS NULL
        AND data_inicio >= DATE '2026-08-01'
        AND data_inicio < DATE '2026-09-01'
    ),
    percentis AS (
      SELECT
        *,
        PERCENTILE_CONT(duracao_horas * 60, 0.5) OVER (
          PARTITION BY competencia, atendente
        ) AS mediana_min,
        PERCENTILE_CONT(duracao_horas * 60, 0.9) OVER (
          PARTITION BY competencia, atendente
        ) AS p90_min
      FROM validos
    ),
    medias AS (
      SELECT
        competencia, atendente,
        COUNT(*) AS atendimentos,
        SUM(duracao_horas) AS horas_total,
        AVG(duracao_horas * 60) AS tma_medio_min,
        ANY_VALUE(mediana_min) AS tma_mediano_min,
        ANY_VALUE(p90_min) AS tma_p90_min,
        AVG(avaliacao_valida) AS avaliacao_media,
        COUNT(avaliacao_valida) AS avaliacoes,
        SAFE_DIVIDE(COUNT(avaliacao_valida), COUNT(*)) * 100 AS cobertura_avaliacao
      FROM percentis
      GROUP BY competencia, atendente
    ),
    componentes AS (
      SELECT
        *,
        COALESCE(SAFE_DIVIDE(atendimentos, MAX(atendimentos) OVER w) * 20, 0) AS pontos_quantidade,
        COALESCE(SAFE_DIVIDE(horas_total, MAX(horas_total) OVER w) * 10, 0) AS pontos_tempo,
        COALESCE(SAFE_DIVIDE(
          MIN(IF(tma_medio_min > 0, tma_medio_min, NULL)) OVER w, tma_medio_min
        ) * 30, 0) AS pontos_tma,
        COALESCE(SAFE_DIVIDE(avaliacao_media, MAX(avaliacao_media) OVER w) * 40, 0) AS pontos_avaliacao
      FROM medias
      WINDOW w AS (PARTITION BY competencia)
    ),
    pontuados AS (
      SELECT
        *,
        pontos_quantidade + pontos_tempo + pontos_tma + pontos_avaliacao AS nota_final
      FROM componentes
    ),
    ranking AS (
      SELECT
        *,
        ROW_NUMBER() OVER (
          PARTITION BY competencia
          ORDER BY nota_final DESC, atendimentos DESC, avaliacao_media DESC,
            REGEXP_REPLACE(UPPER(NORMALIZE(atendente, NFD)), r'\\pM', '')
        ) AS posicao
      FROM pontuados
    )''').replace('__SOURCE__', source)


def build_files() -> dict[str, str]:
    sample = ROOT / 'dados/atendimentos_ficticios.csv'
    with sample.open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream, delimiter=';'))
    if len(rows) != 18:
        raise ValueError('Este recorte exige a amostra original de 18 registros.')
    reference = process_upload(sample.read_bytes(), sample.name, '08/2026', 'Diego Demo')
    if reference['estatisticas']['VALIDOS'] != 10 or reference['estatisticas']['EXCLUIDOS'] != 8:
        raise ValueError('A amostra não corresponde ao caso de referência.')

    mappings = {
        'atendente': 'atendente', 'atendimentos': 'atendimentos', 'horas_total': 'horasTotal',
        'tma_medio_min': 'tmaMedioMin', 'tma_mediano_min': 'tmaMedianoMin',
        'tma_p90_min': 'tmaP90Min', 'avaliacao_media': 'avaliacaoMedia',
        'avaliacoes': 'avaliacoes', 'cobertura_avaliacao': 'coberturaAvaliacao',
        'nota_final': 'notaFinal',
    }
    expected = [{sql: row[python] for sql, python in mappings.items()} for row in reference['ranking']]
    source = source_select(rows)
    transformed = transform_ctes(source)
    metrics = metric_ctes('classificados')
    demo = f'''-- {MARKER} etapa=00_demo
-- GoogleSQL / BigQuery. Consulta autocontida: não cria tabelas e não exige upload.
-- Referência da amostra: agosto/2026; escala 0–5, limite 9h e pesos 20/10/30/40.
WITH
{transformed},
{metrics},
controles AS (
  SELECT
    COUNT(*) AS total_importado,
    COUNTIF(motivo_codigo IS NULL) AS validos,
    COUNTIF(motivo_codigo IS NOT NULL) AS excluidos
  FROM classificados
)
SELECT ranking.*, nota_final >= 85 AS elegivel,
  nota_final >= 85 AND posicao <= 3 AS premiado,
  controles.*,
  total_importado = validos + excluidos AS reconciliacao_ok
FROM ranking CROSS JOIN controles
ORDER BY posicao;
'''

    setup = f'''-- {MARKER} etapa=01_carga
-- Troque {PROJECT_TOKEN} pelo ID do projeto, ou use preparar_case.py --project.
-- Dataset dedicado ao portfólio. CTAS evita INSERT/MERGE, indisponíveis no Sandbox.
CREATE SCHEMA IF NOT EXISTS {T}{DATASET}{T}
OPTIONS(location='US', default_table_expiration_days=60);

CREATE OR REPLACE TABLE {T}{DATASET}.raw_atendimentos{T}
OPTIONS(description='18 registros fictícios do case Python/pandas') AS
{source};
'''
    transform = f'''-- {MARKER} etapa=02_transformacao
-- A tabela conserva registros inválidos para auditoria, inclusive datas nulas.
CREATE OR REPLACE TABLE {T}{DATASET}.atendimentos_tratados{T}
PARTITION BY data_inicio
CLUSTER BY atendente, motivo_codigo
OPTIONS(description='Tipagem, duração, escala de avaliação e primeiro motivo de exclusão') AS
WITH
{transform_ctes(f'SELECT * FROM {T}{DATASET}.raw_atendimentos{T}')}
SELECT * FROM classificados;
'''
    mart = f'''-- {MARKER} etapa=03_indicadores
-- Filtro de data explícito para recortar agosto/2026 e permitir poda de partições.
CREATE OR REPLACE TABLE {T}{DATASET}.mart_atendentes{T}
PARTITION BY competencia
CLUSTER BY atendente
OPTIONS(description='KPIs e ranking do recorte de agosto/2026') AS
WITH
{metric_ctes(f'{T}{DATASET}.atendimentos_tratados{T}')}
SELECT *, nota_final >= 85 AS elegivel,
  nota_final >= 85 AND posicao <= 3 AS premiado
FROM ranking;
'''

    expected_structs = []
    for row in expected:
        fields = [f'{sql_string(value) if isinstance(value, str) else repr(value)} AS {key}' for key, value in row.items()]
        expected_structs.append('  STRUCT(' + ', '.join(fields) + ')')
    expected_sql = 'SELECT * FROM UNNEST([\n' + ',\n'.join(expected_structs) + '\n])'
    numeric = [key for key in mappings if key != 'atendente']
    matches = ['a.atendente IS NOT NULL', 'e.atendente IS NOT NULL']
    matches.extend(f'COALESCE(ABS(a.{key} - e.{key}) <= 1e-8, FALSE)' for key in numeric)
    condition = '\n    AND '.join(matches)
    validation = f'''-- {MARKER} etapa=04_validacao
-- Valores esperados foram calculados no motor Python/pandas, não no BigQuery.
WITH totais AS (
  SELECT COUNT(*) AS total, COUNTIF(motivo_codigo IS NULL) AS validos,
    COUNTIF(motivo_codigo IS NOT NULL) AS excluidos,
    COUNTIF(motivo_codigo IS NULL AND avaliacao_valida IS NOT NULL) AS avaliacoes
  FROM {T}{DATASET}.atendimentos_tratados{T}
), esperados AS (
{expected_sql}
), obtidos AS (
  SELECT * FROM {T}{DATASET}.mart_atendentes{T}
  WHERE competencia = DATE '2026-08-01'
)
SELECT 'total_importado' AS verificacao, total = 18 AS aprovado,
  CAST(total AS STRING) AS observado, '18' AS esperado FROM totais
UNION ALL SELECT 'validos', validos = 10, CAST(validos AS STRING), '10' FROM totais
UNION ALL SELECT 'excluidos', excluidos = 8, CAST(excluidos AS STRING), '8' FROM totais
UNION ALL SELECT 'reconciliacao', total = validos + excluidos,
  CAST(validos + excluidos AS STRING), CAST(total AS STRING) FROM totais
UNION ALL SELECT 'avaliacoes_validas', avaliacoes = 9, CAST(avaliacoes AS STRING), '9' FROM totais
UNION ALL SELECT CONCAT('metricas_', COALESCE(a.atendente, e.atendente)),
  {condition},
  TO_JSON_STRING(a), TO_JSON_STRING(e)
FROM obtidos a FULL OUTER JOIN esperados e USING (atendente)
ORDER BY verificacao;
'''
    evidence = f'''-- {MARKER} etapa=05_coletar_evidencias
-- Executar na localização US. Consulta somente jobs do próprio usuário.
-- A projeção omite e-mail, texto da consulta e dados de outros projetos.
SELECT
  creation_time, job_id, job_type, statement_type, state,
  total_bytes_processed, total_bytes_billed, cache_hit,
  error_result.message AS erro
FROM {T}{PROJECT_TOKEN}.region-us.INFORMATION_SCHEMA.JOBS_BY_USER{T}
WHERE creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 1 DAY)
  AND job_type = 'QUERY'
  AND REGEXP_CONTAINS(COALESCE(query, ''), r'{MARKER}')
  AND NOT REGEXP_CONTAINS(COALESCE(query, ''), r'etapa=05_coletar_evidencias')
ORDER BY creation_time DESC;
'''
    snapshot = {
        'tipo': 'referencia_local_pandas', 'executado_no_bigquery': False,
        'amostra': 'dados/atendimentos_ficticios.csv',
        'amostra_sha256': hashlib.sha256(sample.read_bytes()).hexdigest(),
        'competencia': '2026-08', 'total_importado': 18, 'validos': 10, 'excluidos': 8,
        'avaliacoes_validas': 9, 'cobertura_avaliacao': 90.0,
        'ranking_esperado': expected,
    }
    return {
        'sql/00_demo_autocontida.sql': demo,
        'sql/01_carga.sql': setup,
        'sql/02_transformacao.sql': transform,
        'sql/03_indicadores.sql': mart,
        'sql/04_validacao.sql': validation,
        'sql/05_coletar_evidencias.sql': evidence,
        'referencia_pandas.json': json.dumps(snapshot, ensure_ascii=False, indent=2) + '\n',
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', help='ID do projeto Google Cloud para renderizar consultas locais.')
    parser.add_argument('--check', action='store_true', help='Confere se SQL e referência correspondem à amostra atual.')
    args = parser.parse_args()
    if args.project and not re.fullmatch(r'[a-z][a-z0-9-]{4,28}[a-z0-9]', args.project):
        parser.error('ID de projeto inválido; use de 6 a 30 letras minúsculas, números e hífens.')
    files = build_files()
    for relative, content in files.items():
        path = MODULE / relative
        if args.check:
            if not path.is_file() or path.read_text(encoding='utf-8') != content:
                raise SystemExit(f'Arquivo divergente; gere novamente: {path.relative_to(ROOT)}')
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding='utf-8')
    if args.project:
        destination = MODULE / '.gerado'
        destination.mkdir(exist_ok=True)
        for relative, content in files.items():
            if relative.endswith('.sql'):
                (destination / Path(relative).name).write_text(content.replace(PROJECT_TOKEN, args.project), encoding='utf-8')
        print('Consultas configuradas em bigquery/.gerado/.')
    print(f'{len(files)} arquivos gerados/conferidos a partir de 18 registros fictícios.')
    print('Referência pandas: 10 válidos, 8 exclusões, 9 avaliações e cobertura de 90%.')
    print('Nenhuma consulta foi executada no BigQuery por este script.')


if __name__ == '__main__':
    main()
