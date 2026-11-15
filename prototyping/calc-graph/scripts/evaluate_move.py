"""Score the move-a-column impact engine against the ground-truth answer key.

    uv run python scripts/evaluate_move.py [--out data/eval/synthetic_v2/move_eval.json]

Reads the source data (data/synthetic_v2, read only); writes its result under the derived-outputs root
(calcgraph.store_root.derived_for: data/eval/synthetic_v2/, CALCGRAPH_DERIVED overrides).

For every scenario in data/synthetic_v2/answer_key.json (built by re-running the full
design, `uv run python -m synth.v2.scenarios`), run backend/calcgraph/move_impact.impact on
the BASE design export only and compare:
- stale set: precision / recall of the topological set and of the screened (> 5 %) subset
  against the records whose demand truly moved > 5 % (or whose size/detail changed)
- screening UC error: estimated UC at the current size vs the re-run's UC at the current size
  (beams, girders, columns, footings, connections) - median / p90 / max absolute error
- health band vs ground-truth difficulty: exact agreement, within one band, confusion matrix
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))
sys.path.insert(0, ROOT)

from calcgraph import move_impact  # noqa: E402
from calcgraph.store_root import SYNTH_V2_DIR, SourceDataMissing, derived_for, source_file  # noqa: E402

BANDS = move_impact.BANDS


def pr(pred: set, truth: set) -> tuple[float, float]:
    tp = len(pred & truth)
    return (tp / len(pred) if pred else 1.0, tp / len(truth) if truth else 1.0)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None, help="default <derived>/synthetic_v2/move_eval.json "
                                                 "(move_eval_ingested.json with --source ingested)")
    ap.add_argument("--json-out", default=None, help="evaluate_all contract: {metrics, gated}")
    ap.add_argument("--source", choices=["design", "ingested"], default="design",
                    help="design = generator registry; ingested = registry rebuilt from the documents + IFC")
    a = ap.parse_args()
    base = json.load(open(source_file("design.json")))
    to_truth = None
    if a.source == "ingested":
        from calcgraph import registry_engine
        ing = json.load(open(derived_for(SYNTH_V2_DIR, "registry_ingested.json")))   # scripts/build_registry.py
        eng = registry_engine.to_engine(ing, source_file("model.ifc"))
        # map an ingested record (REC:<sheet>#n) to the truth record id by (calc, subject element) -
        # used ONLY for scoring, never by the engine
        idx = {(r["calc"], e): r["id"] for r in base["records"] for e in r["elements"]}
        to_truth = {r["id"]: idx.get((r["calc"], r["elements"][0])) for r in eng["records"] if r["elements"]}
        base_for_engine = eng
    else:
        base_for_engine = base
    if a.out is None:
        a.out = derived_for(SYNTH_V2_DIR, "move_eval_ingested.json" if a.source == "ingested" else "move_eval.json")
    key = json.load(open(source_file("answer_key.json")))   # synth.v2.scenarios writes it
    rows, errs, conf = [], [], {}
    tp_t = fp_t = fn_t = tp_s = fp_s = fn_s = 0
    for k in key["scenarios"]:
        t = time.time()
        res = move_impact.impact(base_for_engine, k["column"], k["dx"], k["dy"], remove=k["kind"] == "remove")
        if to_truth is not None:
            for s_ in res["stale"]:
                s_["record"] = to_truth.get(s_["record"]) or s_["record"]
        truth = set(k["changed_records"])
        # records that cannot exist before the change (new members) are not predictable by id
        truth_known = {r for r in truth if k["changed_records"][r] != "new record"}
        topo = {s["record"] for s in res["stale"]}
        scr = {s["record"] for s in res["stale"] if s["screened"]}
        p_t, r_t = pr(topo, truth_known)
        p_s, r_s = pr(scr, truth_known)
        tp_t += len(topo & truth_known); fp_t += len(topo - truth_known); fn_t += len(truth_known - topo)
        tp_s += len(scr & truth_known); fp_s += len(scr - truth_known); fn_s += len(truth_known - scr)
        e_s = []
        for eid, v in res["estimates"].items():
            tv = k["uc_at_current"].get(eid)
            if tv is not None and v.get("uc_new") is not None:
                e_s.append({"element": eid, "est": v["uc_new"], "truth": tv, "abs_err": abs(v["uc_new"] - tv)})
        errs += e_s
        band = res["health"]["band"]
        conf.setdefault(k["difficulty"], {}).setdefault(band, 0)
        conf[k["difficulty"]][band] += 1
        rows.append({"id": k["id"], "label": k["label"], "truth_stale": len(truth_known), "new_records": len(truth) - len(truth_known),
                     "topo": len(topo), "screened": len(scr), "P_topo": round(p_t, 3), "R_topo": round(r_t, 3),
                     "P_scr": round(p_s, 3), "R_scr": round(r_s, 3), "uc_n": len(e_s),
                     "uc_med_err": round(statistics.median([e["abs_err"] for e in e_s]), 3) if e_s else None,
                     "truth_band": k["difficulty"], "band": band, "reasons": [r["reason"] for r in res["health"]["reasons"][:3]],
                     "missed": sorted(truth_known - topo)[:8], "seconds": round(time.time() - t, 2)})
    ae = sorted(e["abs_err"] for e in errs)
    def q(p):
        return ae[min(len(ae) - 1, int(p * len(ae)))] if ae else None
    agree = sum(1 for r in rows if r["band"] == r["truth_band"])
    within = sum(1 for r in rows if abs(BANDS.index(r["band"]) - BANDS.index(r["truth_band"])) <= 1)
    summary = {
        "scenarios": len(rows),
        "stale_topological": {"precision": round(tp_t / max(1, tp_t + fp_t), 3), "recall": round(tp_t / max(1, tp_t + fn_t), 3),
                              "tp": tp_t, "fp": fp_t, "fn": fn_t},
        "stale_screened": {"precision": round(tp_s / max(1, tp_s + fp_s), 3), "recall": round(tp_s / max(1, tp_s + fn_s), 3),
                           "tp": tp_s, "fp": fp_s, "fn": fn_s},
        "uc_error": {"n": len(ae), "median": q(0.5), "p90": q(0.9), "max": ae[-1] if ae else None,
                     "within_0.05": round(sum(1 for x in ae if x <= 0.05) / max(1, len(ae)), 3),
                     "over_flag_agreement": round(sum(1 for e in errs if (e["est"] > 1) == (e["truth"] > 1)) / max(1, len(errs)), 3)},
        "health": {"exact": agree, "within_one": within, "confusion_truth_x_engine": conf},
    }
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    json.dump({"summary": summary, "rows": rows, "uc_errors": errs}, open(a.out, "w"), indent=1)
    if a.json_out:
        m = {"stale_topological_precision": summary["stale_topological"]["precision"],
             "stale_topological_recall": summary["stale_topological"]["recall"],
             "stale_screened_precision": summary["stale_screened"]["precision"],
             "stale_screened_recall": summary["stale_screened"]["recall"],
             "uc_within_0_05": summary["uc_error"]["within_0.05"],
             "uc_over_flag_agreement": summary["uc_error"]["over_flag_agreement"],
             "health_band_exact": agree / max(1, len(rows)), "health_band_within_one": within / max(1, len(rows)),
             "uc_abs_err_p90": summary["uc_error"]["p90"]}
        json.dump({"metrics": m, "gated": [k for k in m if k != "uc_abs_err_p90"]}, open(a.json_out, "w"), indent=1)
    for r in rows:
        print(f"{r['id']} P/R topo {r['P_topo']:.2f}/{r['R_topo']:.2f}  scr {r['P_scr']:.2f}/{r['R_scr']:.2f}  "
              f"uc err {r['uc_med_err']}  band {r['band']:<11} truth {r['truth_band']:<11} {r['label'][:48]}")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    try:
        main()
    except SourceDataMissing as e:   # one line naming the producer to run, not a traceback
        sys.exit(str(e))
