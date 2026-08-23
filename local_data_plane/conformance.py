"""Release conformance gates for installed microarchitecture-aware inference."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Mapping, Sequence


CONFORMANCE_SCHEMA_V1 = "simplicio-local.release-conformance/v1"


@dataclass(frozen=True)
class Gate:
    name: str
    passed: bool
    reason: str
    waiver_allowed: bool = False


def run_conformance(evidence: Mapping[str, Any], *, chaos_cases: Sequence[str] = ()) -> dict[str, Any]:
    gates: list[Gate] = []
    gates.append(Gate("correctness", bool(evidence.get("correctness")),
                      "backend-compatible output equivalence" if evidence.get("correctness") else "correctness evidence missing"))
    endpoints = evidence.get("endpoints", {})
    for name in ("models", "chat_completions", "completions"):
        supported = endpoints.get(name)
        if supported is False:
            gates.append(Gate(f"endpoint:{name}", True, "endpoint not supported by backend", True))
        else:
            gates.append(Gate(f"endpoint:{name}", supported is True, "endpoint smoke passed" if supported is True else "endpoint smoke missing"))
    gates.append(Gate("baseline-available", bool(evidence.get("baseline_available")),
                      "baseline fallback is present" if evidence.get("baseline_available") else "baseline fallback missing"))
    gates.append(Gate("artifact-provenance", bool(evidence.get("artifact_sha256") and evidence.get("backend_identity")),
                      "artifact and backend identity pinned" if evidence.get("artifact_sha256") and evidence.get("backend_identity") else "artifact/backend identity missing"))
    gates.append(Gate("oom-safety", evidence.get("oom_safe") is True,
                      "safe plan stayed within budget" if evidence.get("oom_safe") is True else "OOM safety failure"))
    for case in chaos_cases:
        result = bool((evidence.get("chaos") or {}).get(case, False))
        gates.append(Gate(f"chaos:{case}", result, "chaos case handled" if result else "chaos case failed"))
    hard_failures = [gate.name for gate in gates if not gate.passed and not gate.waiver_allowed]
    performance = evidence.get("performance", {})
    if performance.get("regressed"):
        gates.append(Gate("performance-budget", False, "optimization disabled or explicit waiver required", True))
    return {"schema": CONFORMANCE_SCHEMA_V1, "status": "passed" if not hard_failures else "blocked",
            "gates": [asdict(gate) for gate in gates], "blockers": hard_failures,
            "evidence_digest": evidence.get("plan_digest"), "ready": not hard_failures}
