# Validação da pipeline ETL local

- Python: 3.12.14.
- pandas: 2.2.3; NumPy: 2.3.5; xlrd: 2.0.2.
- Testes novos executados e aprovados: **27**.
- Os seis testes e os hashes dos oito arquivos originais são conferidos separadamente por `verificar_codigo.py`.

| Amostra fictícia | Entrada | Válidos | Excluídos | Avaliações | Cobertura | SQL aprovado |
|---|---:|---:|---:|---:|---:|---|
| atendimentos_ficticios.csv | 18 | 10 | 8 | 9 | 90% | True |
| cenarios_qualidade.csv | 22 | 10 | 12 | 8 | 80% | True |

## Contratos verificados

- Equivalência dos 18 campos do ranking com o motor original na amostra de referência, com tolerância numérica de 1e-10.
- Schema, CSV malformado, protocolos em branco e quarentena de todas as cópias duplicadas na mesma competência.
- Nota inválida, cobertura, transferência de setor, competência inicial, horários e regras históricas.
- Top 3, desempate, ausência de avaliações, duração zero e base sem atendimentos válidos.
- Carga idempotente, substituição mensal, preservação de outra competência e rollback de dados e metadados.
- Reconciliação SQL, divergência inserida no ranking, CLI e exportação reproduzível.

Este relatório registra a execução local que o gerou. A execução remota de CI é comprovada pelos runs do GitHub Actions.
