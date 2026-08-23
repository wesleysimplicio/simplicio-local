import unittest

from runtime.benchmarks.qphys_baseline import QPhysMeasurement, create_receipt, pareto_frontier


class QPhysBaselineTests(unittest.TestCase):
    def _measurements(self):
        return (
            QPhysMeasurement("fp16", None, 16, 1000, 1000, 100, 10, 100, 1.0, 1.0, 0.0, 1000),
            QPhysMeasurement("q4", None, 4, 500, 500, 50, 11, 90, 1.01, 0.995, 0.01, 800),
            QPhysMeasurement("low_rank", 8, 4, 300, 300, 40, 9, 110, 1.05, 0.98, 0.04, 900),
            QPhysMeasurement("tensor_train", 8, 4, 250, 250, 35, 12, 80, 1.0, 0.997, 0.02, 850),
            QPhysMeasurement("mpo", 8, 4, 260, 260, 36, 11.5, 82, 1.01, 0.996, 0.02, 860),
        )

    def test_frontier_filters_quality_and_dominated_methods(self):
        frontier = pareto_frontier(self._measurements(), quality_floor=0.99)
        self.assertIn("tensor_train", [item.method for item in frontier])
        self.assertNotIn("low_rank", [item.method for item in frontier])

    def test_receipt_requires_reproducibility_metadata(self):
        receipt = create_receipt({"seed": 1, "corpus": "tiny", "backend": "cpu",
                                  "hardware": "fixture", "model_digest": "m"}, self._measurements())
        self.assertEqual(receipt["status"], "measured")
        self.assertEqual(receipt["schema"], "simplicio-local.qphys-benchmark/v1")
        invalid = create_receipt({}, self._measurements())
        self.assertEqual(invalid["status"], "invalid")

    def test_no_quality_claim_when_method_is_unmeasured(self):
        values = list(self._measurements())
        values[-1] = QPhysMeasurement("mpo", 8, 4, 260, 260, 36, 11.5, 82, 1.01, 0.996, 0.02, 860, False)
        receipt = create_receipt({"seed": 1, "corpus": "tiny", "backend": "cpu",
                                  "hardware": "fixture", "model_digest": "m"}, values)
        self.assertEqual(receipt["status"], "measured")
        self.assertNotIn("mpo", [item["method"] for item in receipt["pareto_frontier"]])

    def test_methods_are_comparable_by_measured_dimensions(self):
        frontier = pareto_frontier(self._measurements())
        for item in frontier:
            self.assertIsNotNone(item.resident_bytes)
            self.assertIsNotNone(item.tok_s)


if __name__ == "__main__":
    unittest.main()
