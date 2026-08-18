import json
import tempfile
import unittest
from pathlib import Path

from local_data_plane.daemon import InferenceDaemon
from local_data_plane.openai_adapter import OpenAIAdapter


class OpenAIAdapterTests(unittest.TestCase):
    def setUp(self):
        self.daemon = InferenceDaemon()
        self.handle = self.daemon.handle({"method": "load", "model_id": "tiny"})[0][1]["handle_id"]
        self.adapter = OpenAIAdapter(self.daemon)

    def test_chat_uses_existing_handle_and_streams(self):
        status_before = len(self.daemon.handles)
        code, headers, body = self.adapter.dispatch(
            "POST", "/v1/chat/completions", {"Content-Type": "application/json"},
            json.dumps({"messages": [{"role": "user", "content": "hello"}], "max_tokens": 2,
                        "stream": True}).encode())
        self.assertEqual(code, 200)
        self.assertEqual(headers["Content-Type"], "text/event-stream")
        self.assertIn(b"[DONE]", body)
        self.assertEqual(len(self.daemon.handles), status_before)

    def test_tools_are_candidates_forbidden_from_execution(self):
        code, _, body = self.adapter.dispatch("POST", "/v1/completions", {},
                                             json.dumps({"prompt": "x", "tools": []}).encode())
        self.assertEqual(code, 400)
        self.assertIn(b"forbidden", body)

    def test_non_loopback_requires_token_and_cors_is_not_added(self):
        with self.assertRaises(ValueError):
            OpenAIAdapter(self.daemon, host="0.0.0.0")
        protected = OpenAIAdapter(self.daemon, host="0.0.0.0", auth_token="secret")
        self.assertEqual(protected.dispatch("GET", "/v1/models")[0], 401)
        self.assertEqual(protected.dispatch("GET", "/v1/models", {"Authorization": "Bearer secret"})[0], 200)
        self.assertNotIn("Access-Control-Allow-Origin", protected.dispatch("GET", "/v1/models", {"Authorization": "Bearer secret"})[1])

    def test_local_benchmark_page_is_served_same_origin(self):
        with tempfile.TemporaryDirectory() as root:
            page = Path(root) / "qwen38.html"
            page.write_text("<title>Qwen benchmark</title>", encoding="utf-8")
            adapter = OpenAIAdapter(self.daemon, static_root=root)
            code, headers, body = adapter.dispatch("GET", "/")
        self.assertEqual(code, 200)
        self.assertEqual(headers["Content-Type"], "text/html; charset=utf-8")
        self.assertIn(b"Qwen benchmark", body)


if __name__ == "__main__":
    unittest.main()
