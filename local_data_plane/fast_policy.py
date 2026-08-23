"""Simplicio Fast policy boundary for local speculative execution.

Fast owns selection; Local owns capability truth and execution.  This module
keeps that boundary explicit and fail-closed when the policy service is not
available or returns an unsupported strategy.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


FAST_POLICY_SCHEMA_V1 = "simplicio-local.fast-policy/v1"
_STRATEGIES = {"baseline", "ngram_prompt_lookup", "draft_model", "dflash", "mtp"}


@dataclass(frozen=True)
class FastPolicyRequest:
    model_id: str
    backend: str
    workload: str
    capabilities: tuple[str, ...] = ()
    hardware: Mapping[str, Any] = field(default_factory=dict)
    mode: str = "auto"
    explicit_strategy: str | None = None
    max_draft_tokens: int = 4

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": FAST_POLICY_SCHEMA_V1,
            "model_id": self.model_id,
            "backend": self.backend,
            "workload": self.workload,
            "capabilities": list(self.capabilities),
            "hardware": dict(self.hardware),
            "mode": self.mode,
            "explicit_strategy": self.explicit_strategy,
            "max_draft_tokens": self.max_draft_tokens,
        }


@dataclass(frozen=True)
class FastPolicyPlan:
    strategy: str
    fallback: str
    max_draft_tokens: int
    explanation: str
    evidence: tuple[str, ...] = ()
    used_fallback: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": FAST_POLICY_SCHEMA_V1,
            "strategy": self.strategy,
            "fallback": self.fallback,
            "max_draft_tokens": self.max_draft_tokens,
            "explanation": self.explanation,
            "evidence": list(self.evidence),
            "used_fallback": self.used_fallback,
        }


@dataclass(frozen=True)
class FastRunReceipt:
    request: FastPolicyRequest
    plan: FastPolicyPlan
    status: str = "planned"

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": FAST_POLICY_SCHEMA_V1,
            "status": self.status,
            "request": self.request.as_dict(),
            "plan": self.plan.as_dict(),
        }


def _strategy(value: object, *, field_name: str = "strategy") -> str:
    if not isinstance(value, str) or value not in _STRATEGIES:
        raise ValueError(f"{field_name} must be one of {sorted(_STRATEGIES)}")
    return value


def _bounded_tokens(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 64:
        raise ValueError("max_draft_tokens must be an integer from 1 to 64")
    return value


def _parse_plan(payload: Mapping[str, Any], request: FastPolicyRequest) -> FastPolicyPlan:
    selected = _strategy(payload.get("strategy"))
    fallback = _strategy(payload.get("fallback", "baseline"), field_name="fallback")
    tokens = _bounded_tokens(payload.get("max_draft_tokens", request.max_draft_tokens))
    evidence = payload.get("evidence", ())
    if not isinstance(evidence, (list, tuple)) or not all(isinstance(item, str) for item in evidence):
        raise ValueError("evidence must be a list of strings")
    explanation = payload.get("explanation")
    if not isinstance(explanation, str) or not explanation.strip():
        raise ValueError("explanation is required")
    return FastPolicyPlan(selected, fallback, tokens, explanation.strip(), tuple(evidence), False)


def _baseline(request: FastPolicyRequest, reason: str) -> FastPolicyPlan:
    return FastPolicyPlan("baseline", "baseline", 1, reason, ("local-fail-closed",), True)


class JsonFastPolicyBridge:
    """Call an installed Fast policy command using a JSON stdin/stdout contract."""

    def __init__(self, command: Sequence[str], *, timeout: float = 10.0):
        if not command:
            raise ValueError("Fast policy command cannot be empty")
        self.command = tuple(command)
        self.timeout = timeout

    def __call__(self, request: FastPolicyRequest) -> Mapping[str, Any]:
        completed = subprocess.run(
            self.command,
            input=json.dumps(request.as_dict()),
            capture_output=True,
            text=True,
            timeout=self.timeout,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(f"Fast policy command exited with {completed.returncode}")
        payload = json.loads(completed.stdout)
        if not isinstance(payload, dict):
            raise ValueError("Fast policy response must be a JSON object")
        return payload


class FastPolicyClient:
    """Resolve mode precedence and keep baseline available at every failure."""

    def __init__(self, provider: Callable[[FastPolicyRequest], Mapping[str, Any]] | None = None):
        self.provider = provider

    @staticmethod
    def request_from_env(**kwargs: Any) -> FastPolicyRequest:
        mode = str(kwargs.pop("mode", os.environ.get("SIMPLICIO_FAST", "auto"))).lower()
        if mode not in {"auto", "off", *_STRATEGIES}:
            raise ValueError("SIMPLICIO_FAST must be auto, off, or a supported strategy")
        explicit = kwargs.pop("explicit_strategy", None)
        if mode not in {"auto", "off"}:
            explicit = mode
            mode = "explicit"
        if explicit is not None:
            _strategy(explicit, field_name="explicit_strategy")
        return FastPolicyRequest(mode=mode, explicit_strategy=explicit, **kwargs)

    def select(self, request: FastPolicyRequest) -> FastPolicyPlan:
        if not request.model_id.strip() or not request.backend.strip():
            raise ValueError("model_id and backend are required")
        if request.mode == "off":
            return FastPolicyPlan("baseline", "baseline", 1, "Fast disabled by explicit override", ("fast-off",))
        if request.mode == "explicit":
            selected = _strategy(request.explicit_strategy, field_name="explicit_strategy")
            if selected not in request.capabilities:
                return _baseline(request, f"Explicit strategy {selected} is not proven for this model/backend")
            return FastPolicyPlan(selected, "baseline", _bounded_tokens(request.max_draft_tokens),
                                  f"Explicit Fast strategy selected: {selected}", ("explicit-override",))
        if request.mode != "auto":
            raise ValueError("mode must be auto, explicit, or off")
        if self.provider is None:
            return _baseline(request, "Fast policy is unavailable; baseline decoding selected")
        try:
            plan = _parse_plan(self.provider(request), request)
        except (OSError, RuntimeError, ValueError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
            return _baseline(request, f"Fast policy failed safely: {exc}")
        if plan.strategy != "baseline" and plan.strategy not in request.capabilities:
            return _baseline(request, f"Fast returned unproven strategy {plan.strategy}; baseline selected")
        return plan

    def receipt(self, request: FastPolicyRequest) -> FastRunReceipt:
        return FastRunReceipt(request, self.select(request))


def write_receipt(receipt: FastRunReceipt, path: str | os.PathLike[str]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(receipt.as_dict(), stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
