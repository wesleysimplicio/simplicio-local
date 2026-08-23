import unittest

from runtime.benchmarks.qwen_experiment import VariantResult, classify_variant, create_experiment_report


class QwenExperimentTests(unittest.TestCase):
    def _result(self, budget=16, **overrides):
        values = {"budget_gib": budget, "variant": "Q4", "resident_bytes": 10, "peak_bytes": 12,
                  "bpt": 4, "kv_bytes_per_token": 100, "ttft_ms": 100, "tok_s": 10, "p95_ms": 200,
                  "quality_delta": -0.01, "endpoint_completed": True, "evidence_id": "e"}
        values.update(overrides)
        return VariantResult(**values)

    def test_statuses_are_strict_and_oom_is_not_discovery(self):
        self.assertEqual(classify_variant(self._result()), "usable")
        self.assertEqual(classify_variant(self._result(peak_bytes=20 * 1024**3)), "cannot_fit")
        self.assertEqual(classify_variant(self._result(quality_delta=-0.5)), "quality_regression")
        self.assertEqual(classify_variant(self._result(ttft_ms=3000)), "experimental_slow")

    def test_report_has_all_budget_buckets_and_alternatives(self):
        results = [self._result(budget) for budget in (8, 16, 24, 32)]
        report = create_experiment_report({"model_digest": "m", "hardware": "h", "corpus": "c", "seed": 1}, results)
        self.assertEqual(report["status"], "measured")
        self.assertEqual(set(report["pareto_by_budget"]), {"8", "16", "24", "32"})
        self.assertIn("smaller-reference-model", report["alternatives"])

    def test_missing_evidence_blocks_claims(self):
        report = create_experiment_report({}, (self._result(),))
        self.assertEqual(report["status"], "invalid")
        self.assertEqual(report["claims"], [])

    def test_endpoint_completion_is_required_for_usable_status(self):
        result = self._result(endpoint_completed=False)
        self.assertEqual(classify_variant(result), "cannot_fit")


if __name__ == "__main__":
    unittest.main()
