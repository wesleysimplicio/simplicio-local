"""Explainable natural-language model request parsing and resolution."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable


MODEL_RESOLUTION_SCHEMA_V1 = "simplicio-local.model-resolution/v1"
_FAMILY_ALIASES = {
    "qwen": "qwen",
    "qwen2": "qwen",
    "qwen3": "qwen",
    "llama": "llama",
    "llama2": "llama",
    "llama3": "llama",
    "mistral": "mistral",
    "mixtral": "mistral",
}
_QUANT_RE = re.compile(r"\b(q\d(?:_[a-z0-9]+)*|int[248]|bf16|fp16)\b", re.IGNORECASE)
_PARAM_RE = re.compile(r"\b(\d+(?:\.\d+)?)\s*[bB]\b")
_VERSION_RE = re.compile(r"\b(?:qwen|llama|mistral|mixtral)[-_ ]?(\d+(?:\.\d+)*)", re.IGNORECASE)


@dataclass(frozen=True)
class ModelRequest:
    raw: str
    family: str | None = None
    version: str | None = None
    parameter_billions: float | None = None
    quantization: str | None = None
    workload: str | None = None
    explicit_id: str | None = None
    explicit_url: str | None = None


@dataclass(frozen=True)
class ModelCandidate:
    model_id: str
    family: str
    version: str
    parameter_billions: float
    quantization: str
    source_url: str
    size_bytes: int
    backend_compatibility: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()
    workload_intents: tuple[str, ...] = ()


@dataclass(frozen=True)
class ResolutionResult:
    status: str
    request: ModelRequest
    selected: ModelCandidate | None
    alternatives: tuple[ModelCandidate, ...] = ()
    explanation: str = ""

    def as_dict(self) -> dict[str, object]:
        def candidate(value: ModelCandidate | None) -> dict[str, object] | None:
            return value.__dict__.copy() if value else None
        return {
            "schema": MODEL_RESOLUTION_SCHEMA_V1,
            "status": self.status,
            "request": self.request.__dict__.copy(),
            "selected": candidate(self.selected),
            "alternatives": [candidate(item) for item in self.alternatives],
            "explanation": self.explanation,
        }


def parse_model_request(text: str, *, explicit_id: str | None = None,
                        explicit_url: str | None = None) -> ModelRequest:
    raw = text.strip()
    if not raw and not explicit_id and not explicit_url:
        raise ValueError("model request cannot be empty")
    lowered = raw.casefold()
    family = None
    for alias, canonical in _FAMILY_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", lowered):
            family = canonical
            break
    version_match = _VERSION_RE.search(raw)
    quant_match = _QUANT_RE.search(raw)
    param_match = _PARAM_RE.search(raw)
    workload = next((name for name in ("coding", "reasoning", "chat", "embedding") if name in lowered), None)
    return ModelRequest(
        raw=raw,
        family=family,
        version=version_match.group(1) if version_match else None,
        parameter_billions=float(param_match.group(1)) if param_match else None,
        quantization=quant_match.group(1).upper() if quant_match else None,
        workload=workload,
        explicit_id=explicit_id,
        explicit_url=explicit_url,
    )


class ModelResolver:
    def __init__(self, candidates: Iterable[ModelCandidate]):
        self.candidates = tuple(candidates)
        if not self.candidates:
            raise ValueError("at least one model candidate is required")

    @staticmethod
    def _score(request: ModelRequest, candidate: ModelCandidate) -> int:
        score = 0
        if request.family:
            score += 10 if candidate.family == request.family else -100
        if request.version:
            score += 8 if candidate.version == request.version else -30
        if request.parameter_billions is not None:
            score += 8 if candidate.parameter_billions == request.parameter_billions else -30
        if request.quantization:
            score += 8 if candidate.quantization.casefold() == request.quantization.casefold() else -20
        if request.workload:
            score += 2 if request.workload in candidate.workload_intents else 0
        normalized = request.raw.casefold()
        if candidate.model_id.casefold() in normalized or any(alias.casefold() in normalized for alias in candidate.aliases):
            score += 12
        return score

    def resolve(self, request: ModelRequest) -> ResolutionResult:
        if request.explicit_id or request.explicit_url:
            matches = tuple(candidate for candidate in self.candidates
                            if (request.explicit_id and candidate.model_id == request.explicit_id)
                            or (request.explicit_url and candidate.source_url == request.explicit_url))
            if len(matches) == 1:
                return ResolutionResult("resolved", request, matches[0], (),
                                        "Explicit model identity override matched exactly")
            return ResolutionResult("unsupported", request, None, self.candidates[:3],
                                    "Explicit model identity did not match the trusted candidate set")
        scored = sorted(((self._score(request, candidate), candidate) for candidate in self.candidates),
                        key=lambda pair: (-pair[0], pair[1].model_id))
        if not request.family or scored[0][0] < 0:
            return ResolutionResult("ambiguous", request, None,
                                    tuple(candidate for _, candidate in scored[:3]),
                                    "Request is missing a supported family or has conflicting constraints")
        best_score, best = scored[0]
        if len(scored) > 1 and scored[1][0] == best_score:
            return ResolutionResult("ambiguous", request, None,
                                    tuple(candidate for _, candidate in scored[:3]),
                                    "Multiple artifacts match equally; add version, size, or quantization")
        if best_score < 10:
            return ResolutionResult("unsupported", request, None,
                                    tuple(candidate for _, candidate in scored[:3]),
                                    "No candidate satisfies the requested family and artifact constraints")
        return ResolutionResult("resolved", request, best, tuple(candidate for _, candidate in scored[1:3]),
                                f"Resolved {best.family} {best.version} {best.parameter_billions:g}B "
                                f"{best.quantization} from {best.source_url}")


def resolve_model(text: str, candidates: Iterable[ModelCandidate], *, explicit_id: str | None = None,
                  explicit_url: str | None = None) -> ResolutionResult:
    return ModelResolver(candidates).resolve(parse_model_request(text, explicit_id=explicit_id, explicit_url=explicit_url))
