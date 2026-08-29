import unittest

from local_data_plane.simd_validation import (
    BenchmarkSummary,
    SimdValidationObservation,
    benchmark_callable,
    evaluate_release_gate,
    run_differential,
)


class SimdValidationTests(unittest.TestCase):
    def test_differential_and_bounded_measurement_are_observable(self):
        differential = run_differential(lambda value: value * 2, lambda value: value + value, range(5))
        self.assertTrue(differential.passed)
        self.assertEqual(differential.cases, 5)
        measured = benchmark_callable(lambda: sum(range(8)), warmups=0, repetitions=3)
        self.assertEqual(measured.runs, 3)
        self.assertGreater(measured.cpu_seconds, 0)

    def _observation(self, **changes):
        values = {
            "requested_isa": "avx2", "effective_kernel": "avx2", "isa_source": "cpuid",
            "correctness_passed": True, "illegal_instruction": False, "memory_safe": True,
            "oom": False, "model_evidence": True,
            "benchmark": BenchmarkSummary(7, 11, 10, 8, 0.008, 5),
            "baseline": BenchmarkSummary(10, 11, 12, 10, 0.010, 5),
        }
        values.update(changes)
        return SimdValidationObservation(**values)

    def test_release_gate_accepts_only_visible_faster_safe_model_path(self):
        accepted = evaluate_release_gate(self._observation())
        self.assertTrue(accepted.accepted)
        self.assertEqual(accepted.receipt["isa"]["effective"], "avx2")
        self.assertIn("all-correctness", accepted.reasons[0])
        missing_model = evaluate_release_gate(self._observation(model_evidence=False))
        self.assertFalse(missing_model.accepted)
        self.assertIn("end-to-end-model-evidence-missing", missing_model.reasons)

    def test_release_gate_rejects_p95_regression_and_safety_failure(self):
        result = evaluate_release_gate(self._observation(
            benchmark=BenchmarkSummary(7, 20, 10, 8, 0.008, 5), memory_safe=False))
        self.assertFalse(result.accepted)
        self.assertIn("p95-regression-exceeds-budget", result.reasons)
        self.assertIn("memory-safety-gate-failed", result.reasons)


if __name__ == "__main__":
    unittest.main()
