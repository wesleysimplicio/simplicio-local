import tempfile
import unittest
from pathlib import Path

from local_data_plane.telemetry import ReceiptBuilder, unknown


class TelemetryTests(unittest.TestCase):
    def test_receipt_redacts_prompt_and_output(self):
        builder = ReceiptBuilder(7, requested_backend="llama-cpp", effective_backend="fixture",
                                 model="tiny", profile="resident")
        builder.record_prompt("secret prompt")
        builder.record_output("secret output")
        receipt = builder.finish("completed")
        payload = receipt.as_dict()
        self.assertNotIn("secret prompt", str(payload))
        self.assertNotIn("secret output", str(payload))
        self.assertEqual(payload["identity"]["requested_backend"], "llama-cpp")
        self.assertEqual(payload["identity"]["effective_backend"], "fixture")
        self.assertEqual(payload["metrics"]["latency.total_ms"]["semantics"], "observed")

    def test_unknown_is_serialized_as_null_with_reason(self):
        self.assertEqual(unknown("bytes", "collector unavailable").as_dict()["value"], None)
        with tempfile.TemporaryDirectory() as temp:
            builder = ReceiptBuilder(1, requested_backend=None, effective_backend=None, model=None, profile=None)
            path = Path(temp) / "receipt.json"
            builder.finish("failed", error_code="io", error_message="disk removed").write(path)
            self.assertIn('"terminal_status":"failed"', path.read_text())


if __name__ == "__main__":
    unittest.main()
