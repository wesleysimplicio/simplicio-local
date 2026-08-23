import unittest

from local_data_plane.sensitivity_optimizer import LayerSensitivity, optimize_allocation


class SensitivityOptimizerTests(unittest.TestCase):
    def _layers(self):
        return (LayerSensitivity("layer.0", 0.9, 100, 80, 0.999, ((4, 60), (8, 80))),
                LayerSensitivity("layer.1", 0.2, 100, 50, 0.997, ((2, 50), (8, 100))))

    def test_sensitive_layers_are_allocated_deterministically(self):
        first = optimize_allocation(model_digest="m", corpus_digest="c", policy_version="p",
                                    layers=self._layers(), memory_budget=140, quality_threshold=0.99)
        second = optimize_allocation(model_digest="m", corpus_digest="c", policy_version="p",
                                     layers=self._layers(), memory_budget=140, quality_threshold=0.99)
        self.assertEqual(first.policy_digest, second.policy_digest)
        self.assertEqual(first.allocations, second.allocations)
        self.assertTrue(first.accepted)

    def test_quality_gate_prevents_aggressive_compression(self):
        plan = optimize_allocation(model_digest="m", corpus_digest="c", policy_version="p",
                                   layers=(LayerSensitivity("sensitive", 1.0, 100, 10, 0.8, ((2, 10),)),),
                                   memory_budget=20, quality_threshold=0.99)
        self.assertFalse(plan.accepted)
        self.assertIn("gate", plan.reason)

    def test_missing_identity_is_rejected(self):
        with self.assertRaises(ValueError):
            optimize_allocation(model_digest="", corpus_digest="c", policy_version="p",
                                layers=self._layers(), memory_budget=100, quality_threshold=0.9)

    def test_plan_records_pareto_memory(self):
        plan = optimize_allocation(model_digest="m", corpus_digest="c", policy_version="p",
                                   layers=self._layers(), memory_budget=200, quality_threshold=0.99)
        self.assertGreater(plan.resident_bytes, 0)
        self.assertGreaterEqual(plan.quality, 0.99)


if __name__ == "__main__":
    unittest.main()
