"""calc-graph command line.

  calc-graph serve [--port 8000]          API + built frontend
  calc-graph ingest model.ifc calcs.pdf   ingest into the store and print a summary
"""
from __future__ import annotations

import argparse


def main() -> None:
    ap = argparse.ArgumentParser(prog="calc-graph")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serve")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)
    i = sub.add_parser("ingest")
    i.add_argument("ifc")
    i.add_argument("pdf", nargs="?")
    a = ap.parse_args()
    if a.cmd == "serve":
        import uvicorn
        uvicorn.run("calcgraph.api:app", host=a.host, port=a.port)
    elif a.cmd == "ingest":
        from .api import st
        from . import pipeline
        pid = st.ensure_project()
        pipeline.ingest_model(st, pid, a.ifc)
        if a.pdf:
            pipeline.ingest_calcs(st, pid, a.pdf)
        s = pipeline.state(st, pid)
        print(f"{len(s['elements'])} elements, {len(s['edges'])} load-path edges, {len(s['calcs'])} calcs, "
              f"{len(s['links'])} links, {len(s['calc_edges'])} calc edges; status {s['counts']}")


if __name__ == "__main__":
    main()
