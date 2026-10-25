# Verificação do recorte pandas

Data de preparação deste material: 25/10/2026.

- Origem: https://github.com/Pedroferreira32/support-performance-analytics
- Commit: 1c06e62c70b9e2d71908381728f9875a5b7c4dc3
- Python desta execução: 3.12.14
- pandas desta execução: 2.2.3
- Arquivos de origem conferidos por hashes Git e SHA-256: 8.
- Testes originais de pipeline executados: 6.
- Resultado: todos aprovados.
- Amostra sintética: reconciliação, oito motivos, avaliação inválida, cobertura, transferência e mês de início conferidos.

## Testes originais executados

- test_historical_rule_has_100_points_and_separate_time_components
- test_competence_uses_start_date_when_end_is_next_month
- test_client_identity_is_preserved_for_recurrence_analysis
- test_automatic_closures_follow_the_regular_duration_rule
- test_only_top_three_eligible_are_awarded
- test_partial_exclusion_and_invalid_rating_are_auditable

Os testes foram executados com unittest.FunctionTestCase sobre as funções originais. API, banco, frontend e implantação estão fora desta verificação.
