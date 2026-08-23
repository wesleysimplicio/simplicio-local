import unittest

from local_data_plane.runtime_config import AutomaticRuntimePlanner, HardwareProfile, ModelFootprint


GB = 1024 ** 3


class RuntimeConfigTests(unittest.TestCase):
    def test_cuda_profile_selects_safe_full_device_plan(self):
        profile = HardwareProfile("linux", "x64", 32 * GB, 24 * GB, 16 * GB, 14 * GB,
                                  has_cuda=True, cpu_threads=64)
        plan = AutomaticRuntimePlanner().plan(profile, ModelFootprint(6 * GB, kv_bytes_per_token=1024),
                                              fast_strategy="ngram_prompt_lookup", dry_run=True)
        self.assertTrue(plan.accepted)
        self.assertEqual(plan.backend, "cuda")
        self.assertEqual(plan.gpu_offload, "full")
        self.assertIn("Fast strategy=ngram_prompt_lookup", plan.explanation)
        self.assertTrue(plan.as_dict()["schema"].endswith("execution-plan/v1"))

    def test_apple_profile_uses_unified_memory(self):
        profile = HardwareProfile("darwin", "arm64", 16 * GB, 12 * GB, unified_memory_bytes=16 * GB,
                                  available_unified_bytes=12 * GB, has_metal=True, cpu_threads=10)
        plan = AutomaticRuntimePlanner().plan(profile, ModelFootprint(4 * GB, kv_bytes_per_token=2048))
        self.assertTrue(plan.accepted)
        self.assertEqual(plan.backend, "unified")

    def test_cpu_only_profile_falls_back_without_gpu_claim(self):
        profile = HardwareProfile("linux", "x64", 16 * GB, 12 * GB, cpu_threads=8)
        plan = AutomaticRuntimePlanner().plan(profile, ModelFootprint(3 * GB, kv_bytes_per_token=1024))
        self.assertTrue(plan.accepted)
        self.assertEqual(plan.backend, "cpu")
        self.assertEqual(plan.kv_cache_policy, "cpu")

    def test_plan_rejects_oom_before_execution(self):
        profile = HardwareProfile("linux", "x64", 8 * GB, 6 * GB, 4 * GB, 3 * GB, has_cuda=True)
        plan = AutomaticRuntimePlanner().plan(profile, ModelFootprint(10 * GB, kv_bytes_per_token=1024))
        self.assertFalse(plan.accepted)
        self.assertEqual(plan.context_tokens, 0)


if __name__ == "__main__":
    unittest.main()
