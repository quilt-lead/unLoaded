"""Pyright ratchet for calc-graph: a NEW type error fails; errors that already exist are the baseline.

    uv run python scripts/check_types.py --base origin/main     # baseline = pyright on the merge-base
    uv run python scripts/check_types.py                        # baseline = eval/pyright_baseline.json
    uv run python scripts/check_types.py --write-baseline       # record HEAD's errors as that file

CI only (type checkers are blocked on the dev Mac). Config: pyrightconfig.json (standard mode over
backend/calcgraph, backend/tests, scripts, synth; generated clients excluded). Pyright runs through uvx at
the version pinned below, against this project's venv (`--pythonpath sys.executable`).

Baseline: with --base REF the merge-base of REF and HEAD is checked out in a temporary git worktree and
pyright runs there with HEAD's pyrightconfig.json, so both sides use the same rules. An error is identified
by (file, rule, message) - not its line, so moving code does not make old errors look new; a key whose
count grows is new. Without a usable --base the committed eval/pyright_baseline.json is the baseline;
with neither, the ratchet reports only (the canary still gates). Every run writes HEAD's errors to
<derived>/pyright_current.json (data/eval/, store_root.derived_path) - CI uploads it, and committing it as
eval/pyright_baseline.json gates runs that have no base.

Canary: scripts/typecheck_canary.py lines marked `# CANARY` must get a reportArgumentType error and lines
marked `# CLEAN` none, or this fails - proof on every run that the configured checker (venv resolution,
FastAPI's decorator typing, pydantic models) still reports a dict passed where a model is required, the
a410607 inbox -> impact_timeline bug.

Exit 0 = no new errors and the canary holds; 1 = new errors or the canary failed; 2 = pyright did not run.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections import Counter

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from calcgraph.store_root import derived_path  # noqa: E402

PYRIGHT = "pyright==1.1.400"
CANARY = "scripts/typecheck_canary.py"
BASELINE = os.path.join(ROOT, "eval", "pyright_baseline.json")


def git(*args: str, cwd: str = ROOT, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=check)


def pyright(project: str) -> list[dict]:
    """Every diagnostic pyright reports for the project at `project` (paths relative to it)."""
    cmd = ["uvx", "--from", PYRIGHT, "pyright", "--outputjson", "--pythonpath", sys.executable,
           "--project", os.path.join(project, "pyrightconfig.json")]
    env = {**os.environ, "PYRIGHT_PYTHON_IGNORE_WARNINGS": "1"}   # no "new version" notice in the JSON
    p = subprocess.run(cmd, cwd=project, capture_output=True, text=True, env=env)
    start = p.stdout.find("{")
    if p.returncode not in (0, 1) or start < 0:   # 0 clean, 1 errors reported; else pyright itself failed
        print(f"pyright did not run (exit {p.returncode}) in {project}:\n{p.stderr[-2000:]}\n{p.stdout[-2000:]}")
        sys.exit(2)
    real = os.path.realpath(project)
    out = []
    for d in json.loads(p.stdout[start:])["generalDiagnostics"]:
        msg = d["message"].replace(real + os.sep, "").replace(project + os.sep, "")
        out.append({"file": os.path.relpath(os.path.realpath(d["file"]), real), "line": d["range"]["start"]["line"] + 1,
                    "severity": d["severity"], "rule": d.get("rule", ""), "message": msg})
    return out


def errors(diags: list[dict]) -> list[dict]:
    return [d for d in diags if d["severity"] == "error" and d["file"] != CANARY]


def key(d: dict) -> tuple[str, str, str]:
    return (d["file"], d["rule"], d["message"])


def base_errors(ref: str) -> list[dict] | None:
    """Pyright errors on merge-base(ref, HEAD), or None when that commit cannot be resolved."""
    mb = git("merge-base", ref, "HEAD", check=False)
    if mb.returncode:
        print(f"--base {ref}: no merge-base with HEAD ({mb.stderr.strip()[:200]})")
        return None
    sha = mb.stdout.strip()
    top = git("rev-parse", "--show-toplevel").stdout.strip()
    rel = os.path.relpath(ROOT, top)
    tmp = tempfile.mkdtemp(prefix="cg-pyright-base-")
    wt = os.path.join(tmp, "base")
    git("worktree", "add", "--detach", wt, sha, cwd=top)
    try:
        proj = os.path.join(wt, rel)
        if not os.path.isdir(proj):
            print(f"base {sha[:10]}: no {rel} - every error is new")
            return []
        shutil.copy(os.path.join(ROOT, "pyrightconfig.json"), proj)   # the same rules on both sides
        errs = errors(pyright(proj))
        print(f"baseline: merge-base {sha[:10]} of {ref} and HEAD, {len(errs)} errors")
        return errs
    finally:
        git("worktree", "remove", "--force", wt, cwd=top, check=False)
        shutil.rmtree(tmp, ignore_errors=True)


def canary_failures(diags: list[dict]) -> list[str]:
    lines = open(os.path.join(ROOT, CANARY)).read().splitlines()
    got = [d for d in diags if d["file"] == CANARY]
    bad = []
    for n, text in enumerate(lines, 1):
        here = [d for d in got if d["line"] == n]
        if text.rstrip().endswith("# CANARY") and not any(d["severity"] == "error" and d["rule"] == "reportArgumentType"
                                                           for d in here):
            bad.append(f"{CANARY}:{n} expected a reportArgumentType error, got {[(d['rule'], d['message'][:80]) for d in here]}")
        if text.rstrip().endswith("# CLEAN") and here:
            bad.append(f"{CANARY}:{n} expected no diagnostic, got {[(d['rule'], d['message'][:80]) for d in here]}")
    if not any(t.rstrip().endswith("# CANARY") for t in lines):
        bad.append(f"{CANARY} has no # CANARY line")
    return bad


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="", help="git ref whose merge-base with HEAD is the baseline (PR base, push before)")
    ap.add_argument("--write-baseline", action="store_true", help=f"write HEAD's errors to {os.path.relpath(BASELINE, ROOT)}")
    a = ap.parse_args()

    head = pyright(ROOT)
    cur = errors(head)
    counts = Counter(map(key, cur))
    snapshot = [{"file": f, "rule": r, "message": m, "count": c} for (f, r, m), c in sorted(counts.items())]
    out = derived_path("pyright_current.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as fh:
        json.dump({"pyright": PYRIGHT, "errors": snapshot}, fh, indent=1)
    if a.write_baseline:
        with open(BASELINE, "w") as fh:
            json.dump({"about": "pyright errors accepted as the baseline (scripts/check_types.py --write-baseline); "
                                "a NEW (file, rule, message) or a higher count fails CI", "pyright": PYRIGHT,
                       "errors": snapshot}, fh, indent=1)
        print(f"wrote {os.path.relpath(BASELINE, ROOT)}: {len(cur)} errors")

    base = base_errors(a.base) if a.base else None
    if base is not None:
        base_counts = Counter(map(key, base))
    elif os.path.exists(BASELINE) and not a.write_baseline:
        base_counts = Counter({(e["file"], e["rule"], e["message"]): e["count"] for e in json.load(open(BASELINE))["errors"]})
        print(f"baseline: {os.path.relpath(BASELINE, ROOT)}, {sum(base_counts.values())} errors")
    else:
        base_counts = None

    print(f"HEAD: {len(cur)} errors ({PYRIGHT}); written to {os.path.relpath(out, ROOT)}")
    failed = False
    bad = canary_failures(head)
    if bad:
        failed = True
        print("CANARY FAILED - the checker no longer reports a dict passed where a model is required:")
        for b in bad:
            print("  " + b)
    else:
        print(f"canary: {CANARY} reported as expected (dict for Move is an error, typed Move is clean)")

    if base_counts is None:
        print("NO BASELINE (no usable --base, no eval/pyright_baseline.json): ratchet is report-only this run")
    else:
        new = counts - base_counts
        fixed = base_counts - counts
        if fixed:
            print(f"fixed since the baseline: {sum(fixed.values())}")
        if new:
            failed = True
            print(f"NEW TYPE ERRORS: {sum(new.values())}")
            for (f, r, m), c in sorted(new.items()):
                where = ", ".join(str(d["line"]) for d in cur if key(d) == (f, r, m))
                print(f"  {f}:{where}  [{r}] {m}" + (f"  ({c} new of {counts[(f, r, m)]})" if counts[(f, r, m)] > c else ""))
        else:
            print("no new type errors")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
