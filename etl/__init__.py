"""Pipeline local e auditável de atendimentos fictícios."""

from .config import PipelineConfig
from .pipeline import PipelineResult, run_pipeline

__all__ = ["PipelineConfig", "PipelineResult", "run_pipeline"]
