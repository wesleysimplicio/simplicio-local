import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from local_data_plane.daemon import InferenceDaemon


FAKE_SERVER = r'''#!/usr/bin/env python3
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

if "--version" in sys.argv:
    print("llama-server atomic-smoke")
    raise SystemExit(0)
if "--help" in sys.argv:
    print("--cache-type-k turbo2|turbo3|turbo4 --cache-type-v turbo3 --flash-attn")
    raise SystemExit(0)

with open(os.environ["FAKE_LLAMA_ARGS"], "w", encoding="utf-8") as stream:
    json.dump(sys.argv[1:], stream)

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_GET(self):
        self.send_response(200 if self.path == "/health" else 404)
        self.end_headers()
        self.wfile.write(b"ok")

    def do_POST(self):
        size = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(size)
        payload = {"choices": [{"message": {"content": "atomic smoke"}, "finish_reason": "stop"}],
                   "usage": {"completion_tokens": 2, "prompt_tokens": 1},
                   "timings": {"prompt_ms": 1.0, "predicted_ms": 2.0}}
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

port = int(sys.argv[sys.argv.index("--port") + 1])
HTTPServer(("127.0.0.1", port), Handler).serve_forever()
'''


class TurboQuantServerTests(unittest.TestCase):
    def test_daemon_runs_atomic_flags_through_real_process_boundary(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            executable = root / "llama-server"
            executable.write_text(FAKE_SERVER, encoding="utf-8")
            executable.chmod(0o755)
            model = root / "model.gguf"
            model.write_bytes(b"GGUF" + b"atomic-smoke")
            args_path = root / "args.json"
            environment = {
                "FAKE_LLAMA_ARGS": str(args_path),
                "SIMPLICIO_LOCAL_LLAMA_STARTUP_TIMEOUT": "10",
            }
            daemon = None
            with patch.dict(os.environ, environment, clear=False):
                daemon = InferenceDaemon(home=root, repo_root=Path.cwd())
                loaded = daemon.handle({"method": "load", "model_id": "atomic-smoke",
                                        "backend": "turboquant", "path": str(model),
                                        "executable": str(executable)})[0][1]
                self.assertTrue(loaded["ok"], loaded)
                self.assertEqual(loaded["backend"], "llama-cpp-turboquant")
                args = json.loads(args_path.read_text(encoding="utf-8"))
                self.assertEqual(args[args.index("--cache-type-k") + 1], "turbo3")
                self.assertEqual(args[args.index("--cache-type-v") + 1], "turbo3")
                self.assertEqual(args[args.index("--flash-attn") + 1], "auto")
                self.assertIn("-kvu", args)
                response = daemon.handle({"method": "generate", "handle_id": loaded["handle_id"],
                                          "backend": "turboquant", "prompt": "hello", "max_tokens": 2}, 91)[-1][1]
                self.assertTrue(response["ok"], response)
                self.assertEqual(response["text"], "atomic smoke")
                self.assertEqual(response["effective_backend"], "llama-cpp-turboquant")
                daemon.handle({"method": "shutdown"})


if __name__ == "__main__":
    unittest.main()
