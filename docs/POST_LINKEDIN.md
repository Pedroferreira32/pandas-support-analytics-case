O que acontece com os dados antes de um dashboard mostrar um KPI?

No projeto Performance do Suporte, uma parte essencial está na pipeline que prepara e valida a base de atendimentos.

Usei Python e pandas para:

- Ler arquivos CSV e Excel e padronizar os campos.
- Tratar datas, duração dos atendimentos e avaliações fora da escala.
- Aplicar regras de negócio com máscaras booleanas.
- Registrar o motivo de exclusão de cada atendimento.
- Agrupar os registros por atendente e calcular volume, TMA, percentis, avaliação média e cobertura de respostas.

Um cuidado importante foi manter a rastreabilidade: cada exclusão tem um motivo, e a base precisa fechar a conta:

Total importado = atendimentos válidos + registros excluídos.

Organizei um recorte técnico com código real do projeto, referências aos arquivos de origem e uma demonstração executável com dados fictícios. Na amostra: 18 registros de entrada, 10 válidos e 8 exclusões explicadas.

A experiência no suporte ajudou a traduzir situações da operação em critérios que podem ser conferidos no código. Esse é um dos pontos que mais me interessam em dados: conectar o tratamento da base às decisões que ela precisa apoiar.

Projeto Python/pandas no GitHub:
https://github.com/Pedroferreira32/pandas-support-analytics-case

Quais validações você considera indispensáveis antes de calcular os indicadores de uma operação?

#Python #Pandas #AnaliseDeDados #QualidadeDeDados #BusinessIntelligence
