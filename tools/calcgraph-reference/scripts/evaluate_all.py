"""Run every evaluation, print one scorecard, exit non-zero on a regression vs the stored baseline.

  uv run python scripts/evaluate_all.py                    # every stage (from tools/calcgraph-reference/)
  uv run python scripts/evaluate_all.py --synthetic-only   # CI: a LOCAL_ONLY stage may skip (loudly)
  uv run python scripts/evaluate_all.py --update-baseline  # accept the current numbers as the baseline

Stages (a stage whose inputs are missing reports SKIPPED; see Gating for what a skip means):
  synthetic_check  python -m synth.generate --check: the synthetic generator is byte-stable (pass/fail)
  synthetic_v1     scripts/evaluate.py: the TypeScript calc engine (packages/calc-mapper, run through its
                   Node CLI on the element graphs scripts/build_graph.mjs builds) scored on the synthetic
                   package - segmentation, design-mapping P/R per tier, xref, load path, calc edges,
                   rev1 -> rev2 diff, decisions carried forward, C8 impact; link roles, typical-group
                   links and findings; and on the supplement package - span boundaries, roles, group
                   links, size-mismatch findings. Needs Node + `npm ci`.
  move_answer_key  scripts/evaluate_move.py: the TypeScript move-a-column screen (packages/move-impact, run
                   through its Node CLI on the v2 model's element graph + calc facts from
                   scripts/move_fixture.py) scored on the v2 answer key - stale P/R (topological, screened),
                   UC error, health band. Skipped unless data/synthetic_v2/ holds design.json,
                   answer_key.json and model.graph.json (synth.v2.generate, synth.v2.scenarios,
                   scripts/build_graph.mjs). Needs Node.
  (The copyright guard is not a stage: the CI `copyright` job runs its --self-test, --tracked and the
  PR / push range, and the pre-commit hook runs --staged. Re-running --tracked here cost ~30 s per run.)

Gating (compare(), over the UNION of the baseline's and the run's keys):
  - gated metric (higher is better): a drop larger than --tolerance (default 0.005 absolute) is a
    regression. These are ratios in 0..1, where 0.005 is half a point.
  - gated_lower metric (an error, e.g. uc_abs_err_p90): a RISE larger than lower_tolerance(baseline)
    = max(LOWER_REL_TOL x baseline, LOWER_ABS_FLOOR) is. An error metric sits near zero (the p90 UC
    error baseline is 0.0008), where a 0.005 absolute band would allow a ~7x rise; 25% relative keeps
    the band proportional, and the 0.001 floor is one step of the 3-decimal rounding the printed calc
    values (the truth the error is measured against) carry, so a one-step rounding change is not noise
  - exact metric (link counts per tier, xref, calc-edge tp/fp/fn, diff and impact counts): must
    equal the baseline
  - a baseline metric or check the run no longer emits (a tier or metric that disappeared) is a
    regression; a gated / exact metric the run emits with no baseline value (a new tier) fails
    too, telling you to add it with --update-baseline
  - a pass/fail check that passed in the baseline and fails now is a regression, and any failing
    check exits 1; a crashed stage is a regression
  - a stage with a baseline that did not run is a regression, except a stage in LOCAL_ONLY under
    --synthetic-only (CI): that is printed as a LOCAL-ONLY banner at the top and bottom of the
    scorecard, naming the metrics left unchecked. Without --synthetic-only (the full local run)
    a skipped LOCAL_ONLY stage is a regression too. Under GitHub Actions each such skip is also
    emitted as a `::warning::` annotation, so it shows on the PR instead of reading as green. A stage left out with --only is reported as
    not selected. A stage in the baseline that no longer exists is a regression.
The baseline file (eval/baseline.json) holds numbers only - no drawing text - and is committed.
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

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))  # tools/calcgraph-reference/
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
    # counts that must equal the baseline exactly (a drop OR a rise is a behaviour change to look at)
    x, im = r["xref_tier"], r["impact_remove_C8"]
    exact = {
        "segmentation_exact_count": sg["exact"], "segmentation_truth_calcs": sg["truth_calcs"],
        **{f"tier_{t}_links": v["links"] for t, v in d_tiers(r).items()},
        **{f"tier_{t}_correct": v["correct"] for t, v in d_tiers(r).items()},
        "xref_links": x["links"], "xref_real_mentions": x["real_mentions"],
        "calc_edges_tp": r["calc_edges"]["tp"], "calc_edges_fp": r["calc_edges"]["fp"], "calc_edges_fn": r["calc_edges"]["fn"],
        "diff_removed": rv["diff_removed"]["pred"], "diff_changed": rv["diff_changed"]["pred"], "diff_added": rv["diff_added"]["pred"],
        "impact_c8_removed": im["removed"], "impact_c8_hit": im["hit"], "impact_c8_stale_calcs": len(im["stale_calcs"]),
    }
    # roles / typical groups / findings / spans (main package + supplement)
    fm, sp = r["features_main"], r.get("supplement") or {}
    feat = {"role_accuracy_main": fm["role_accuracy"], "group_link_precision_main": fm["group_link_precision"],
            "role_accuracy_supplement": sp.get("role_accuracy"), "span_boundary_accuracy_supplement": sp.get("span_boundary_accuracy"),
            "group_link_precision_supplement": sp.get("group_link_precision"),
            "group_link_recall_supplement": sp.get("group_link_recall"),
            "mismatch_precision_supplement": sp.get("mismatch_precision"),
            "mismatch_recall_supplement": sp.get("mismatch_recall")}
    exact |= {"roles_checked_main": fm["roles_checked"], "group_links_main": fm["group_links"], "findings_main": fm["findings"],
              "calcs_supplement": sp.get("calcs"), "calcs_with_exact_spans_supplement": sp.get("calcs_with_exact_spans"),
              "group_links_supplement": sp.get("group_links"), "findings_supplement": sp.get("findings")}
    return {"metrics": m | feat | exact, "gated": list(m) + list(feat), "exact": list(exact)}


def d_tiers(r: dict) -> dict:
    return r["design_mapping"]["per_tier"]


def st_move_answer_key(a) -> dict:
    v2 = os.path.join(ROOT, "data", "synthetic_v2")
    need = ("design.json", "answer_key.json", "model.graph.json")
    missing = [n for n in need if not os.path.exists(os.path.join(v2, n))]
    if missing:
        raise Skip(f"data/synthetic_v2 lacks {', '.join(missing)} (run synth.v2.generate, synth.v2.scenarios, build_graph.mjs)")
    p = run([PY, "scripts/move_fixture.py"])
    if p.returncode:
        raise RuntimeError(f"scripts/move_fixture.py exit {p.returncode}: {p.stderr[-600:]}")
    d = "data/synthetic_v2"
    p = run(["node", "../../packages/move-impact/scripts/run-scenarios.ts", "--graph", f"{d}/model.graph.json",
             "--scenarios", f"{d}/move_scenarios.json", "--facts", f"{d}/move_facts.json",
             "--sections", f"{d}/move_sections.json", "--out", f"{d}/move_results.json"])
    if p.returncode:
        raise RuntimeError(f"run-scenarios.ts exit {p.returncode}: {p.stderr[-600:]}")
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "move.json")
        p = run([PY, "scripts/evaluate_move.py", "--json-out", out])
        if p.returncode:
            raise RuntimeError(f"scripts/evaluate_move.py exit {p.returncode}: {p.stderr[-600:]}")
        r = json.load(open(out))
    return {"metrics": r["metrics"], "gated": r["gated"], "gated_lower": r.get("gated_lower", []),
            "notes": ["calc facts are printed calc-row values from the generator's calc-sheet data (stand-in for matcher output)"]}


STAGES = [("synthetic_check", st_synthetic_check), ("synthetic_v1", st_synthetic_v1), ("move_answer_key", st_move_answer_key)]

LOWER_REL_TOL = 0.25     # gated_lower: relative band (see Gating)
LOWER_ABS_FLOOR = 0.001  # gated_lower: one step of 3-decimal rounding


def lower_tolerance(baseline: float) -> float:
    return max(LOWER_REL_TOL * abs(baseline), LOWER_ABS_FLOOR)

# Stages CI cannot run, with why. Only these may skip under --synthetic-only, and never silently.
LOCAL_ONLY = {
    "move_answer_key": "needs data/synthetic_v2, whose generator designs with the AISC shapes table - gitignored, "
                       "not committed while its licence is undecided (decision D22). Run it locally before merging "
                       "a change to packages/move-impact.",
}


# ----------------------------------------------------------------------------- gate

def compare(res: dict, base_stages: dict, tolerance: float, synthetic_only: bool,
            selected: set[str] | None = None, known: set[str] | None = None) -> tuple[list[str], list[str], list[str]]:
    """(regressions, improvements, local_only notices) of a run against the baseline's stages."""
    known = known if known is not None else {n for n, _ in STAGES}
    regressions, improvements, local_only = [], [], []
    for name in sorted(base_stages):
        if name not in known:
            regressions.append(f"{name}: stage is in the baseline but no longer exists (remove it with --update-baseline "
                               f"only if that is intended)")
        elif name not in res and not (selected and name not in selected):
            regressions.append(f"{name}: has a baseline but did not run")
    for name, r in res.items():
        b = base_stages.get(name)
        if r["status"] == "error":
            regressions.append(f"{name}: stage crashed - {r['reason']}")
            continue
        if r["status"] != "ok":
            if b:
                unchecked = len(b.get("metrics", {})) + len(b.get("checks", {}))
                if synthetic_only and name in LOCAL_ONLY:
                    local_only.append(f"{name}: SKIPPED, {unchecked} baseline metric(s)/check(s) NOT compared in this "
                                      f"run - {LOCAL_ONLY[name]} (skip reason: {r.get('reason', '')})")
                else:
                    why = "run it" if name in LOCAL_ONLY else "a stage with a baseline may not skip"
                    regressions.append(f"{name}: SKIPPED but has a baseline ({unchecked} metric(s)/check(s) unchecked; "
                                       f"{why}) - {r.get('reason', '')}")
            continue
        if b is None:
            if r.get("metrics") or r.get("checks"):
                regressions.append(f"{name}: no baseline for this stage - add it with --update-baseline")
            continue
        bm, cm = b.get("metrics", {}), r.get("metrics", {})
        gated, lower, exact = set(r.get("gated", [])), set(r.get("gated_lower", [])), set(r.get("exact", []))
        for k in sorted(set(bm) | set(cm)):
            v, bv = cm.get(k), bm.get(k)
            if bv is None and v is None:
                continue
            if v is None:
                regressions.append(f"{name}.{k}: missing from this run (baseline {fmt(bv)})")
            elif bv is None:
                if k in gated | lower | exact:
                    regressions.append(f"{name}.{k}: {fmt(v)} has no baseline value - add it with --update-baseline")
            elif k in exact:
                if v != bv:
                    regressions.append(f"{name}.{k}: {fmt(v)} != baseline {fmt(bv)} (must match exactly)")
            elif k in lower:
                tol = lower_tolerance(bv)
                if v > bv + tol:
                    regressions.append(f"{name}.{k}: {fmt(v)} > baseline {fmt(bv)} + {tol:g} (lower is better)")
                elif v < bv - tol:
                    improvements.append(f"{name}.{k}: {fmt(v)} < baseline {fmt(bv)} (lower is better)")
            elif k in gated:
                if v < bv - tolerance:
                    regressions.append(f"{name}.{k}: {fmt(v)} < baseline {fmt(bv)}")
                elif v > bv + tolerance:
                    improvements.append(f"{name}.{k}: {fmt(v)} > baseline {fmt(bv)}")
        bc, cc = b.get("checks", {}), r.get("checks", {})
        for k in sorted(set(bc) | set(cc)):
            if bc.get(k) and k not in cc:
                regressions.append(f"{name}.{k}: missing from this run (passed in baseline)")
            elif bc.get(k) and not cc[k]:
                regressions.append(f"{name}.{k}: FAIL (passed in baseline)")
    return regressions, improvements, local_only


def annotate(local_only: list[str], env=os.environ) -> list[str]:
    """GitHub Actions `::warning::` lines for each LOCAL-ONLY skip (printed only under GITHUB_ACTIONS),
    so a stage CI did not gate shows on the PR's checks instead of reading as green."""
    if env.get("GITHUB_ACTIONS") != "true":
        return []
    return [f"::warning title=evaluate_all: stage NOT gated in CI::{x.replace(chr(10), ' ')}" for x in local_only]


def banner(local_only: list[str]) -> None:
    if not local_only:
        return
    print("!" * 100)
    for x in local_only:
        print(f"LOCAL-ONLY, NOT GATED HERE: {x}")
    print("!" * 100)


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
                    help="CI mode: a LOCAL_ONLY stage whose inputs are missing is reported loudly instead of failing")
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
    regressions, improvements, local_only = compare(res, base["stages"], a.tolerance, a.synthetic_only, only or None)

    now = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M %Z")
    print(f"calc-graph scorecard - {now} (Eastern){'  [synthetic only]' if a.synthetic_only else ''}")
    print(f"baseline: {os.path.relpath(a.baseline, ROOT)} ({base.get('updated', 'none')})\n")
    banner(local_only)
    for name in sorted(set(base["stages"]) - set(res)):
        if only and name not in only:
            print(f"{name:<16} NOT SELECTED (--only): its baseline was not compared")
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
            mark = "" if k in r.get("gated", []) else "   (lower is better)" if k in r.get("gated_lower", []) \
                else "   (exact)" if k in r.get("exact", []) else "   (info)"
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
    banner(local_only)
    for line in annotate(local_only):
        print(line)

    os.makedirs(os.path.dirname(a.json_out), exist_ok=True)
    json.dump({"run_at": now, "synthetic_only": a.synthetic_only, "stages": res, "regressions": regressions,
               "local_only_not_gated": local_only},
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
