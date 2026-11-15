"""Score the calc engine (packages/calc-mapper, the TypeScript port the app runs) against the
synthetic ground truth.

    uv run python scripts/evaluate.py [--seed 7] [--regen]

Pipeline (all on the synthetic package in data/synthetic/, generated if absent):
  1. scripts/build_graph.mjs        model_rev{1,2}.ifc -> serialized element graphs (packages/ifc-parser +
                                    packages/element-graph: what the UI builds)
  2. packages/calc-mapper/scripts/run-pipeline.ts on rev 1 + calc_package.pdf -> export, auto links, the
                                    rev1 -> rev2 diff, and the impact of removing column C8
  3. two human decisions on rev 1 links (confirm the first size-tier link, reject the first partial one),
     then run-pipeline.ts on rev 2 with that decision log -> are they carried forward?
Reports:
  - calc segmentation (pages, front matter, scanned detection)
  - design mapping precision / recall: overall, per tier, per calc, per element
  - cross-reference tier: is each xref link a real mention?
  - load-path edges precision / recall (rev 1 and rev 2)
  - calc dependency edges precision / recall
  - revisions: rev1 -> rev2 element diff vs truth, and human decisions carried forward
Writes data/eval/latest.json (+ the raw engine outputs in data/eval/engine/). Needs Node >= 22.18 and the
repo's `npm ci`.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))  # tools/calcgraph-reference/
REPO = os.path.abspath(os.path.join(ROOT, "..", ".."))
sys.path.insert(0, ROOT)

from synth.generate import generate  # noqa: E402

BUILD_GRAPH = os.path.join(ROOT, "scripts", "build_graph.mjs")
RUN_PIPELINE = os.path.join(REPO, "packages", "calc-mapper", "scripts", "run-pipeline.ts")
ENGINE = "calc-mapper (packages/calc-mapper)"


def node(*args: str) -> None:
    p = subprocess.run(["node", *args], cwd=REPO, capture_output=True, text=True)
    if p.returncode:
        sys.exit(f"node {os.path.basename(args[0])} exit {p.returncode}:\n{(p.stderr or p.stdout)[-2000:]}")


def run_engine(graph: str, pdf: str, out: str, decisions: str | None = None, compare_to: str | None = None,
               impacts: list[str] = ()) -> dict:
    args = [RUN_PIPELINE, "--graph", graph, "--pdf", pdf, "--out", out]
    if decisions:
        args += ["--decisions", decisions]
    if compare_to:
        args += ["--compare-to", compare_to]
    for i in impacts:
        args += ["--impact", i]
    node(*args)
    return json.load(open(out))


def links_of(export: dict) -> list[dict]:
    """Every element -> calc link of an export, flattened."""
    return [{"global_id": el["global_id"], "calc_key": l["calc"], "conf": l["confidence"], "tier": l["tier"],
             "status": l["review"]} for el in export["elements"] for l in el["calcs"]]


def prf(tp: int, fp: int, fn: int) -> dict:
    p = tp / (tp + fp) if tp + fp else None
    r = tp / (tp + fn) if tp + fn else None
    f = 2 * p * r / (p + r) if p and r else None
    return {"tp": tp, "fp": fp, "fn": fn, "precision": p, "recall": r, "f1": f}


def pct(x) -> str:
    return "  -  " if x is None else f"{100 * x:5.1f}%"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--data", default=os.path.join(ROOT, "data", "synthetic"))
    ap.add_argument("--regen", action="store_true", help="regenerate the synthetic data first")
    a = ap.parse_args()
    if a.regen or not os.path.exists(os.path.join(a.data, "ground_truth.json")):
        generate(a.data, a.seed)
    truth = json.load(open(os.path.join(a.data, "ground_truth.json")))
    T = truth["elements"]
    eng = os.path.join(ROOT, "data", "eval", "engine")
    os.makedirs(eng, exist_ok=True)
    g1, g2 = (os.path.join(a.data, f"model_rev{n}.graph.json") for n in (1, 2))
    node(BUILD_GRAPH, os.path.join(a.data, "model_rev1.ifc"), g1, os.path.join(a.data, "model_rev2.ifc"), g2)
    pdf = os.path.join(a.data, "calc_package.pdf")
    c8 = next(g for g, e in T.items() if e["key"] == "col:C/2")
    r1 = run_engine(g1, pdf, os.path.join(eng, "rev1.json"), compare_to=g2, impacts=[f"{c8}:remove"])
    ex1 = r1["export"]
    report: dict = {"engine": ENGINE, "seed": truth["seed"],
                    "run_at": datetime.now(ZoneInfo("America/New_York")).isoformat(timespec="seconds")}

    # ---------------- segmentation ----------------
    tcalcs = truth["calcs"]
    pcalcs = [{"key": c["key"], "pages": c["pages"], "front": c["front_matter"], "scanned": c["scanned"],
               "software": c["software"], "cat": c["element_type"]} for c in ex1["calcs"]]
    by_first = {c["pages"][0]: c for c in pcalcs}
    t2p: dict[str, str] = {}
    seg_rows = []
    for tc in tcalcs:
        pc = by_first.get(tc["pages"][0])
        ok = bool(pc and pc["pages"] == tc["pages"] and pc["front"] == tc["front"] and pc["scanned"] == tc["scanned"])
        if pc:
            t2p[tc["id"]] = pc["key"]
        seg_rows.append({"truth": tc["id"], "title": tc["title"], "pages": tc["pages"], "pred": pc["key"] if pc else None,
                         "pred_pages": pc["pages"] if pc else None, "ok": ok,
                         "software_ok": (not tc["software"]) or bool(pc and pc["software"] == tc["software"]),
                         "type_ok": (not tc["element_type"]) or bool(pc and pc["cat"] == tc["element_type"])})
    p2t = {v: k for k, v in t2p.items()}
    report["segmentation"] = {"truth_calcs": len(tcalcs), "predicted_calcs": len(pcalcs),
                              "exact": sum(r["ok"] for r in seg_rows), "rows": seg_rows}

    # ---------------- design mapping ----------------
    links = [l for l in links_of(ex1) if l["status"] != "rejected"]
    design_pred = {(l["global_id"], p2t.get(l["calc_key"], l["calc_key"])): l for l in links if l["tier"] != "xref"}
    design_truth = {(g, e["design_calc"]) for g, e in T.items() if e["design_calc"]}
    tp = design_pred.keys() & design_truth
    overall = prf(len(tp), len(design_pred.keys() - design_truth), len(design_truth - design_pred.keys()))
    tiers: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for k, l in design_pred.items():
        tiers[l["tier"]][0] += 1
        tiers[l["tier"]][1] += k in design_truth
    per_calc = {}
    for tc in tcalcs:
        cid = tc["id"]
        tr = {g for g, c in design_truth if c == cid}
        pr = {g for g, c in design_pred if c == cid}
        per_calc[cid] = {"title": tc["title"], **prf(len(tr & pr), len(pr - tr), len(tr - pr))}
    # element-level: is the highest-confidence non-xref link the designing calc?
    best: dict[str, dict] = {}
    for (g, c), l in design_pred.items():
        if g not in best or l["conf"] > best[g]["conf"]:
            best[g] = {"calc": c, "conf": l["conf"]}
    el_rows = {"with_design_calc": 0, "top_link_correct": 0, "no_link": 0, "wrong_top_link": 0,
               "true_negatives": 0, "false_links_on_uncovered": 0}
    for g, e in T.items():
        if e["design_calc"]:
            el_rows["with_design_calc"] += 1
            if g not in best:
                el_rows["no_link"] += 1
            elif best[g]["calc"] == e["design_calc"]:
                el_rows["top_link_correct"] += 1
            else:
                el_rows["wrong_top_link"] += 1
        else:
            el_rows["true_negatives" if g not in best else "false_links_on_uncovered"] += 1
    misses = sorted({T[g]["mark"] or T[g]["key"] for g, c in design_truth - design_pred.keys()})
    fps = defaultdict(list)
    for (g, c) in design_pred.keys() - design_truth:
        fps[(c, design_pred[(g, c)]["tier"])].append(T[g]["mark"] or T[g]["key"])
    report["design_mapping"] = {
        "overall": overall,
        "per_tier": {t: {"links": n, "correct": ok, "precision": ok / n} for t, (n, ok) in sorted(tiers.items())},
        "per_calc": per_calc, "elements": el_rows, "missed_marks": misses,
        "false_positives": [{"calc": c, "tier": t, "count": len(v), "marks": sorted(set(v))[:12]}
                            for (c, t), v in sorted(fps.items())],
    }
    # ---------------- xref tier ----------------
    xr = [l for l in links if l["tier"] == "xref"]
    real = 0
    for l in xr:
        c = p2t.get(l["calc_key"], l["calc_key"])
        e = T[l["global_id"]]
        real += c in e["ref_calcs"] or c == e["design_calc"]
    ref_truth = {(g, c) for g, e in T.items() for c in e["ref_calcs"]}
    ref_pred = {(l["global_id"], p2t.get(l["calc_key"], l["calc_key"])) for l in xr}
    report["xref_tier"] = {"links": len(xr), "real_mentions": real, "precision": real / len(xr) if xr else None,
                           "reference_recall": len(ref_truth & ref_pred) / len(ref_truth) if ref_truth else None,
                           "xref_that_are_actually_designs": sum(1 for l in xr if T[l["global_id"]]["design_calc"]
                                                                 == p2t.get(l["calc_key"]))}

    # ---------------- load path ----------------
    # truth models connection plates as path nodes (member -> plate -> support), as the element
    # graph's supports edges do
    pred_lp = {(e["src"], e["dst"]) for e in ex1["load_path"]}
    true_lp = {tuple(x) for x in truth["load_path"]}
    report["load_path_rev1"] = prf(len(pred_lp & true_lp), len(pred_lp - true_lp), len(true_lp - pred_lp))

    # ---------------- calc edges ----------------
    pred_ce = {(p2t.get(e["src"], e["src"]), p2t.get(e["dst"], e["dst"])) for e in ex1["calc_edges"]}
    true_ce = {tuple(x) for x in truth["calc_edges"]}
    report["calc_edges"] = {**prf(len(pred_ce & true_ce), len(pred_ce - true_ce), len(true_ce - pred_ce)),
                            "false": sorted(pred_ce - true_ce), "missed": sorted(true_ce - pred_ce)}

    # ---------------- revisions + carried-forward decisions ----------------
    run1 = r1["run"]["links"]  # auto links in run order (calc_key, global_id)
    keep = next(l for l in run1 if l["tier"] == "size")
    drop = next(l for l in run1 if l["tier"] == "partial")
    decisions = [
        {"id": 1, "global_id": keep["global_id"], "calc_key": keep["calc_key"], "action": "confirm", "actor": "eval",
         "note": None, "at": report["run_at"], "model_rev": "rev1", "calc_rev": "calcs"},
        {"id": 2, "global_id": drop["global_id"], "calc_key": drop["calc_key"], "action": "reject", "actor": "eval",
         "note": "CB1 is the hand-calc cantilever", "at": report["run_at"], "model_rev": "rev1", "calc_rev": "calcs"}]
    dpath = os.path.join(eng, "decisions.json")
    json.dump(decisions, open(dpath, "w"))
    r2 = run_engine(g2, pdf, os.path.join(eng, "rev2.json"), decisions=dpath)
    by2 = {(l["global_id"], l["calc_key"]): l for l in links_of(r2["export"])}
    carried = {"confirm": by2.get((keep["global_id"], keep["calc_key"]), {}).get("status"),
               "reject": by2.get((drop["global_id"], drop["calc_key"]), {}).get("status")}
    diff = r1["compare"]
    r2t = truth["rev2"]
    pred_lp2 = {(e["src"], e["dst"]) for e in r2["export"]["load_path"]}
    true_lp2 = {tuple(x) for x in r2t["load_path"]}
    report["revisions"] = {
        "model_revisions": ["rev1", "rev2"],
        "diff_removed": {"pred": len(diff["removed"]), "truth": len(r2t["removed"]),
                         "exact": sorted(x["global_id"] for x in diff["removed"]) == r2t["removed"]},
        "diff_added": {"pred": len(diff["added"]), "truth": len(r2t["added"])},
        "diff_changed": {"pred": len(diff["changed"]), "truth": len(r2t["changed"]),
                         "exact": sorted(x["global_id"] for x in diff["changed"]) == r2t["changed"]},
        "load_path_rev2": prf(len(pred_lp2 & true_lp2), len(pred_lp2 - true_lp2), len(true_lp2 - pred_lp2)),
        "decisions_carried_forward": carried, "mapping_runs": 2,
    }
    # impact on rev 1: remove column C8
    im = r1["impacts"][f"{c8}:remove"]
    report["impact_remove_C8"] = {"removed": len(im["removed"]), "hit": len(im["hit"]), "waves": im["waves"],
                                  "stale_calcs": sorted(p2t.get(k, k) for k in im["stale"])}

    os.makedirs(os.path.join(ROOT, "data", "eval"), exist_ok=True)
    with open(os.path.join(ROOT, "data", "eval", "latest.json"), "w") as fh:
        json.dump(report, fh, indent=1, default=str)
    _print(report)


def _print(r: dict) -> None:
    print(f"calc-graph evaluation - {r['engine']} - seed {r['seed']} - {r['run_at']} (Eastern)\n")
    sg = r["segmentation"]
    print(f"SEGMENTATION  {sg['exact']}/{sg['truth_calcs']} calcs with exact page ranges + front/scanned flags "
          f"({sg['predicted_calcs']} predicted)")
    for row in sg["rows"]:
        flag = "ok " if row["ok"] else "BAD"
        print(f"  {flag} {row['truth']} pp{row['pages']} -> {row['pred']}  software {'ok' if row['software_ok'] else 'WRONG'}"
              f"  type {'ok' if row['type_ok'] else 'WRONG'}")
    d = r["design_mapping"]
    o = d["overall"]
    print(f"\nDESIGN MAPPING (element -> calc that sized it; xref links excluded)")
    print(f"  overall   precision {pct(o['precision'])}  recall {pct(o['recall'])}  F1 {pct(o['f1'])}   "
          f"(tp {o['tp']}, fp {o['fp']}, fn {o['fn']})")
    print("  per tier:")
    for t, v in d["per_tier"].items():
        print(f"    {t:<8} {v['links']:>4} links  precision {pct(v['precision'])}")
    print("  per calc:")
    for cid, v in d["per_calc"].items():
        if v["tp"] + v["fp"] + v["fn"]:
            print(f"    {cid} {v['title'][:44]:<44} P {pct(v['precision'])}  R {pct(v['recall'])}  "
                  f"(tp {v['tp']}, fp {v['fp']}, fn {v['fn']})")
    e = d["elements"]
    print(f"  elements: {e['top_link_correct']}/{e['with_design_calc']} top link correct, {e['no_link']} unlinked, "
          f"{e['wrong_top_link']} wrong top link; uncovered elements: {e['true_negatives']} correctly unlinked, "
          f"{e['false_links_on_uncovered']} falsely linked")
    print(f"  missed: {', '.join(d['missed_marks']) or '-'}")
    for fp in d["false_positives"]:
        print(f"  false positives: {fp['count']:>3} via {fp['tier']:<8} -> {fp['calc']}  e.g. {', '.join(fp['marks'][:6])}")
    x = r["xref_tier"]
    print(f"\nXREF TIER  {x['links']} links, {x['real_mentions']} are real mentions (precision {pct(x['precision'])}), "
          f"reference recall {pct(x['reference_recall'])}, {x['xref_that_are_actually_designs']} are really designs")
    lp = r["load_path_rev1"]
    print(f"\nLOAD PATH rev1  precision {pct(lp['precision'])}  recall {pct(lp['recall'])}  (tp {lp['tp']}, fp {lp['fp']}, fn {lp['fn']})")
    ce = r["calc_edges"]
    print(f"CALC EDGES      precision {pct(ce['precision'])}  recall {pct(ce['recall'])}  (tp {ce['tp']}, fp {ce['fp']}, fn {ce['fn']})")
    print(f"  false: {ce['false']}\n  missed: {ce['missed']}")
    rv = r["revisions"]
    print(f"\nREVISIONS  model revs {rv['model_revisions']}, mapping runs {rv['mapping_runs']}")
    print(f"  rev1->rev2 diff: removed {rv['diff_removed']['pred']}/{rv['diff_removed']['truth']} "
          f"(exact {rv['diff_removed']['exact']}), changed {rv['diff_changed']['pred']}/{rv['diff_changed']['truth']} "
          f"(exact {rv['diff_changed']['exact']}), added {rv['diff_added']['pred']}/{rv['diff_added']['truth']}")
    lp2 = rv["load_path_rev2"]
    print(f"  load path rev2 precision {pct(lp2['precision'])} recall {pct(lp2['recall'])}")
    print(f"  decisions carried to rev2: confirm -> {rv['decisions_carried_forward']['confirm']}, "
          f"reject -> {rv['decisions_carried_forward']['reject']}")
    im = r["impact_remove_C8"]
    print(f"\nIMPACT remove C8 (rev1): {im['removed']} removed, {im['hit']} elements hit over {im['waves']} waves, "
          f"stale calcs {im['stale_calcs']}")


if __name__ == "__main__":
    main()
