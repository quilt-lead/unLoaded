"""Score the full pipeline against the synthetic ground truth.

    uv run python scripts/evaluate.py [--seed 7] [--regen]

Runs the PRODUCTION modules (calcgraph.pipeline -> ifc_ingest, loadpath, pdf_ingest,
segment, matcher, calcdeps, store) on the synthetic package in a throwaway store and
reports:
  - calc segmentation (pages, front matter, scanned detection)
  - design mapping precision / recall: overall, per tier, per calc, per element
  - cross-reference tier: is each xref link a real mention?
  - load-path edges precision / recall (rev 1 and rev 2)
  - calc dependency edges precision / recall
  - revisions: rev1 -> rev2 element diff vs truth, and human decisions carried forward
Writes data/eval/latest.json.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))
sys.path.insert(0, ROOT)

from calcgraph import ENGINE_VERSION, pipeline  # noqa: E402
from calcgraph.store import Store  # noqa: E402
from synth.generate import generate  # noqa: E402


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
    report: dict = {"engine": ENGINE_VERSION, "seed": truth["seed"],
                    "run_at": datetime.now(ZoneInfo("America/New_York")).isoformat(timespec="seconds")}

    with tempfile.TemporaryDirectory() as tmp:
        st = Store(tmp)
        pid = st.ensure_project("eval")
        rev1 = pipeline.ingest_model(st, pid, os.path.join(a.data, "model_rev1.ifc"), "model_rev1.ifc", "rev1")
        crev = pipeline.ingest_calcs(st, pid, os.path.join(a.data, "calc_package.pdf"), "calc_package.pdf", "calcs")
        s = pipeline.state(st, pid)

        # ---------------- segmentation ----------------
        tcalcs = truth["calcs"]
        by_first = {c["pages"][0]: c for c in s["calcs"]}
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
        report["segmentation"] = {"truth_calcs": len(tcalcs), "predicted_calcs": len(s["calcs"]),
                                  "exact": sum(r["ok"] for r in seg_rows), "rows": seg_rows}

        # ---------------- design mapping ----------------
        links = [l for l in s["links"] if l["status"] != "rejected"]
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
        pred_lp = {(e["src"], e["dst"]) for e in s["edges"]}
        true_lp = {tuple(x) for x in truth["load_path"]}
        report["load_path_rev1"] = prf(len(pred_lp & true_lp), len(pred_lp - true_lp), len(true_lp - pred_lp))

        # ---------------- calc edges ----------------
        pred_ce = {(p2t.get(e["src"], e["src"]), p2t.get(e["dst"], e["dst"])) for e in s["calc_edges"]}
        true_ce = {tuple(x) for x in truth["calc_edges"]}
        report["calc_edges"] = {**prf(len(pred_ce & true_ce), len(pred_ce - true_ce), len(true_ce - pred_ce)),
                                "false": sorted(pred_ce - true_ce), "missed": sorted(true_ce - pred_ce)}

        # ---------------- revisions + carried-forward decisions ----------------
        keep = next(l for l in s["links"] if l["tier"] == "size")
        drop = next(l for l in s["links"] if l["tier"] == "partial")
        st.add_decision(pid, keep["global_id"], keep["calc_key"], "confirm", "eval", None)
        st.add_decision(pid, drop["global_id"], drop["calc_key"], "reject", "eval", "CB1 is the hand-calc cantilever")
        rev2 = pipeline.ingest_model(st, pid, os.path.join(a.data, "model_rev2.ifc"), "model_rev2.ifc", "rev2")
        s2 = pipeline.state(st, pid)
        by2 = {(l["global_id"], l["calc_key"]): l for l in s2["links"]}
        carried = {"confirm": by2.get((keep["global_id"], keep["calc_key"]), {}).get("status"),
                   "reject": by2.get((drop["global_id"], drop["calc_key"]), {}).get("status")}
        diff = st.compare_models(rev1, rev2)
        r2 = truth["rev2"]
        pred_lp2 = {(e["src"], e["dst"]) for e in s2["edges"]}
        true_lp2 = {tuple(x) for x in r2["load_path"]}
        report["revisions"] = {
            "model_revisions": [r["id"] for r in st.revisions(pid) if r["kind"] == "model"],
            "diff_removed": {"pred": len(diff["removed"]), "truth": len(r2["removed"]),
                             "exact": sorted(x["global_id"] for x in diff["removed"]) == r2["removed"]},
            "diff_added": {"pred": len(diff["added"]), "truth": len(r2["added"])},
            "diff_changed": {"pred": len(diff["changed"]), "truth": len(r2["changed"]),
                             "exact": sorted(x["global_id"] for x in diff["changed"]) == r2["changed"]},
            "load_path_rev2": prf(len(pred_lp2 & true_lp2), len(pred_lp2 - true_lp2), len(true_lp2 - pred_lp2)),
            "decisions_carried_forward": carried, "mapping_runs": len(st.runs(pid)),
        }
        # impact demo on rev1 data: remove column C8
        st2 = Store(os.path.join(tmp, "imp"))
        pid2 = st2.ensure_project("impact")
        pipeline.ingest_model(st2, pid2, os.path.join(a.data, "model_rev1.ifc"))
        pipeline.ingest_calcs(st2, pid2, os.path.join(a.data, "calc_package.pdf"))
        c8 = next(g for g, e in T.items() if e["key"] == "col:C/2")
        im = pipeline.impact_of(st2, pid2, c8, "remove")
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
