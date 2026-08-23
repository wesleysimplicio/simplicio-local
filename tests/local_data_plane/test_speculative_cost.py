import unittest

from local_data_plane.speculative_cost import CostObservation, select_speculative_cost_plan


class SpeculativeCostTests(unittest.TestCase):
    def _baseline(self):
        return CostObservation("baseline", "baseline", 10, None, None, 100, 4_000, 0, 0.2, 0.1)

    def test_candidate_must_improve_throughput_without_pressure_regression(self):
        candidate = CostObservation("mtp", "same-gpu", 12, 20, 0.6, 105, 5_000, 0, 0.3, 0.1)
        plan = select_speculative_cost_plan(baseline=self._baseline(), candidates=(candidate,),
                                            memory_budget_bytes=10_000, target_headroom_bytes=1_000)
        self.assertEqual(plan.strategy, "mtp")
        self.assertFalse(plan.used_fallback)
        self.assertEqual(plan.receipt["schema"], "simplicio-local.speculative-cost/v1")

    def test_memory_pressure_disables_speculation(self):
        candidate = CostObservation("draft_model", "draft-cpu-target-gpu", 20, 30, 0.8, 100, 9_500, 100, 0.2, 0.1)
        plan = select_speculative_cost_plan(baseline=self._baseline(), candidates=(candidate,),
                                            memory_budget_bytes=10_000, target_headroom_bytes=1_000)
        self.assertEqual(plan.strategy, "baseline")
        self.assertTrue(plan.used_fallback)

    def test_ttft_and_bandwidth_gates_disable_regression(self):
        candidate = CostObservation("ngram_prompt_lookup", "cpu", 12, 14, 0.5, 130, 4_500, 0, 0.95, 0.1)
        plan = select_speculative_cost_plan(baseline=self._baseline(), candidates=(candidate,),
                                            memory_budget_bytes=10_000, target_headroom_bytes=1_000)
        self.assertTrue(plan.used_fallback)
        self.assertIn("gates", plan.reason)

    def test_unmeasured_baseline_is_rejected(self):
        with self.assertRaises(ValueError):
            select_speculative_cost_plan(baseline=CostObservation("baseline", "baseline", None, None, None, None, None, None, None, None, False), candidates=(), memory_budget_bytes=1, target_headroom_bytes=0)


if __name__ == "__main__":
    unittest.main()
