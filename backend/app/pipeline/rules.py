from __future__ import annotations

from dataclasses import asdict, dataclass
import re


META_ELEGIBILIDADE = 85.0


@dataclass(frozen=True)
class RuleConfig:
    competencia: str
    perfil_regra: str
    modo: str
    max_horas: float
    escala_avaliacao_max: float
    peso_quantidade: float
    peso_tempo: float
    peso_tma: float
    peso_avaliacao: float
    incluir_fora_expediente: bool
    incluir_finalizados_automaticamente: bool
    neutralizar_tempo_automaticos: bool
    pontuacao_tempo_tma_fixa: bool
    nota_minima: float
    hora_inicio: str
    hora_fim: str
    teto_pontuacao: float

    def to_api(self) -> dict[str, object]:
        values = asdict(self)
        aliases = {
            "perfil_regra": "perfilRegra",
            "max_horas": "maxHoras",
            "escala_avaliacao_max": "escalaAvaliacaoMax",
            "peso_quantidade": "pesoQuantidade",
            "peso_tempo": "pesoTempo",
            "peso_tma": "pesoTma",
            "peso_avaliacao": "pesoAvaliacao",
            "incluir_fora_expediente": "incluirForaExpediente",
            "incluir_finalizados_automaticamente": "incluirFinalizadosAutomaticamente",
            "neutralizar_tempo_automaticos": "neutralizarTempoAutomaticos",
            "pontuacao_tempo_tma_fixa": "pontuacaoTempoTmaFixa",
            "nota_minima": "notaMinima",
            "hora_inicio": "horaInicio",
            "hora_fim": "horaFim",
            "teto_pontuacao": "tetoPontuacao",
        }
        return {aliases.get(key, key): value for key, value in values.items()}


def official_config(competencia: str) -> RuleConfig:
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", competencia):
        raise ValueError("Competência inválida. Use o formato AAAA-MM.")

    base = RuleConfig(
        competencia=competencia,
        perfil_regra="Novo modelo oficial — 100 pontos com Tempo e TMA separados",
        modo="padrao",
        max_horas=9,
        escala_avaliacao_max=5,
        peso_quantidade=20,
        peso_tempo=10,
        peso_tma=30,
        peso_avaliacao=40,
        incluir_fora_expediente=False,
        incluir_finalizados_automaticamente=False,
        neutralizar_tempo_automaticos=False,
        pontuacao_tempo_tma_fixa=False,
        nota_minima=META_ELEGIBILIDADE,
        hora_inicio="08:00",
        hora_fim="19:59",
        teto_pontuacao=100.0,
    )

    if competencia <= "2026-05":
        return RuleConfig(
            **{
                **asdict(base),
                "perfil_regra": "Modelo histórico — 100 pontos; Tempo Total e TMA separados",
                "max_horas": 8,
                "escala_avaliacao_max": 10,
                "peso_quantidade": 30,
                "peso_tempo": 15,
                "peso_tma": 25,
                "peso_avaliacao": 30,
            }
        )

    return base
