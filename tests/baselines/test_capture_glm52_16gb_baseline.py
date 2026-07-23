import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "capture_glm52_16gb_baseline.py"
SPEC = importlib.util.spec_from_file_location("capture_glm52_16gb_baseline", SCRIPT)
capture = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(capture)


class CaptureGlm52BaselineTest(unittest.TestCase):
    def test_matrix_has_cold_and_three_warm_runs_for_each_prompt(self):
        cases = capture.case_matrix()
        ids = {case["id"] for case in cases}
        for prompt_id in ("short", "medium", "long"):
            self.assertIn(f"baseline-{prompt_id}-cold-1", ids)
            for repetition in range(1, 4):
                self.assertIn(f"baseline-{prompt_id}-warm-{repetition}", ids)
        for variant in ("topp-0.7", "mtp-on", "direct-on"):
            for repetition in range(1, 4):
                self.assertIn(f"{variant}-medium-warm-{repetition}", ids)
        self.assertEqual(len(cases), 21)
        baseline = next(case for case in cases if case["id"] == "baseline-medium-warm-1")
        self.assertEqual(baseline["environment"]["TOPP"], "0")

    def test_checkpoint_guard_rejects_tiny_fixture(self):
        with tempfile.TemporaryDirectory() as directory:
            model = Path(directory)
            (model / "config.json").write_text("{}", encoding="utf-8")
            (model / "tokenizer.json").write_text("{}", encoding="utf-8")
            (model / "out-00000.safetensors").write_bytes(b"fixture")
            checkpoint, blockers = capture.inspect_checkpoint(model)
        self.assertEqual(checkpoint["safetensors_files"], 1)
        self.assertTrue(any(item.startswith("checkpoint_too_small") for item in blockers))
        self.assertIn("checkpoint_missing_mtp_int8_evidence", blockers)

    def test_checkpoint_guard_accepts_a_sparse_glm52_scale_layout(self):
        with tempfile.TemporaryDirectory() as directory:
            model = Path(directory)
            (model / "config.json").write_text(
                json.dumps({"num_hidden_layers": 78, "n_routed_experts": 256}),
                encoding="utf-8",
            )
            (model / "tokenizer.json").write_text("{}", encoding="utf-8")
            with (model / "out-00000.safetensors").open("wb") as stream:
                stream.truncate(capture.MIN_CHECKPOINT_BYTES)
            (model / "out-mtp-00000.safetensors").write_bytes(b"mtp")
            checkpoint, blockers = capture.inspect_checkpoint(model)
        self.assertEqual(blockers, [])
        self.assertEqual(checkpoint["mtp_shards"], 1)

    def test_cgroup_limit_is_read_without_treating_max_as_a_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "memory.max").write_text(str(16 * capture.GIB), encoding="utf-8")
            self.assertEqual(capture.cgroup_memory_limit_bytes(root), 16 * capture.GIB)
            (root / "memory.max").write_text("max", encoding="utf-8")
            self.assertIsNone(capture.cgroup_memory_limit_bytes(root))

    def test_parser_never_fills_unobservable_metrics(self):
        stdout = (
            "prompt: 52 token | genero fino a 20 (stop EOS=1) | draft n-gram=0\n"
            "---\n20 token in 10.00s (2.00 tok/s) | hit-rate expert 75.0% | RSS 12.50 GB\n"
        )
        metrics = capture.parse_metrics(stdout, "")
        self.assertEqual(metrics["prompt_tokens"]["value"], 52)
        self.assertEqual(metrics["decode_tokens_per_second"]["value"], 2.0)
        self.assertEqual(metrics["peak_rss_bytes"]["value"], 12_500_000_000)
        self.assertEqual(metrics["expert_cache_hit_rate"]["value"], 0.75)
        self.assertIsNone(metrics["prefill_tokens_per_second"]["value"])
        self.assertTrue(metrics["prefill_tokens_per_second"]["unavailable_reason"])
        self.assertIsNone(metrics["disk_read_bytes_per_generated_token"]["value"])

    def test_finalize_is_incomplete_when_metrics_are_null(self):
        session = {
            "preflight": {"status": "ready", "blockers": []},
            "cases": capture.case_matrix(),
            "verdict": {"status": "incomplete", "reasons": []},
        }
        for case in session["cases"]:
            case["status"] = "passed"
            case["metrics"] = {
                name: capture.metric(None, None, "not_observed")
                for name in capture.REQUIRED_METRICS
            }
        capture.finalize(session)
        self.assertEqual(session["verdict"]["status"], "incomplete")
        self.assertTrue(session["verdict"]["reasons"])

    def test_versioned_prompts_and_schema_parse(self):
        prompts = json.loads(
            (REPO / "docs" / "baselines" / "glm52-16gb-prompts.json").read_text(encoding="utf-8")
        )
        schema = json.loads(
            (REPO / "docs" / "baselines" / "glm52-16gb-capture.schema.json").read_text(encoding="utf-8")
        )
        self.assertEqual(prompts["schema"], "simplicio-local/glm52-16gb-prompts-v1")
        self.assertEqual(len(prompts["prompts"]), 3)
        self.assertEqual(schema["$id"], capture.SCHEMA)


if __name__ == "__main__":
    unittest.main()
