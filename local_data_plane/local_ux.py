"""Minimal zero-config control surface for recommend/status/use/stop."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from typing import Any, Callable, Iterable, Mapping

from .model_cache import CacheArtifact, ModelCache
from .model_resolver import ModelCandidate, ModelResolver, parse_model_request
from .model_catalog import TrustedModelCatalog
from .runtime_config import AutomaticRuntimePlanner, HardwareProfile, ModelFootprint
from .server_manager import OpenAICompatibleServerManager, ServerSpec


UX_SCHEMA_V1 = "simplicio-local.ux/v1"


class LocalUXService:
    def __init__(self, state_root: str):
        self.cache = ModelCache(state_root + "/models")
        self.server = OpenAICompatibleServerManager(state_root + "/server")
        self.planner = AutomaticRuntimePlanner()

    def status(self) -> dict[str, Any]:
        server = self.server.status()
        return {"schema": UX_SCHEMA_V1, "command": "status", "state": server.get("state", "empty"),
                "server": server, "cache": self.cache.status(),
                "text": "No managed local model is running" if server.get("state") == "empty"
                else f"Managed server is {server.get('state')}"}

    def stop(self) -> dict[str, Any]:
        result = self.server.stop()
        return {"schema": UX_SCHEMA_V1, "command": "stop", **result,
                "text": "Stopped managed server" if result.get("stopped") else "No managed server to stop"}

    def recommend(self, request: str, candidates: Iterable[ModelCandidate], profile: HardwareProfile,
                  footprints: Mapping[str, ModelFootprint]) -> dict[str, Any]:
        resolution = ModelResolver(candidates).resolve(parse_model_request(request))
        ranked: list[dict[str, Any]] = []
        for candidate in candidates:
            footprint = footprints.get(candidate.model_id)
            if footprint is None:
                continue
            plan = self.planner.plan(profile, footprint, requested_context=4096, fast_strategy="auto")
            ranked.append({"model_id": candidate.model_id, "family": candidate.family,
                           "parameter_billions": candidate.parameter_billions,
                           "quantization": candidate.quantization, "accepted": plan.accepted,
                           "backend": plan.backend, "context_tokens": plan.context_tokens,
                           "explanation": plan.explanation})
        ranked.sort(key=lambda item: (not item["accepted"], -item["parameter_billions"], item["model_id"]))
        return {"schema": UX_SCHEMA_V1, "command": "recommend", "request": request,
                "resolved_hint": resolution.selected.model_id if resolution.selected else None,
                "recommendations": ranked, "text": f"{len(ranked)} model(s) evaluated for current hardware"}

    def use(self, request: str, *, candidates: Iterable[ModelCandidate], catalog: TrustedModelCatalog,
            profile: HardwareProfile, footprints: Mapping[str, ModelFootprint],
            server_spec: Callable[[str, str, str, str], ServerSpec]) -> dict[str, Any]:
        resolution = ModelResolver(candidates).resolve(parse_model_request(request))
        if resolution.status != "resolved" or resolution.selected is None:
            return {"schema": UX_SCHEMA_V1, "command": "use", "state": "blocked",
                    "reason": resolution.explanation, "alternatives": [item.model_id for item in resolution.alternatives]}
        selected = resolution.selected
        artifacts = catalog.rank_artifacts(selected.model_id, platform=profile.platform)
        if not artifacts:
            return {"schema": UX_SCHEMA_V1, "command": "use", "state": "blocked",
                    "reason": "no compatible trusted artifact"}
        artifact = artifacts[0]
        try:
            model_path = self.cache.download(CacheArtifact(
                selected.model_id, selected.quantization, artifact.url, artifact.size_bytes, artifact.sha256,
                {"catalog_revision": catalog.revision}))
        except (OSError, ValueError) as exc:
            return {"schema": UX_SCHEMA_V1, "command": "use", "state": "blocked", "reason": str(exc)}
        plan = self.planner.plan(profile, footprints[selected.model_id], fast_strategy="auto")
        if not plan.accepted:
            return {"schema": UX_SCHEMA_V1, "command": "use", "state": "blocked",
                    "reason": plan.explanation, "model_path": str(model_path)}
        metadata = self.server.start(server_spec(selected.model_id, plan.backend, selected.quantization,
                                                   str(model_path)))
        health = self.server.health(metadata)
        return {"schema": UX_SCHEMA_V1, "command": "use", "state": "ready" if health["ready"] else "blocked",
                "model_id": selected.model_id, "model_path": str(model_path), "backend": plan.backend,
                "quantization": selected.quantization, "strategy": plan.fast_strategy,
                "connection": metadata.as_dict(), "health": health,
                "reason": "endpoint passed readiness checks" if health["ready"] else "endpoint health check failed"}


def _main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("status", "stop"))
    parser.add_argument("--state-root", default=".simplicio")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    result = getattr(LocalUXService(args.state_root), args.command)()
    print(json.dumps(result, indent=2, sort_keys=True) if args.json else result["text"])
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
