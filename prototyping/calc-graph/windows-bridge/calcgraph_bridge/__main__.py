"""``python -m calcgraph_bridge [--port 8765]``: serve on 127.0.0.1 ONLY (reach it via ssh -L)."""

import argparse

import uvicorn

parser = argparse.ArgumentParser(prog="calcgraph_bridge")
parser.add_argument("--port", type=int, default=8765)
args = parser.parse_args()
# Loopback is not configurable on purpose: no firewall rule, no LAN exposure.
uvicorn.run("calcgraph_bridge.app:app", host="127.0.0.1", port=args.port, workers=1, log_level="info")
