# Roteiro para demonstrar e explicar o projeto

## 1. Apresente a decisão de negócio

Uma base de atendimentos alimenta indicadores e um ranking. Antes de agregar, é necessário definir quais registros podem participar e manter a explicação de cada exclusão. Use o caso da nota 8 fora da escala: o atendimento permanece válido, mas a avaliação sai da média.

## 2. Execute a pipeline e acompanhe as etapas

Na raiz, com o ambiente instalado conforme o README:

```bash
python -m etl
```

Explique as contagens: 18 extraídos, 10 válidos, 8 excluídos, 3 atendentes e 21 linhas de dados carregadas no SQLite. O total de 21 combina tabelas de grãos diferentes e não representa 21 atendimentos.

Abra `resultados/etl/manifesto.json`, `excluidos.csv` e `ranking.csv`. A linha e os campos brutos permitem ligar o resultado à entrada. O manifesto conserva o SHA-256 da origem e os parâmetros usados.

## 3. Mostre três decisões no código

1. Em `etl/validate.py`, mostre `between`/`where`, as funções que devolvem máscaras e a prioridade de motivos. Explique por que contar falhas detectadas é diferente de contar registros excluídos.
2. Em `etl/transform.py`, mostre `groupby().agg()`, `size` versus `count` e o P90. Explique que P90 observa a cauda das durações e que esse tempo não mede trabalho ativo.
3. Em `etl/load.py`, mostre `BEGIN IMMEDIATE`, a substituição filtrada por competência, a consulta de reconciliação e o rollback.

## 4. Reprocesse e confira no banco

```bash
python -m etl
python -m etl --reconcile-only
```

As contagens continuam iguais. A mesma entrada/configuração reutiliza o identificador; a carga não acrescenta cópias às tabelas ativas.

Consulte com qualquer cliente SQLite ou com Python:

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

## 5. Demonstre os controles novos

```bash
python -m etl --source dados/cenarios_qualidade.csv --database resultados/qualidade/suporte.sqlite --output-dir resultados/qualidade
```

Essa amostra tem 22 entradas, 10 válidos e 12 excluídos. O protocolo V001 aparece duas vezes: ambas as cópias vão para quarentena. Há também um protocolo ausente, um registro de outra competência e uma avaliação textual. A cobertura passa a 80% porque restam oito avaliações válidas entre dez atendimentos.

## 6. Execute os testes e consulte o CI

```bash
python scripts/verificar_codigo.py
python scripts/verificar_etl.py
```

Mostre o teste de equivalência dos indicadores e o teste que força a reprovação da reconciliação durante a carga. Esse último confere que dados e metadados anteriores continuam no banco após o rollback.

No GitHub Actions, confira o estado real dos jobs Linux/Windows. Os artefatos de cada run incluem os bancos demonstrativos e as evidências geradas, permitindo repetir as consultas.

## Perguntas que você deve conseguir responder

- Por que uma nota inválida não elimina automaticamente o atendimento?
- Por que `count` e `size` produzem resultados diferentes?
- Por que colocar todas as cópias duplicadas em quarentena?
- O que muda quando 10 atendimentos se tornam três linhas de ranking?
- O que acontece se a carga falhar depois de apagar os dados antigos dentro da transação?
- Como a consulta SQL detecta uma divergência no ranking?
- O que este case comprova e quais comportamentos ainda exigiriam trabalho para operar continuamente?
