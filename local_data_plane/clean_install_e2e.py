"""Evidence-first clean-install flow harness.

The harness accepts product adapters so it can run against a real Local
installation or deterministic test doubles.  It never reports ``ready`` until
both the models endpoint and a chat request have succeeded.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping


E2E_SCHEMA_V1 = "simplicio-local.clean-install-e2e/v1"


@dataclass(frozen=True)
class E2EAdapters:
    resolve: Callable[[str], Mapping[str, Any]]
    acquire: Callable[[Mapping[str, Any]], Mapping[str, Any]]
    configure: Callable[[Mapping[str, Any]], Mapping[str, Any]]
    start: Callable[[Mapping[str, Any]], Mapping[str, Any]]
    models: Callable[[Mapping[str, Any]], Mapping[str, Any]]
    chat: Callable[[Mapping[str, Any], str], Mapping[str, Any]]


def _step(name: str, started: float, **values: Any) -> dict[str, Any]:
    return {"name": name, "elapsed_seconds": round(time.perf_counter() - started, 6), **values}


def run_clean_install(request: str, adapters: E2EAdapters) -> dict[str, Any]:
    started = time.perf_counter()
    steps: list[dict[str, Any]] = []
    evidence: dict[str, Any] = {"request": request, "status": "blocked", "ready": False}
    try:
        step_started = time.perf_counter()
        resolved = dict(adapters.resolve(request))
        if not resolved.get("model_id"):
            raise RuntimeError("resolver returned no canonical model_id")
        steps.append(_step("resolve", step_started, result=resolved))

        step_started = time.perf_counter()
        acquired = dict(adapters.acquire(resolved))
        if not acquired.get("verified"):
            raise RuntimeError("artifact acquisition did not return verified=true")
        steps.append(_step("acquire_verify", step_started, result=acquired))

        step_started = time.perf_counter()
        configured = dict(adapters.configure({**resolved, **acquired}))
        if not configured.get("accepted"):
            raise RuntimeError("runtime configuration was rejected")
        steps.append(_step("configure", step_started, result=configured))

        step_started = time.perf_counter()
        started_server = dict(adapters.start(configured))
        if not started_server.get("base_url"):
            raise RuntimeError("server start returned no base_url")
        steps.append(_step("start", step_started, result=started_server))

        step_started = time.perf_counter()
        models = dict(adapters.models(started_server))
        if models.get("status") != 200 or not models.get("model_id"):
            raise RuntimeError("/v1/models readiness check failed")
        steps.append(_step("health_models", step_started, result=models))

        step_started = time.perf_counter()
        chat = dict(adapters.chat(started_server, "ping"))
        if chat.get("status") != 200 or not str(chat.get("text", "")).strip():
            raise RuntimeError("/v1/chat/completions readiness check failed")
        steps.append(_step("health_chat", step_started, result=chat))
        evidence.update({"status": "ready", "ready": True, "connection": started_server,
                         "model": resolved, "artifact": acquired, "configuration": configured,
                         "health": {"models": models, "chat": chat}})
    except (OSError, RuntimeError, ValueError) as exc:
        evidence.update({"status": "blocked", "ready": False, "failure": str(exc)})
    evidence["schema"] = E2E_SCHEMA_V1
    evidence["elapsed_seconds"] = round(time.perf_counter() - started, 6)
    evidence["steps"] = steps
    return evidence


def write_evidence(path: str, receipt: Mapping[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as stream:
        json.dump(dict(receipt), stream, indent=2, sort_keys=True)
        stream.write("\n")
