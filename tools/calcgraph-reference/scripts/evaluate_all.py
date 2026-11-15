"""Run every evaluation, print one scorecard, exit non-zero on a regression vs the stored baseline.

  uv run python scripts/evaluate_all.py                    # every stage (from backend/)
  uv run python scripts/evaluate_all.py --synthetic-only   # CI (today the same stages: all are synthetic)
  uv run python scripts/evaluate_all.py --update-baseline  # accept the current numbers as the baseline

Stages (a stage whose inputs are missing is SKIPPED, never failed):
  synthetic_check  python -m synth.generate --check: the synthetic generator is byte-stable (pass/fail)
  synthetic_v1     scripts/evaluate.py on the synthetic package (segmentation, design-mapping P/R, xref,
                   load path, calc edges, revisions), scored on the element graphs the UI's packages build
                   (scripts/build_graph.mjs, rebuilt here from data/synthetic/model_rev{1,2}.ifc; needs Node)
  copyright        scripts/check_no_copyrighted.py --tracked (pass/fail)

Gating: a metric is compared with the baseline when it is listed as gated; a drop larger than
--tolerance (default 0.005 absolute) is a regression; a pass/fail check that passed in the baseline
and fails now is a regression, and any failing check exits 1. Metrics of skipped stages are not
compared. The baseline file (eval/baseline.json) holds numbers only - no drawing text - and is committed.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))  # backend/
PY = sys.executable
BASELINE = os.path.join(ROOT, "eval", "baseline.json")


class Skip(Exception):
    pass


def run(cmd: list[str], timeout: int = 1800) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout)


# ----------------------------------------------------------------------------- stages

def st_synthetic_check(a) -> dict:
    """The generator writes the same bytes twice for one seed (python -m synth.generate --check)."""
    with tempfile.TemporaryDirectory() as tmp:
        p = run([PY, "-m", "synth.generate", "--check", "--out", tmp])
    tail = (p.stdout.strip().splitlines() or [""])[-1]
    return {"checks": {"generator_byte_stable": p.returncode == 0},
            "notes": [f"synth.generate --check: {tail[:120] if p.returncode == 0 else (p.stderr or p.stdout)[-300:]}"]}


def st_synthetic_v1(a) -> dict:
    syn = os.path.join(ROOT, "data", "synthetic")
    if not os.path.exists(os.path.join(syn, "ground_truth.json")):
        g = run([PY, "-m", "synth.generate", "--out", syn])
        if g.returncode:
            raise RuntimeError(f"synth.generate exit {g.returncode}: {g.stderr[-600:]}")
    b = run(["node", "scripts/build_graph.mjs"] + [os.path.join(syn, f"model_rev{n}{ext}") for n in (1, 2)
                                                   for ext in (".ifc", ".graph.json")])
    if b.returncode:
        raise RuntimeError(f"scripts/build_graph.mjs exit {b.returncode}: {b.stderr[-600:]}")
    p = run([PY, "scripts/evaluate.py"])
    if p.returncode:
        raise RuntimeError(f"scripts/evaluate.py exit {p.returncode}: {p.stderr[-600:]}")
    r = json.load(open(os.path.join(ROOT, "data", "eval", "latest.json")))
    d, sg = r["design_mapping"]["overall"], r["segmentation"]
    rv = r["revisions"]
    m = {
        "segmentation_exact": sg["exact"] / sg["truth_calcs"],
        "design_precision": d["precision"], "design_recall": d["recall"], "design_f1": d["f1"],
        "xref_precision": r["xref_tier"]["precision"],
        "load_path_precision": r["load_path_rev1"]["precision"], "load_path_recall": r["load_path_rev1"]["recall"],
        "calc_edges_precision": r["calc_edges"]["precision"], "calc_edges_recall": r["calc_edges"]["recall"],
        "rev2_load_path_recall": rv["load_path_rev2"]["recall"],
        "rev_diff_exact": float(rv["diff_removed"]["exact"] and rv["diff_changed"]["exact"]),
        "decisions_carried": float(rv["decisions_carried_forward"] == {"confirm": "confirmed", "reject": "rejected"}),
    }
    return {"metrics": m, "gated": list(m)}


def _check(cmd: list[str], name: str) -> tuple[bool, str]:
    p = run(cmd)
    tail = (p.stdout.strip().splitlines() or [""])[-1]
    return p.returncode == 0, f"{name}: {tail[:120]}"


def st_copyright(a) -> dict:
    c = _check([PY, "scripts/check_no_copyrighted.py", "--tracked"], "copyright")
    return {"checks": {"no_copyrighted_in_head": c[0]}, "notes": [c[1]]}


STAGES = [("synthetic_check", st_synthetic_check), ("synthetic_v1", st_synthetic_v1), ("copyright", st_copyright)]


# ----------------------------------------------------------------------------- scorecard

def fmt(v) -> str:
    if v is None:
        return "-"
    if isinstance(v, bool):
        return "PASS" if v else "FAIL"
    if isinstance(v, float) and 0 <= v <= 1:
        return f"{100 * v:.1f}%"
    return f"{v:g}" if isinstance(v, float) else str(v)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--synthetic-only", action="store_true",
                    help="skip stages that need local, non-synthetic inputs (none remain; kept for CI)")
    ap.add_argument("--only", default="", help="comma-separated stage names")
    ap.add_argument("--update-baseline", action="store_true")
    ap.add_argument("--tolerance", type=float, default=0.005)
    ap.add_argument("--baseline", default=BASELINE)
    ap.add_argument("--json-out", default=os.path.join(ROOT, "data", "eval", "scorecard.json"))
    a = ap.parse_args()
    only = set(filter(None, a.only.split(",")))
    res: dict[str, dict] = {}
    for name, fn in STAGES:
        if only and name not in only:
            continue
        try:
            res[name] = {"status": "ok", **fn(a)}
        except Skip as s:
            res[name] = {"status": "skipped", "reason": str(s)}
        except Exception as e:  # a crashed stage is a failure, never a pass
            res[name] = {"status": "error", "reason": f"{type(e).__name__}: {e}"}

    base = json.load(open(a.baseline)) if os.path.exists(a.baseline) else {"stages": {}}
    regressions, improvements = [], []
    for name, r in res.items():
        b = base["stages"].get(name, {})
        if r["status"] == "error":
            regressions.append(f"{name}: stage crashed - {r['reason']}")
            continue
        if r["status"] != "ok" or not b:
            continue
        for k in r.get("gated", []):
            v, bv = r["metrics"].get(k), b.get("metrics", {}).get(k)
            if bv is None:
                continue
            if v is None or v < bv - a.tolerance:
                regressions.append(f"{name}.{k}: {fmt(v)} < baseline {fmt(bv)}")
            elif v > bv + a.tolerance:
                improvements.append(f"{name}.{k}: {fmt(v)} > baseline {fmt(bv)}")
        for k, v in r.get("checks", {}).items():
            if b.get("checks", {}).get(k) and not v:
                regressions.append(f"{name}.{k}: FAIL (passed in baseline)")

    now = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M %Z")
    print(f"calc-graph scorecard - {now} (Eastern){'  [synthetic only]' if a.synthetic_only else ''}")
    print(f"baseline: {os.path.relpath(a.baseline, ROOT)} ({base.get('updated', 'none')})\n")
    for name, r in res.items():
        dep = ""
        if r["status"] != "ok":
            print(f"{name:<16} {r['status'].upper()}: {r['reason']}{dep}")
            continue
        b = base["stages"].get(name, {})
        print(f"{name}{dep}")
        for k, v in r.get("checks", {}).items():
            print(f"  {k:<36} {fmt(v)}")
        for k, v in r.get("metrics", {}).items():
            bv = b.get("metrics", {}).get(k)
            mark = "" if k in r.get("gated", []) else "   (info)"
            print(f"  {k:<36} {fmt(v):>8}   baseline {fmt(bv):>8}{mark}")
        for n in r.get("notes", []):
            print(f"  - {n}")
    print()
    failing_checks = [f"{n}.{k}" for n, r in res.items() for k, v in r.get("checks", {}).items() if not v]
    if failing_checks:
        print("FAILING CHECKS: " + ", ".join(failing_checks))
    for x in improvements:
        print(f"improved   {x}")
    for x in regressions:
        print(f"REGRESSION {x}")

    os.makedirs(os.path.dirname(a.json_out), exist_ok=True)
    json.dump({"run_at": now, "synthetic_only": a.synthetic_only, "stages": res, "regressions": regressions},
              open(a.json_out, "w"), indent=1, default=str)

    if a.update_baseline:
        nb = {"about": "calc-graph evaluation baseline - numbers only, no drawing text. Written by "
                       "scripts/evaluate_all.py --update-baseline.", "updated": now, "stages": dict(base["stages"])}
        for name, r in res.items():
            if r["status"] == "ok":
                nb["stages"][name] = {k: r[k] for k in ("metrics", "checks") if k in r}
        os.makedirs(os.path.dirname(os.path.abspath(a.baseline)), exist_ok=True)
        json.dump(nb, open(a.baseline, "w"), indent=1, sort_keys=True)
        print(f"baseline updated: {os.path.relpath(a.baseline, ROOT)}")
        return
    sys.exit(1 if regressions or failing_checks else 0)


if __name__ == "__main__":
    main()
