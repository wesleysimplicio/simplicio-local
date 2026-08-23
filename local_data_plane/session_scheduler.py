"""Multi-session admission, KV isolation and bounded backpressure."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


SESSION_SCHEDULER_SCHEMA_V1 = "simplicio-local.session-scheduler/v1"


@dataclass(frozen=True)
class SessionRequest:
    session_id: str
    kv_bytes: int
    model_id: str
    template_hash: str
    priority: int = 0


@dataclass(frozen=True)
class AdmissionDecision:
    accepted: bool
    status: str
    retry_after_ms: int | None
    reason: str


class MultiSessionScheduler:
    def __init__(self, *, memory_budget_bytes: int, kv_budget_bytes: int, max_sessions: int = 8,
                 batch_evidence: Mapping[str, float] | None = None):
        if min(memory_budget_bytes, kv_budget_bytes) < 0 or max_sessions < 1:
            raise ValueError("budgets must be non-negative and max_sessions positive")
        self.memory_budget_bytes = memory_budget_bytes
        self.kv_budget_bytes = kv_budget_bytes
        self.max_sessions = max_sessions
        self.batch_evidence = dict(batch_evidence or {})
        self._sessions: dict[str, SessionRequest] = {}

    def admit(self, request: SessionRequest) -> AdmissionDecision:
        if not request.session_id or request.kv_bytes < 0:
            raise ValueError("session_id and non-negative kv_bytes are required")
        if request.session_id in self._sessions:
            return AdmissionDecision(True, "reused", None, "session already owns an isolated KV budget")
        if len(self._sessions) >= self.max_sessions:
            return AdmissionDecision(False, "busy", 250, "session limit reached; retry after a bounded delay")
        used = sum(session.kv_bytes for session in self._sessions.values())
        if used + request.kv_bytes > self.kv_budget_bytes or used + request.kv_bytes > self.memory_budget_bytes:
            return AdmissionDecision(False, "busy", 500, "KV/memory budget reached; request was not admitted")
        self._sessions[request.session_id] = request
        return AdmissionDecision(True, "accepted", None, "session admitted with isolated KV allocation")

    def cancel(self, session_id: str) -> bool:
        return self._sessions.pop(session_id, None) is not None

    def form_batch(self, session_ids: list[str]) -> tuple[str, ...]:
        if not session_ids or any(session_id not in self._sessions for session_id in session_ids):
            return ()
        speedup = float(self.batch_evidence.get("throughput_gain", 0.0))
        p95 = float(self.batch_evidence.get("p95_regression", 1.0))
        if speedup < 0.02 or p95 > 0.10:
            return tuple(session_ids[:1])
        return tuple(sorted(session_ids, key=lambda session_id: (-self._sessions[session_id].priority, session_id)))

    def status(self) -> dict[str, Any]:
        used = sum(session.kv_bytes for session in self._sessions.values())
        return {"schema": SESSION_SCHEDULER_SCHEMA_V1, "active_sessions": len(self._sessions),
                "kv_used_bytes": used, "kv_budget_bytes": self.kv_budget_bytes,
                "sessions": {session_id: {"model_id": session.model_id, "template_hash": session.template_hash}
                             for session_id, session in self._sessions.items()}}
