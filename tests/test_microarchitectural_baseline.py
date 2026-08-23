import sys
import unittest

from runtime.benchmarks.microarchitectural_baseline import BenchmarkCase, classify_roofline, create_baseline, hardware_fingerprint


class MicroarchitecturalBaselineTests(unittest.TestCase):
    def test_roofline_classification_requires_evidence(self):
        self.assertEqual(classify_roofline(arithmetic_intensity=1, bandwidth_gib_s=100, compute_gflops=1000), "memory-bandwidth-bound")
        self.assertEqual(classify_roofline(arithmetic_intensity=100, bandwidth_gib_s=10, compute_gflops=100), "compute-bound")
        self.assertEqual(classify_roofline(arithmetic_intensity=None, bandwidth_gib_s=None, compute_gflops=None), "unavailable")

    def test_baseline_separates_phase_and_unavailable_metrics(self):
        case = BenchmarkCase("cpu-prompt", "coding", "cpu", "baseline", "prompt", 4096,
                             (sys.executable, "-c", "print('ok')"))
        receipt = create_baseline((case,))
        self.assertEqual(receipt["status"], "measured")
        self.assertEqual(receipt["cases"][0]["case"]["phase"], "prompt")
        self.assertEqual(receipt["claims"], [])
        self.assertEqual(receipt["cases"][0]["metrics"]["cycles"]["status"], "unavailable")

    def test_fingerprint_is_stable_and_excludes_identity(self):
        first = hardware_fingerprint()
        second = hardware_fingerprint()
        self.assertEqual(first["fingerprint"], second["fingerprint"])
        self.assertNotIn("hostname", first)

    def test_transfer_is_prioritized_when_observed(self):
        self.assertEqual(classify_roofline(arithmetic_intensity=100, bandwidth_gib_s=100,
                                           compute_gflops=100, transfer_fraction=0.5), "transfer-bound")


if __name__ == "__main__":
    unittest.main()
