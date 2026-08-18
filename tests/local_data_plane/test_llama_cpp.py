import tempfile
import unittest
from pathlib import Path

from local_data_plane.llama_cpp import LlamaCppProvider, inspect_gguf


class LlamaCppTests(unittest.TestCase):
    def test_gguf_identity_uses_header_and_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "qwen3.6-27b.gguf"
            path.write_bytes(b"GGUF" + b"fixture-model")
            identity = inspect_gguf(path)
            self.assertEqual(identity.magic, "GGUF")
            self.assertEqual(identity.size_bytes, len(path.read_bytes()))
            self.assertEqual(len(identity.sha256), 64)

    def test_filename_does_not_promote_non_gguf(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "Qwen3.6.gguf"
            path.write_bytes(b"not-a-gguf")
            with self.assertRaises(ValueError):
                inspect_gguf(path)

    def test_missing_server_is_explicit(self):
        probe = LlamaCppProvider(executable=None).probe()
        self.assertFalse(probe.linked)
        self.assertIn("not found", probe.reason)


if __name__ == "__main__":
    unittest.main()
