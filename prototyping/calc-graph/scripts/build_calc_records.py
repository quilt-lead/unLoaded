"""Break a calc package into design records -> data/sets/<sid>/calc_records.json (gitignored).

    uv run python scripts/build_calc_records.py [--set dana-point-bldg12]

Reads the set's meta.json for the local PDF paths and its graph.json (read-only) for the
drawing-set elements used by the positional match. Prints the counts the report needs.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from calcgraph import calc_records  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="dana-point-bldg12")
    a = ap.parse_args()
    d = os.path.join(os.environ.get("CALCGRAPH_SETS", os.path.join(ROOT, "data", "sets")), a.set)
    meta = json.load(open(os.path.join(d, "meta.json")))
    gp = os.path.join(d, "graph.json")
    graph = json.load(open(gp)) if os.path.exists(gp) else None
    calcs = [(v["path"], k, None if k == "calcs" else k.upper()) for k, v in meta["docs"].items() if v["role"] == "Calc package"]
    t0 = time.time()
    out = calc_records.build(calcs, graph, meta["docs"]["plans"]["path"])
    out["set"] = a.set
    out["built_at"] = time.strftime("%Y-%m-%d %H:%M:%S %Z")
    out["build_seconds"] = round(time.time() - t0, 1)
    with open(os.path.join(d, "calc_records.json"), "w") as fh:
        json.dump(out, fh)
    print(json.dumps(out["stats"], indent=1))
    print("written", os.path.join(d, "calc_records.json"), out["build_seconds"], "s")


if __name__ == "__main__":
    main()
