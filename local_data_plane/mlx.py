"""MLX-LM/native MLX probe and promotion gate."""

from __future__ import annotations

import importlib.util
import platform
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .registry import EvidenceLevel


@dataclass(frozen=True)
class MlxProbe:
    apple_silicon: bool
    mlx_lm_importable: bool
    native_source_present: bool
    available: bool
    reason: str


@dataclass(frozen=True)
class PromotionResult:
    promoted: bool
    evidence_level: EvidenceLevel
    reason: str
    requested_backend: str
    effective_backend: str | None
    artifact_refs: tuple[str, ...] = ()


class MlxProvider:
    def __init__(self, repo_root: str | Path | None = None):
        self.repo_root = Path(repo_root or Path.cwd())

    def probe(self) -> MlxProbe:
        apple = platform.system() == "Darwin" and platform.machine().lower() in {"arm64", "aarch64"}
        importable = importlib.util.find_spec("mlx_lm") is not None
        native = (self.repo_root / "runtime/mlx/native_mlx_backend.cpp").is_file()
        if not apple:
            return MlxProbe(False, importable, native, False, "MLX requires Apple Silicon")
        if not importable:
            return MlxProbe(True, False, native, False, "mlx_lm is not importable")
        return MlxProbe(True, True, native, True, "MLX-LM import probe passed")


class MlxPromotionGate:
    """Promotion is evidence-driven and never inferred from source presence."""

    @staticmethod
    def compare_outputs(reference: Sequence[str], candidate: Sequence[str]) -> bool:
        return list(reference) == list(candidate)

    def promote_fixture(self, reference: Sequence[str], candidate: Sequence[str], artifact: str) -> PromotionResult:
        if not self.compare_outputs(reference, candidate):
            return PromotionResult(False, EvidenceLevel.SOURCE_PRESENT, "fixture output mismatch", "mlx", None)
        return PromotionResult(True, EvidenceLevel.FIXTURE_EXECUTED, "fixture parity passed", "mlx", "mlx", (artifact,))

    def promote_real_model(self, reference: Sequence[str], candidate: Sequence[str], *, model: str,
                           hardware: str, elapsed_ms: float, artifact: str) -> PromotionResult:
        if not model or not hardware or elapsed_ms < 0:
            return PromotionResult(False, EvidenceLevel.FIXTURE_EXECUTED, "model, hardware and timing are required", "mlx", None)
        if not self.compare_outputs(reference, candidate):
            return PromotionResult(False, EvidenceLevel.FIXTURE_EXECUTED, "real-model parity mismatch", "mlx", None)
        return PromotionResult(True, EvidenceLevel.REAL_MODEL_EXECUTED,
                               f"real model parity passed on {hardware}", "mlx", "mlx", (artifact,))

    def promote_benchmark(self, real: PromotionResult, *, hardware: str, model: str,
                          tokens: int, elapsed_ms: float, artifact: str) -> PromotionResult:
        if not real.promoted or real.evidence_level < EvidenceLevel.REAL_MODEL_EXECUTED:
            return PromotionResult(False, real.evidence_level, "real-model evidence is required before benchmark promotion", "mlx", None)
        if not hardware or not model or tokens <= 0 or elapsed_ms <= 0:
            return PromotionResult(False, real.evidence_level, "benchmark metadata is incomplete", "mlx", None)
        return PromotionResult(True, EvidenceLevel.BENCHMARKED_ON_TARGET,
                               f"{tokens / (elapsed_ms / 1000.0):.3f} tokens/s observed", "mlx", "mlx", (artifact,))
