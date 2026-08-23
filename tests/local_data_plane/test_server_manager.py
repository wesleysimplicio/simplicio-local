import json
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from local_data_plane.server_manager import OpenAICompatibleServerManager, ServerSpec


class ServerManagerTests(unittest.TestCase):
    def _server_command(self, root: Path):
        script = root / "server.py"
        script.write_text(textwrap.dedent("""
            import json, sys
            from http.server import BaseHTTPRequestHandler, HTTPServer
            class Handler(BaseHTTPRequestHandler):
                def do_GET(self):
                    if self.path == '/v1/models':
                        body = json.dumps({'data': [{'id': 'qwen3'}]}).encode()
                        self.send_response(200); self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)
                    else:
                        self.send_response(404); self.end_headers()
                def log_message(self, *_): pass
            HTTPServer(('127.0.0.1', int(sys.argv[1])), Handler).serve_forever()
        """))
        return (sys.executable, str(script), "{port}")

    def test_start_reuse_health_and_stop(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manager = OpenAICompatibleServerManager(root / "state")
            spec = ServerSpec("qwen3", "cpu", "Q4", self._server_command(root), auth_enabled=True)
            metadata = manager.start(spec)
            self.assertEqual(metadata.health, "ready")
            self.assertTrue(manager.status()["health"]["models"])
            reused = manager.start(spec)
            self.assertEqual(reused.pid, metadata.pid)
            self.assertTrue(manager.stop()["stopped"])
            self.assertEqual(manager.status()["state"], "empty")

    def test_connection_metadata_is_machine_readable(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manager = OpenAICompatibleServerManager(root / "state")
            spec = ServerSpec("llama", "cpu", "Q4", self._server_command(root))
            metadata = manager.start(spec)
            payload = json.loads(manager.metadata_path.read_text())
            self.assertEqual(payload["schema"], "simplicio-local.connection-metadata/v1")
            self.assertEqual(payload["base_url"], metadata.base_url)
            manager.stop()

    def test_empty_stop_is_safe(self):
        with tempfile.TemporaryDirectory() as temp:
            result = OpenAICompatibleServerManager(Path(temp) / "state").stop()
            self.assertFalse(result["stopped"])


if __name__ == "__main__":
    unittest.main()
