"""The evaluation gate (scripts/evaluate_all.py compare()): skips are explicit, keys are compared
over the union of baseline and run, and lower-is-better metrics are gated in that direction.
Pure-function tests on hand-built results; no stage is run."""
import importlib.util
import json
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_spec = importlib.util.spec_from_file_location("evaluate_all", os.path.join(ROOT, "scripts", "evaluate_all.py"))
ev = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ev)

KNOWN = {"a", "move", "chk"}


def ok(metrics=None, gated=(), lower=(), exact=(), checks=None):
    r = {"status": "ok", "metrics": metrics or {}, "gated": list(gated), "gated_lower": list(lower), "exact": list(exact)}
    if checks is not None:
        r["checks"] = checks
    return r


def gate(res, base, synthetic_only=True, selected=None, local_only=None):
    saved = dict(ev.LOCAL_ONLY)
    ev.LOCAL_ONLY.clear()
    ev.LOCAL_ONLY.update(local_only if local_only is not None else {"move": "needs local data"})
    try:
        return ev.compare(res, base, 0.005, synthetic_only, selected, KNOWN)
    finally:
        ev.LOCAL_ONLY.clear()
        ev.LOCAL_ONLY.update(saved)


def test_skipped_stage_with_baseline_is_a_regression():
    reg, _, lo = gate({"a": {"status": "skipped", "reason": "no data"}}, {"a": {"metrics": {"m": 1.0}}})
    assert reg and "SKIPPED but has a baseline" in reg[0] and not lo


def test_local_only_skip_is_loud_in_ci_and_fails_locally():
    res, base = {"move": {"status": "skipped", "reason": "no v2"}}, {"move": {"metrics": {"m": 1.0}}}
    reg, _, lo = gate(res, base, synthetic_only=True)
    assert not reg and lo and "NOT compared" in lo[0] and "needs local data" in lo[0]
    reg, _, lo = gate(res, base, synthetic_only=False)
    assert reg and not lo


def test_stage_that_did_not_run_at_all_is_a_regression_unless_deselected():
    base = {"a": {"metrics": {"m": 1.0}}}
    assert gate({}, base)[0]
    assert not gate({}, base, selected={"chk"})[0]


def test_stage_removed_from_the_code_is_a_regression():
    assert any("no longer exists" in r for r in gate({}, {"gone": {"metrics": {"m": 1}}})[0])


def test_lower_is_better_metric_is_gated():
    base = {"move": {"metrics": {"err": 0.01}}}
    reg, imp, _ = gate({"move": ok({"err": 0.05}, lower=["err"])}, base)
    assert reg and "lower is better" in reg[0]
    reg, imp, _ = gate({"move": ok({"err": 0.001}, lower=["err"])}, base)
    assert not reg and imp


def test_evaluate_move_declares_uc_p90_lower_is_better():
    src = open(os.path.join(ROOT, "scripts", "evaluate_move.py")).read()
    assert '"gated_lower": ["uc_abs_err_p90"]' in src


def test_metric_missing_from_the_run_is_a_regression():
    base = {"a": {"metrics": {"tier_x_links": 5, "p": 0.9}}}
    reg, _, _ = gate({"a": ok({"p": 0.9}, gated=["p"])}, base)
    assert reg == ["a.tier_x_links: missing from this run (baseline 5)"]


def test_new_exact_key_without_baseline_fails_with_instructions():
    base = {"a": {"metrics": {"p": 0.9}}}
    reg, _, _ = gate({"a": ok({"p": 0.9, "tier_new_links": 3}, gated=["p"], exact=["tier_new_links"])}, base)
    assert len(reg) == 1 and "tier_new_links" in reg[0] and "--update-baseline" in reg[0]


def test_info_metric_without_baseline_is_not_gated():
    assert not gate({"a": ok({"p": 0.9, "note": 7}, gated=["p"])}, {"a": {"metrics": {"p": 0.9}}})[0]


def test_baseline_check_missing_or_failing_is_a_regression():
    base = {"chk": {"checks": {"x": True, "y": True}}}
    reg, _, _ = gate({"chk": {"status": "ok", "checks": {"x": False}}}, base)
    assert any("chk.x: FAIL" in r for r in reg) and any("chk.y: missing" in r for r in reg)


def test_stage_without_baseline_fails():
    reg, _, _ = gate({"a": ok({"p": 1.0}, gated=["p"])}, {})
    assert reg and "no baseline for this stage" in reg[0]


def test_drop_and_exact_mismatch_still_regress():
    base = {"a": {"metrics": {"p": 0.9, "n": 4}}}
    reg, _, _ = gate({"a": ok({"p": 0.8, "n": 5}, gated=["p"], exact=["n"])}, base)
    assert len(reg) == 2


def test_real_baseline_and_declarations_agree():
    """Every baseline stage exists in the code, every LOCAL_ONLY stage is a real stage."""
    names = {n for n, _ in ev.STAGES}
    base = json.load(open(ev.BASELINE))["stages"]
    assert set(base) <= names
    assert set(ev.LOCAL_ONLY) <= names


def test_small_error_metric_uses_a_relative_band():
    """uc_abs_err_p90's baseline is ~0.0008: the 0.005 absolute band would allow a ~7x rise."""
    base = {"move": {"metrics": {"err": 0.0008}}}
    assert gate({"move": ok({"err": 0.0058}, lower=["err"])}, base)[0]          # 7x: a regression now
    assert gate({"move": ok({"err": 0.0019}, lower=["err"])}, base)[0]          # past the 0.001 floor
    assert not gate({"move": ok({"err": 0.0017}, lower=["err"])}, base)[0]      # one rounding step: noise
    assert ev.lower_tolerance(0.2) == 0.05 and ev.lower_tolerance(0.0) == ev.LOWER_ABS_FLOOR


def test_local_only_skip_is_a_github_warning_annotation_in_ci():
    notices = ["move: SKIPPED, 9 baseline metric(s)/check(s) NOT compared in this run"]
    lines = ev.annotate(notices, {"GITHUB_ACTIONS": "true"})
    assert len(lines) == 1 and lines[0].startswith("::warning ") and "NOT compared" in lines[0]
    assert ev.annotate(notices, {}) == []                     # a local run prints the banner only
    src = open(os.path.join(ROOT, "scripts", "evaluate_all.py")).read()
    assert "for line in annotate(local_only):" in src


def test_copyright_guard_is_not_rerun_by_evaluate_all():
    """The CI copyright job runs the guard (pinned in test_copyright_guard); evaluate_all must not repeat
    the ~30 s --tracked scan, and the baseline must not expect a copyright stage."""
    assert "copyright" not in {n for n, _ in ev.STAGES}
    assert "copyright" not in json.load(open(ev.BASELINE))["stages"]
