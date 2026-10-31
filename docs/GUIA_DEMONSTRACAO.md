# Como avaliar este projeto

Reuni aqui os critérios, os comandos e as evidências que usei para validar a pipeline principal em `etl/`. Os dados de todas as demonstrações são fictícios. O código em `backend/` foi preservado como referência histórica.

## 1. Problema e critérios de validade

Ao estruturar o case, separei a validade do atendimento da validade de sua avaliação. Uma nota 8 em uma escala de 0 a 5 fica fora da média e da contagem de respostas; o atendimento permanece quando satisfaz os demais critérios.

Registrei o primeiro motivo de exclusão conforme a prioridade das regras e mantive as contagens de todas as máscaras detectadas. Assim, uma linha com várias falhas continua sendo contada apenas uma vez na base excluída.

## 2. Reprodução da amostra de referência

Na raiz do repositório, com o ambiente instalado conforme o README, a execução é:

```bash
python -m etl
```

Na amostra de referência, obtive 18 atendimentos extraídos, 10 válidos e 8 excluídos. A transformação produziu três linhas de ranking, uma por atendente. Na carga, acompanhei separadamente as tabelas `validos`, `excluidos` e `ranking`, porque elas possuem grãos diferentes.

Em `resultados/etl/manifesto.json`, registrei o SHA-256 da origem, os parâmetros e as contagens por etapa. Em `excluidos.csv` e `ranking.csv`, preservei as saídas para inspeção. A linha de origem e os campos brutos permitem ligar cada classificação à entrada.

## 3. Evidências no código

| Decisão | Implementação | Evidência de verificação |
|---|---|---|
| Separei avaliação inválida de atendimento inválido | `between` e `where` em [validate.py](../etl/validate.py) | Nove avaliações entre dez atendimentos na amostra de referência |
| Mantive regras independentes e uma prioridade explícita | Funções que retornam máscaras e sequência `RULES` em [validate.py](../etl/validate.py) | Testes de prioridade e contagem de falhas detectadas |
| Diferenciei volume de cobertura de respostas | `size` e `count` em [transform.py](../etl/transform.py) | Comparação dos 18 campos do ranking com o motor original |
| Calculei mediana e P90 das durações | Agregações e `quantile` em [transform.py](../etl/transform.py) | Equivalência numérica com a referência |
| Protegi a substituição mensal contra falhas | `BEGIN IMMEDIATE`, SQL parametrizado e rollback em [load.py](../etl/load.py) | Testes de falha por divergência e restrição real do SQLite |
| Conferi a carga no próprio banco | [reconciliar.sql](../sql/reconciliar.sql) antes do commit | Contagens, linhas de origem e correspondência por atendente |

A duração entre início e fim é a medida disponível no case. Não a interpretei como tempo de trabalho ativo nem como comprovação de resolução ou retrabalho.

## 4. Reprocessamento e consulta ao banco

Repeti a execução e consultei a reconciliação com:

```bash
python -m etl
python -m etl --reconcile-only
```

Mantive as contagens e reutilizei o identificador para a mesma entrada e configuração. A carga substitui somente a competência solicitada e preserva as demais.

Uma consulta reproduzível ao ranking é:

```python
from contextlib import closing
import sqlite3

with closing(sqlite3.connect("resultados/etl/suporte.sqlite")) as connection:
    print(connection.execute(
        "SELECT atendente, atendimentos, avaliacao_media, cobertura_avaliacao "
        "FROM ranking WHERE competencia = ? ORDER BY posicao",
        ("2026-08",),
    ).fetchall())
```

## 5. Casos adicionais de qualidade

Acrescentei uma segunda amostra e a executei com:

```bash
python -m etl --source dados/cenarios_qualidade.csv --database resultados/qualidade/suporte.sqlite --output-dir resultados/qualidade
```

Obtive 22 entradas, 10 válidos e 12 excluídos. Coloquei as duas cópias de V001 em quarentena e auditei também um protocolo ausente e um atendimento de outra competência. Desconsiderei a avaliação textual e obtive oito avaliações válidas entre dez atendimentos, com cobertura de 80%.

## 6. Testes e CI

Executei:

```bash
python scripts/verificar_codigo.py
python scripts/verificar_etl.py
```

Conferi seis testes originais, os hashes de oito arquivos preservados e 27 testes novos. Nos testes de carga, forcei uma divergência de reconciliação e uma falha real de restrição SQLite; em ambos, verifiquei a preservação dos dados e metadados anteriores após o rollback.

Configurei o GitHub Actions para executar a verificação em Linux e Windows. Os logs e artefatos de cada run registram o resultado remoto; `resultados/VALIDACAO_ETL.md` registra a execução que gerou o relatório versionado.

## Escopo da avaliação

Com esse conjunto, demonstrei regras de negócio, uso de pandas, persistência transacional e validação reproduzível. Não medi desempenho em escala nem implementei operação contínua. Registrei no [README](../README.md#limites-e-o-que-ainda-preciso-implementar) as lacunas de agendamento, carga incremental, alertas, tentativas com falha e evolução de schema.
