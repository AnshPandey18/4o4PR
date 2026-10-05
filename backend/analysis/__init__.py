"""Root-cause analysis agent package."""

from .root_cause_agent import (
    AnalysisResult,
    OpenAICompatibleClient,
    RootCauseAnalysisAgent,
    RootCauseAnalysisError,
)
from .patch_generator import PatchCandidate, PatchGenerationError, PatchGenerator
from .patch_applier import PatchApplicationError, PatchApplicationResult, PatchApplier
from .validator import TestValidator, ValidationResult
from .reporting import ExplanationGenerator, build_pr_body

__all__ = [
    "AnalysisResult",
    "OpenAICompatibleClient",
    "RootCauseAnalysisAgent",
    "RootCauseAnalysisError",
    "PatchCandidate",
    "PatchGenerationError",
    "PatchGenerator",
    "PatchApplicationError",
    "PatchApplicationResult",
    "PatchApplier",
    "TestValidator",
    "ValidationResult",
    "ExplanationGenerator",
    "build_pr_body",
]