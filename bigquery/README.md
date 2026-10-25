# BigQuery aplicado ao case de suporte

**Status: preparado para execução; ainda sem execução comprovada no BigQuery.**

Este módulo leva a mesma amostra fictícia do projeto Python/pandas para GoogleSQL. A meta é construir uma evidência verificável de BigQuery: SQL versionado, tabelas criadas na plataforma, indicadores reconciliados com pandas e IDs dos jobs executados.

## O que este case permite demonstrar

| Etapa | Código | Competência |
|---|---|---|
| Primeira consulta | [00_demo_autocontida.sql](sql/00_demo_autocontida.sql) | CTEs, UNNEST, STRUCT, regras, agregações e funções de janela |
| Carga da amostra | [01_carga.sql](sql/01_carga.sql) | Dataset dedicado e criação de tabela por CTAS |
| Tratamento | [02_transformacao.sql](sql/02_transformacao.sql) | Conversão segura de tipos, datas, CASE, particionamento e clustering |
| Indicadores | [03_indicadores.sql](sql/03_indicadores.sql) | AVG, COUNT, SAFE_DIVIDE, percentis exatos, pontuação e ROW_NUMBER |
| Reconciliação | [04_validacao.sql](sql/04_validacao.sql) | Comparação entre SQL e a referência do motor pandas |
| Evidências reais | [05_coletar_evidencias.sql](sql/05_coletar_evidencias.sql) | Consulta aos metadados dos próprios jobs |

O cálculo trata os casos de data inválida, falta de atendente, outro departamento, exclusão da campanha, falta de finalização, duração negativa, duração acima do limite e início fora do expediente ou no domingo. A primeira regra aplicável define um único motivo de exclusão.

## Recorte e referência

A origem é [atendimentos_ficticios.csv](../dados/atendimentos_ficticios.csv), com 18 registros. O motor Python original calcula os valores esperados: 10 válidos, 8 exclusões, 9 avaliações válidas e cobertura de 90%.

Este módulo aplica o recorte de agosto/2026: escala de avaliação 0–5, duração máxima de 9 horas, pesos 20/10/30/40 e meta de 85 pontos. Um atendimento iniciado em agosto e finalizado em setembro permanece em agosto. A nota 8 é desconsiderada na avaliação; o atendimento continua válido quando passa nas demais regras.

O SQL é um recorte didático para esta amostra. Ele não substitui o importador completo, não implementa todos os formatos de data e cabeçalho do motor Python e não generaliza os perfis históricos. A validação deve ser concluída no próprio BigQuery.

## Primeira execução, sem criar tabelas

1. Abra o [BigQuery Studio](https://console.cloud.google.com/bigquery) com um projeto de Sandbox.
2. Crie uma consulta SQL e cole o conteúdo completo de 00_demo_autocontida.sql.
3. Execute com GoogleSQL e confira as três linhas de indicadores e a reconciliação 18 = 10 + 8.
4. Registre o ID do job e exporte o resultado. A consulta contém a amostra, portanto não exige upload nem criação prévia de dataset.

Essa primeira execução demonstra a consulta no BigQuery. A sequência seguinte acrescenta as evidências de armazenamento, transformação e organização das tabelas.

## Execução completa com tabelas

Na raiz do repositório, com as dependências Python já instaladas:

```bash
python bigquery/preparar_case.py --check
python bigquery/preparar_case.py --project seu-projeto-gcp
```

O segundo comando configura as consultas em bigquery/.gerado/. Ele somente prepara os arquivos locais; não se autentica no Google e não executa consultas.

No BigQuery Studio, use a localização US e execute os arquivos configurados na ordem 01, 02, 03, 04 e 05. A carga usa os 18 registros embutidos no SQL para garantir uma amostra reproduzível. Ela não demonstra upload de CSV; uma evolução pode acrescentar um job de carga de arquivo.

O dataset dedicado é support_analytics_portfolio. A tabela raw_atendimentos mantém os valores de origem; atendimentos_tratados conserva a classificação e o motivo de exclusão; mart_atendentes recebe os KPIs e a pontuação. As etapas 01–03 reaplicam a amostra com CREATE OR REPLACE TABLE exclusivamente nessas tabelas do case.

O particionamento usa a data inicial e a competência, e o clustering usa atendente e motivo de exclusão. Os filtros de agosto estão explícitos nas consultas de indicadores. A auditoria consulta também as linhas com datas inválidas. Nesta amostra pequena, a estrutura não comprova ganho de custo ou desempenho.

## Como fechar a comprovação

Confira se 04_validacao.sql retorna aprovado = true em todas as linhas. A consulta compara totais e os indicadores de cada atendente, incluindo TMA, mediana, P90, avaliação, cobertura e pontuação, com tolerância numérica de 1e-8.

Depois exporte os metadados de 05_coletar_evidencias.sql. Ela consulta apenas os jobs do próprio usuário, filtrados pelo marcador do case, e retorna ID, estado, erro, bytes processados e uso de cache. Registre as evidências na [pasta de execução](evidencias/README.md).

Somente após essa etapa será adequado apresentar o material como um case executado no BigQuery. Código preparado e referência calculada em pandas são etapas de construção, com estados distintos da execução em nuvem.

## Sandbox

O Sandbox permite começar sem cartão de crédito e sem criar uma conta de faturamento. As cotas gratuitas, limitações e regras de expiração devem ser conferidas na documentação oficial. O case usa consultas e CTAS; não depende de INSERT, MERGE, streaming ou Data Transfer Service, recursos que o Sandbox não oferece.

Os recursos do Sandbox expiram após 60 dias. Por isso, preserve SQL e resultados exportados como documentação da execução.

## Fontes oficiais

- [BigQuery Sandbox](https://docs.cloud.google.com/bigquery/docs/sandbox)
- [DDL e criação de tabelas](https://docs.cloud.google.com/bigquery/docs/reference/standard-sql/data-definition-language)
- [Conversão de datas](https://docs.cloud.google.com/bigquery/docs/reference/standard-sql/datetime_functions#parse_datetime)
- [PERCENTILE_CONT](https://docs.cloud.google.com/bigquery/docs/reference/standard-sql/navigation_functions#percentile_cont)
- [Metadados JOBS_BY_USER](https://docs.cloud.google.com/bigquery/docs/information-schema-jobs-by-user)
