"""Leitura, qualidade, validação e cálculo da premiação."""

from .engine import detect_competence, process_upload
from .rules import META_ELEGIBILIDADE, official_config

__all__ = ["META_ELEGIBILIDADE", "detect_competence", "official_config", "process_upload"]

