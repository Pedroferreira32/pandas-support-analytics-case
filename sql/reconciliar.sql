-- Parâmetro :competencia em AAAA-MM. A consulta também roda dentro da transação.
WITH
v AS (
  SELECT COUNT(*) AS validos, COUNT(avaliacao) AS avaliacoes
  FROM validos WHERE competencia = :competencia
),
e AS (SELECT COUNT(*) AS excluidos FROM excluidos WHERE competencia = :competencia),
r AS (
  SELECT COUNT(*) AS atendentes, COALESCE(SUM(atendimentos), 0) AS atendimentos_ranking,
    COALESCE(SUM(avaliacoes), 0) AS avaliacoes_ranking
  FROM ranking WHERE competencia = :competencia
),
origens AS (
  SELECT linha_origem FROM validos WHERE competencia = :competencia
  UNION ALL
  SELECT linha_origem FROM excluidos WHERE competencia = :competencia
),
base_por_atendente AS (
  SELECT atendente, COUNT(*) AS atendimentos, COUNT(avaliacao) AS avaliacoes
  FROM validos WHERE competencia = :competencia GROUP BY atendente
),
divergencias AS (
  SELECT b.atendente FROM base_por_atendente b
  LEFT JOIN ranking r ON r.competencia = :competencia AND r.atendente = b.atendente
  WHERE r.atendente IS NULL OR b.atendimentos <> r.atendimentos OR b.avaliacoes <> r.avaliacoes
  UNION ALL
  SELECT r.atendente FROM ranking r
  LEFT JOIN base_por_atendente b ON b.atendente = r.atendente
  WHERE r.competencia = :competencia AND b.atendente IS NULL
),
controles AS (
  SELECT c.competencia, c.execucao_id, c.total_extraido, v.*, e.*, r.*,
    (SELECT COUNT(DISTINCT linha_origem) FROM origens) AS linhas_distintas,
    (SELECT MIN(linha_origem) FROM origens) AS primeira_linha,
    (SELECT MAX(linha_origem) FROM origens) AS ultima_linha,
    (SELECT COUNT(*) FROM divergencias) AS divergencias_ranking,
    (SELECT COUNT(*) FROM (
      SELECT protocolo_chave FROM validos WHERE competencia = :competencia
      GROUP BY protocolo_chave HAVING COUNT(*) > 1
    )) AS protocolos_duplicados_validos
  FROM competencias c CROSS JOIN v CROSS JOIN e CROSS JOIN r
  WHERE c.competencia = :competencia
)
SELECT *,
  total_extraido = validos + excluidos
  AND total_extraido = linhas_distintas
  AND primeira_linha = 2 AND ultima_linha = total_extraido + 1
  AND validos = atendimentos_ranking
  AND avaliacoes = avaliacoes_ranking
  AND divergencias_ranking = 0
  AND protocolos_duplicados_validos = 0 AS reconciliado
FROM controles;
