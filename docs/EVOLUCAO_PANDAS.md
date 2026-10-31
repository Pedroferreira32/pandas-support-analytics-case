# Evolução do código pandas

## Origem e implementação nova

O repositório começou como recorte executável do projeto Performance do Suporte. Os oito arquivos listados em [origem_codigo.json](origem_codigo.json) continuam com os mesmos bytes e hashes do commit de origem. Isso mantém uma referência verificável para os resultados.

A implementação modular foi acrescentada em `etl/`. Ela não chama `process_upload`. Reutiliza somente a configuração histórica de pontuação em `rules.py`, separa responsabilidades e adiciona um contrato de entrada mais estreito, regras de identidade e persistência SQLite.

## Agregação: antes e depois

O motor de referência monta listas e séries dentro de um loop por atendente. Fragmento de `backend/app/pipeline/engine.py`:

```python
for attendant, group in valid.groupby("atendente", sort=False):
    timed = group.loc[group["duracaoConsiderada"]]
    ratings = group["avaliacao"].dropna().astype(float).tolist()
    tmas = timed["tmaMinutos"].astype(float).tolist()
```

A nova implementação agrega diretamente as colunas, com nomes explícitos para a saída:

```python
grouped = valid.groupby("atendente", sort=False, observed=True)
ranking = grouped.agg(
    atendimentos=("protocolo", "size"),
    horas_total=("duracao_horas", "sum"),
    tma_medio_min=("tma_minutos", "mean"),
    tma_mediano_min=("tma_minutos", "median"),
    avaliacao_media=("avaliacao", "mean"),
    avaliacoes=("avaliacao", "count"),
    automaticos=("suspeito_automatico", "sum"),
)
p90 = grouped["tma_minutos"].quantile(0.9, interpolation="linear")
ranking = ranking.join(p90.rename("tma_p90_min")).reset_index()
```

`size` conta atendimentos; `count` ignora avaliações ausentes. Essa diferença produz a cobertura de respostas e mantém separadas a validade do atendimento e a validade da nota. A pontuação utiliza operações sobre colunas e o Top 3 é definido após a ordenação.

Não foi feito benchmark. A melhoria demonstrada é a organização da lógica, a explicitação das agregações e a equivalência dos resultados na amostra, não uma redução medida de tempo de execução.

## Tipos, regras e parâmetros

- A extração mantém o conteúdo textual, inclusive zeros iniciais de protocolos.
- Início e fim são convertidos uma vez a partir das respectivas colunas brutas, com formato documentado. A duração usa diretamente as colunas `datetime64` resultantes.
- As funções de validação devolvem máscaras com o mesmo índice. O loop percorre as regras e atribui o motivo principal; não percorre os atendimentos individualmente.
- Horários, dias permitidos, limite de premiados e unidades de conversão recebem nomes explícitos.
- O loop pequeno dos componentes da nota aplica a mesma operação vetorizada a métricas diferentes; não é um loop por atendente.
- A serialização de linhas para SQLite usa `executemany` parametrizado dentro de uma transação.

## O que a equivalência cobre

Na amostra original, os testes comparam os 18 campos do ranking: atendente, volume, horas, média/mediana/P90 da duração, média e contagem de avaliações, cobertura, automáticos, quatro componentes da pontuação, nota, posição, elegibilidade e premiação.

A equivalência vale para esse contrato e amostra. O importador original aceita formatos e cabeçalhos adicionais que a nova extração não pretende reproduzir. Regras novas, como quarentena de protocolos duplicados, são verificadas com cenários próprios.

## Diferenças intencionais

| Situação | Referência original | Pipeline modular |
|---|---|---|
| CSV com colunas ausentes/extras | Importador flexível com aliases | Contrato exato e falha explícita |
| Protocolo em branco | Identificador de contingência por linha | Exclusão `SEM_PROTOCOLO`, com linha preservada |
| Protocolo repetido no mês | Sem política de deduplicação | Quarentena de todas as cópias |
| Registro de outra competência | Bloqueio se maioria pertence a outro mês | Exclusão explícita por linha |
| Nenhum atendimento válido | Exceção de processamento | Base de excluídos carregada e ranking vazio auditável |
| Persistência neste recorte | Exportações CSV/JSON | Transação SQLite, além das exportações |

O motor de referência foi preservado para evitar alterar retroativamente o material de origem. A refatoração é apresentada como evolução comparável e verificável neste repositório.
