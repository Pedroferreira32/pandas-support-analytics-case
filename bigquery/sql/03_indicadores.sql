-- portfolio_bigquery_case_v1 etapa=03_indicadores
-- Filtro de data explícito para recortar agosto/2026 e permitir poda de partições.
CREATE OR REPLACE TABLE `__PROJECT_ID__.support_analytics_portfolio.mart_atendentes`
PARTITION BY competencia
CLUSTER BY atendente
OPTIONS(description='KPIs e ranking do recorte de agosto/2026') AS
WITH
validos AS (
  SELECT *
  FROM `__PROJECT_ID__.support_analytics_portfolio.atendimentos_tratados`
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
)
SELECT *, nota_final >= 85 AS elegivel,
  nota_final >= 85 AND posicao <= 3 AS premiado
FROM ranking;
