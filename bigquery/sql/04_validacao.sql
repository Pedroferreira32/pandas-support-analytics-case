-- portfolio_bigquery_case_v1 etapa=04_validacao
-- Valores esperados foram calculados no motor Python/pandas, não no BigQuery.
WITH totais AS (
  SELECT COUNT(*) AS total, COUNTIF(motivo_codigo IS NULL) AS validos,
    COUNTIF(motivo_codigo IS NOT NULL) AS excluidos,
    COUNTIF(motivo_codigo IS NULL AND avaliacao_valida IS NOT NULL) AS avaliacoes
  FROM `__PROJECT_ID__.support_analytics_portfolio.atendimentos_tratados`
), esperados AS (
SELECT * FROM UNNEST([
  STRUCT("Carla Demo" AS atendente, 3 AS atendimentos, 1.5 AS horas_total, 30.0 AS tma_medio_min, 30.0 AS tma_mediano_min, 38.0 AS tma_p90_min, 4.666666666666667 AS avaliacao_media, 3 AS avaliacoes, 100.0 AS cobertura_avaliacao, 86.52046783625731 AS nota_final),
  STRUCT("Ana Demo" AS atendente, 4 AS atendimentos, 6.75 AS horas_total, 101.25 AS tma_medio_min, 52.5 AS tma_mediano_min, 207.00000000000003 AS tma_p90_min, 4.75 AS avaliacao_media, 4 AS avaliacoes, 100.0 AS cobertura_avaliacao, 78.88888888888889 AS nota_final),
  STRUCT("Bruno Demo" AS atendente, 3 AS atendimentos, 2.25 AS horas_total, 45.0 AS tma_medio_min, 45.0 AS tma_mediano_min, 57.0 AS tma_p90_min, 4.5 AS avaliacao_media, 2 AS avaliacoes, 66.66666666666666 AS cobertura_avaliacao, 76.22807017543859 AS nota_final)
])
), obtidos AS (
  SELECT * FROM `__PROJECT_ID__.support_analytics_portfolio.mart_atendentes`
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
  a.atendente IS NOT NULL
    AND e.atendente IS NOT NULL
    AND COALESCE(ABS(a.atendimentos - e.atendimentos) <= 1e-8, FALSE)
    AND COALESCE(ABS(a.horas_total - e.horas_total) <= 1e-8, FALSE)
    AND COALESCE(ABS(a.tma_medio_min - e.tma_medio_min) <= 1e-8, FALSE)
    AND COALESCE(ABS(a.tma_mediano_min - e.tma_mediano_min) <= 1e-8, FALSE)
    AND COALESCE(ABS(a.tma_p90_min - e.tma_p90_min) <= 1e-8, FALSE)
    AND COALESCE(ABS(a.avaliacao_media - e.avaliacao_media) <= 1e-8, FALSE)
    AND COALESCE(ABS(a.avaliacoes - e.avaliacoes) <= 1e-8, FALSE)
    AND COALESCE(ABS(a.cobertura_avaliacao - e.cobertura_avaliacao) <= 1e-8, FALSE)
    AND COALESCE(ABS(a.nota_final - e.nota_final) <= 1e-8, FALSE),
  TO_JSON_STRING(a), TO_JSON_STRING(e)
FROM obtidos a FULL OUTER JOIN esperados e USING (atendente)
ORDER BY verificacao;
