-- portfolio_bigquery_case_v1 etapa=05_coletar_evidencias
-- Executar na localização US. Consulta somente jobs do próprio usuário.
-- A projeção omite e-mail, texto da consulta e dados de outros projetos.
SELECT
  creation_time, job_id, job_type, statement_type, state,
  total_bytes_processed, total_bytes_billed, cache_hit,
  error_result.message AS erro
FROM `__PROJECT_ID__.region-us.INFORMATION_SCHEMA.JOBS_BY_USER`
WHERE creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 1 DAY)
  AND job_type = 'QUERY'
  AND REGEXP_CONTAINS(COALESCE(query, ''), r'portfolio_bigquery_case_v1')
  AND NOT REGEXP_CONTAINS(COALESCE(query, ''), r'etapa=05_coletar_evidencias')
ORDER BY creation_time DESC;
