# Contrato e decisões da pipeline

## Responsabilidades

| Etapa | Entrada | Saída | Falhas e controles |
|---|---|---|---|
| `extract()` | Bytes do CSV local | DataFrame textual, nome e hash da origem | Schema e estrutura incompatíveis bloqueiam o arquivo |
| `validate()` | Campos textuais e parâmetros | Base classificada, válidos, excluídos e contagens por regra | Uma conversão por coluna temporal; motivo principal e flags preservados |
| `transform()` | Atendimentos válidos | Um registro por atendente | Agregações nomeadas, percentis, pontuação e desempate |
| `load()` | Válidos, excluídos, ranking e metadados | Tabelas SQLite e reconciliação SQL | Substituição mensal atômica; rollback se houver divergência |

`pipeline.run_pipeline()` orquestra essas funções e devolve DataFrames e manifesto. A CLI exporta também CSVs e resumo; essas exportações ocorrem após o commit e podem ser regeneradas. A transação cobre o banco, não o conjunto de arquivos exportados.

## Contrato CSV

Campos obrigatórios, com nomes exatos e ordem livre:

```text
Protocolo;Contact ID;Revenda;User ID;Iniciado;Fim;Setores;Setores Transfers;Rating
```

- Encoding UTF-8, com ou sem BOM; separador ponto e vírgula.
- Cabeçalhos duplicados, extras ou ausentes são erros de schema.
- A quantidade de campos deve ser igual ao cabeçalho em todos os registros. Registros vazios também não são descartados silenciosamente.
- Todos os campos entram como texto. Isso preserva zeros iniciais de protocolos e impede inferência de tipos sobre identificadores.
- `Iniciado` e `Fim` aceitam `DD/MM/AAAA HH:MM`. Datas incompatíveis viram ausentes e são auditadas pelas regras correspondentes.
- `Rating` usa conversão numérica, aceita vírgula decimal e aplica a escala da competência. Campo vazio, texto ou número fora da escala fica ausente na avaliação.
- `linha_origem` é o número lógico do registro CSV, a partir de 2. Em campos com quebra de linha entre aspas, não equivale necessariamente à linha física do arquivo.
- Não há detecção de outros cabeçalhos, formatos Excel ou encodings nesta implementação modular. O motor original preservado cobre um contrato mais abrangente.

## Regras e prioridade

Cada função em `validate.py` devolve uma máscara booleana. Todas são avaliadas, mas somente a primeira regra aplicável determina `motivo_codigo`.

| Prioridade | Código | Condição |
|---:|---|---|
| 1 | `FORA_SUPORTE` | Suporte ausente no setor e na transferência |
| 2 | `SEM_ATENDENTE` | Atendente vazio ou marcador de ausência |
| 3 | `ATENDENTE_EXCLUIDO` | Nome parcial normalizado corresponde à lista configurada |
| 4 | `DATA_INVALIDA` | Início não convertido |
| 5 | `SEM_FINALIZACAO` | Fim ausente ou não convertido |
| 6 | `DURACAO_NEGATIVA` | Fim anterior ao início |
| 7 | `ACIMA_H` | Duração superior ao limite histórico |
| 8 | `PERIODO` | Início em dia/horário não permitido |
| 9 | `FORA_COMPETENCIA` | Mês inicial diferente do solicitado |
| 10 | `SEM_PROTOCOLO` | Protocolo em branco após remover espaços externos |
| 11 | `PROTOCOLO_DUPLICADO` | Chave repetida no mesmo mês inicial |

O manifesto separa `detectados` de `motivo_principal`. Um atendimento pode acionar várias máscaras, mas entra apenas uma vez no total de excluídos. A contagem de máscaras detectadas não deve ser somada como se fosse a contagem de exclusões.

### Protocolos duplicados

A chave compara `protocolo.strip().casefold()` junto ao mês inicial. Todas as cópias ficam em quarentena, inclusive quando os conteúdos diferem. Escolher `keep='first'` poderia manter uma versão incorreta sem justificativa.

O protocolo bruto e a linha de origem continuam nas saídas. O flag `protocolo_duplicado` pode ser verdadeiro em uma linha cujo motivo principal seja outro, por causa da prioridade. Protocolos iguais em meses iniciais diferentes não são tratados como duplicados. Esta é uma decisão do case, não uma afirmação sobre a unicidade global dos protocolos de todo sistema de origem.

### Expediente, datas e pontuação

O padrão aceita segunda a sábado, das 08:00 inclusive às 20:00 exclusive. O início determina a competência e o expediente; o fim pode estar no mês seguinte. Os limites e os pesos vêm das regras históricas originais:

| Competência | Escala | Duração máxima | Quantidade | Horas | TMA | Avaliação |
|---|---:|---:|---:|---:|---:|---:|
| Até 2026-05 | 0–10 | 8 h | 30 | 15 | 25 | 30 |
| De 2026-06 em diante | 0–5 | 9 h | 20 | 10 | 30 | 40 |

Os componentes são relativos ao melhor resultado do grupo: maior volume, maior total de horas, menor TMA positivo e maior média de avaliação. A meta é 85 pontos e no máximo três elegíveis são premiados. Nenhuma precisão é descartada antes da apresentação.

A ordenação usa nota, volume, avaliação e nome normalizado; o nome literal resolve também um empate entre grafias que normalizam igualmente. Duração zero continua válida; recebe zero no componente inverso de TMA. Ausência de avaliações gera zero no componente de avaliação e permanece ausente na média, sem inventar uma nota.

Finalizações às 06:00 ou pelo menos 20 finais no mesmo minuto são sinalizadas como potencialmente automáticas. O flag não altera o filtro regular de duração nem neutraliza tempo. O ranking agrega a duração observada, conforme o recorte público.

## Banco e reprocessamento

| Tabela | Grão e finalidade |
|---|---|
| `validos` | Uma linha por competência e registro de origem; protocolo único por competência |
| `excluidos` | Uma linha por competência e registro de origem, com motivo principal |
| `ranking` | Uma linha por competência e atendente |
| `competencias` | Execução ativa e total extraído de cada mês |
| `execucoes` | Identificador, origem, hash, configuração e data de gravação |
| `etapas` | Quatro contagens por identificador de execução |

O identificador é um SHA-256 do hash da entrada e da configuração, que inclui a versão da pipeline. A repetição do mesmo arquivo com os mesmos parâmetros reutiliza esse identificador. Não é um identificador de tentativa; a tabela não registra tentativas que falharam antes do commit. Mudanças de comportamento exigem incrementar `PIPELINE_VERSION`.

A carga abre `BEGIN IMMEDIATE`, registra os metadados, substitui válidos/excluídos/ranking somente do mês solicitado e roda `sql/reconciliar.sql` antes do commit. SQL parametrizado protege os valores; os nomes de tabelas são constantes internos. Uma divergência ou erro de inserção desfaz dados e metadados da transação, preservando a carga anterior e outras competências.

O banco contém os dados ativos de cada competência e metadados de execuções confirmadas. Os registros antigos são substituídos; não é implementado histórico completo de versões de cada linha.

## Reconciliação SQL e contagens

A consulta verifica:

1. Total extraído igual à soma de válidos e excluídos.
2. Linhas de origem distintas e intervalo completo de registros.
3. Contagem de atendimentos e avaliações do ranking igual à base válida.
4. Correspondência das contagens por atendente, incluindo ausência de atendentes extras.
5. Ausência de protocolos duplicados na base válida.

Os testes de equivalência comparam separadamente todos os 18 campos do ranking com a referência pandas original, com tolerância de `1e-10` para valores numéricos. A consulta de reconciliação não recalcula cada percentil e componente da nota.

Em `transform`, 10 entradas e 3 saídas representam mudança do grão de atendimento para atendente. Em `load`, 21 linhas representam 10 válidos + 8 excluídos + 3 rankings. Metadados não entram nessa contagem. Assim, uma agregação não é confundida com perda de registros.

## Limites

A execução é local, em lote, com arquivos fictícios pequenos. Não foram medidos desempenho, redução de trabalho ou escala. A persistência transacional, a reprodução e as falhas testadas são o escopo demonstrado. Configuração de fonte remota, agendamento, alertas e operação contínua exigiriam decisões e testes adicionais.
