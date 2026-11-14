"""Build the ETABS view of the synthetic v2 building, write its .e2k text model, read it back,
and run one MOCK send/pull round trip.

    uv run python scripts/build_etabs.py [--change '{"moved": {"2B": [5, 0]}}'] [--no-job]

Reads data/synthetic_v2/design.json (read only; `uv run python -m synth.v2.generate` makes it),
writes data/synthetic_v2/model.e2k and data/synthetic_v2/etabs_jobs/<job id>/ (gitignored).
ETABS does not run anywhere in this script: the "results" are calc-graph's own design re-run
(synth.v2.design.run, PyNite inside, ~30 s) in ETABS OAPI result shapes.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from calcgraph.analysis import get_adapter  # noqa: E402
from calcgraph.analysis.base import DATA_DIR  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--change", default='{"moved": {"2B": [5, 0]}}')
    ap.add_argument("--no-job", action="store_true", help="skip the mock send/pull (the ~30 s re-run)")
    a = ap.parse_args()

    etabs = get_adapter("etabs")
    objs = etabs.model_objects()
    print("ETABS-style objects by kind:", json.dumps(dict(Counter(o.kind for o in objs))))
    occ = etabs.occurrences()
    print(f"occurrences: {len(occ)} rows, {len({o['ref'] for o in occ})} distinct registry ids;",
          json.dumps(dict(Counter(o["object_type"] for o in occ))))
    ex = next(o for o in occ if o["object_type"] == "Frame")
    print("  e.g.", json.dumps(ex))

    path = os.path.join(DATA_DIR, "model.e2k")
    info = etabs.export_model(path)
    print(f"\nwrote {path}: {info['lines']} lines, {info['points']} plan points, {info['line_labels']} line labels, "
          f"{info['frames']} frame objects (label x story), {info['sections']} sections, {info['combos']} combos")
    rt = etabs.roundtrip(path)
    print("round trip (read_e2k vs design.json):")
    for k in rt["counts_model"]:
        print(f"  {k:24s} model {rt['counts_model'][k]:4d}   read back {rt['counts_read'][k]:4d}")
    print(f"  frame segments: {rt['matched']}/{rt['design_segments']} design segments matched by 3D end coordinates, "
          f"{rt['extra_n']} extra, {rt['section_mismatch_n']} section mismatches, max coord error {rt['max_coord_err_ft']:.2e} ft, "
          f"{rt['label_map_mismatch_n']} label->registry mismatches")
    print("  ROUND TRIP", "OK" if rt["ok"] else "FAILED")

    if a.no_job:
        return
    change = json.loads(a.change)
    t = time.time()
    job = etabs.send_change(None, change)
    print(f"\nmock send_change {json.dumps(change)} -> job {job['job_id']} ({job['status']}), diff {json.dumps(job['diff_summary'])}")
    print("  files:", ", ".join(os.path.relpath(p, DATA_DIR) for p in job["files"].values()))
    res = etabs.pull_results(job)
    s = res["summary"]
    print(f"mock pull_results ({time.time() - t:.0f} s): {res['method']}")
    print(f"  story drift D/C by line: base {json.dumps(s['base_max_drift_dc'])} -> changed {json.dumps(s['max_drift_dc'])}")
    print(f"  frame design rows {len(res['frame_design'])}, max ratio {s['max_ratio']}, over 1.0: {s['frames_over_1'] or 'none'}")
    print(f"  sections changed by the re-run: {s['sections_changed']}")
    for r in s["sections_changed_list"][:12]:
        print(f"    {r['label']:>4s} @ {r['story']}  {r['element_id']:16s} {r['from']} -> {r['to']}")
    worst = sorted(res["frame_design"], key=lambda r: -(r["Ratio"] - (r["base_Ratio"] or 0)))[:5]
    print("  largest D/C increases:")
    for r in worst:
        print(f"    {r['Label']:>4s} @ {r['Story']}  {r['element_id']:16s} {r['base_Ratio']} -> {r['Ratio']}  ({r['ComboName']})")
    print("  base reactions (FX, FY, FZ kip):", "; ".join(f"{r['LoadCase']} {r['FX']}, {r['FY']}, {r['FZ']}" for r in res["base_reactions"]))
    print(f"  infeasible: {s['infeasible'] or 'none'}, clashes: {s['clashes']}")
    print("  every row tagged method =", json.dumps(res["story_drifts"][0]["method"]))


if __name__ == "__main__":
    main()
