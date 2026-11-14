"""Break a calc package into design records -> data/sets/<sid>/calc_records.json (gitignored),
then re-integrate the set (integrated.json) so the app shows them.

    uv run python scripts/build_calc_records.py [--set dana-point-bldg12]

Reads the set's meta.json for the local PDF paths and its graph.json (read-only) for the
drawing-set elements used by the positional match. Prints the counts the report needs.
`uv run calc-graph ingest-set ...` runs this step itself.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from calcgraph import set_pipeline  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="dana-point-bldg12")
    a = ap.parse_args()
    out = set_pipeline.build_records(a.set)
    print(json.dumps(out["stats"], indent=1))
    print("written calc_records.json", out["build_seconds"], "s")
    integ = set_pipeline.finish_set(a.set)
    if integ:
        print("integrated.json:", json.dumps(integ["coverage"], indent=1))


if __name__ == "__main__":
    main()
