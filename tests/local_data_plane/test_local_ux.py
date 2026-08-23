import tempfile
import unittest

from local_data_plane.local_ux import LocalUXService
from local_data_plane.model_resolver import ModelCandidate
from local_data_plane.runtime_config import HardwareProfile, ModelFootprint


GB = 1024 ** 3


class LocalUXTests(unittest.TestCase):
    def setUp(self):
        self.candidates = (ModelCandidate("qwen3-8b", "qwen", "3", 8, "Q4_K_M", "https://invalid/qwen", 1),)
        self.profile = HardwareProfile("linux", "x64", 16 * GB, 12 * GB, cpu_threads=8)
        self.footprints = {"qwen3-8b": ModelFootprint(3 * GB, kv_bytes_per_token=1024)}

    def test_empty_status_and_stop_are_json_safe(self):
        with tempfile.TemporaryDirectory() as temp:
            service = LocalUXService(temp)
            self.assertEqual(service.status()["state"], "empty")
            self.assertFalse(service.stop()["stopped"])

    def test_recommendation_explains_backend_and_capacity(self):
        with tempfile.TemporaryDirectory() as temp:
            result = LocalUXService(temp).recommend("Qwen3 8B Q4", self.candidates, self.profile, self.footprints)
            self.assertEqual(result["schema"], "simplicio-local.ux/v1")
            self.assertEqual(result["recommendations"][0]["model_id"], "qwen3-8b")
            self.assertEqual(result["recommendations"][0]["backend"], "cpu")

    def test_unresolved_use_is_blocked_before_download_or_server(self):
        with tempfile.TemporaryDirectory() as temp:
            result = LocalUXService(temp).use("unknown 99B", candidates=self.candidates, catalog=None,
                                              profile=self.profile, footprints=self.footprints, server_spec=lambda *_: None)
            self.assertEqual(result["state"], "blocked")


if __name__ == "__main__":
    unittest.main()
