"""Parâmetros explícitos; os pesos continuam na referência histórica original."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, time
import re

from backend.app.pipeline.rules import RuleConfig, official_config

PIPELINE_VERSION = "1"
MINUTES_PER_HOUR = 60
SECONDS_PER_HOUR = 3600
DATE_FORMAT = "%d/%m/%Y %H:%M"


@dataclass(frozen=True)
class PipelineConfig:
    competencia: str = "2026-08"
    excluded_attendants: tuple[str, ...] = ("Diego Demo",)
    business_start: time = time(8)
    business_end_exclusive: time = time(20)
    allowed_weekdays: tuple[int, ...] = (0, 1, 2, 3, 4, 5)
    max_awards: int = 3

    def __post_init__(self) -> None:
        if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", self.competencia):
            raise ValueError("Competência inválida. Use AAAA-MM.")
        date.fromisoformat(f"{self.competencia}-01")
        if self.business_start >= self.business_end_exclusive:
            raise ValueError("O fim do expediente deve ser posterior ao início.")
        if not self.allowed_weekdays or any(day not in range(7) for day in self.allowed_weekdays):
            raise ValueError("Dias permitidos devem estar entre 0 (segunda) e 6 (domingo).")
        if self.max_awards < 1:
            raise ValueError("O limite de premiados deve ser positivo.")

    @property
    def rules(self) -> RuleConfig:
        return official_config(self.competencia)

    def to_dict(self) -> dict[str, object]:
        return {
            "pipeline_version": PIPELINE_VERSION,
            "competencia": self.competencia,
            "excluded_attendants": list(self.excluded_attendants),
            "business_start": self.business_start.isoformat(),
            "business_end_exclusive": self.business_end_exclusive.isoformat(),
            "allowed_weekdays": list(self.allowed_weekdays),
            "max_awards": self.max_awards,
            "duplicate_policy": "quarantine_all_within_start_month",
            "rules": asdict(self.rules),
        }
