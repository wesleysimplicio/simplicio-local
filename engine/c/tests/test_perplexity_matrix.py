import hashlib
import json
import math
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
ENGINE_ROOT = HERE.parent
REPO_ROOT = ENGINE_ROOT.parents[1]
HARNESS = ENGINE_ROOT / "tools" / "perplexity_matrix.py"
TEMPLATE = REPO_ROOT / "docs" / "benchmarks" / "fixtures" / "perplexity-matrix.template.json"
sys.path.insert(0, str(ENGINE_ROOT / "tools"))

from perplexity_matrix import (  # noqa: E402
    MANIFEST_SCHEMA,
    parse_score_output,
    validate_manifest_shape,
)


class PerplexityMatrixTest(unittest.TestCase):
    def test_repository_template_has_valid_structure(self):
        manifest = json.loads(TEMPLATE.read_text(encoding="utf-8"))
        self.assertEqual(validate_manifest_shape(manifest), [])

    def test_aggregates_token_weighted_perplexity(self):
        log_probability, tokens = parse_score_output(
            "== engine banner ==\n-2.0 2 0\n-3.0 3 1\n", [2, 3]
        )
        self.assertEqual(log_probability, -5.0)
        self.assertEqual(tokens, 5)
        self.assertAlmostEqual(math.exp(-log_probability / tokens), math.e)

    def test_rejects_missing_or_malformed_score_rows(self):
        with self.assertRaisesRegex(RuntimeError, "emitted 1 score rows"):
            parse_score_output("-2.0 2 0\n", [2, 3])
        with self.assertRaisesRegex(RuntimeError, "token count"):
            parse_score_output("-2.0 1 0\n", [2])
        with self.assertRaisesRegex(RuntimeError, "log probability"):
            parse_score_output("nan 2 0\n", [2])

    def test_manifest_rejects_duplicate_variants_and_bad_quantization(self):
        manifest = {
            "schema": MANIFEST_SCHEMA,
            "suite_id": "bad",
            "family": "glm",
            "corpus": {"path": "x", "format": "token-ids-jsonl", "sha256": "0" * 64},
            "variants": [
                {
                    "id": "same",
                    "checkpoint": "x",
                    "checkpoint_manifest": "x",
                    "checkpoint_manifest_sha256": "0" * 64,
                    "checkpoint_id": "x",
                    "engine": "x",
                    "quantization": {"label": "bad", "expert_bits": 5, "dense_bits": 4},
                },
                {
                    "id": "same",
                    "checkpoint": "x",
                    "checkpoint_manifest": "x",
                    "checkpoint_manifest_sha256": "0" * 64,
                    "checkpoint_id": "x",
                    "engine": "x",
                    "quantization": {"label": "int4", "expert_bits": 4, "dense_bits": 4},
                },
            ],
        }
        errors = " ".join(validate_manifest_shape(manifest))
        self.assertIn("expert_bits is invalid", errors)
        self.assertIn("duplicates same", errors)

    def test_run_writes_completed_receipt_for_exact_engine_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            corpus = root / "corpus.jsonl"
            corpus.write_text(
                '{"id":"a","token_ids":[1,2,3]}\n'
                '{"id":"b","token_ids":[4,5,6,7]}\n',
                encoding="utf-8",
            )
            checkpoint = root / "checkpoint"
            checkpoint.mkdir()
            (checkpoint / "config.json").write_text('{"model_type":"test"}\n', encoding="utf-8")
            checkpoint_manifest = checkpoint / "weights.manifest.json"
            checkpoint_manifest.write_text('{"fixture":true}\n', encoding="utf-8")
            engine = root / "fake_engine.py"
            engine.write_text(
                "#!/usr/bin/env python3\n"
                "import os\n"
                "for line in open(os.environ['SCORE']):\n"
                "    fields=line.split(); n=int(fields[1]); print(f'{-0.5*n} {n} 0')\n",
                encoding="utf-8",
            )
            engine.chmod(engine.stat().st_mode | stat.S_IXUSR)
            manifest = self._manifest(corpus, checkpoint, checkpoint_manifest, engine)
            manifest_path = root / "manifest.json"
            output = root / "receipt.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(HARNESS),
                    "run",
                    "--manifest",
                    str(manifest_path),
                    "--output",
                    str(output),
                    "--repo-root",
                    str(REPO_ROOT),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            receipt = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(receipt["status"], "completed")
        self.assertRegex(receipt["source_revision"], r"^[0-9a-f]{40}$")
        self.assertEqual(receipt["variants"][0]["metrics"]["predicted_tokens"], 5)
        self.assertAlmostEqual(receipt["variants"][0]["metrics"]["perplexity"], math.exp(0.5))
        self.assertRegex(receipt["variants"][0]["inputs"]["engine_sha256"], r"^[0-9a-f]{64}$")

    def test_preflight_failure_writes_receipt_and_never_runs_engine(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            corpus = root / "corpus.jsonl"
            corpus.write_text('{"id":"a","token_ids":[1,2]}\n', encoding="utf-8")
            checkpoint = root / "checkpoint"
            checkpoint.mkdir()
            (checkpoint / "config.json").write_text("{}\n", encoding="utf-8")
            checkpoint_manifest = checkpoint / "weights.manifest.json"
            checkpoint_manifest.write_text("{}\n", encoding="utf-8")
            marker = root / "engine-ran"
            engine = root / "fake_engine.py"
            engine.write_text(
                f"#!/usr/bin/env python3\nfrom pathlib import Path\nPath({str(marker)!r}).touch()\n",
                encoding="utf-8",
            )
            engine.chmod(engine.stat().st_mode | stat.S_IXUSR)
            manifest = self._manifest(corpus, checkpoint, checkpoint_manifest, engine)
            manifest["corpus"]["sha256"] = "0" * 64
            manifest_path = root / "manifest.json"
            output = root / "receipt.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(HARNESS),
                    "run",
                    "--manifest",
                    str(manifest_path),
                    "--output",
                    str(output),
                    "--repo-root",
                    str(REPO_ROOT),
                ],
                capture_output=True,
                text=True,
            )
            receipt = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(completed.returncode, 2)
            self.assertEqual(receipt["status"], "failed")
            self.assertIn("SHA-256 mismatch", receipt["failure_reason"])
            self.assertFalse(marker.exists())

    def test_engine_failure_preserves_logs_and_null_metrics(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            corpus = root / "corpus.jsonl"
            corpus.write_text('{"id":"a","token_ids":[1,2]}\n', encoding="utf-8")
            checkpoint = root / "checkpoint"
            checkpoint.mkdir()
            (checkpoint / "config.json").write_text("{}\n", encoding="utf-8")
            checkpoint_manifest = checkpoint / "weights.manifest.json"
            checkpoint_manifest.write_text("{}\n", encoding="utf-8")
            engine = root / "fake_engine.py"
            engine.write_text(
                "#!/usr/bin/env python3\nimport sys\nprint('checkpoint rejected', file=sys.stderr)\nsys.exit(7)\n",
                encoding="utf-8",
            )
            engine.chmod(engine.stat().st_mode | stat.S_IXUSR)
            manifest = self._manifest(corpus, checkpoint, checkpoint_manifest, engine)
            manifest_path = root / "manifest.json"
            output = root / "receipt.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(HARNESS),
                    "run",
                    "--manifest",
                    str(manifest_path),
                    "--output",
                    str(output),
                    "--repo-root",
                    str(REPO_ROOT),
                ],
                capture_output=True,
                text=True,
            )
            receipt = json.loads(output.read_text(encoding="utf-8"))
        variant = receipt["variants"][0]
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(variant["command_receipt"]["exit_code"], 7)
        self.assertIn("checkpoint rejected", variant["command_receipt"]["stderr"])
        self.assertIsNone(variant["metrics"]["perplexity"])
        self.assertEqual(variant["metrics"]["unavailable_reason"], "execution_failed")

    @staticmethod
    def _manifest(
        corpus: Path, checkpoint: Path, checkpoint_manifest: Path, engine: Path
    ):
        return {
            "schema": MANIFEST_SCHEMA,
            "suite_id": "test-suite",
            "family": "test",
            "corpus": {
                "id": "tiny-contract",
                "path": str(corpus),
                "format": "token-ids-jsonl",
                "sha256": hashlib.sha256(corpus.read_bytes()).hexdigest(),
            },
            "variants": [
                {
                    "id": "int4",
                    "checkpoint": str(checkpoint),
                    "checkpoint_manifest": str(checkpoint_manifest),
                    "checkpoint_manifest_sha256": hashlib.sha256(
                        checkpoint_manifest.read_bytes()
                    ).hexdigest(),
                    "checkpoint_id": "fixture",
                    "engine": str(engine),
                    "expert_cache_cap": 8,
                    "quantization": {
                        "label": "int4",
                        "expert_bits": 4,
                        "dense_bits": 4,
                    },
                }
            ],
        }


if __name__ == "__main__":
    unittest.main()
