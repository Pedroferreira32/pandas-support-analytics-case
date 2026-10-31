# Execução da pipeline ETL local

Dados exclusivamente fictícios.

| Etapa | Entrada | Saída | Excluídos | Unidade |
|---|---:|---:|---:|---|
| extract | 22 | 22 | 0 | atendimentos |
| validate | 22 | 10 | 12 | atendimentos |
| transform | 10 | 3 | 0 | atendimentos -> atendentes |
| load | 25 | 25 | 0 | linhas: validos + excluidos + ranking |

Reconciliação SQL: **22 = 10 válidos + 12 excluídos**.
Avaliações válidas: **8**. Cobertura: **80.00%**.
Controles SQL aprovados: **True**.

A saída de transform está no grão de atendente. A carga conta linhas das três tabelas, sem contar os metadados.

A consulta SQL confere contagens, exclusividade das linhas de origem, protocolos válidos únicos e contagens por atendente; não prova qualidade operacional.
