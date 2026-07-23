#!/usr/bin/env python3
"""Fail-closed GLM-5.2 int4 baseline capture for issue #118.

The script intentionally does not download weights, purge caches, use sudo, or
invent metrics that the engine/host did not expose.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any


SCHEMA = "simplicio-local/glm52-16gb-capture-v1"
GIB = 1024**3
MIN_HOST_GIB = 15
MAX_HOST_GIB = 17
MIN_CHECKPOINT_BYTES = 300_000_000_000
REQUIRED_METRICS = {
    "prompt_tokens",
    "prefill_tokens_per_second",
    "decode_tokens_per_second",
    "peak_rss_bytes",
    "expert_cache_hit_rate",
    "disk_read_bytes_per_generated_token",
    "swap_observed",
}
ENGINE_SUMMARY_RE = re.compile(
    r"(?P<generated>\d+) token in (?P<seconds>[0-9.]+)s "
    r"\((?P<tps>[0-9.]+) tok/s\) \| hit-rate expert "
    r"(?P<hit>[0-9.]+)% \| RSS (?P<rss>[0-9.]+) GB"
)
PROMPT_TOKENS_RE = re.compile(r"prompt:\s*(\d+)\s+token")


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def physical_memory_bytes() -> int | None:
    if platform.system() == "Darwin":
        result = subprocess.run(
            ["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, check=False
        )
        try:
            return int(result.stdout.strip()) if result.returncode == 0 else None
        except ValueError:
            return None
    if hasattr(os, "sysconf"):
        try:
            return int(os.sysconf("SC_PHYS_PAGES")) * int(os.sysconf("SC_PAGE_SIZE"))
        except (OSError, ValueError, TypeError):
            return None
    return None


def cgroup_memory_limit_bytes(root: Path = Path("/sys/fs/cgroup")) -> int | None:
    candidates = [root / "memory.max", root / "memory" / "memory.limit_in_bytes"]
    for path in candidates:
        try:
            raw = path.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if raw == "max":
            continue
        try:
            value = int(raw)
        except ValueError:
            continue
        if 0 < value < (1 << 60):
            return value
    return None


def probe_host(model_dir: Path) -> dict[str, Any]:
    physical = physical_memory_bytes()
    cgroup = cgroup_memory_limit_bytes()
    effective_candidates = [value for value in (physical, cgroup) if value is not None]
    effective = min(effective_candidates) if effective_candidates else None
    source = "cgroup" if cgroup is not None and effective == cgroup else "physical"
    usage = shutil.disk_usage(model_dir)
    stat = os.statvfs(model_dir)
    return {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor() or None,
        "logical_cpus": os.cpu_count(),
        "physical_memory_bytes": physical,
        "cgroup_memory_limit_bytes": cgroup,
        "effective_memory_bytes": effective,
        "memory_limit_source": source if effective is not None else None,
        "disk": {
            "path": str(model_dir),
            "total_bytes": usage.total,
            "free_bytes": usage.free,
            "filesystem_block_size": stat.f_frsize,
        },
    }


def inspect_checkpoint(model_dir: Path) -> tuple[dict[str, Any], list[str]]:
    blockers: list[str] = []
    config = model_dir / "config.json"
    tokenizer = model_dir / "tokenizer.json"
    manifest = model_dir / "container_manifest.json"
    shards = sorted(model_dir.glob("*.safetensors"))
    shard_bytes = sum(path.stat().st_size for path in shards)
    if not config.is_file():
        blockers.append("checkpoint_missing_config_json")
        config_payload: dict[str, Any] = {}
    else:
        try:
            config_payload = read_json(config)
        except (OSError, json.JSONDecodeError, ValueError):
            config_payload = {}
            blockers.append("checkpoint_config_json_invalid")
    if not tokenizer.is_file():
        blockers.append("checkpoint_missing_tokenizer_json")
    if not shards:
        blockers.append("checkpoint_missing_safetensors")
    if shard_bytes < MIN_CHECKPOINT_BYTES:
        blockers.append(
            f"checkpoint_too_small(required>={MIN_CHECKPOINT_BYTES},observed={shard_bytes})"
        )
    hidden_layers = int(config_payload.get("num_hidden_layers", 0) or 0)
    routed_experts = int(config_payload.get("n_routed_experts", 0) or 0)
    if config_payload and (hidden_layers < 70 or routed_experts < 100):
        blockers.append(
            "checkpoint_config_not_glm52_scale"
            f"(layers={hidden_layers},routed_experts={routed_experts})"
        )
    mtp_shards = list(model_dir.glob("out-mtp-*.safetensors"))
    manifest_has_mtp = False
    if manifest.is_file():
        try:
            manifest_payload = read_json(manifest)
            prefix = f"model.layers.{hidden_layers}."
            manifest_tensors = manifest_payload.get("tensors", manifest_payload)
            manifest_has_mtp = isinstance(manifest_tensors, dict) and any(
                str(name).startswith(prefix) for name in manifest_tensors
            )
        except (OSError, json.JSONDecodeError, ValueError, TypeError):
            blockers.append("checkpoint_manifest_json_invalid")
    if not mtp_shards and not manifest_has_mtp:
        blockers.append("checkpoint_missing_mtp_int8_evidence")
    inventory = "\n".join(f"{path.name}\0{path.stat().st_size}" for path in shards)
    return {
        "path": str(model_dir.resolve()),
        "config_sha256": sha256_file(config) if config.is_file() else None,
        "tokenizer_sha256": sha256_file(tokenizer) if tokenizer.is_file() else None,
        "safetensors_files": len(shards),
        "safetensors_bytes": shard_bytes,
        "shard_inventory_sha256": hashlib.sha256(inventory.encode()).hexdigest(),
        "manifest_sha256": sha256_file(manifest) if manifest.is_file() else None,
        "mtp_shards": len(mtp_shards),
        "manifest_has_mtp": manifest_has_mtp,
    }, blockers


def git_source(repo: Path) -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=False
    )
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True, check=False
    )
    return {
        "git_commit": commit.stdout.strip() if commit.returncode == 0 else None,
        "git_dirty": bool(status.stdout.strip()) if status.returncode == 0 else None,
    }


def metric(value: Any, unit: str | None, reason: str | None = None) -> dict[str, Any]:
    if value is None and not reason:
        raise ValueError("a null metric requires unavailable_reason")
    if value is not None and reason is not None:
        raise ValueError("an observed metric cannot have unavailable_reason")
    return {"value": value, "unit": unit, "unavailable_reason": reason}


def case_matrix() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    baseline_env = {"COLI_PROFILE": "16gb", "TOPP": "0", "MTP": "0", "DIRECT": "0"}
    for prompt_id in ("short", "medium", "long"):
        cases.append(new_case(f"baseline-{prompt_id}-cold-1", prompt_id, "cold", 1, "baseline", baseline_env))
        for repetition in range(1, 4):
            cases.append(new_case(
                f"baseline-{prompt_id}-warm-{repetition}",
                prompt_id, "warm", repetition, "baseline", baseline_env,
            ))
    variants = {
        "topp-0.7": {**baseline_env, "TOPP": "0.7"},
        "mtp-on": {**baseline_env, "MTP": "1"},
        "direct-on": {**baseline_env, "DIRECT": "1"},
    }
    for variant, environment in variants.items():
        for repetition in range(1, 4):
            cases.append(new_case(
                f"{variant}-medium-warm-{repetition}",
                "medium", "warm", repetition, variant, environment,
            ))
    return cases


def new_case(
    case_id: str, prompt_id: str, cache_state: str, repetition: int,
    variant: str, environment: dict[str, str],
) -> dict[str, Any]:
    return {
        "id": case_id,
        "prompt_id": prompt_id,
        "cache_state": cache_state,
        "repetition": repetition,
        "variant": variant,
        "environment": dict(environment),
        "cold_cache_attestation": None,
        "status": "planned",
        "receipt": empty_receipt([]),
        "metrics": {},
    }


def empty_receipt(argv: list[str]) -> dict[str, Any]:
    return {
        "argv": argv,
        "exit_code": None,
        "stdout_path": None,
        "stderr_path": None,
        "stdout_sha256": None,
        "stderr_sha256": None,
    }


def run_receipt(argv: list[str], cwd: Path, log_dir: Path, name: str,
                environment: dict[str, str] | None = None) -> dict[str, Any]:
    stdout_path = log_dir / f"{name}.stdout.log"
    stderr_path = log_dir / f"{name}.stderr.log"
    env = os.environ.copy()
    env.update(environment or {})
    started_at = utc_now()
    started = time.monotonic()
    completed = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True, check=False)
    stdout_path.write_text(completed.stdout, encoding="utf-8")
    stderr_path.write_text(completed.stderr, encoding="utf-8")
    return {
        "argv": argv,
        "environment_overrides": environment or {},
        "started_at": started_at,
        "finished_at": utc_now(),
        "duration_seconds": round(time.monotonic() - started, 6),
        "exit_code": completed.returncode,
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
        "stdout_sha256": sha256_file(stdout_path),
        "stderr_sha256": sha256_file(stderr_path),
    }


def load_prompts(repo: Path) -> dict[str, dict[str, Any]]:
    payload = read_json(repo / "docs" / "baselines" / "glm52-16gb-prompts.json")
    return {item["id"]: item for item in payload["prompts"]}


def parse_metrics(stdout: str, stderr: str) -> dict[str, dict[str, Any]]:
    summary = ENGINE_SUMMARY_RE.search(stdout)
    prompt_match = PROMPT_TOKENS_RE.search(stdout)
    generated = int(summary.group("generated")) if summary else None
    metrics = {
        "prompt_tokens": metric(
            int(prompt_match.group(1)) if prompt_match else None,
            "tokens", None if prompt_match else "engine_did_not_report_prompt_tokens",
        ),
        "prefill_tokens_per_second": metric(
            None, "tokens/second", "engine_does_not_report_separate_prefill_duration"
        ),
        "decode_tokens_per_second": metric(
            float(summary.group("tps")) if summary else None,
            "tokens/second", None if summary else "engine_summary_missing",
        ),
        "generated_tokens": metric(
            generated, "tokens", None if summary else "engine_summary_missing"
        ),
        "peak_rss_bytes": metric(
            int(float(summary.group("rss")) * 1_000_000_000) if summary else None,
            "bytes", None if summary else "engine_summary_missing",
        ),
        "expert_cache_hit_rate": metric(
            float(summary.group("hit")) / 100.0 if summary else None,
            "ratio", None if summary else "engine_summary_missing",
        ),
        "disk_read_bytes": metric(
            None, "bytes", "per_process_physical_disk_bytes_not_exposed_by_engine"
        ),
        "disk_read_bytes_per_generated_token": metric(
            None, "bytes/token", "per_process_physical_disk_bytes_not_exposed_by_engine"
        ),
        "swap_observed": metric(
            None, "boolean", "per_process_swap_not_exposed_by_engine"
        ),
        "ssd_temperature_celsius": metric(
            None, "celsius", "storage_temperature_not_exposed_without_host_tooling"
        ),
    }
    if "RSS GATE] ABORT" in stderr:
        metrics["rss_gate_aborted"] = metric(True, "boolean")
    return metrics


def validate_session(session: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if session.get("schema") != SCHEMA:
        errors.append(f"schema must be {SCHEMA}")
    if session.get("preflight", {}).get("status") not in {"ready", "blocked"}:
        errors.append("preflight.status is invalid")
    expected_ids = [case["id"] for case in case_matrix()]
    observed_ids = [case.get("id") for case in session.get("cases", [])]
    if observed_ids != expected_ids:
        errors.append("case matrix does not match the versioned issue #118 matrix")
    for case in session.get("cases", []):
        if case.get("status") not in {"planned", "passed", "failed", "blocked", "invalid"}:
            errors.append(f"{case.get('id')}: invalid status")
        if case.get("cache_state") == "cold" and case.get("status") != "planned":
            if not case.get("cold_cache_attestation"):
                errors.append(f"{case.get('id')}: cold case lacks cache attestation")
        for name, observed in case.get("metrics", {}).items():
            value = observed.get("value")
            reason = observed.get("unavailable_reason")
            if value is None and not reason:
                errors.append(f"{case.get('id')}.{name}: null metric lacks reason")
            if value is not None and reason is not None:
                errors.append(f"{case.get('id')}.{name}: observed metric has unavailable reason")
    return errors


def locate_repo() -> Path:
    return Path(__file__).resolve().parents[1]


def cmd_prepare(args: argparse.Namespace) -> int:
    repo = locate_repo()
    model_dir = Path(args.model_dir).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    log_dir = output_dir / "logs"
    log_dir.mkdir(exist_ok=True)
    blockers: list[str] = []
    source = git_source(repo)
    if source["git_dirty"]:
        blockers.append("source_worktree_dirty")
    if not model_dir.is_dir():
        blockers.append("model_directory_missing")
        host = {
            "platform": platform.platform(), "machine": platform.machine(),
            "logical_cpus": os.cpu_count(), "physical_memory_bytes": physical_memory_bytes(),
            "effective_memory_bytes": None, "memory_limit_source": None, "disk": {},
        }
        checkpoint = {
            "path": str(model_dir), "config_sha256": None, "tokenizer_sha256": None,
            "safetensors_files": 0, "safetensors_bytes": 0,
            "shard_inventory_sha256": hashlib.sha256(b"").hexdigest(),
            "manifest_sha256": None, "mtp_shards": 0,
        }
    else:
        host = probe_host(model_dir)
        checkpoint, checkpoint_blockers = inspect_checkpoint(model_dir)
        blockers.extend(checkpoint_blockers)
        effective = host["effective_memory_bytes"]
        if effective is None:
            blockers.append("host_memory_unknown")
        elif not MIN_HOST_GIB * GIB <= effective <= MAX_HOST_GIB * GIB:
            blockers.append(
                f"host_memory_outside_16gb_tolerance(observed={effective})"
            )

    engine = repo / "engine" / "c" / ("glm.exe" if os.name == "nt" else "glm")
    if not engine.is_file():
        blockers.append("engine_binary_missing")
    coli = repo / "engine" / "c" / "coli"
    base = [sys.executable, str(coli)]
    plan_argv = base + ["plan", "--json", "--model", str(model_dir), "--profile", "16gb", "--ctx", "4096"]
    doctor_argv = base + ["doctor", "--json", "--model", str(model_dir), "--profile", "16gb", "--ctx", "4096"]
    if blockers:
        plan = empty_receipt(plan_argv)
        doctor = empty_receipt(doctor_argv)
    else:
        plan = run_receipt(plan_argv, repo, log_dir, "plan")
        doctor = run_receipt(doctor_argv, repo, log_dir, "doctor")
        if plan["exit_code"] != 0:
            blockers.append("plan_failed")
        if doctor["exit_code"] != 0:
            blockers.append("doctor_failed")
        if doctor["exit_code"] == 0:
            try:
                doctor_payload = read_json(Path(doctor["stdout_path"]))
                if doctor_payload.get("status") != "ok":
                    blockers.append(f"doctor_status_{doctor_payload.get('status', 'unknown')}")
            except (OSError, ValueError, json.JSONDecodeError):
                blockers.append("doctor_json_invalid")
    session = {
        "schema": SCHEMA,
        "session_id": str(uuid.uuid4()),
        "created_at": utc_now(),
        "source": source,
        "host": host,
        "checkpoint": checkpoint,
        "preflight": {
            "status": "blocked" if blockers else "ready",
            "blockers": blockers,
            "plan": plan,
            "doctor": doctor,
        },
        "prompts_sha256": sha256_file(repo / "docs" / "baselines" / "glm52-16gb-prompts.json"),
        "cases": case_matrix(),
        "verdict": {
            "status": "does_not_run" if any(x in blockers for x in ("plan_failed", "doctor_failed")) else "incomplete",
            "reasons": blockers or ["required_cases_not_captured"],
        },
    }
    session_path = output_dir / "session.json"
    write_json(session_path, session)
    print(session_path)
    return 2 if blockers else 0


def find_case(session: dict[str, Any], case_id: str) -> dict[str, Any]:
    for case in session["cases"]:
        if case["id"] == case_id:
            return case
    raise ValueError(f"unknown case: {case_id}")


def cmd_list_cases(args: argparse.Namespace) -> int:
    session = read_json(Path(args.session))
    for case in session["cases"]:
        print(f"{case['id']}\t{case['status']}")
    return 0


def cmd_run_case(args: argparse.Namespace) -> int:
    repo = locate_repo()
    session_path = Path(args.session).resolve()
    session = read_json(session_path)
    if session["preflight"]["status"] != "ready":
        print("preflight is blocked; refusing to run the engine", file=sys.stderr)
        return 2
    case = find_case(session, args.case)
    if case["status"] != "planned" and not args.rerun:
        print("case already captured; pass --rerun to replace its receipt", file=sys.stderr)
        return 2
    if case["cache_state"] == "cold" and not args.cold_cache_attestation:
        print("cold cases require --cold-cache-attestation", file=sys.stderr)
        return 2
    prompts = load_prompts(repo)
    prompt = prompts[case["prompt_id"]]["text"]
    model_dir = session["checkpoint"]["path"]
    coli = repo / "engine" / "c" / "coli"
    argv = [
        sys.executable, str(coli), "run", "--model", model_dir,
        "--profile", "16gb", "--ctx", "4096", "--ngen", str(args.max_tokens), prompt,
    ]
    log_dir = session_path.parent / "logs"
    receipt = run_receipt(argv, repo, log_dir, case["id"], case["environment"])
    stdout = Path(receipt["stdout_path"]).read_text(encoding="utf-8")
    stderr = Path(receipt["stderr_path"]).read_text(encoding="utf-8")
    case["receipt"] = receipt
    case["metrics"] = parse_metrics(stdout, stderr)
    case["cold_cache_attestation"] = args.cold_cache_attestation
    prompt_tokens = case["metrics"]["prompt_tokens"]["value"]
    target = prompts[case["prompt_id"]]["target_tokens"]
    tolerance = prompts[case["prompt_id"]]["tolerance_tokens"]
    if prompt_tokens is not None and abs(prompt_tokens - target) > tolerance:
        case["status"] = "invalid"
        case["validation_error"] = (
            f"prompt_token_count_outside_tolerance(target={target},"
            f"tolerance={tolerance},observed={prompt_tokens})"
        )
    else:
        case["status"] = (
            "passed"
            if receipt["exit_code"] == 0 and ENGINE_SUMMARY_RE.search(stdout)
            else "failed"
        )
    write_json(session_path, session)
    print(f"{case['id']}={case['status']}")
    return 0 if case["status"] == "passed" else 3


def finalize(session: dict[str, Any]) -> None:
    if session["preflight"]["status"] == "blocked":
        session["verdict"] = {
            "status": "does_not_run"
            if any(reason in {"plan_failed", "doctor_failed"} for reason in session["preflight"]["blockers"])
            else "incomplete",
            "reasons": list(session["preflight"]["blockers"]),
        }
        return
    failed = [case["id"] for case in session["cases"] if case["status"] in {"failed", "blocked", "invalid"}]
    planned = [case["id"] for case in session["cases"] if case["status"] == "planned"]
    missing_metrics = [
        f"{case['id']}.{name}"
        for case in session["cases"]
        if case["status"] == "passed"
        for name in REQUIRED_METRICS
        if case.get("metrics", {}).get(name, {}).get("value") is None
    ]
    if failed:
        session["verdict"] = {"status": "does_not_run", "reasons": [f"failed_case:{x}" for x in failed]}
    elif planned or missing_metrics:
        reasons = [f"missing_case:{x}" for x in planned]
        reasons.extend(f"unobservable_metric:{x}" for x in missing_metrics)
        session["verdict"] = {"status": "incomplete", "reasons": reasons}
    else:
        swapped = any(case["metrics"]["swap_observed"]["value"] for case in session["cases"])
        session["verdict"] = {
            "status": "runs_degraded" if swapped else "runs",
            "reasons": ["swap_observed"] if swapped else [],
        }


def cmd_finalize(args: argparse.Namespace) -> int:
    path = Path(args.session).resolve()
    session = read_json(path)
    finalize(session)
    write_json(path, session)
    print(f"verdict={session['verdict']['status']}")
    return 0 if session["verdict"]["status"] in {"runs", "runs_degraded"} else 3


def cmd_validate(args: argparse.Namespace) -> int:
    session = read_json(Path(args.session).resolve())
    errors = validate_session(session)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 2
    print("validation=ok")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare")
    prepare.add_argument("--model-dir", required=True)
    prepare.add_argument("--output-dir", required=True)
    prepare.set_defaults(func=cmd_prepare)
    listing = sub.add_parser("list-cases")
    listing.add_argument("--session", required=True)
    listing.set_defaults(func=cmd_list_cases)
    run = sub.add_parser("run-case")
    run.add_argument("--session", required=True)
    run.add_argument("--case", required=True)
    run.add_argument("--max-tokens", type=int, default=20)
    run.add_argument("--cold-cache-attestation")
    run.add_argument("--rerun", action="store_true")
    run.set_defaults(func=cmd_run_case)
    finish = sub.add_parser("finalize")
    finish.add_argument("--session", required=True)
    finish.set_defaults(func=cmd_finalize)
    validate = sub.add_parser("validate")
    validate.add_argument("--session", required=True)
    validate.set_defaults(func=cmd_validate)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
