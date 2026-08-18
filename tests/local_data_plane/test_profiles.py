import unittest

from local_data_plane.profiles import InferenceProfile, validate_turboquant
from local_data_plane.registry import EvidenceLevel


class ProfileTests(unittest.TestCase):
    def test_storage_and_workload_axes_are_explicit(self):
        with self.assertRaises(ValueError):
            InferenceProfile(storage="layer-stream").validate()
        profile = InferenceProfile(storage="layer-stream", workload="deep-offline", experimental=True)
        self.assertEqual(profile.as_dict()["storage"], "layer-stream")

    def test_turboquant_needs_observed_backend(self):
        blocked = validate_turboquant(requested=True, backend="llama-cpp",
                                      backend_evidence=EvidenceLevel.SOURCE_PRESENT,
                                      reference=[1.0], candidate=[1.0])
        self.assertFalse(blocked.active)

    def test_turboquant_quality_gate(self):
        passed = validate_turboquant(requested=True, backend="fixture",
                                     backend_evidence=EvidenceLevel.FIXTURE_EXECUTED,
                                     reference=[1.0, 2.0], candidate=[1.001, 2.001])
        self.assertTrue(passed.active)
        failed = validate_turboquant(requested=True, backend="fixture",
                                     backend_evidence=EvidenceLevel.FIXTURE_EXECUTED,
                                     reference=[1.0], candidate=[1.2])
        self.assertFalse(failed.active)


if __name__ == "__main__":
    unittest.main()
