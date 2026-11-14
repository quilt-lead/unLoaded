"""Coverage numbers for a drawing-set project (no ground truth exists for a real set).

  uv run python scripts/evaluate_set.py [--sid dana-point-bldg12] [--rebuild]

--rebuild re-runs the ingest from the local PDFs (CALCGRAPH_SET_DIR, default
~/Downloads/dana-point-bldg12-public-set); otherwise reads data/sets/<sid>/graph.json.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from calcgraph import set_pipeline  # noqa: E402

DEFAULT_DIR = os.environ.get("CALCGRAPH_SET_DIR", os.path.expanduser("~/Downloads/dana-point-bldg12-public-set"))


def build(sid: str) -> dict:
    d = DEFAULT_DIR
    return set_pipeline.ingest_set(sid, "Dana Point Harbor Bldg 12 (permit set)",
                                   os.path.join(d, "OC-DPH_PKG21-0516_Bldg12_ApprovedPlans.pdf"),
                                   [(os.path.join(d, "OC-DPH_PKG21-0516_Bldg12_Calcs.pdf"), "calcs", None),
                                    (os.path.join(d, "OC-DPH_PKG21-0516_Bldg12_StairCalcs.pdf"), "stair", "STAIR")])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sid", default="dana-point-bldg12")
    ap.add_argument("--rebuild", action="store_true")
    a = ap.parse_args()
    if a.rebuild:
        g = build(a.sid)
    else:
        g = json.load(open(os.path.join(set_pipeline.SETS_DIR, a.sid, "graph.json")))
    c = g["coverage"]
    print(f"== {g['name']}  (built {g['built_at']}, {g['build_seconds']} s)")
    print(f"S-sheets read: {len(g['sheets'])}; elements (unique tags): {c['elements']}")
    print("Tags by sheet and type:")
    for sh, d in c["tags_by_sheet_type"].items():
        print(f"  {sh:9s} " + ", ".join(f"{k} {v}" for k, v in sorted(d.items(), key=lambda x: -x[1])))
    print("Tags by type: " + ", ".join(f"{k} {v}" for k, v in c["tags_by_type"].items()))
    print(f"Elements linked to >=1 calc page: {c['elements_linked']}/{c['elements']} "
          f"({100 * c['elements_linked'] / max(1, c['elements']):.0f}%); with a link scored >= 0.62: {c['elements_linked_strong']}")
    by_type = Counter(); by_type_l = Counter()
    linked = {l["el"] for l in g["links"]}
    for e in g["elements"]:
        by_type[e["type"]] += 1
        by_type_l[e["type"]] += e["id"] in linked
    print("  linked by type: " + ", ".join(f"{t} {by_type_l[t]}/{n}" for t, n in by_type.most_common()))
    print(f"Calc pages: {c['calc_pages']}; linked to >=1 element: {c['calc_pages_linked']}; linked to nothing: {c['calc_pages_unlinked']}")
    print(f"Links: {c['links']} by tier {c['links_by_tier']}")
    print(f"Calc page roles: {c.get('calc_page_roles')}")
    print(f"Links refused by the system -> section table: {c.get('links_refused_by_system')}")
    print(f"System -> allowed sections: {c.get('system_sections')}")
    print(f"Calc edges: {c['calc_edges']} by rule {c['calc_edges_by_rule']}")
    print(f"RISA-3D floor -> level check: {c['floor_level_check']}")
    print(f"Load-path edges: {c['load_path_edges']}; stats {c['load_path']}")
    print("Findings: " + ", ".join(f"{k} {v}" for k, v in Counter(f["kind"] for f in g["findings"]).items()))
    for f in g["findings"]:
        if f["kind"] in ("grid mismatch", "size mismatch", "truncated sizes in calcs"):
            print(f"  [{f['kind']}] {f['text']}")


if __name__ == "__main__":
    main()
