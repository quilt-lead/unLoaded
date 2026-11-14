"""Build connection nodes (types from S8 details, instances on plans/elevations) for a drawing set,
then re-integrate the set (integrated.json) so the app shows them.

  uv run python scripts/build_connections.py [--sid dana-point-bldg12]

Reads data/sets/<sid>/graph.json (sheets + elements, read-only) and meta.json (local PDF paths),
writes data/sets/<sid>/connections.json (gitignored: derived from copyrighted PDFs) and prints counts.
`uv run calc-graph ingest-set ...` runs this step itself.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from calcgraph import set_pipeline  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sid", default="dana-point-bldg12")
    a = ap.parse_args()
    res = set_pipeline.build_connections(a.sid)
    print(json.dumps(res["coverage"], indent=1, default=str))
    integ = set_pipeline.finish_set(a.sid)
    if integ:
        print("integrated.json:", json.dumps(integ["coverage"], indent=1))


if __name__ == "__main__":
    main()
