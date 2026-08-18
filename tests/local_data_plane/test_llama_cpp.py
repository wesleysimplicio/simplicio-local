import tempfile
import unittest
from pathlib import Path
import sys

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

    def test_atomic_turboquant_probe_and_command_flags(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            executable = root / "fake-llama-server.py"
            executable.write_text(
                "#!/usr/bin/env python3\n"
                "import sys\n"
                "if '--version' in sys.argv:\n"
                " print('llama-server turboquant-test')\n"
                "elif '--help' in sys.argv:\n"
                " print('--cache-type-k {q4_0|turbo3} --cache-type-v turbo3 --flash-attn')\n"
                "else:\n"
                " print('server')\n",
                encoding="utf-8",
            )
            executable.chmod(0o755)
            model = root / "model.gguf"
            model.write_bytes(b"GGUF" + b"test")
            provider = LlamaCppProvider(executable=str(executable), turboquant=True)
            probe = provider.probe()
            self.assertTrue(probe.linked)
            self.assertTrue(probe.turboquant)
            args = provider.server_args(model, 1234, context_size=2048, parallel=2,
                                        threads=4, threads_batch=4, reasoning="off")
            self.assertEqual(args[args.index("--cache-type-k") + 1], "turbo3")
            self.assertEqual(args[args.index("--cache-type-v") + 1], "turbo3")
            self.assertEqual(args[args.index("--flash-attn") + 1], "auto")
            self.assertIn("-kvu", args)
            self.assertEqual(args[args.index("--batch-size") + 1], "2048")
            self.assertEqual(args[args.index("--ubatch-size") + 1], "512")
            self.assertIn("--cont-batching", args)

    def test_atomic_turboquant_rejects_upstream_help(self):
        with tempfile.TemporaryDirectory() as temp:
            executable = Path(temp) / "fake-llama-server.py"
            executable.write_text(
                f"#!{sys.executable}\n"
                "import sys\n"
                "print('llama-server upstream' if '--version' in sys.argv else '--cache-type-k q4_0')\n",
                encoding="utf-8",
            )
            executable.chmod(0o755)
            probe = LlamaCppProvider(executable=str(executable), turboquant=True).probe()
            self.assertTrue(probe.linked)
            self.assertFalse(probe.turboquant)
            self.assertIn("does not advertise TurboQuant", probe.reason)


if __name__ == "__main__":
    unittest.main()
