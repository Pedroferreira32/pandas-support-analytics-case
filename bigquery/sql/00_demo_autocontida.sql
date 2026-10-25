-- portfolio_bigquery_case_v1 etapa=00_demo
-- GoogleSQL / BigQuery. Consulta autocontida: não cria tabelas e não exige upload.
-- Referência da amostra: agosto/2026; escala 0–5, limite 9h e pesos 20/10/30/40.
WITH
raw AS (
  SELECT * FROM UNNEST([
    STRUCT(2 AS linha_origem, "V001" AS protocolo, "Cliente Fictício 01" AS cliente, "Canal Exemplo A" AS revenda, "Ana Demo" AS atendente, "10/08/2026 09:00" AS inicio_raw, "10/08/2026 10:00" AS fim_raw, "Suporte" AS setores, "" AS transferencias, "5" AS avaliacao_raw),
    STRUCT(3 AS linha_origem, "V002" AS protocolo, "Cliente Fictício 02" AS cliente, "Canal Exemplo A" AS revenda, "Ana Demo" AS atendente, "11/08/2026 10:00" AS inicio_raw, "11/08/2026 10:30" AS fim_raw, "Suporte" AS setores, "" AS transferencias, "4" AS avaliacao_raw),
    STRUCT(4 AS linha_origem, "V003" AS protocolo, "Cliente Fictício 03" AS cliente, "Canal Exemplo B" AS revenda, "Ana Demo" AS atendente, "12/08/2026 11:00" AS inicio_raw, "12/08/2026 11:45" AS fim_raw, "Suporte" AS setores, "" AS transferencias, "5" AS avaliacao_raw),
    STRUCT(5 AS linha_origem, "V004" AS protocolo, "Cliente Fictício 01" AS cliente, "Canal Exemplo A" AS revenda, "Ana Demo" AS atendente, "31/08/2026 19:30" AS inicio_raw, "01/09/2026 00:00" AS fim_raw, "Suporte" AS setores, "" AS transferencias, "5" AS avaliacao_raw),
    STRUCT(6 AS linha_origem, "V005" AS protocolo, "Cliente Fictício 04" AS cliente, "Canal Exemplo B" AS revenda, "Bruno Demo" AS atendente, "10/08/2026 09:00" AS inicio_raw, "10/08/2026 09:30" AS fim_raw, "Suporte" AS setores, "" AS transferencias, "4" AS avaliacao_raw),
    STRUCT(7 AS linha_origem, "V006" AS protocolo, "Cliente Fictício 05" AS cliente, "Canal Exemplo B" AS revenda, "Bruno Demo" AS atendente, "11/08/2026 10:00" AS inicio_raw, "11/08/2026 11:00" AS fim_raw, "Comercial" AS setores, "Suporte" AS transferencias, "5" AS avaliacao_raw),
    STRUCT(8 AS linha_origem, "V007" AS protocolo, "Cliente Fictício 06" AS cliente, "Canal Exemplo A" AS revenda, "Bruno Demo" AS atendente, "12/08/2026 11:00" AS inicio_raw, "12/08/2026 11:45" AS fim_raw, "Suporte" AS setores, "" AS transferencias, "8" AS avaliacao_raw),
    STRUCT(9 AS linha_origem, "V008" AS protocolo, "Cliente Fictício 07" AS cliente, "Canal Exemplo A" AS revenda, "Carla Demo" AS atendente, "10/08/2026 09:00" AS inicio_raw, "10/08/2026 09:20" AS fim_raw, "Suporte" AS setores, "" AS transferencias, "5" AS avaliacao_raw),
    STRUCT(10 AS linha_origem, "V009" AS protocolo, "Cliente Fictício 08" AS cliente, "Canal Exemplo B" AS revenda, "Carla Demo" AS atendente, "11/08/2026 10:00" AS inicio_raw, "11/08/2026 10:40" AS fim_raw, "Suporte" AS setores, "" AS transferencias, "5" AS avaliacao_raw),
    STRUCT(11 AS linha_origem, "V010" AS protocolo, "Cliente Fictício 09" AS cliente, "Canal Exemplo B" AS revenda, "Carla Demo" AS atendente, "12/08/2026 11:00" AS inicio_raw, "12/08/2026 11:30" AS fim_raw, "Suporte" AS setores, "" AS transferencias, "4" AS avaliacao_raw),
    STRUCT(12 AS linha_origem, "E001" AS protocolo, "Cliente Fictício 10" AS cliente, "Canal Exemplo A" AS revenda, "" AS atendente, "10/08/2026 09:00" AS inicio_raw, "10/08/2026 10:00" AS fim_raw, "Financeiro" AS setores, "" AS transferencias, "5" AS avaliacao_raw),
    STRUCT(13 AS linha_origem, "E002" AS protocolo, "Cliente Fictício 11" AS cliente, "Canal Exemplo A" AS revenda, "" AS atendente, "10/08/2026 09:00" AS inicio_raw, "10/08/2026 10:00" AS fim_raw, "Suporte" AS setores, "" AS transferencias, "5" AS avaliacao_raw),
    STRUCT(14 AS linha_origem, "E003" AS protocolo, "Cliente Fictício 12" AS cliente, "Canal Exemplo A" AS revenda, "Diego Demo" AS atendente, "10/08/2026 09:00" AS inicio_raw, "10/08/2026 10:00" AS fim_raw, "Suporte" AS setores, "" AS transferencias, "5" AS avaliacao_raw),
    STRUCT(15 AS linha_origem, "E004" AS protocolo, "Cliente Fictício 13" AS cliente, "Canal Exemplo B" AS revenda, "Ana Demo" AS atendente, "Pendente" AS inicio_raw, "10/08/2026 10:00" AS fim_raw, "Suporte" AS setores, "" AS transferencias, "5" AS avaliacao_raw),
    STRUCT(16 AS linha_origem, "E005" AS protocolo, "Cliente Fictício 14" AS cliente, "Canal Exemplo B" AS revenda, "Ana Demo" AS atendente, "10/08/2026 09:00" AS inicio_raw, "" AS fim_raw, "Suporte" AS setores, "" AS transferencias, "5" AS avaliacao_raw),
    STRUCT(17 AS linha_origem, "E006" AS protocolo, "Cliente Fictício 15" AS cliente, "Canal Exemplo B" AS revenda, "Bruno Demo" AS atendente, "10/08/2026 10:00" AS inicio_raw, "10/08/2026 09:00" AS fim_raw, "Suporte" AS setores, "" AS transferencias, "5" AS avaliacao_raw),
    STRUCT(18 AS linha_origem, "E007" AS protocolo, "Cliente Fictício 16" AS cliente, "Canal Exemplo A" AS revenda, "Bruno Demo" AS atendente, "10/08/2026 09:00" AS inicio_raw, "10/08/2026 19:00" AS fim_raw, "Suporte" AS setores, "" AS transferencias, "5" AS avaliacao_raw),
    STRUCT(19 AS linha_origem, "E008" AS protocolo, "Cliente Fictício 17" AS cliente, "Canal Exemplo B" AS revenda, "Carla Demo" AS atendente, "09/08/2026 09:00" AS inicio_raw, "09/08/2026 10:00" AS fim_raw, "Suporte" AS setores, "" AS transferencias, "5" AS avaliacao_raw)
  ])
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
),
validos AS (
  SELECT *
  FROM classificados
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
        REGEXP_REPLACE(UPPER(NORMALIZE(atendente, NFD)), r'\pM', '')
    ) AS posicao
  FROM pontuados
),
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
