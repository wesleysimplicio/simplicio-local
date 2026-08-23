import unittest

from local_data_plane.tiered_weights import plan_tiered_weights


class TieredWeightsTests(unittest.TestCase):
    def test_full_resident_is_preferred_when_it_fits(self):
        plan = plan_tiered_weights(artifact_bytes=100, resident_budget_bytes=200, predicted_bytes_per_token=0,
                                   ssd_bandwidth_bytes=1, ssd_latency_ms=1, latency_budget_ms=10)
        self.assertEqual(plan.mode, "full-resident")
        self.assertTrue(plan.accepted)

    def test_conditional_access_can_use_tiered_plan_below_break_even(self):
        plan = plan_tiered_weights(artifact_bytes=1000, resident_budget_bytes=400, predicted_bytes_per_token=100,
                                   ssd_bandwidth_bytes=1000, ssd_latency_ms=1, latency_budget_ms=200,
                                   conditional_access=True, pagein_queue=20)
        self.assertTrue(plan.accepted)
        self.assertEqual(plan.mode, "tiered-mmap-ssd")
        self.assertEqual(plan.pagein_queue, 8)

    def test_dense_page_thrash_is_rejected(self):
        plan = plan_tiered_weights(artifact_bytes=1000, resident_budget_bytes=400, predicted_bytes_per_token=100,
                                   ssd_bandwidth_bytes=1000, ssd_latency_ms=1, latency_budget_ms=200,
                                   conditional_access=True, observed_page_fault_rate=0.5)
        self.assertFalse(plan.accepted)
        self.assertIn("thrash", plan.reason)

    def test_unproven_streaming_does_not_replace_baseline(self):
        plan = plan_tiered_weights(artifact_bytes=1000, resident_budget_bytes=400, predicted_bytes_per_token=100,
                                   ssd_bandwidth_bytes=1000, ssd_latency_ms=1, latency_budget_ms=200)
        self.assertFalse(plan.accepted)
        self.assertEqual(plan.mode, "cannot-fit")


if __name__ == "__main__":
    unittest.main()
