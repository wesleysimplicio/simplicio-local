#!/usr/bin/env python3
"""Run the optional OpenAI-compatible adapter over the Local daemon."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from local_data_plane.daemon import InferenceDaemon
from local_data_plane.openai_adapter import run_server


parser = argparse.ArgumentParser()
parser.add_argument("--host", default="127.0.0.1")
parser.add_argument("--port", type=int, default=8080)
parser.add_argument("--auth-token")
parser.add_argument("--model")
parser.add_argument("--model-id")
parser.add_argument("--backend", default="fixture")
parser.add_argument("--executable")
parser.add_argument("--llama-port", type=int, default=0)
args = parser.parse_args()
daemon = InferenceDaemon(standalone=True)
if args.model:
    model_id = args.model_id or Path(args.model).stem
    loaded = daemon.handle({"method": "load", "model_id": model_id, "path": args.model,
                            "backend": args.backend, "executable": args.executable,
                            "port": args.llama_port})[0][1]
    if not loaded.get("ok"):
        print(json.dumps(loaded, sort_keys=True), file=sys.stderr)
        raise SystemExit(2)
run_server(daemon, host=args.host, port=args.port, auth_token=args.auth_token,
           static_root=Path(__file__).resolve().parents[1] / "web")
