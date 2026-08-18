"""Runtime v2 control-plane bridge for the Local physical data plane.

The Runtime owns admission, leases, routing and policy. Local only validates
the envelope, checks prompt integrity, executes the selected physical handle,
and returns hash-safe events/receipts with the Runtime identity attached.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any, Mapping

from .binary import ERROR, EVENT, RESPONSE
from .protocol import error, ok
from .profiles import ResolvedTurboQuantProfile, resolve_turboquant_profile

RUNTIME_BACKEND_SCHEMA = "simplicio.inference-backend/v2"
RUNTIME_EVENT_SCHEMA = RUNTIME_BACKEND_SCHEMA
LOCAL_PHYSICAL_RECEIPT_SCHEMA = "simplicio.local.physical-receipt/v1"
RUNTIME_RECEIPT_SCHEMA = "simplicio.inference-receipt/v2"
MAX_RUNTIME_OUTPUT_TOKENS = 4096
MAX_PROTOCOL_FIELDS = 64
MAX_LIST_ITEMS = 256


class RuntimeBridgeError(ValueError):
    """A typed, fail-closed Runtime-to-Local contract error."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _required(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise RuntimeBridgeError("invalid_request", f"{key} is required")
    return value


def _hex_digest(value: object, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise RuntimeBridgeError("invalid_request", f"{label} must be a 64-character hex digest")
    try:
        int(value, 16)
    except ValueError as exc:
        raise RuntimeBridgeError("invalid_request", f"{label} must be hexadecimal") from exc
    return value


@dataclass(frozen=True)
class RuntimeRequestV2:
    payload: dict[str, Any]
    request_id: str
    correlation_id: str
    idempotency_key: str
    owner: str
    lease_id: str
    fence: int
    prompt: dict[str, Any]
    limits: dict[str, Any]
    intents: dict[str, Any]
    deadline_unix_ms: int
    cancellation_token: str

    @classmethod
    def parse(cls, payload: Mapping[str, Any], *, now_ms: int | None = None) -> "RuntimeRequestV2":
        if not isinstance(payload, Mapping):
            raise RuntimeBridgeError("invalid_request", "Runtime request must be an object")
        if payload.get("schema") != RUNTIME_BACKEND_SCHEMA:
            raise RuntimeBridgeError("invalid_schema", "request schema is not inference-backend/v2")
        request_id = _required(payload, "request_id")
        correlation_id = _required(payload, "correlation_id")
        idempotency_key = _required(payload, "idempotency_key")
        owner = _required(payload, "owner")
        lease_id = _required(payload, "lease_id")
        cancellation_token = _required(payload, "cancellation_token")
        fence = payload.get("fence")
        deadline = payload.get("deadline_unix_ms")
        if not isinstance(fence, int) or fence <= 0 or not isinstance(deadline, int) or deadline <= 0:
            raise RuntimeBridgeError("invalid_request", "request fence and deadline are required")
        now = int(time.time() * 1000) if now_ms is None else now_ms
        if deadline <= now:
            raise RuntimeBridgeError("deadline_expired", "Runtime inference deadline has expired")

        prompt = payload.get("prompt")
        if not isinstance(prompt, Mapping):
            raise RuntimeBridgeError("invalid_request", "prompt reference is required")
        _required(prompt, "locator")
        _hex_digest(prompt.get("sha256"), "prompt.sha256")
        if not isinstance(prompt.get("byte_len"), int) or prompt["byte_len"] < 0:
            raise RuntimeBridgeError("invalid_request", "prompt.byte_len must be non-negative")

        limits = payload.get("limits")
        if not isinstance(limits, Mapping):
            raise RuntimeBridgeError("invalid_request", "generation limits are required")
        max_tokens = limits.get("max_output_tokens")
        if not isinstance(max_tokens, int) or not 0 < max_tokens <= MAX_RUNTIME_OUTPUT_TOKENS:
            raise RuntimeBridgeError("invalid_argument", "max_output_tokens is outside the Local bound")
        temperature = limits.get("temperature")
        if temperature is not None and (not isinstance(temperature, (int, float)) or temperature < 0):
            raise RuntimeBridgeError("invalid_argument", "temperature must be non-negative")
        top_p = limits.get("top_p")
        if top_p is not None and (not isinstance(top_p, (int, float)) or not 0 <= top_p <= 1):
            raise RuntimeBridgeError("invalid_argument", "top_p must be between 0 and 1")
        stops = limits.get("stop_sequences", [])
        if not isinstance(stops, list) or len(stops) > MAX_LIST_ITEMS or not all(isinstance(item, str) for item in stops):
            raise RuntimeBridgeError("invalid_argument", "stop_sequences is outside the bounded range")

        intents = payload.get("intents")
        if not isinstance(intents, Mapping):
            raise RuntimeBridgeError("invalid_request", "inference intents are required")
        allowed = {
            "weights_profile": {"compatibility", "quality", "balanced", "memory"},
            "cache_profile": {"compatibility", "quality", "balanced", "memory"},
            "storage_profile": {"resident", "mmap", "expert_stream", "layer_stream", "auto"},
            "device_profile": {"cpu", "metal", "mlx", "cuda", "vulkan", "npu", "auto"},
            "workload_class": {"interactive", "background", "batch", "deep_offline"},
        }
        for key, values in allowed.items():
            if intents.get(key) not in values:
                raise RuntimeBridgeError("invalid_intent", f"unsupported intents.{key}")
        quality_floor = intents.get("quality_floor")
        if quality_floor is not None and (not isinstance(quality_floor, (int, float)) or not 0 <= quality_floor <= 1):
            raise RuntimeBridgeError("invalid_intent", "quality_floor must be between 0 and 1")
        max_context = intents.get("max_context")
        if max_context is not None and (not isinstance(max_context, int) or max_context <= 0):
            raise RuntimeBridgeError("invalid_intent", "max_context must be positive")
        if not isinstance(intents.get("allow_fallback"), bool):
            raise RuntimeBridgeError("invalid_intent", "allow_fallback must be boolean")
        turboquant_profile = payload.get("turboquant_profile")
        if turboquant_profile is not None and not isinstance(turboquant_profile, str):
            raise RuntimeBridgeError("invalid_intent", "turboquant_profile must be a string")
        return cls(dict(payload), request_id, correlation_id, idempotency_key, owner, lease_id,
                   fence, dict(prompt), dict(limits), dict(intents), deadline,
                   cancellation_token)

    def prompt_text(self) -> str:
        value = self.payload.get("prompt_text")
        if not isinstance(value, str):
            raise RuntimeBridgeError("prompt_unavailable", "Local requires Runtime-resolved prompt_text")
        if len(value.encode("utf-8")) != self.prompt["byte_len"] or _sha256_text(value) != self.prompt["sha256"]:
            raise RuntimeBridgeError("prompt_integrity_failure", "prompt_text does not match its Runtime reference")
        return value


def _metrics_from_local(receipt: Mapping[str, Any]) -> list[dict[str, Any]]:
    metrics = []
    raw_metrics = receipt.get("metrics") or {}
    if not isinstance(raw_metrics, Mapping):
        return metrics
    for name, value in raw_metrics.items():
        if not isinstance(value, Mapping):
            continue
        metrics.append({
            "name": name,
            "metric": {
                "value": value.get("value"),
                "unit": value.get("unit", "unknown"),
                "source": value.get("source") or "local-unknown",
                "reason": value.get("reason"),
            },
        })
    return metrics


class RuntimeInferenceBridge:
    """Translate Runtime intents into one Local physical generation."""

    def __init__(self, daemon: Any):
        self.daemon = daemon
        self._replays: dict[str, tuple[str, list[tuple[int, dict[str, Any]]]]] = {}

    def generate(self, payload: Mapping[str, Any], request_id: int) -> list[tuple[int, dict[str, Any]]]:
        try:
            request = RuntimeRequestV2.parse(payload)
            request_digest = _digest(request.payload)
            if request.idempotency_key in self._replays:
                original_digest, cached = self._replays[request.idempotency_key]
                if original_digest != request_digest:
                    raise RuntimeBridgeError("idempotency_conflict",
                                             "idempotency_key was reused with a different request")
                replay = [(kind, dict(event)) for kind, event in cached]
                replay[-1][1]["replayed"] = True
                return replay
            prompt = request.prompt_text()
            try:
                profile = resolve_turboquant_profile(
                    request.payload.get("turboquant_profile"),
                    self.daemon.turboquant_capabilities,
                    allow_fallback=request.intents["allow_fallback"],
                )
            except (RuntimeError, ValueError) as exc:
                raise RuntimeBridgeError("profile_unavailable", str(exc)) from exc
            local_request = {
                "method": "generate",
                "prompt": prompt,
                "max_tokens": request.limits["max_output_tokens"],
                "profile": request.intents["cache_profile"],
                "turboquant_profile": profile.effective,
            }
            if payload.get("handle_id") is not None:
                local_request["handle_id"] = payload["handle_id"]
            backend = payload.get("backend") or payload.get("requested_backend")
            if backend is not None:
                local_request["backend"] = backend
            local_events = self.daemon.handle(local_request, request_id)
            terminal = local_events[-1][1]
            local_receipt = terminal.get("receipt") or {}
            runtime_event = self._event(request, terminal, local_receipt)
            physical_receipt = self._physical_receipt(request, terminal, local_receipt, profile)
            runtime_receipt = self._receipt(request, terminal, local_receipt, physical_receipt, profile)
            event_frame = (EVENT, {"method": "runtime_generate", "event": runtime_event})
            if terminal.get("ok", False):
                response = ok("runtime_generate", request_id=request.request_id,
                              correlation_id=request.correlation_id, lease_id=request.lease_id,
                              fence=request.fence, text=terminal.get("text", ""),
                              generated_tokens=terminal.get("generated_tokens", 0),
                              runtime_event=runtime_event, runtime_receipt=runtime_receipt,
                              local_physical_receipt=physical_receipt)
                result = [event_frame, (RESPONSE, response)]
            else:
                failure = terminal.get("error") or {}
                response = error("runtime_generate", str(failure.get("code") or "backend_error"),
                                 str(failure.get("message") or "physical backend failed"),
                                 request_id=request.request_id, correlation_id=request.correlation_id,
                                 lease_id=request.lease_id, fence=request.fence,
                                 runtime_event=runtime_event, runtime_receipt=runtime_receipt,
                                 local_physical_receipt=physical_receipt)
                result = [event_frame, (ERROR, response)]
            self._replays[request.idempotency_key] = (request_digest, result)
            return result
        except RuntimeBridgeError as exc:
            return [(ERROR, error("runtime_generate", exc.code, exc.message))]

    @staticmethod
    def _event(request: RuntimeRequestV2, terminal: Mapping[str, Any], receipt: Mapping[str, Any]) -> dict[str, Any]:
        failed = not terminal.get("ok", False)
        return {
            "schema": RUNTIME_EVENT_SCHEMA,
            "request_id": request.request_id,
            "correlation_id": request.correlation_id,
            "kind": "terminal",
            "sequence": 1,
            "terminal_status": "failed" if failed else "completed",
            "observed_metrics": _metrics_from_local(receipt),
            "output_hash": (receipt.get("redaction") or {}).get("output_sha256") or None,
            "reason": (terminal.get("error") or {}).get("message") if failed else None,
        }

    @staticmethod
    def _physical_receipt(request: RuntimeRequestV2, terminal: Mapping[str, Any],
                          local: Mapping[str, Any], profile: ResolvedTurboQuantProfile) -> dict[str, Any]:
        identity = local.get("identity") if isinstance(local.get("identity"), Mapping) else {}
        effective_backend = str(terminal.get("effective_backend") or terminal.get("requested_backend") or "unknown")
        effective_model = str(request.payload.get("effective_model") or request.payload.get("model_id") or
                              identity.get("model") or "unknown")
        status = "completed" if terminal.get("ok", False) else "failed"
        receipt = {
            "schema": LOCAL_PHYSICAL_RECEIPT_SCHEMA,
            "request_id": request.request_id,
            "correlation_id": request.correlation_id,
            "lease_id": request.lease_id,
            "fence": request.fence,
            "owner": request.owner,
            "backend_hash": _digest(effective_backend),
            "model_hash": _digest(effective_model),
            "profile_hash": _digest(profile.as_dict()),
            "effect_authority": "none",
            "metrics": _metrics_from_local(local),
            "output_hash": (local.get("redaction") or {}).get("output_sha256") or None,
            "terminal_status": status,
            "failure_reason": (terminal.get("error") or {}).get("message") if status == "failed" else None,
        }
        receipt["receipt_hash"] = _digest(receipt)
        return receipt

    @staticmethod
    def _receipt(request: RuntimeRequestV2, terminal: Mapping[str, Any], local: Mapping[str, Any],
                 physical: Mapping[str, Any], profile: ResolvedTurboQuantProfile) -> dict[str, Any]:
        local_hash = _digest(local)
        output_hash = (local.get("redaction") or {}).get("output_sha256") or None
        effective_backend = str(terminal.get("effective_backend") or terminal.get("requested_backend") or "unknown")
        effective_model = str(request.payload.get("effective_model") or request.payload.get("model_id") or "unknown")
        runtime = {
            "request_id": request.request_id,
            "correlation_id": request.correlation_id,
            "attempt_id": str(request.payload.get("attempt_id") or request.request_id),
            "coordinator_kind": str(request.payload.get("coordinator_kind") or "simplicio-runtime"),
            "owner": request.owner,
            "lease_id": request.lease_id,
            "fence": request.fence,
            "route_decision_digest": _hex_or_digest(request.payload.get("route_decision_digest"), request.payload.get("backend")),
            "policy_revision": str(request.payload.get("policy_revision") or "unversioned"),
            "admission_digest": _hex_or_digest(request.payload.get("admission_digest"), {"lease_id": request.lease_id, "fence": request.fence}),
            "requested_lane": str(request.payload.get("requested_lane") or "local_hot"),
            "effective_lane": "local_hot",
            "requested_model": str(request.payload.get("requested_model") or effective_model),
            "effective_model": effective_model,
            "requested_backend": str(request.payload.get("requested_backend") or effective_backend),
            "effective_backend": effective_backend,
            "profile_hash": _hex_or_digest(request.payload.get("profile_hash"), request.intents),
        }
        status = "completed" if terminal.get("ok", False) else "failed"
        receipt = {
            "schema": RUNTIME_RECEIPT_SCHEMA,
            "runtime": runtime,
            "local_receipt_hash": local_hash,
            "physical_receipt_hash": physical["receipt_hash"],
            "status": status,
            "metrics": [item["metric"] | {"name": item["name"]} for item in _metrics_from_local(local)],
            "estimate_observed_delta": {},
            "output_hash": output_hash,
            "failure_reason": (terminal.get("error") or {}).get("message") if status == "failed" else None,
            "evidence_refs": [f"local-physical-receipt:{physical['receipt_hash']}"],
            "previous_receipt_hash": None,
            "profile_resolution": profile.as_dict(),
        }
        receipt["receipt_hash"] = _digest(receipt)
        return receipt


def _hex_or_digest(value: object, fallback: object) -> str:
    if isinstance(value, str) and len(value) == 64:
        try:
            int(value, 16)
            return value
        except ValueError:
            pass
    return _digest(fallback)
