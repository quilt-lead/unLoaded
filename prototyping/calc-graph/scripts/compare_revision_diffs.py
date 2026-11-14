"""ifcdiff vs the revision store's key-join diff on the same v2 revision pair.

    uv run python scripts/compare_revision_diffs.py [--move 2B:5,0] [--remove 2B] [--json-out PATH]

Writes the v2 base design and the moved design (as /api/v2/apply does: minimum-change re-design,
ifc_v2.write) into a TEMPORARY revision store (never data/store), ingests both through the
production pipeline (pipeline.ingest_model), then runs calcgraph.ifc_diff.diff_revisions, which
returns both diffs. Reports, for physical elements: added / removed / changed GlobalIds each diff
found, where they agree, and every disagreement with the fields that explain it. Analytical items
(which ifc_ingest does not read, so the store cannot see) are counted separately.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from collections import Counter

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path[:0] = [ROOT, os.path.join(ROOT, "backend")]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--move", default="2B:5,0", help="COLUMN:dx,dy in ft")
    ap.add_argument("--remove", help="remove this column instead")
    ap.add_argument("--json-out")
    a = ap.parse_args()
    from calcgraph import ifc_diff, pipeline, recalc
    from calcgraph.store import Store
    from synth.v2 import ifc_v2
    from synth.v2.generate import build

    if a.remove:
        change, label = {"removed": [a.remove]}, f"Remove {a.remove}"
    else:
        c, xy = a.move.split(":")
        dx, dy = (float(v) for v in xy.split(","))
        change, label = {"moved": {c: [dx, dy]}}, f"Move {c} ({dx:+g}, {dy:+g}) ft"
    with tempfile.TemporaryDirectory() as tmp:
        d, exp = build()
        p0 = os.path.join(tmp, "base.ifc")
        ifc_v2.write(exp, p0, d)
        d1, exp1 = build(recalc.layout_from_change(change | {"label": label}), keep={e["id"]: e for e in exp["elements"]})
        p1 = os.path.join(tmp, "moved.ifc")
        ifc_v2.write(exp1, p1, d1, label=label)
        st = Store(os.path.join(tmp, "store"))
        pid = st.db.execute("INSERT INTO project(name, created_at) VALUES ('diff check', '')").lastrowid
        st.commit()
        ra = pipeline.ingest_model(st, pid, p0, "base.ifc", "Base design")
        rb = pipeline.ingest_model(st, pid, p1, "moved.ifc", label)
        r = ifc_diff.diff_revisions(st, ra, rb)
    s = r["store"]
    phys = lambda rows: {x["global_id"] for x in rows if not x["class"].startswith("IfcStructural")}  # noqa: E731
    ia, ir, ic = phys(r["added"]), phys(r["removed"]), phys(r["changed"])
    sa, sr = {x["global_id"] for x in s["added"]}, {x["global_id"] for x in s["removed"]}
    sc = {x["global_id"] for x in s["changed"]}
    ich = {x["global_id"]: x for x in r["changed"]}
    sch = {x["global_id"]: x for x in s["changed"]}
    only_ifc = sorted(ic - sc)
    only_store = sorted(sc - ic)
    both = sorted(ic & sc)
    same_fields = [g for g in both if {k: [str(v[0]), str(v[1])] for k, v in ich[g].get("fields", {}).items()}
                   == {k: [str(v[0]), str(v[1])] for k, v in sch[g]["fields"].items() if "." in k}]
    agree_geom = {g for g in ic if "geometry" in ich[g]["kinds"]} == {g for g in sc if "geometry" in sch[g]["fields"]}
    agree_attr = {g for g in ic if "attributes" in ich[g]["kinds"]} == {g for g in sc if "type_name" in sch[g]["fields"]}
    rep = {
        "change": label,
        "per_element": {"pset_fields_identical": f"{len(same_fields)}/{len(both)}", "geometry_sets_equal": agree_geom,
                        "attributes_vs_type_name_sets_equal": agree_attr},
        "physical": {
            "added": {"ifcdiff": len(ia), "store": len(sa), "agree": ia == sa},
            "removed": {"ifcdiff": len(ir), "store": len(sr), "agree": ir == sr},
            "changed": {"ifcdiff": len(ic), "store": len(sc), "both": len(ic & sc), "ifcdiff_only": len(only_ifc),
                        "store_only": len(only_store)},
            "ifcdiff_kinds": dict(Counter(k for g in ic for k in ich[g]["kinds"])),
            "store_fields": dict(Counter(f for g in sc for f in sch[g]["fields"])),
            "ifcdiff_only_examples": [{"global_id": g, "name": ich[g]["name"], "kinds": ich[g]["kinds"],
                                       "fields": ich[g].get("fields", {})} for g in only_ifc[:8]],
            "store_only_examples": [{"global_id": g, "mark": sch[g]["mark"], "fields": sch[g]["fields"]} for g in only_store[:8]],
            "ifcdiff_only_kinds": dict(Counter(k for g in only_ifc for k in ich[g]["kinds"])),
            "store_only_fields": dict(Counter(f for g in only_store for f in sch[g]["fields"])),
        },
        "analytical_ifcdiff_only": {"added": r["counts"]["added"], "removed": r["counts"]["removed"],
                                    "changed": {k: v for k, v in r["counts"]["changed"].items() if k.startswith("IfcStructural")}},
        "store_edges": {"added": len(s["edges_added"]), "removed": len(s["edges_removed"])},
    }
    print(json.dumps(rep, indent=1, default=str))
    if a.json_out:
        with open(a.json_out, "w") as fh:
            json.dump({"report": rep, "ifcdiff": {k: r[k] for k in ("added", "removed", "changed", "counts")}, "store": s},
                      fh, indent=1, default=str)


if __name__ == "__main__":
    main()
