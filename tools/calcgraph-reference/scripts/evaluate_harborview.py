"""Score the calc engine on the Harborview sample (data/harborview, made by synth.harborview.generate).

    cd tools/calcgraph-reference
    uv run python scripts/evaluate_harborview.py [--data ../../data/harborview] [--json out.json]

Builds the rev 1 element graph from harborview-rev1.ifc with the UI's packages (scripts/build_graph.mjs), runs
packages/calc-mapper on the combined rev 1 package, and scores against ground_truth.json:
segmentation (every truth calc found by title, with the right element type), design links (role "design",
not xref), load references (xref links vs the calcs' "from" lines), calc -> calc edges, and the planted size
mismatch. Reported, not gated (no baseline yet).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
REPO = os.path.abspath(os.path.join(ROOT, "..", ".."))
BUILD_GRAPH = os.path.join(ROOT, "scripts", "build_graph.mjs")
RUN_PIPELINE = os.path.join(REPO, "packages", "calc-mapper", "scripts", "run-pipeline.ts")


def node(*args: str) -> None:
    p = subprocess.run(["node", *args], cwd=REPO, capture_output=True, text=True)
    if p.returncode:
        sys.exit(f"node {os.path.basename(args[0])} exit {p.returncode}:\n{(p.stderr or p.stdout)[-2000:]}")


def norm(s: str) -> str:
    return "".join(ch for ch in (s or "").upper() if ch.isalnum())


def prf(pred: set, true: set) -> dict:
    tp, fp, fn = len(pred & true), len(pred - true), len(true - pred)
    p = tp / (tp + fp) if tp + fp else None
    r = tp / (tp + fn) if tp + fn else None
    return {"tp": tp, "fp": fp, "fn": fn, "precision": p, "recall": r,
            "f1": 2 * p * r / (p + r) if p and r else None}


def pct(x) -> str:
    return "   -  " if x is None else f"{100 * x:5.1f}%"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join(REPO, "data", "harborview"))
    ap.add_argument("--json", help="write the full report here")
    a = ap.parse_args()
    truth = json.load(open(os.path.join(a.data, "ground_truth.json"), encoding="utf-8"))
    out = os.path.join(ROOT, "data", "eval", "harborview")
    os.makedirs(out, exist_ok=True)
    graph = os.path.join(out, "harborview-rev1.graph.json")
    node(BUILD_GRAPH, os.path.join(a.data, truth["files"]["model_rev1"]), graph)
    exp = os.path.join(out, "rev1.json")
    node(RUN_PIPELINE, "--graph", graph, "--pdf", os.path.join(a.data, truth["files"]["calc_package"]), "--out", exp)
    ex = json.load(open(exp, encoding="utf-8"))["export"]

    T = truth["elements"]
    # segmentation: truth calc -> engine calc key, by title
    by_title = {norm(c["title"]): c for c in ex["calcs"]}
    t2p = {}
    seg_bad = []
    for c in truth["calcs"]:
        pc = by_title.get(norm(c["title"]))
        if pc:
            t2p[c["id"]] = pc["key"]
        if not pc or pc.get("element_type") != c["element_type"]:
            seg_bad.append({"truth": c["title"], "found": bool(pc), "type": pc and pc.get("element_type"), "want": c["element_type"]})
    p2t = {v: k for k, v in t2p.items()}

    links = [{"g": el["global_id"], "c": p2t.get(l["calc"], l["calc"]), "tier": l["tier"], "role": l.get("role"),
              "conf": l["confidence"]} for el in ex["elements"] for l in el["calcs"] if l["review"] != "rejected"]
    design_pred = {(l["g"], l["c"]) for l in links if l["tier"] != "xref" and l["role"] == "design"}
    design_true = {(g, e["design_calc"]) for g, e in T.items() if e["design_calc"]}
    ref_pred = {(l["g"], l["c"]) for l in links if l["tier"] == "xref"}
    ref_true = {(g, c) for g, e in T.items() for c in e["ref_calcs"]}
    edges_pred = {(p2t.get(e["src"], e["src"]), p2t.get(e["dst"], e["dst"])) for e in ex["calc_edges"]}
    edges_true = {tuple(e) for e in truth["calc_edges"]}
    mis_pred = {(f["global_id"], p2t.get(f["calc_key"], f["calc_key"]), f["model_size"], f["calc_size"]) for f in ex["findings"]}
    mis_true = {(m["global_id"], m["calc"], m["model_size"].upper(), m["calc_size"].upper()) for m in truth["mismatches"]}
    mis_pred = {(g, c, ms.upper(), cs.upper()) for g, c, ms, cs in mis_pred}

    # elements whose best design link is the right calc
    best: dict[str, tuple[float, str]] = {}
    for l in links:
        if l["tier"] != "xref" and l["role"] == "design" and (l["g"] not in best or l["conf"] > best[l["g"]][0]):
            best[l["g"]] = (l["conf"], l["c"])
    top_ok = sum(1 for g, e in T.items() if e["design_calc"] and best.get(g, (0, None))[1] == e["design_calc"])

    def marks(pairs):
        return sorted(f"{T[g]['mark']} @ {c}" for g, c in pairs)[:15] if pairs else []

    report = {
        "segmentation": {"truth_calcs": len(truth["calcs"]), "engine_calcs": len(ex["calcs"]), "problems": seg_bad},
        "design": {**prf(design_pred, design_true), "elements": len(T), "top_link_correct": top_ok,
                   "missed": marks(design_true - design_pred), "false": marks(design_pred - design_true)},
        "load_refs": {**prf(ref_pred, ref_true), "missed": marks(ref_true - ref_pred), "false": marks(ref_pred - ref_true)},
        "calc_edges": {**prf(edges_pred, edges_true), "missed": sorted(edges_true - edges_pred)[:15],
                       "false": sorted(edges_pred - edges_true)[:15]},
        "mismatch": {**prf(mis_pred, mis_true), "false": sorted(mis_pred - mis_true)[:10]},
        "tiers": {t: sum(1 for l in links if l["tier"] == t) for t in sorted({l["tier"] for l in links})},
        "group_links": len(ex.get("group_links", [])),
    }
    s, d, r, e, m = (report[k] for k in ("segmentation", "design", "load_refs", "calc_edges", "mismatch"))
    print(f"Harborview rev 1: {s['truth_calcs']} truth calcs, {s['engine_calcs']} found, {len(s['problems'])} segmentation problems")
    print(f"  design links    P {pct(d['precision'])}  R {pct(d['recall'])}  F1 {pct(d['f1'])}   top link correct {d['top_link_correct']}/{d['elements']}")
    print(f"  load references P {pct(r['precision'])}  R {pct(r['recall'])}")
    print(f"  calc edges      P {pct(e['precision'])}  R {pct(e['recall'])}   ({e['tp']} of {e['tp'] + e['fn']})")
    print(f"  size mismatch   P {pct(m['precision'])}  R {pct(m['recall'])}")
    print(f"  tiers {report['tiers']}  group links {report['group_links']}")
    for k in ("segmentation", "design", "load_refs", "calc_edges", "mismatch"):
        sec = report[k]
        for f in ("problems", "missed", "false"):
            if sec.get(f):
                print(f"  {k}.{f}: {sec[f][:8]}")
    if a.json:
        json.dump(report, open(a.json, "w", encoding="utf-8"), indent=1)


if __name__ == "__main__":
    main()
