# Registro de execução no BigQuery

**Estado atual: aguardando execução no Google Cloud.**

As consultas e os resultados esperados foram preparados. O arquivo referencia_pandas.json contém a referência calculada localmente pelo Python/pandas. Ele não comprova execução no BigQuery.

Depois de executar o case, registrar aqui:

- Data e localização da execução.
- IDs dos jobs e estado final sem erro.
- Resultado exportado de 04_validacao.sql, com todas as verificações aprovadas.
- Resultado exportado de 05_coletar_evidencias.sql.
- Resultado dos indicadores por atendente para comparação com a referência pandas.

O conjunto deve permitir ligar o SQL versionado aos resultados efetivamente produzidos pelo BigQuery. Evite publicar credenciais, tokens, e-mails de login ou dados reais de atendimento.
