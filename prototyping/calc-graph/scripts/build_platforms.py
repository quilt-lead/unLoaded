"""Build the synthetic construction-platform state (Procore, ACC Build, Forma) from design.json,
write data/synthetic_v2/platforms.json (gitignored), print counts, and run one example
change-order estimate.

  uv run python scripts/build_platforms.py [--design data/synthetic_v2/design.json] [--quiet]

Everything is SYNTHETIC (fictional project, companies, people) and every figure an estimate.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from calcgraph.platforms import construction_status, estimate, get_adapters, get_state, load_design  # noqa: E402
from calcgraph.platforms.synthetic import shape_props  # noqa: E402

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))


def next_size_up(size: str) -> str:
    """Next heavier W shape of the same nominal depth in the AISC v16 subset."""
    from synth.v2 import aisc
    depth = size.upper().split("X")[0]
    w = shape_props(size)["lb_per_ft"]
    cands = sorted((s["W"], n) for n, s in aisc.shapes().items()
                   if n.upper().split("X")[0] == depth and s.get("Type") == "W" and s["W"] > w)
    return cands[0][1] if cands else size


def example_impact(design: dict) -> dict:
    """Column COL-2B moved 5 ft: members framing into it go one size up, two ST-3 tabs -> ST-4,
    footing F-2B grows 8.5 -> 9.0 ft (made-up impact; the lead's impact engine produces the real one)."""
    els = {e["id"]: e for e in design["elements"]}
    members = sorted({r["src"] for r in design["relations"]
                      if r["kind"] == "frames-into" and r["dst"] == "COL-2B" and els.get(r["src"], {}).get("type") in ("beam", "girder")})
    resized = [{"id": m, "old_size": els[m]["size"], "new_size": next_size_up(els[m]["size"]),
                "length_ft": els[m]["span_ft"]} for m in members]
    tabs = [c for c in ("CX-B-L2-B-12-j", "CX-B-L3-B-23-i") if els.get(c, {}).get("conn_type") == "ST-3"]
    ftg = els["F-2B"]
    recs = ["B-COL:2B", "D-FTG:2B", "D-PIER:2B", "E-BP:2B"] + [f"B-BM:{m}" for m in members] + [f"E-CX:{c}" for c in tabs]
    known = {r["id"] for r in design["records"]}
    return {
        "elements": ["COL-2B", "BP-2B", "P-2B", "F-2B"] + members + tabs,
        "resized": resized,
        "connections_changed": [{"id": c, "old_type": "ST-3", "new_type": "ST-4"} for c in tabs],
        "footings_changed": [{"id": "F-2B", "old_B_ft": 8.5, "new_B_ft": 9.0, "old_h_in": ftg["h_in"], "new_h_in": ftg["h_in"]}],
        "records": [r for r in recs if r in known],
        "sheets": ["S-101", "S-201"],
        "spec_articles": ["05 12 00 3.4 Field quality control (connection inspection)"],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--design", default=os.path.join(ROOT, "data", "synthetic_v2", "design.json"))
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "synthetic_v2", "platforms.json"))
    ap.add_argument("--quiet", action="store_true", help="print the estimate summary only")
    a = ap.parse_args()
    design = load_design(a.design)
    state = get_state(design)
    adapters = get_adapters(design)
    out = {"synthetic": True, "state": state.to_dict(), "platforms": {}}
    for ad in adapters:
        out["platforms"][ad.name] = {**ad.describe(), "counts": ad.counts(),
                                     "records": {rt: [r.to_dict() for r in ad.list(rt)] for rt in sorted(ad.capabilities)}}
    print(f"project: {state.project['name']} ({state.project['number']}), status as of {state.as_of} (data date "
          f"{state.project['data_date']}), start {state.project['start']}, forecast finish {state.forecast_finish}, "
          f"contract finish {state.contract_finish}")
    print("\n== counts per platform (record type: total, by normalized status)")
    for ad in adapters:
        print(f"-- {ad.name}")
        for rt, c in ad.counts().items():
            print(f"   {rt:20s} {c}")
    print("\n== submittal packages (stage read off the schedule)")
    for s in state.submittals:
        print(f"   {s['number']:14s} {s['status']:10s} {len(s['element_ids']):4d} el  {s['title'][:70]}"
              + (f"  [{'; '.join(s['stage_notes'])}]" if s["stage_notes"] else ""))
    by_stage: dict[str, int] = {}
    for ix in state.element_index.values():
        by_stage[ix["stage"]] = by_stage.get(ix["stage"], 0) + 1
    print("\n== elements by construction stage:", dict(sorted(by_stage.items())))
    print("\n== construction_status('COL-2B'):")
    cs = construction_status("COL-2B", adapters)
    print(json.dumps({k: cs[k] for k in ("stage", "float_days", "reasons", "move_difficulty")}, indent=1))
    imp = example_impact(design)
    est = estimate(imp, adapters, design)
    out["example"] = {"impact": imp, "estimate": est}
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w") as fh:
        json.dump(out, fh, indent=1, default=str)
    print(f"\n== example estimate: {est['summary']['headline']}")
    if a.quiet:
        return
    print("\n-- impact:", json.dumps(imp, indent=1))
    print("\n-- submittals:")
    for s in est["submittals"]:
        print(f"   {s['number']:14s} {s['status']:10s} flag={s['flag']!s:16s} {s['action']:45s} {s['link']}  ({len(s['sources'])} platforms)")
    print("-- rfis:")
    for r in est["rfis"]:
        print(f"   {r['number']} {r['status']:9s} {r['action']:45s} {r['link']}")
    print("-- sheets:", [s["number"] for s in est["sheets"]])
    print("-- spec articles:", [s["article"] for s in est["spec_articles"]])
    print("-- cost lines:")
    for ln in est["cost"]["lines"]:
        f = ln["figure"]
        print(f"   {ln['category']:24s} {f['value']:>11,.2f} {f['unit']}  {ln['description']}\n{'':29s}basis: {f['basis']}")
    print("-- cost by category:", {k: v["value"] for k, v in est["cost"]["by_category"].items()})
    print("-- total:", est["cost"]["total"])
    print("-- schedule:", json.dumps({k: v for k, v in est["schedule"].items() if k not in ("rules",)}, indent=1))
    if est["warnings"]:
        print("-- warnings:", est["warnings"])
    print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()
