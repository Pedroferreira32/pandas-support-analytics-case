# Execução da pipeline ETL local

Dados exclusivamente fictícios.

| Etapa | Entrada | Saída | Excluídos | Unidade |
|---|---:|---:|---:|---|
| extract | 18 | 18 | 0 | atendimentos |
| validate | 18 | 10 | 8 | atendimentos |
| transform | 10 | 3 | 0 | atendimentos -> atendentes |
| load | 21 | 21 | 0 | linhas: validos + excluidos + ranking |

Reconciliação SQL: **18 = 10 válidos + 8 excluídos**.
Avaliações válidas: **9**. Cobertura: **90.00%**.
Controles SQL aprovados: **True**.

A saída de transform está no grão de atendente. A carga conta linhas das três tabelas, sem contar os metadados.

A consulta SQL confere contagens, exclusividade das linhas de origem, protocolos válidos únicos e contagens por atendente; não prova qualidade operacional.
