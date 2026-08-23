import unittest

from local_data_plane.memory_placement import MemoryRequirements, plan_memory_placement


class MemoryPlacementTests(unittest.TestCase):
    def test_full_gpu_placement_reserves_headroom(self):
        plan = plan_memory_placement(
            {"backend": "cuda", "available_gpu_bytes": 10_000_000_000, "available_system_bytes": 20_000_000_000},
            MemoryRequirements(target_bytes=5_000_000_000, draft_bytes=1_000_000_000,
                               kv_cache_bytes=1_000_000_000, working_bytes=500_000_000),
        )
        self.assertTrue(plan.accepted)
        self.assertEqual(plan.mode, "full-device")
        self.assertGreater(plan.headroom_bytes, 0)

    def test_hybrid_moves_only_draft_when_supported(self):
        plan = plan_memory_placement(
            {"backend": "cuda", "available_gpu_bytes": 5_000_000_000, "available_system_bytes": 20_000_000_000,
             "separate_draft_device_supported": True},
            MemoryRequirements(target_bytes=4_000_000_000, draft_bytes=2_000_000_000,
                               kv_cache_bytes=500_000_000),
        )
        self.assertTrue(plan.accepted)
        self.assertEqual(plan.mode, "hybrid-target-device-draft-cpu")
        self.assertEqual(plan.target_device, "cuda")
        self.assertEqual(plan.draft_device, "cpu")

    def test_oom_is_rejected_before_execution(self):
        plan = plan_memory_placement(
            {"backend": "metal", "available_gpu_bytes": 4_000_000_000, "available_system_bytes": 5_000_000_000},
            MemoryRequirements(target_bytes=10_000_000_000, draft_bytes=1_000_000_000,
                               kv_cache_bytes=1_000_000_000),
        )
        self.assertFalse(plan.accepted)
        self.assertEqual(plan.mode, "rejected")

    def test_cpu_fallback_is_explicit(self):
        plan = plan_memory_placement(
            {"backend": "cuda", "available_gpu_bytes": 2_000_000_000, "available_system_bytes": 20_000_000_000},
            MemoryRequirements(target_bytes=4_000_000_000, kv_cache_bytes=1_000_000_000),
        )
        self.assertTrue(plan.accepted)
        self.assertEqual(plan.mode, "cpu-fallback")
        self.assertEqual(plan.target_device, "cpu")


if __name__ == "__main__":
    unittest.main()
