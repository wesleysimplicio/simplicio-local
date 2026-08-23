import unittest

from local_data_plane.residency import plan_residency


class ResidencyTests(unittest.TestCase):
    def test_cuda_keeps_invariant_weights_and_kv_on_device(self):
        plan = plan_residency(backend="cuda", weights_bytes=4_000, kv_bytes=1_000,
                              scratch_bytes=500, draft_bytes=500, device_available_bytes=10_000,
                              system_available_bytes=20_000)
        self.assertTrue(plan.accepted)
        self.assertEqual(plan.weights.device, "cuda")
        self.assertEqual(plan.transfers_per_token, 0)

    def test_unified_memory_is_not_treated_as_discrete_cuda(self):
        plan = plan_residency(backend="unified", weights_bytes=4_000, kv_bytes=1_000,
                              scratch_bytes=500, device_available_bytes=10_000, system_available_bytes=20_000)
        self.assertEqual(plan.weights.device, "unified")
        self.assertIn("unified", plan.reason)

    def test_hybrid_requires_break_even_evidence(self):
        plan = plan_residency(backend="cuda", weights_bytes=7_000, kv_bytes=1_000, scratch_bytes=500,
                              draft_bytes=2_000, device_available_bytes=8_000, system_available_bytes=20_000,
                              separate_draft_device_supported=True,
                              transfer_evidence={"hybrid_throughput_delta": 0.05})
        self.assertTrue(plan.accepted)
        self.assertEqual(plan.draft.device, "cpu")

    def test_pressure_falls_back_or_rejects_before_execution(self):
        plan = plan_residency(backend="cuda", weights_bytes=9_000, kv_bytes=2_000, scratch_bytes=1_000,
                              device_available_bytes=4_000, system_available_bytes=5_000)
        self.assertFalse(plan.accepted)
        self.assertIn("exceed", plan.reason)


if __name__ == "__main__":
    unittest.main()
