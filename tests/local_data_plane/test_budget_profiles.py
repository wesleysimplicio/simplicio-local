import unittest

from local_data_plane.budget_profiles import canonical_profiles, select_budget_profile


class BudgetProfileTests(unittest.TestCase):
    def test_canonical_profiles_cover_cpu_apple_and_cuda(self):
        profiles = canonical_profiles()
        ids = {profile.profile_id for profile in profiles}
        self.assertIn("cpu-8gb", ids)
        self.assertIn("apple-unified-16gb", ids)
        self.assertIn("cuda-12gb", ids)
        self.assertTrue(all(profile.digest for profile in profiles))

    def test_profile_selection_is_backend_aware(self):
        cpu = select_budget_profile(platform="linux", backend="cpu", available_bytes=16 * 1024**3)
        cuda = select_budget_profile(platform="linux", backend="cuda", available_bytes=12 * 1024**3)
        apple = select_budget_profile(platform="darwin", backend="metal", available_bytes=16 * 1024**3)
        self.assertEqual(cpu.profile_id, "cpu-16gb")
        self.assertEqual(cuda.profile_id, "cuda-12gb")
        self.assertEqual(apple.profile_id, "apple-unified-16gb")

    def test_unknown_hardware_gets_custom_measured_profile(self):
        profile = select_budget_profile(platform="plan9", backend="cpu", available_bytes=10 * 1024**3)
        self.assertEqual(profile.profile_id, "custom")
        self.assertIn("measured", profile.notes[0])

    def test_small_memory_does_not_claim_a_larger_profile(self):
        profile = select_budget_profile(platform="linux", backend="cpu", available_bytes=4 * 1024**3)
        self.assertEqual(profile.profile_id, "custom")
        self.assertEqual(profile.resident_bytes, 4 * 1024**3)


if __name__ == "__main__":
    unittest.main()
