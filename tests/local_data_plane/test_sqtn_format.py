import hashlib
import tempfile
import unittest
from pathlib import Path

from local_data_plane.sqtn_format import SQTN_SCHEMA_V1, SQTNTensor, SQTNManifest, verify_sqtn_artifact


class SQTNFormatTests(unittest.TestCase):
    def _manifest(self, data):
        digest = hashlib.sha256(data).hexdigest()
        ident = "a" * 64
        return SQTNManifest(SQTN_SCHEMA_V1, "qwen", ident, ident, ident, ident, ident,
                            (SQTNTensor("layer.0", "tensor_train", (4, 4), (2, 2), "int4", 0, len(data), 1, digest),), len(data), {"quality": 0.99})

    def test_manifest_bounds_and_checksum_verify_without_dense_materialization(self):
        data = b"factor-bytes"
        manifest = self._manifest(data)
        manifest.validate()
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "model.sqtn"
            path.write_bytes(data)
            result = verify_sqtn_artifact(path, manifest)
            self.assertTrue(result["verified"])
            self.assertFalse(result["dense_materialized"])

    def test_corruption_is_detected(self):
        data = b"factor-bytes"
        manifest = self._manifest(data)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "model.sqtn"
            path.write_bytes(b"corrupt-data")
            self.assertFalse(verify_sqtn_artifact(path, manifest)["verified"])

    def test_overlapping_or_unaligned_ranges_are_rejected(self):
        data = b"0123456789"
        first = SQTNTensor("a", "mps", (2,), (1,), "int4", 0, 5, 4, hashlib.sha256(data[:5]).hexdigest())
        second = SQTNTensor("b", "mps", (2,), (1,), "int4", 4, 5, 4, hashlib.sha256(data[4:9]).hexdigest())
        manifest = SQTNManifest(SQTN_SCHEMA_V1, "m", "a"*64, "a"*64, "a"*64, "a"*64, "a"*64, (first, second), 10, {})
        with self.assertRaises(ValueError):
            manifest.validate()

    def test_executable_payload_is_not_part_of_format(self):
        manifest = self._manifest(b"factor-bytes")
        self.assertNotIn("plugin", manifest.as_dict())


if __name__ == "__main__":
    unittest.main()
