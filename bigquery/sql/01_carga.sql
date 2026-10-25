-- portfolio_bigquery_case_v1 etapa=01_carga
-- Troque __PROJECT_ID__ pelo ID do projeto, ou use preparar_case.py --project.
-- Dataset dedicado ao portfólio. CTAS evita INSERT/MERGE, indisponíveis no Sandbox.
CREATE SCHEMA IF NOT EXISTS `__PROJECT_ID__.support_analytics_portfolio`
OPTIONS(location='US', default_table_expiration_days=60);

CREATE OR REPLACE TABLE `__PROJECT_ID__.support_analytics_portfolio.raw_atendimentos`
OPTIONS(description='18 registros fictícios do case Python/pandas') AS
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
]);
