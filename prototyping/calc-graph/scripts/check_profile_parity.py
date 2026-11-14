"""Parity gate for the per-set profile refactor: run the four profile-reading ingest stages on a
drawing set and write their raw outputs as canonical JSON, or compare two such snapshots.

    uv run python scripts/check_profile_parity.py snapshot <out_dir> --set <set id>
    uv run python scripts/check_profile_parity.py compare <before_dir> <after_dir>

Stages (called directly, not through set_pipeline, so the gate isolates the modules that read
profiles): drawing_ingest.read_plans (+ drawing_loadpath.infer, which annotates the elements the
later stages read), calcpkg_ingest.read_package per calc doc, calc_records.build,
connections.build. Inputs come from data/sets/<set>/meta.json (local PDF paths).

Snapshots are DERIVED FROM THE SET'S PDFS: write them to a gitignored dir or a scratchpad,
never into the repo. `compare` exits 1 on any difference and prints the first differing paths.
`snapshot` re-runs itself with PYTHONHASHSEED=0 so set-iteration order cannot differ between runs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

STAGES = ("drawing", "calcpkg", "calc_records", "connections")


def _default(o):
    if isinstance(o, (tuple, set, frozenset)):
        return sorted(o) if isinstance(o, (set, frozenset)) else list(o)
    if hasattr(o, "x0") and hasattr(o, "y1"):          # pymupdf.Rect
        return [o.x0, o.y0, o.x1, o.y1]
    return str(o)


def canon(obj) -> str:
    # round-trip once so tuples / Rects become lists the same way everywhere, then sort keys
    return json.dumps(json.loads(json.dumps(obj, default=_default)), sort_keys=True, separators=(",", ":"))


def _strip_volatile(obj):
    """Wall-clock fields are not outputs of the rules."""
    if isinstance(obj, dict):
        return {k: _strip_volatile(v) for k, v in obj.items() if k not in ("built_at", "build_seconds")}
    if isinstance(obj, list):
        return [_strip_volatile(v) for v in obj]
    return obj


def snapshot(out_dir: str, sid: str) -> None:
    from calcgraph import calc_records, calcpkg_ingest, connections, drawing_ingest, drawing_loadpath

    sets = os.environ.get("CALCGRAPH_SETS", os.path.join(ROOT, "data", "sets"))
    meta = json.load(open(os.path.join(sets, sid, "meta.json")))
    docs = meta["docs"]
    plans = docs["plans"]["path"]
    calcs = [(v["path"], k, None if k == "calcs" else k.upper()) for k, v in docs.items() if v["role"] == "Calc package"]
    os.makedirs(out_dir, exist_ok=True)
    timings = {}

    t = time.time()
    dr = drawing_ingest.read_plans(plans)
    edges, lp_stats = drawing_loadpath.infer(plans, dr["sheets"], dr["elements"])
    timings["drawing"] = time.time() - t
    _write(out_dir, "drawing", {"read_plans": dr, "element_edges": edges, "loadpath_stats": lp_stats})

    t = time.time()
    pkgs = {key: calcpkg_ingest.read_package(path, key, prefix) for path, key, prefix in calcs}
    timings["calcpkg"] = time.time() - t
    _write(out_dir, "calcpkg", pkgs)

    graph = {"sheets": dr["sheets"], "elements": dr["elements"]}
    t = time.time()
    cr = calc_records.build(calcs, graph, plans)
    timings["calc_records"] = time.time() - t
    _write(out_dir, "calc_records", cr)

    calc_docs = [(k, v["path"]) for k, v in docs.items() if v.get("role") == "Calc package"]
    calc_ids = {(p["doc"], p["page"]): p["id"] for pk in pkgs.values() for p in pk["pages"]}
    s_sheets = [s for s in dr["sheets"] if s["sheet"].startswith("S")]
    t = time.time()
    cn = connections.build(plans, s_sheets, dr["elements"], calc_docs, calc_ids)
    timings["connections"] = time.time() - t
    _write(out_dir, "connections", cn)
    print(json.dumps({k: round(v, 1) for k, v in timings.items()}))


def _write(out_dir: str, stage: str, obj) -> None:
    s = canon(_strip_volatile(obj))
    with open(os.path.join(out_dir, f"{stage}.json"), "w") as fh:
        fh.write(s)
    print(f"{stage}: {len(s):,} bytes sha256 {hashlib.sha256(s.encode()).hexdigest()[:16]}")


def _diff(a, b, path="$", out=None, limit=20):
    out = [] if out is None else out
    if len(out) >= limit:
        return out
    if type(a) is not type(b):
        out.append(f"{path}: type {type(a).__name__} != {type(b).__name__}")
    elif isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                out.append(f"{path}.{k}: only in {'after' if k not in a else 'before'}")
            else:
                _diff(a[k], b[k], f"{path}.{k}", out, limit)
    elif isinstance(a, list):
        if len(a) != len(b):
            out.append(f"{path}: length {len(a)} != {len(b)}")
        for i, (x, y) in enumerate(zip(a, b)):
            _diff(x, y, f"{path}[{i}]", out, limit)
    elif a != b:
        out.append(f"{path}: {str(a)[:80]!r} != {str(b)[:80]!r}")
    return out


def compare(before: str, after: str) -> int:
    bad = 0
    for st in STAGES:
        a = open(os.path.join(before, f"{st}.json")).read()
        b = open(os.path.join(after, f"{st}.json")).read()
        if a == b:
            print(f"{st}: IDENTICAL ({len(a):,} bytes, sha256 {hashlib.sha256(a.encode()).hexdigest()[:16]})")
            continue
        bad += 1
        print(f"{st}: DIFFERENT")
        for line in _diff(json.loads(a), json.loads(b)):
            print("   ", line)
    return 1 if bad else 0


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("snapshot")
    s.add_argument("out_dir")
    s.add_argument("--set", required=True)
    c = sub.add_parser("compare")
    c.add_argument("before")
    c.add_argument("after")
    a = ap.parse_args()
    if a.cmd == "snapshot":
        if os.environ.get("PYTHONHASHSEED") != "0":
            os.execve(sys.executable, [sys.executable] + sys.argv, {**os.environ, "PYTHONHASHSEED": "0"})
        snapshot(a.out_dir, a.set)
    else:
        sys.exit(compare(a.before, a.after))


if __name__ == "__main__":
    main()
