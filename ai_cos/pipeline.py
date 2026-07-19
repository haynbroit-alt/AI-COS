"""Alias de compatibilité — module déplacé vers ai_cos.product.pipeline."""
from ai_cos.product.pipeline import (  # noqa: F401
    CONSTITUTION_FILE, REQUIRED_TEST_KINDS, ControlPipeline, ControlledMission,
    PipelineError, Plan, Stage, TestReport, Verdict,
)
