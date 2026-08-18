import unittest

from local_data_plane.artifacts import ARTIFACT_PIN_SCHEMA_V1, InferenceArtifactPin, validate_artifact


class ArtifactTests(unittest.TestCase):
    def _pin(self, **overrides):
        values = {
            "schema": ARTIFACT_PIN_SCHEMA_V1,
            "artifact_id": "qwen-gguf",
            "artifact_kind": "model-weights",
            "version": "2026.08.18",
            "sha256": "a" * 64,
            "source_url": "https://example.invalid/qwen.gguf",
            "upstream_commit": "0123456789abcdef0123456789abcdef01234567",
            "license": "Apache-2.0",
        }
        values.update(overrides)
        return InferenceArtifactPin(**values)

    def test_valid_pin_is_accepted(self):
        receipt = validate_artifact(self._pin())
        self.assertTrue(receipt.accepted)
        self.assertEqual(receipt.reason, "pinned-artifact-validated")
        self.assertEqual(receipt.sha256, "a" * 64)

    def test_mutable_pin_is_rejected(self):
        receipt = validate_artifact(self._pin(version="latest"))
        self.assertFalse(receipt.accepted)
        self.assertIn("immutable", receipt.reason)

    def test_digest_and_transport_are_rejected(self):
        receipt = validate_artifact(self._pin(sha256="bad", source_url="http://example.invalid/qwen.gguf"))
        self.assertFalse(receipt.accepted)
        self.assertIn("sha256", receipt.reason)


if __name__ == "__main__":
    unittest.main()
