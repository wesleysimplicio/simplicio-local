import io
import unittest

from local_data_plane.binary import EVENT, REQUEST, RESPONSE, decode_frame, encode_frame
from local_data_plane.daemon import InferenceDaemon


class DaemonLifecycleTests(unittest.TestCase):
    def test_lifecycle_and_fixture_generation(self):
        daemon = InferenceDaemon(standalone=True)
        self.assertTrue(daemon.handle({"method": "handshake"})[0][1]["ok"])
        loaded = daemon.handle({"method": "load", "model_id": "tiny"})[0][1]
        handle = loaded["handle_id"]
        self.assertEqual(daemon.handle({"method": "warm", "handle_id": handle})[0][1]["state"], "warmed")
        events = daemon.handle({"method": "generate", "handle_id": handle, "prompt": "hello", "max_tokens": 2}, 9)
        self.assertEqual(sum(kind == EVENT for kind, _ in events), 2)
        self.assertTrue(events[-1][1]["ok"])
        self.assertEqual(daemon.handle({"method": "drain"})[0][1]["state"], "draining")
        self.assertEqual(daemon.handle({"method": "unload", "handle_id": handle})[0][1]["unloaded"], True)
        self.assertEqual(daemon.handle({"method": "shutdown"})[0][1]["state"], "stopped")

    def test_stdio_transport_emits_framed_response(self):
        inbound = io.BytesIO(encode_frame(REQUEST, 4, {"method": "handshake"}))
        outbound = io.BytesIO()
        InferenceDaemon().serve(inbound, outbound)
        kind, request_id, payload = decode_frame(outbound.getvalue())
        self.assertEqual((kind, request_id), (RESPONSE, 4))
        self.assertEqual(payload["protocol"], "simplicio.inference-backend/v2")

    def test_generate_contains_terminal_redacted_receipt(self):
        daemon = InferenceDaemon()
        handle = daemon.handle({"method": "load", "model_id": "tiny"})[0][1]["handle_id"]
        response = daemon.handle({"method": "generate", "handle_id": handle,
                                  "prompt": "do not persist", "max_tokens": 1}, 11)[-1][1]
        receipt = response["receipt"]
        self.assertEqual(receipt["terminal_status"], "completed")
        self.assertNotIn("do not persist", str(receipt))
        self.assertEqual(receipt["identity"]["effective_backend"], "fixture")

    def test_backend_request_cannot_fallback_to_fixture(self):
        daemon = InferenceDaemon()
        handle = daemon.handle({"method": "load", "model_id": "tiny"})[0][1]["handle_id"]
        response = daemon.handle({"method": "generate", "handle_id": handle,
                                  "backend": "llama-cpp", "prompt": "hello", "max_tokens": 1}, 12)[-1][1]
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["code"], "backend_mismatch")


if __name__ == "__main__":
    unittest.main()
