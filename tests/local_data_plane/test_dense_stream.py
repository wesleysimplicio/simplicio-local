import struct
import tempfile
import unittest
from pathlib import Path

from local_data_plane.dense_stream import DenseStreamExecutor, LayerDescriptor


class DenseStreamTests(unittest.TestCase):
    def test_int8_stream_matches_expected_tiny_forward(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = root / "layer0.bin"
            second = root / "layer1.bin"
            first.write_bytes(struct.pack("!bbbb", 1, 0, 0, 1))
            second.write_bytes(struct.pack("!bbbb", 2, 0, 0, 2))
            executor = DenseStreamExecutor([
                LayerDescriptor(str(first), 2, 2, "int8"),
                LayerDescriptor(str(second), 2, 2, "int8"),
            ], rows_per_slab=1)
            result = executor.run([3, 4])
            self.assertEqual(result.status, "completed")
            self.assertEqual(result.output, (6.0, 8.0))
            self.assertLessEqual(result.metrics.maximum_weight_slots, 2)
            self.assertEqual(result.metrics.bytes_per_token, 8.0)

    def test_interactive_and_partial_failure_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "layer.bin"
            path.write_bytes(struct.pack("!f", 1.0))
            with self.assertRaises(ValueError):
                DenseStreamExecutor([LayerDescriptor(str(path), 1, 1)], workload="interactive")
            result = DenseStreamExecutor([LayerDescriptor(str(path), 1, 1)]).run([1.0], cancelled=lambda: True)
            self.assertEqual(result.status, "cancelled")
            self.assertEqual(result.output, ())

    def test_truncated_container_has_no_partial_success(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "layer.bin"
            path.write_bytes(b"\x00")
            result = DenseStreamExecutor([LayerDescriptor(str(path), 1, 2)]).run([1.0, 2.0])
            self.assertEqual(result.status, "failed")
            self.assertEqual(result.output, ())


if __name__ == "__main__":
    unittest.main()
