from __future__ import annotations

from backend.app.pipeline.engine import detect_competence, process_upload
from backend.app.pipeline.rules import official_config


HEADER = "Protocolo,User ID,Iniciado,Fim,Setores,Setores Transfers,Rating"


def csv_bytes(*rows: str) -> bytes:
    return "\n".join([HEADER, *rows]).encode("utf-8")


def test_historical_rule_has_100_points_and_separate_time_components() -> None:
    config = official_config("2026-05")
    assert config.teto_pontuacao == 100
    assert config.pontuacao_tempo_tma_fixa is False
    assert config.peso_quantidade + config.peso_tempo + config.peso_tma + config.peso_avaliacao == 100

    result = process_upload(
        csv_bytes(
            "1,Ana,10/05/2026 10:00,10/05/2026 11:00,Suporte,,10",
            "2,Ana,11/05/2026 10:00,11/05/2026 11:00,Suporte,,10",
            "3,Bruna,10/05/2026 10:00,10/05/2026 12:00,Suporte,,8",
        ),
        "historico.csv",
        "05/2026",
    )
    leader = result["ranking"][0]
    assert leader["atendente"] == "Ana"
    assert round(leader["pontosTempo"], 6) == 15
    assert round(leader["pontosTma"], 6) == 25
    assert round(leader["notaFinal"], 6) == 100


def test_competence_uses_start_date_when_end_is_next_month() -> None:
    content = csv_bytes("1,Ana,31/08/2026 19:56,01/09/2026 02:47,Suporte,,5")
    assert detect_competence(content, "agosto.csv") == "2026-08"
    result = process_upload(content, "agosto.csv", "08/2026")
    assert result["competencia"] == "2026-08"
    assert len(result["validos"]) == 1


def test_client_identity_is_preserved_for_recurrence_analysis() -> None:
    content = (
        "Protocolo,Contact ID,Contact Number,Revenda,User ID,Iniciado,Fim,Setores,Rating\n"
        "1,Cliente Exemplo,5511999999999,Revenda Demo,Ana,10/08/2026 10:00,10/08/2026 11:00,Suporte,5"
    ).encode("utf-8")

    result = process_upload(content, "clientes.csv", "08/2026")

    assert result["validos"][0]["cliente"] == "Cliente Exemplo"
    assert result["validos"][0]["contato"] == "5511999999999"
    assert result["validos"][0]["revenda"] == "Revenda Demo"
    assert result["revendas"][0]["revenda"] == "Revenda Demo"
    assert result["revendas"][0]["atendimentos"] == 1
    assert result["mapeamento"]["cliente"] == "Contact ID"
    assert result["mapeamento"]["contato"] == "Contact Number"
    assert result["mapeamento"]["revenda"] == "Revenda"


def test_automatic_closures_follow_the_regular_duration_rule() -> None:
    rows = [
        f"{index},Ana,31/08/2026 10:{index:02d},01/09/2026 02:47,Suporte,,5"
        for index in range(20)
    ]
    rows.append("normal,Ana,31/08/2026 10:30,31/08/2026 11:30,Suporte,,5")
    result = process_upload(csv_bytes(*rows), "automaticos.csv", "08/2026")
    assert len(result["validos"]) == 1
    assert result["estatisticas"]["AUTOMATICOS_VALIDOS"] == 0
    assert result["estatisticas"]["AUTOMATICOS_EXCLUIDOS"] == 20
    assert result["ranking"][0]["notaFinal"] == 100


def test_only_top_three_eligible_are_awarded() -> None:
    rows = []
    for employee_index, (name, rating) in enumerate(
        [("Ana", 5), ("Bruna", 4.9), ("Carla", 4.8), ("Diana", 4.7)], start=1
    ):
        for row_index in range(10):
            rows.append(
                f"{employee_index}-{row_index},{name},10/08/2026 10:{row_index:02d},"
                f"10/08/2026 11:{row_index:02d},Suporte,,{rating}"
            )
    result = process_upload(csv_bytes(*rows), "ranking.csv", "08/2026")
    assert all(row["elegivel"] for row in result["ranking"])
    assert [row["atendente"] for row in result["ranking"] if row["premiado"]] == ["Ana", "Bruna", "Carla"]


def test_partial_exclusion_and_invalid_rating_are_auditable() -> None:
    result = process_upload(
        csv_bytes(
            "1,Fabíola Santos,10/08/2026 10:00,10/08/2026 11:00,Suporte,,5",
            "2,Ana Sofia,10/08/2026 10:00,10/08/2026 11:00,Suporte,,8",
        ),
        "nomes.csv",
        "08/2026",
        "Fabíola",
    )
    assert [row["atendente"] for row in result["validos"]] == ["Ana Sofia"]
    assert result["validos"][0]["avaliacao"] is None
    assert result["excluidos"][0]["motivoCodigo"] == "ATENDENTE_EXCLUIDO"
