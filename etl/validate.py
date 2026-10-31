"""Conversão explícita e regras independentes que devolvem máscaras booleanas."""
from __future__ import annotations

from dataclasses import dataclass
import re

import pandas as pd

from .config import DATE_FORMAT, MINUTES_PER_HOUR, SECONDS_PER_HOUR, PipelineConfig

INVALID_ATTENDANTS = {"", "-", "NAN", "NAT", "NONE", "NULL", "PENDENTE", "SEM ATENDENTE", "NAO INFORMADO"}


def normalize_text(series: pd.Series) -> pd.Series:
    return (series.astype("string").fillna("").str.strip().str.normalize("NFD")
            .str.replace(r"[\u0300-\u036f]", "", regex=True).str.upper())


def prepare(frame: pd.DataFrame, config: PipelineConfig) -> pd.DataFrame:
    data = frame.copy()
    data["protocolo_raw"] = data["protocolo"]
    data["atendente_raw"] = data["atendente"]
    data["protocolo"] = data["protocolo"].str.strip()
    data["protocolo_chave"] = data["protocolo"].str.casefold()
    data["atendente"] = data["atendente"].str.strip()
    data["atendente_normalizado"] = normalize_text(data["atendente"])
    # Cada coluna é convertida uma vez; a duração utiliza diretamente datetime64.
    for field in ("inicio", "fim"):
        data[field] = pd.to_datetime(data[f"{field}_raw"].str.strip(), format=DATE_FORMAT, errors="coerce")
    data["competencia_registro"] = data["inicio"].dt.strftime("%Y-%m").astype("string")
    data["duracao_horas"] = (data["fim"] - data["inicio"]).dt.total_seconds() / SECONDS_PER_HOUR
    data["tma_minutos"] = data["duracao_horas"] * MINUTES_PER_HOUR
    numeric_rating = pd.to_numeric(data["avaliacao_raw"].str.strip().str.replace(",", ".", regex=False), errors="coerce")
    data["avaliacao"] = numeric_rating.where(numeric_rating.between(0, config.rules.escala_avaliacao_max)).astype("Float64")
    # Não se escolhe arbitrariamente qual cópia é correta: todas ficam em quarentena.
    data["protocolo_duplicado"] = (
        data.duplicated(["competencia_registro", "protocolo_chave"], keep=False)
        & data["protocolo_chave"].ne("")
    )
    end_minute = data["fim"].dt.floor("min")
    repeated_end = end_minute.map(end_minute.value_counts()).fillna(0).ge(20)
    data["suspeito_automatico"] = (
        (data["fim"].dt.hour.eq(6) & data["fim"].dt.minute.eq(0)) | repeated_end
    )
    return data


def outside_support(data: pd.DataFrame, config: PipelineConfig) -> pd.Series:
    return ~(normalize_text(data["setores"]).str.contains("SUPORTE", regex=False)
             | normalize_text(data["transferencias"]).str.contains("SUPORTE", regex=False))


def missing_attendant(data: pd.DataFrame, config: PipelineConfig) -> pd.Series:
    return data["atendente_normalizado"].isin(INVALID_ATTENDANTS)


def excluded_attendant(data: pd.DataFrame, config: PipelineConfig) -> pd.Series:
    names = normalize_text(pd.Series(config.excluded_attendants, dtype="string"))
    pattern = "|".join(re.escape(value) for value in names if value)
    return data["atendente_normalizado"].str.contains(pattern, regex=True) if pattern else pd.Series(False, index=data.index)


def invalid_start(data: pd.DataFrame, config: PipelineConfig) -> pd.Series:
    return data["inicio"].isna()


def invalid_end(data: pd.DataFrame, config: PipelineConfig) -> pd.Series:
    return data["fim"].isna()


def negative_duration(data: pd.DataFrame, config: PipelineConfig) -> pd.Series:
    return data["duracao_horas"].lt(0)


def excessive_duration(data: pd.DataFrame, config: PipelineConfig) -> pd.Series:
    return data["duracao_horas"].gt(config.rules.max_horas)


def outside_business_hours(data: pd.DataFrame, config: PipelineConfig) -> pd.Series:
    start = config.business_start.hour * MINUTES_PER_HOUR + config.business_start.minute
    end = config.business_end_exclusive.hour * MINUTES_PER_HOUR + config.business_end_exclusive.minute
    minute = data["inicio"].dt.hour * MINUTES_PER_HOUR + data["inicio"].dt.minute
    return (~data["inicio"].dt.dayofweek.isin(config.allowed_weekdays) | minute.lt(start) | minute.ge(end))


def outside_month(data: pd.DataFrame, config: PipelineConfig) -> pd.Series:
    return data["competencia_registro"].ne(config.competencia)


def missing_protocol(data: pd.DataFrame, config: PipelineConfig) -> pd.Series:
    return data["protocolo"].eq("")


def duplicate_protocol(data: pd.DataFrame, config: PipelineConfig) -> pd.Series:
    return data["protocolo_duplicado"]


# A ordem é parte do contrato: um motivo principal por registro, sem dupla contagem.
RULES = (
    ("FORA_SUPORTE", outside_support),
    ("SEM_ATENDENTE", missing_attendant),
    ("ATENDENTE_EXCLUIDO", excluded_attendant),
    ("DATA_INVALIDA", invalid_start),
    ("SEM_FINALIZACAO", invalid_end),
    ("DURACAO_NEGATIVA", negative_duration),
    ("ACIMA_H", excessive_duration),
    ("PERIODO", outside_business_hours),
    ("FORA_COMPETENCIA", outside_month),
    ("SEM_PROTOCOLO", missing_protocol),
    ("PROTOCOLO_DUPLICADO", duplicate_protocol),
)


@dataclass(frozen=True)
class ValidationResult:
    classified: pd.DataFrame
    valid: pd.DataFrame
    excluded: pd.DataFrame
    rule_counts: dict[str, dict[str, int]]


def validate(frame: pd.DataFrame, config: PipelineConfig) -> ValidationResult:
    data = prepare(frame, config)
    reason = pd.Series(pd.NA, index=data.index, dtype="string")
    counts = {}
    for code, rule in RULES:
        mask = rule(data, config).fillna(False).astype(bool)
        selected = reason.isna() & mask
        reason.loc[selected] = code
        counts[code] = {"detectados": int(mask.sum()), "motivo_principal": int(selected.sum())}
    data["motivo_codigo"] = reason
    valid = data.loc[reason.isna()].copy()
    excluded = data.loc[reason.notna()].copy()
    if len(data) != len(valid) + len(excluded):
        raise AssertionError("A classificação não reconciliou a entrada.")
    return ValidationResult(data, valid, excluded, counts)
