#!/usr/bin/env python3
"""Fail-closed perplexity matrix runner for the C engine.

The engine's SCORE mode emits one line per teacher-forced sequence:
    <continuation_log_probability> <continuation_tokens> <greedy>

This runner validates every input before launching the first variant, executes
the same corpus for each declared quantization, and writes an auditable receipt.
It never substitutes estimates for missing measurements.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


MANIFEST_SCHEMA = "simplicio-local/perplexity-matrix-manifest-v1"
RECEIPT_SCHEMA = "simplicio-local/perplexity-matrix-receipt-v1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
ENV_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


class HarnessError(RuntimeError):
    """An input or execution failure that must remain visible in the receipt."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        handle.write(encoded)
        temporary = Path(handle.name)
    temporary.replace(path)


def expand_environment(value: str) -> str:
    missing = sorted({name for name in ENV_RE.findall(value) if name not in os.environ})
    if missing:
        raise HarnessError(f"environment variable(s) not set: {', '.join(missing)}")
    return ENV_RE.sub(lambda match: os.environ[match.group(1)], value)


def validate_manifest_shape(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if manifest.get("schema") != MANIFEST_SCHEMA:
        errors.append(f"schema must be {MANIFEST_SCHEMA}")
    if not manifest.get("suite_id"):
        errors.append("suite_id is required")
    if not manifest.get("family"):
        errors.append("family is required")

    corpus = manifest.get("corpus")
    if not isinstance(corpus, dict):
        errors.append("corpus must be an object")
    else:
        if not corpus.get("path"):
            errors.append("corpus.path is required")
        if corpus.get("format") not in {"text-jsonl", "token-ids-jsonl"}:
            errors.append("corpus.format must be text-jsonl or token-ids-jsonl")
        if not SHA256_RE.fullmatch(str(corpus.get("sha256", ""))):
            errors.append("corpus.sha256 must be a lowercase SHA-256 digest")

    variants = manifest.get("variants")
    if not isinstance(variants, list) or not variants:
        errors.append("variants must be a non-empty array")
        return errors

    ids: set[str] = set()
    for index, variant in enumerate(variants):
        label = f"variants[{index}]"
        if not isinstance(variant, dict):
            errors.append(f"{label} must be an object")
            continue
        variant_id = str(variant.get("id", ""))
        if not variant_id:
            errors.append(f"{label}.id is required")
        elif variant_id in ids:
            errors.append(f"{label}.id duplicates {variant_id}")
        ids.add(variant_id)
        for field in (
            "checkpoint",
            "checkpoint_manifest",
            "checkpoint_manifest_sha256",
            "engine",
            "checkpoint_id",
        ):
            if not variant.get(field):
                errors.append(f"{label}.{field} is required")
        if variant.get("checkpoint_manifest_sha256") and not SHA256_RE.fullmatch(
            str(variant["checkpoint_manifest_sha256"])
        ):
            errors.append(f"{label}.checkpoint_manifest_sha256 must be a SHA-256 digest")
        quantization = variant.get("quantization")
        if not isinstance(quantization, dict):
            errors.append(f"{label}.quantization must be an object")
        else:
            if not quantization.get("label"):
                errors.append(f"{label}.quantization.label is required")
            for field in ("expert_bits", "dense_bits"):
                value = quantization.get(field)
                if not isinstance(value, int) or value not in {2, 3, 4, 8, 16}:
                    errors.append(f"{label}.quantization.{field} is invalid")
        cap = variant.get("expert_cache_cap", 64)
        if not isinstance(cap, int) or cap < 1:
            errors.append(f"{label}.expert_cache_cap must be a positive integer")
    return errors


def load_corpus(path: Path, corpus_format: str) -> tuple[list[dict[str, Any]], str]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as source:
        for line_number, raw in enumerate(source, start=1):
            if not raw.strip():
                continue
            try:
                row = json.loads(raw)
            except json.JSONDecodeError as error:
                raise HarnessError(f"corpus line {line_number} is invalid JSON: {error}") from error
            if not isinstance(row, dict) or not row.get("id"):
                raise HarnessError(f"corpus line {line_number} requires a non-empty id")
            if corpus_format == "text-jsonl":
                if not isinstance(row.get("text"), str) or not row["text"].strip():
                    raise HarnessError(f"corpus line {line_number} requires non-empty text")
            else:
                token_ids = row.get("token_ids")
                if (
                    not isinstance(token_ids, list)
                    or len(token_ids) < 2
                    or any(not isinstance(token, int) or token < 0 for token in token_ids)
                ):
                    raise HarnessError(
                        f"corpus line {line_number} requires at least two non-negative token_ids"
                    )
            rows.append(row)
    if not rows:
        raise HarnessError("corpus contains no usable rows")
    return rows, sha256_file(path)


def tokenize_rows(rows: list[dict[str, Any]], checkpoint: Path) -> list[list[int]]:
    tokenizer_path = checkpoint / "tokenizer.json"
    if not tokenizer_path.is_file():
        raise HarnessError(f"tokenizer missing: {tokenizer_path}")
    try:
        from tokenizers import Tokenizer
    except ImportError as error:
        raise HarnessError("text-jsonl requires the tokenizers Python package") from error
    tokenizer = Tokenizer.from_file(str(tokenizer_path))
    sequences = [tokenizer.encode(row["text"]).ids for row in rows]
    if any(len(sequence) < 2 for sequence in sequences):
        raise HarnessError("every corpus row must encode to at least two tokens")
    return sequences


def validate_sequence_lengths(sequences: list[list[int]], maximum: int) -> None:
    for index, sequence in enumerate(sequences, start=1):
        if len(sequence) > maximum:
            raise HarnessError(
                f"corpus row {index} has {len(sequence)} tokens; maximum is {maximum}"
            )


def make_score_requests(sequences: list[list[int]], path: Path) -> int:
    predicted_tokens = 0
    with path.open("w", encoding="utf-8") as output:
        for sequence in sequences:
            continuation = len(sequence) - 1
            predicted_tokens += continuation
            output.write(f"1 {continuation} {' '.join(map(str, sequence))}\n")
    return predicted_tokens


def parse_score_output(stdout: str, expected_lengths: list[int]) -> tuple[float, int]:
    lines: list[str] = []
    for raw_line in stdout.splitlines():
        fields = raw_line.split()
        if len(fields) != 3:
            continue
        try:
            int(fields[1])
            int(fields[2])
        except ValueError:
            continue
        lines.append(raw_line.strip())
    if len(lines) != len(expected_lengths):
        raise HarnessError(
            f"engine emitted {len(lines)} score rows; expected {len(expected_lengths)}"
        )
    total_log_probability = 0.0
    total_tokens = 0
    for index, (line, expected_length) in enumerate(zip(lines, expected_lengths), start=1):
        fields = line.split()
        if len(fields) != 3:
            raise HarnessError(f"score row {index} must contain exactly three fields")
        try:
            log_probability = float(fields[0])
            token_count = int(fields[1])
            greedy = int(fields[2])
        except ValueError as error:
            raise HarnessError(f"score row {index} contains invalid numbers") from error
        if not math.isfinite(log_probability) or log_probability > 0:
            raise HarnessError(f"score row {index} has invalid log probability")
        if token_count != expected_length:
            raise HarnessError(
                f"score row {index} token count {token_count} != expected {expected_length}"
            )
        if greedy not in {0, 1}:
            raise HarnessError(f"score row {index} greedy flag must be 0 or 1")
        total_log_probability += log_probability
        total_tokens += token_count
    if total_tokens < 1:
        raise HarnessError("engine scored zero continuation tokens")
    return total_log_probability, total_tokens


def host_receipt() -> dict[str, Any]:
    return {
        "platform": platform.system().lower(),
        "platform_release": platform.release(),
        "machine": platform.machine(),
        "python": platform.python_version(),
    }


def source_revision(repo_root: Path) -> str | None:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    revision = completed.stdout.strip()
    return revision if completed.returncode == 0 and COMMIT_RE.fullmatch(revision) else None


def preflight(
    manifest: dict[str, Any], manifest_path: Path
) -> list[dict[str, Any]]:
    shape_errors = validate_manifest_shape(manifest)
    if shape_errors:
        raise HarnessError("; ".join(shape_errors))

    corpus_spec = manifest["corpus"]
    corpus_path = Path(expand_environment(str(corpus_spec["path"])))
    if not corpus_path.is_absolute():
        corpus_path = (manifest_path.parent / corpus_path).resolve()
    if not corpus_path.is_file():
        raise HarnessError(f"corpus missing: {corpus_path}")
    rows, observed_hash = load_corpus(corpus_path, corpus_spec["format"])
    if observed_hash != corpus_spec["sha256"]:
        raise HarnessError(
            f"corpus SHA-256 mismatch: expected {corpus_spec['sha256']}, observed {observed_hash}"
        )

    maximum_tokens = corpus_spec.get("max_tokens_per_document", 2048)
    if not isinstance(maximum_tokens, int) or maximum_tokens < 2:
        raise HarnessError("corpus.max_tokens_per_document must be an integer >= 2")
    common_sequences: list[list[int]] | None = None
    resolved_variants: list[dict[str, Any]] = []
    for variant in manifest["variants"]:
        resolved = dict(variant)
        checkpoint = Path(expand_environment(str(variant["checkpoint"]))).resolve()
        checkpoint_manifest = Path(
            expand_environment(str(variant["checkpoint_manifest"]))
        ).resolve()
        engine = Path(expand_environment(str(variant["engine"]))).resolve()
        if not checkpoint.is_dir():
            raise HarnessError(f"{variant['id']}: checkpoint missing: {checkpoint}")
        config = checkpoint / "config.json"
        if not config.is_file():
            raise HarnessError(f"{variant['id']}: checkpoint config missing: {config}")
        if not checkpoint_manifest.is_file():
            raise HarnessError(
                f"{variant['id']}: checkpoint manifest missing: {checkpoint_manifest}"
            )
        observed_manifest_hash = sha256_file(checkpoint_manifest)
        if observed_manifest_hash != variant["checkpoint_manifest_sha256"]:
            raise HarnessError(
                f"{variant['id']}: checkpoint manifest SHA-256 mismatch"
            )
        if not engine.is_file() or not os.access(engine, os.X_OK):
            raise HarnessError(f"{variant['id']}: engine is missing or not executable: {engine}")
        if corpus_spec["format"] == "text-jsonl" and not (checkpoint / "tokenizer.json").is_file():
            raise HarnessError(f"{variant['id']}: tokenizer.json missing")
        sequences = (
            [row["token_ids"] for row in rows]
            if corpus_spec["format"] == "token-ids-jsonl"
            else tokenize_rows(rows, checkpoint)
        )
        validate_sequence_lengths(sequences, maximum_tokens)
        if common_sequences is not None and sequences != common_sequences:
            raise HarnessError(
                f"{variant['id']}: tokenizer output differs from the first variant"
            )
        common_sequences = sequences
        resolved["_checkpoint"] = checkpoint
        resolved["_engine"] = engine
        resolved["_config_sha256"] = sha256_file(config)
        resolved["_checkpoint_manifest_sha256"] = observed_manifest_hash
        resolved["_engine_sha256"] = sha256_file(engine)
        resolved["_sequences"] = sequences
        tokenizer_path = checkpoint / "tokenizer.json"
        resolved["_tokenizer_sha256"] = (
            sha256_file(tokenizer_path) if tokenizer_path.is_file() else None
        )
        resolved_variants.append(resolved)
    return resolved_variants


def execute_variant(
    variant: dict[str, Any],
    work_dir: Path,
) -> dict[str, Any]:
    checkpoint: Path = variant["_checkpoint"]
    engine: Path = variant["_engine"]
    quantization = variant["quantization"]
    sequences = variant["_sequences"]
    request_path = work_dir / f"{variant['id']}.score.txt"
    expected_tokens = make_score_requests(sequences, request_path)
    argv = [
        str(engine),
        str(variant.get("expert_cache_cap", 64)),
        str(quantization["expert_bits"]),
        str(quantization["dense_bits"]),
    ]
    environment = os.environ.copy()
    environment["SNAP"] = str(checkpoint)
    environment["SCORE"] = str(request_path)
    profile = variant.get("profile")
    if profile:
        environment["COLI_PROFILE"] = str(profile)

    started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    start = time.perf_counter()
    completed = subprocess.run(
        argv,
        cwd=engine.parent,
        env=environment,
        capture_output=True,
        text=True,
    )
    duration_ms = round((time.perf_counter() - start) * 1000.0, 3)
    redacted_stdout = completed.stdout.replace(str(checkpoint), "$CHECKPOINT").replace(
        str(work_dir), "$WORK"
    )
    redacted_stderr = completed.stderr.replace(str(checkpoint), "$CHECKPOINT").replace(
        str(work_dir), "$WORK"
    )
    command_receipt = {
        "argv": [engine.name, *argv[1:]],
        "started_at": started_at,
        "duration_ms": duration_ms,
        "exit_code": completed.returncode,
        "stdout": redacted_stdout,
        "stderr": redacted_stderr,
        "stdout_sha256": hashlib.sha256(redacted_stdout.encode()).hexdigest(),
        "stderr_sha256": hashlib.sha256(redacted_stderr.encode()).hexdigest(),
    }
    result: dict[str, Any] = {
        "id": variant["id"],
        "checkpoint_id": variant["checkpoint_id"],
        "quantization": quantization,
        "profile": profile,
        "status": "failed",
        "inputs": {
            "config_sha256": variant["_config_sha256"],
            "checkpoint_manifest_sha256": variant["_checkpoint_manifest_sha256"],
            "engine_sha256": variant["_engine_sha256"],
            "tokenizer_sha256": variant["_tokenizer_sha256"],
            "documents": len(sequences),
            "expected_predicted_tokens": expected_tokens,
        },
        "command_receipt": command_receipt,
        "metrics": {
            "negative_log_likelihood": None,
            "predicted_tokens": None,
            "perplexity": None,
            "unavailable_reason": "execution_failed",
        },
    }
    if completed.returncode != 0:
        result["failure_reason"] = f"engine exited with code {completed.returncode}"
        return result
    try:
        total_log_probability, token_count = parse_score_output(
            completed.stdout, [len(sequence) - 1 for sequence in sequences]
        )
        mean_nll = -total_log_probability / token_count
        perplexity = math.exp(mean_nll)
        if not math.isfinite(perplexity):
            raise HarnessError("computed perplexity is not finite")
    except HarnessError as error:
        result["failure_reason"] = str(error)
        return result
    result["status"] = "completed"
    result["metrics"] = {
        "negative_log_likelihood": -total_log_probability,
        "mean_negative_log_likelihood": mean_nll,
        "predicted_tokens": token_count,
        "perplexity": perplexity,
        "unavailable_reason": None,
    }
    return result


def base_receipt(manifest: dict[str, Any], manifest_path: Path, repo_root: Path) -> dict[str, Any]:
    return {
        "schema": RECEIPT_SCHEMA,
        "suite_id": manifest.get("suite_id"),
        "family": manifest.get("family"),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "status": "failed",
        "failure_reason": None,
        "source_revision": source_revision(repo_root),
        "manifest_sha256": sha256_file(manifest_path),
        "host": host_receipt(),
        "corpus": {
            "id": manifest.get("corpus", {}).get("id"),
            "format": manifest.get("corpus", {}).get("format"),
            "sha256": manifest.get("corpus", {}).get("sha256"),
        },
        "variants": [],
    }


def run_manifest(manifest_path: Path, output_path: Path, repo_root: Path) -> int:
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"manifest_error={error}", file=sys.stderr)
        return 2
    receipt = base_receipt(manifest, manifest_path, repo_root)
    try:
        variants = preflight(manifest, manifest_path)
        with tempfile.TemporaryDirectory(prefix="simplicio-perplexity-") as directory:
            for variant in variants:
                result = execute_variant(
                    variant, Path(directory)
                )
                receipt["variants"].append(result)
                if result["status"] != "completed":
                    raise HarnessError(
                        f"{result['id']}: {result.get('failure_reason', 'execution failed')}"
                    )
        receipt["status"] = "completed"
    except (HarnessError, OSError, subprocess.SubprocessError) as error:
        receipt["failure_reason"] = str(error)
    write_json_atomic(output_path, receipt)
    if receipt["status"] != "completed":
        print(f"quality_run_failed={receipt['failure_reason']}", file=sys.stderr)
        return 2
    print(f"quality_receipt={output_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a reproducible perplexity matrix")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="validate manifest structure")
    validate.add_argument("--manifest", required=True)

    run = subparsers.add_parser("run", help="preflight and execute every variant")
    run.add_argument("--manifest", required=True)
    run.add_argument("--output", required=True)
    run.add_argument("--repo-root", default=".")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    manifest_path = Path(args.manifest).resolve()
    if args.command == "validate":
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            print(f"manifest_error={error}", file=sys.stderr)
            return 2
        errors = validate_manifest_shape(manifest)
        if errors:
            for error in errors:
                print(f"manifest_validation_error={error}", file=sys.stderr)
            return 2
        print("manifest_validation=ok")
        return 0
    return run_manifest(
        manifest_path, Path(args.output).resolve(), Path(args.repo_root).resolve()
    )


if __name__ == "__main__":
    raise SystemExit(main())
