"""Physical inference receipts with provenance and default redaction."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import resource
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class MetricValue:
    value: int | float | str | None
    semantics: str
    unit: str
    reason: str | None = None
    source: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {"value": self.value, "semantics": self.semantics, "unit": self.unit,
                "reason": self.reason, "source": self.source}


def observed(value: int | float | str, unit: str, source: str) -> MetricValue:
    return MetricValue(value, "observed", unit, source=source)


def unknown(unit: str, reason: str) -> MetricValue:
    return MetricValue(None, "unknown", unit, reason=reason)


@dataclass(frozen=True)
class InferenceReceipt:
    schema: str
    receipt_id: str
    request_id: int
    terminal_status: str
    identity: dict[str, str | None]
    metrics: dict[str, MetricValue]
    redaction: dict[str, str]
    error: dict[str, str] | None = None
    created_at: str = ""

    def as_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "receipt_id": self.receipt_id,
            "request_id": self.request_id,
            "terminal_status": self.terminal_status,
            "identity": self.identity,
            "metrics": {key: self.metrics[key].as_dict() for key in sorted(self.metrics)},
            "redaction": self.redaction,
            "error": self.error,
            "created_at": self.created_at,
        }

    def write(self, path: str | os.PathLike[str]) -> None:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        temporary.write_text(json.dumps(self.as_dict(), sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        os.replace(temporary, destination)


class ReceiptBuilder:
    def __init__(self, request_id: int, *, requested_backend: str | None,
                 effective_backend: str | None, model: str | None, profile: str | None):
        self.request_id = request_id
        self.identity = {
            "daemon_build": "python-data-plane",
            "platform": platform.system().lower(),
            "requested_backend": requested_backend,
            "effective_backend": effective_backend,
            "model": model,
            "profile": profile,
        }
        self.metrics: dict[str, MetricValue] = {}
        self.started = time.monotonic()
        self.prompt_hash: str | None = None
        self.output_hash: str | None = None

    def record_prompt(self, prompt: str) -> None:
        self.prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()

    def record_output(self, output: str) -> None:
        self.output_hash = hashlib.sha256(output.encode("utf-8")).hexdigest()

    def record(self, name: str, value: int | float | str, unit: str, source: str) -> None:
        self.metrics[name] = observed(value, unit, source)

    def finish(self, status: str, *, error_code: str | None = None,
               error_message: str | None = None) -> InferenceReceipt:
        elapsed_ms = (time.monotonic() - self.started) * 1000.0
        self.record("latency.total_ms", elapsed_ms, "milliseconds", "monotonic clock")
        usage = resource.getrusage(resource.RUSAGE_SELF)
        self.record("process.user_cpu_ms", usage.ru_utime * 1000.0, "milliseconds", "getrusage")
        self.record("process.system_cpu_ms", usage.ru_stime * 1000.0, "milliseconds", "getrusage")
        return InferenceReceipt(
            "simplicio-local/inference-receipt-v1", uuid.uuid4().hex, self.request_id, status,
            self.identity, dict(self.metrics),
            {"prompt": "hash-only" if self.prompt_hash else "not-recorded",
             "output": "hash-only" if self.output_hash else "not-recorded",
             "prompt_sha256": self.prompt_hash or "",
             "output_sha256": self.output_hash or ""},
            {"code": error_code, "message": error_message} if error_code else None,
            time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )
