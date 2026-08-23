import unittest

from local_data_plane.kv_policy import KVCachePlanner, KVRequest, PrefixIdentity


class KVPolicyTests(unittest.TestCase):
    def test_context_reduces_before_oom(self):
        plan = KVCachePlanner().plan(KVRequest(4096, 512, 100, 100_000, 10_000, "cuda"))
        self.assertTrue(plan.accepted)
        self.assertLess(plan.max_context, 4096)
        self.assertEqual(plan.tier, "hot-device")

    def test_quantized_kv_is_selected_only_when_supported(self):
        plan = KVCachePlanner().plan(KVRequest(4096, 512, 100, 300_000, 10_000, "metal",
                                               quantized_bytes_per_token=25, quantization_supported=True,
                                               requested_policy="quantized"))
        self.assertTrue(plan.accepted)
        self.assertTrue(plan.format.quantized)

    def test_pressure_rejects_below_minimum_context(self):
        plan = KVCachePlanner().plan(KVRequest(4096, 512, 100, 1_000, 900, "cpu"))
        self.assertFalse(plan.accepted)
        self.assertEqual(plan.max_context, 0)

    def test_prefix_identity_and_fair_share_are_deterministic(self):
        first = PrefixIdentity("qwen", "tok", "template", "temp0")
        same = PrefixIdentity("qwen", "tok", "template", "temp0")
        changed = PrefixIdentity("qwen", "tok", "other-template", "temp0")
        self.assertTrue(KVCachePlanner.can_reuse_prefix(first, same))
        self.assertFalse(KVCachePlanner.can_reuse_prefix(first, changed))
        self.assertEqual(KVCachePlanner.fair_share(10, 3), (4, 3, 3))


if __name__ == "__main__":
    unittest.main()
