#!/usr/bin/env python3
"""Run the optional OpenAI-compatible adapter over the Local daemon."""

import argparse

from local_data_plane.daemon import InferenceDaemon
from local_data_plane.openai_adapter import run_server


parser = argparse.ArgumentParser()
parser.add_argument("--host", default="127.0.0.1")
parser.add_argument("--port", type=int, default=8080)
parser.add_argument("--auth-token")
args = parser.parse_args()
run_server(InferenceDaemon(standalone=True), host=args.host, port=args.port, auth_token=args.auth_token)
