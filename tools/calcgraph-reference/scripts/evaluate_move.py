"""Score packages/move-impact (the TypeScript move-a-column screen) against the v2 answer key.

    cd tools/calcgraph-reference
    uv run python scripts/evaluate_move.py [--results data/synthetic_v2/move_results.json] [--json-out m.json]

Port of the hackathon's scripts/evaluate_move.py (calc-graph prototype). The engine under test is no
longer the Python engine on the generator's design file: it is the TS package run by
packages/move-impact/scripts/run-scenarios.ts on the element graph of the uploaded IFC plus calc facts
(scripts/move_fixture.py - printed calc-row values, a stand-in for matcher output). Same metrics and
the same definitions as the hackathon scorer:

- stale set: precision / recall of the topological calc rows and of the screened (> 5 %) subset
  against the records whose demand truly moved > 5 % (or whose size / detail changed); records that
  cannot exist before the change ("new record") are not predictable by id and are left out
- UC error: estimated utilisation at the current size vs the re-run's UC at the current size
  (beams, girders, columns, footings, connections) - median / p90 / max absolute error, share within
  0.05, and over/under-1.0 flag agreement
- health band vs the answer key's difficulty: exact, within one band, confusion matrix
- (info, also without calc facts) element level: the elements of the truly changed records vs the
  engine's topological / screened elements

Fact ids are the generator's record ids (scripts/move_fixture.py), and estimates are keyed by
GlobalId; design.json maps GlobalIds back to the answer key's element ids. That mapping is used ONLY
here, for scoring - never by the engine.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
V2 = os.path.join(ROOT, "data", "synthetic_v2")
BANDS = ["easy", "moderate", "hard", "do-not-move"]


def pr(pred: set, truth: set) -> tuple[float, float]:
    tp = len(pred & truth)
    return (tp / len(pred) if pred else 1.0, tp / len(truth) if truth else 1.0)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=V2)
    ap.add_argument("--results", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--json-out", default=None, help="evaluate_all contract: {metrics, gated}")
    a = ap.parse_args()
    res_path = a.results or os.path.join(a.dir, "move_results.json")
    out_path = a.out or os.path.join(a.dir, "move_eval.json")
    key = json.load(open(os.path.join(a.dir, "answer_key.json")))
    des = json.load(open(os.path.join(a.dir, "design.json")))
    to_id = {e["global_id"]: e["id"] for e in des["elements"] if e.get("global_id")}
    rec_els = {r["id"]: r["elements"] for r in des["records"]}
    results = {r["id"]: r for r in json.load(open(res_path))["results"]}
    rows, errs, conf = [], [], {}
    tp_t = fp_t = fn_t = tp_s = fp_s = fn_s = 0
    el_t = [0, 0, 0]   # element level (works without calc facts): tp, fp, fn of the screened elements
    el_s = [0, 0, 0]
    for k in key["scenarios"]:
        res = results[k["id"]]["result"]
        truth = set(k["changed_records"])
        truth_known = {r for r in truth if k["changed_records"][r] != "new record"}
        rows_ = res.get("staleRows") or []
        topo = {s["fact"] for s in rows_}
        scr = {s["fact"] for s in rows_ if s["screened"]}
        p_t, r_t = pr(topo, truth_known)
        p_s, r_s = pr(scr, truth_known)
        tp_t += len(topo & truth_known); fp_t += len(topo - truth_known); fn_t += len(truth_known - topo)
        tp_s += len(scr & truth_known); fp_s += len(scr - truth_known); fn_s += len(truth_known - scr)
        # element level: elements of the truly changed records that exist in the model
        truth_el = {e for r in truth_known for e in rec_els.get(r, []) if e in to_id.values()}
        for acc, pred in ((el_t, {to_id.get(t["element"]) for t in res["topological"]}),
                          (el_s, {to_id.get(t["element"]) for t in res["screened"]})):
            pred.discard(None)
            acc[0] += len(pred & truth_el); acc[1] += len(pred - truth_el); acc[2] += len(truth_el - pred)
        e_s = []
        for gid, v in (res.get("estimates") or {}).items():
            eid = to_id.get(gid)
            tv = k["uc_at_current"].get(eid) if eid else None
            if tv is not None and v.get("utilisationAfter") is not None:
                e_s.append({"element": eid, "est": v["utilisationAfter"], "truth": tv, "abs_err": abs(v["utilisationAfter"] - tv)})
        errs += e_s
        band = (res.get("health") or {}).get("band", "n/a")
        conf.setdefault(k["difficulty"], {}).setdefault(band, 0)
        conf[k["difficulty"]][band] += 1
        rows.append({"id": k["id"], "label": k["label"], "truth_stale": len(truth_known), "new_records": len(truth) - len(truth_known),
                     "topo": len(topo), "screened": len(scr), "P_topo": round(p_t, 3), "R_topo": round(r_t, 3),
                     "P_scr": round(p_s, 3), "R_scr": round(r_s, 3), "uc_n": len(e_s),
                     "uc_med_err": round(statistics.median([e["abs_err"] for e in e_s]), 3) if e_s else None,
                     "truth_band": k["difficulty"], "band": band,
                     "reasons": [r["reason"] for r in (res.get("health") or {}).get("reasons", [])[:3]],
                     "missed": sorted(truth_known - topo)[:8], "missed_screened": sorted(truth_known - scr)[:8],
                     "extra_screened": sorted(scr - truth_known)[:8]})
    ae = sorted(e["abs_err"] for e in errs)

    def q(p):
        return ae[min(len(ae) - 1, int(p * len(ae)))] if ae else None
    agree = sum(1 for r in rows if r["band"] == r["truth_band"])
    within = sum(1 for r in rows if r["band"] in BANDS and abs(BANDS.index(r["band"]) - BANDS.index(r["truth_band"])) <= 1)
    summary = {
        "scenarios": len(rows),
        "stale_topological": {"precision": round(tp_t / max(1, tp_t + fp_t), 3), "recall": round(tp_t / max(1, tp_t + fn_t), 3),
                              "tp": tp_t, "fp": fp_t, "fn": fn_t},
        "stale_screened": {"precision": round(tp_s / max(1, tp_s + fp_s), 3), "recall": round(tp_s / max(1, tp_s + fn_s), 3),
                           "tp": tp_s, "fp": fp_s, "fn": fn_s},
        "elements_topological": {"precision": round(el_t[0] / max(1, el_t[0] + el_t[1]), 3), "recall": round(el_t[0] / max(1, el_t[0] + el_t[2]), 3)},
        "elements_screened": {"precision": round(el_s[0] / max(1, el_s[0] + el_s[1]), 3), "recall": round(el_s[0] / max(1, el_s[0] + el_s[2]), 3)},
        "uc_error": {"n": len(ae), "median": q(0.5), "p90": q(0.9), "max": ae[-1] if ae else None,
                     "within_0.05": round(sum(1 for x in ae if x <= 0.05) / max(1, len(ae)), 3),
                     "over_flag_agreement": round(sum(1 for e in errs if (e["est"] > 1) == (e["truth"] > 1)) / max(1, len(errs)), 3)},
        "health": {"exact": agree, "within_one": within, "confusion_truth_x_engine": conf},
    }
    json.dump({"summary": summary, "rows": rows, "uc_errors": errs}, open(out_path, "w"), indent=1)
    m = {"stale_topological_precision": summary["stale_topological"]["precision"],
         "stale_topological_recall": summary["stale_topological"]["recall"],
         "stale_screened_precision": summary["stale_screened"]["precision"],
         "stale_screened_recall": summary["stale_screened"]["recall"],
         "uc_within_0_05": summary["uc_error"]["within_0.05"],
         "uc_over_flag_agreement": summary["uc_error"]["over_flag_agreement"],
         "health_band_exact": agree / max(1, len(rows)), "health_band_within_one": within / max(1, len(rows)),
         "uc_abs_err_p90": summary["uc_error"]["p90"]}
    if a.json_out:
        # uc_abs_err_p90 is an error: lower is better, so it is gated in that direction
        json.dump({"metrics": m, "gated": [k for k in m if k != "uc_abs_err_p90"], "gated_lower": ["uc_abs_err_p90"]},
                  open(a.json_out, "w"), indent=1)
    for r in rows:
        print(f"{r['id']} P/R topo {r['P_topo']:.2f}/{r['R_topo']:.2f}  scr {r['P_scr']:.2f}/{r['R_scr']:.2f}  "
              f"uc err {r['uc_med_err']}  band {r['band']:<11} truth {r['truth_band']:<11} {r['label'][:48]}")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
