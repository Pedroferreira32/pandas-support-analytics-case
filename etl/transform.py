"""Agregações nomeadas e pontuação vetorizada, sem loop por atendente."""
from __future__ import annotations

import pandas as pd

from .config import PipelineConfig
from .validate import normalize_text

RANKING_DTYPES = {
    "atendente": "string", "atendimentos": "int64", "horas_total": "float64",
    "tma_medio_min": "float64", "tma_mediano_min": "float64", "tma_p90_min": "float64",
    "avaliacao_media": "float64", "avaliacoes": "int64", "cobertura_avaliacao": "float64",
    "automaticos": "int64", "pontos_quantidade": "float64", "pontos_tempo": "float64",
    "pontos_tma": "float64", "pontos_avaliacao": "float64", "nota_final": "float64",
    "posicao": "int64", "elegivel": "bool", "premiado": "bool",
}


def transform(valid: pd.DataFrame, config: PipelineConfig) -> pd.DataFrame:
    if valid.empty:
        return pd.DataFrame({column: pd.Series(dtype=dtype) for column, dtype in RANKING_DTYPES.items()})
    grouped = valid.groupby("atendente", sort=False, observed=True)
    ranking = grouped.agg(
        atendimentos=("protocolo", "size"), horas_total=("duracao_horas", "sum"),
        tma_medio_min=("tma_minutos", "mean"), tma_mediano_min=("tma_minutos", "median"),
        avaliacao_media=("avaliacao", "mean"), avaliacoes=("avaliacao", "count"),
        automaticos=("suspeito_automatico", "sum"),
    ).join(grouped["tma_minutos"].quantile(0.9, interpolation="linear").rename("tma_p90_min")).reset_index()
    ranking["cobertura_avaliacao"] = ranking["avaliacoes"].div(ranking["atendimentos"]).mul(100)
    rules = config.rules
    for metric, points, weight in (
        ("atendimentos", "pontos_quantidade", rules.peso_quantidade),
        ("horas_total", "pontos_tempo", rules.peso_tempo),
        ("avaliacao_media", "pontos_avaliacao", rules.peso_avaliacao),
    ):
        maximum = ranking[metric].max()
        ranking[points] = ranking[metric].div(maximum).mul(weight).fillna(0) if pd.notna(maximum) and maximum > 0 else 0.0
    positive_tma = ranking["tma_medio_min"].where(ranking["tma_medio_min"].gt(0))
    ranking["pontos_tma"] = positive_tma.rdiv(positive_tma.min()).mul(rules.peso_tma).fillna(0)
    ranking["nota_final"] = ranking[["pontos_quantidade", "pontos_tempo", "pontos_tma", "pontos_avaliacao"]].sum(axis=1)
    ranking["ordem_nome"] = normalize_text(ranking["atendente"])
    ranking = ranking.sort_values(
        ["nota_final", "atendimentos", "avaliacao_media", "ordem_nome", "atendente"],
        ascending=[False, False, False, True, True], na_position="last", kind="stable",
    ).drop(columns="ordem_nome").reset_index(drop=True)
    ranking["posicao"] = range(1, len(ranking) + 1)
    ranking["elegivel"] = ranking["nota_final"].ge(rules.nota_minima)
    ranking["premiado"] = ranking["elegivel"] & ranking["elegivel"].cumsum().le(config.max_awards)
    return ranking[list(RANKING_DTYPES)].astype(RANKING_DTYPES)
