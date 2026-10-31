-- portfolio_bigquery_case_v1 etapa=02_transformacao
-- A tabela conserva registros inválidos para auditoria, inclusive datas nulas.
CREATE OR REPLACE TABLE `__PROJECT_ID__.support_analytics_portfolio.atendimentos_tratados`
PARTITION BY data_inicio
CLUSTER BY atendente, motivo_codigo
OPTIONS(description='Tipagem, duração, escala de avaliação e primeiro motivo de exclusão') AS
WITH
raw AS (
  SELECT * FROM `__PROJECT_ID__.support_analytics_portfolio.raw_atendimentos`
),
tipado AS (
  SELECT
    *,
    SAFE.PARSE_DATETIME('%d/%m/%Y %H:%M', NULLIF(TRIM(inicio_raw), '')) AS inicio_dt,
    SAFE.PARSE_DATETIME('%d/%m/%Y %H:%M', NULLIF(TRIM(fim_raw), '')) AS fim_dt,
    SAFE_CAST(REPLACE(NULLIF(TRIM(avaliacao_raw), ''), ',', '.') AS FLOAT64) AS avaliacao_num,
    REGEXP_REPLACE(UPPER(NORMALIZE(TRIM(atendente), NFD)), r'\pM', '') AS atendente_normalizado
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
)
SELECT * FROM classificados;
