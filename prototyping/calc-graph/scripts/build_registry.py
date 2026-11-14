"""Rebuild the element registry of the synthetic v2 building from its DOCUMENTS ONLY.

    uv run python scripts/build_registry.py [--dir data/synthetic_v2] [--out PATH]

Reads model.ifc, drawings.pdf, specs.pdf, calc_package.pdf (never design.json or
registry_truth.json) through backend/calcgraph/registry_ingest.py and writes
data/synthetic_v2/registry_ingested.json in the registry schema (synth/v2/registry_truth.py).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from calcgraph import registry_ingest  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=os.path.join(ROOT, "data", "synthetic_v2"))
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    paths = {"ifc": "model.ifc", "drawings": "drawings.pdf", "specs": "specs.pdf", "calcs": "calc_package.pdf"}
    paths = {k: os.path.join(a.dir, v) for k, v in paths.items() if os.path.exists(os.path.join(a.dir, v))}
    if "ifc" not in paths:
        raise SystemExit(f"no model.ifc in {a.dir} - run `uv run python -m synth.v2.generate` first")
    t = time.time()
    reg = registry_ingest.build(paths)
    out = a.out or os.path.join(a.dir, "registry_ingested.json")
    with open(out, "w") as fh:
        json.dump(reg, fh, indent=1, sort_keys=True)
    print(json.dumps({"seconds": round(time.time() - t, 1), "out": os.path.relpath(out, ROOT), **reg["counts"]}, indent=1))
    print(json.dumps({k: v for k, v in reg["meta"].items() if k != "inputs"}, indent=1, default=str)[:4000])


if __name__ == "__main__":
    main()
