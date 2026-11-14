"""Build connection nodes (types from S8 details, instances on plans/elevations) for a drawing set.

  uv run python scripts/build_connections.py [--sid dana-point-bldg12]

Reads data/sets/<sid>/graph.json (sheets + elements, read-only) and meta.json (local PDF paths),
writes data/sets/<sid>/connections.json (gitignored: derived from copyrighted PDFs) and prints counts.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from calcgraph import connections  # noqa: E402
from calcgraph.set_pipeline import SETS_DIR  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sid", default="dana-point-bldg12")
    a = ap.parse_args()
    d = os.path.join(SETS_DIR, a.sid)
    g = json.load(open(os.path.join(d, "graph.json")))
    meta = json.load(open(os.path.join(d, "meta.json")))
    docs = meta["docs"]
    calc_docs = [(k, v["path"]) for k, v in docs.items() if v.get("role") == "Calc package"]
    calc_ids = {(c["doc"], c["page"]): c["id"] for c in g["calcs"]}
    t0 = time.time()
    s_sheets = [s for s in g["sheets"] if s["sheet"].startswith("S")]
    out = connections.build(docs["plans"]["path"], s_sheets, g["elements"], calc_docs, calc_ids)
    inst = out["instances"]
    att = [i for i in inst if i["attached"]]
    cov = {
        "connection_types": len(out["types"]),
        "connection_types_titled_as_connections": sum(t["is_connection"] for t in out["types"]),
        "types_with_instances": sum(1 for t in out["types"] if t["instances"]),
        "instances": len(inst),
        "instances_attached": len(att),
        "instances_unattached": len(inst) - len(att),
        "unattached_located_via_view": sum(1 for i in inst if not i["attached"] and i.get("located_via_view")),
        "unattached_located_via_view_with_elements": sum(1 for i in inst if not i["attached"] and i.get("view_elements")),
        "unattached_by_sheet": dict(Counter(i["sheet"] for i in inst if not i["attached"])),
        "views": len(out["views"]),
        "instances_by_via": dict(Counter(i["via"] for i in inst)),
        "instances_by_sheet_via": dict(Counter(f"{i['sheet']} {i['via']}{' ' + i['symbol'] if i['symbol'] else ''}" for i in inst)),
        "instances_missing_type": sorted({i["ref"] for i in inst if i.get("missing_type")}),
        "detail_to_detail_refs": len(out["detail_refs"]),
        "other_callouts": len(out["other_callouts"]),
        "note_refs": len(out["note_refs"]),
        "legend_check": out["legend_check"],
        "calc_hits_by_rule": dict(Counter(h["rule"] for h in out["calc"]["hits"])),
        "calc_pages_designing_connections": sorted({f"{h["calc"]} ({h["doc"]} p{h["page"]})" for h in out["calc"]["hits"] if h["designs_connection"]}),
        "calc_detail_refs": sorted({f"{r['calc']} -> {r['ref']} ({r['target_kind']})" for r in out["calc"]["detail_refs"]}),
        "unresolved_refs": sorted({o["ref"] for o in out["other_callouts"] if "not found" in o["kind"]} | {r["ref"] for r in out["detail_refs"] if not r["known"]}),
        "stats": out["stats"],
        "build_seconds": round(time.time() - t0, 1),
    }
    res = {"id": a.sid, "built_at": time.strftime("%Y-%m-%d %H:%M:%S %Z"), "source_graph_built_at": g.get("built_at"),
           "coverage": cov} | out
    with open(os.path.join(d, "connections.json"), "w") as fh:
        json.dump(res, fh, default=lambda o: list(o) if isinstance(o, tuple) else str(o))
    print(json.dumps(cov, indent=1, default=str))


if __name__ == "__main__":
    main()
