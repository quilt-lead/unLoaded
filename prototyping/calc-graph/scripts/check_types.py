"""Pyright ratchet for calc-graph: the committed eval/pyright_baseline.json is the ONE baseline, and it only
ever shrinks.

    uv run python scripts/check_types.py                         # CI: gate HEAD against the committed baseline
    uv run python scripts/check_types.py --tighten-from FILE     # shrink the baseline to a CI pyright_current.json

Pyright runs in CI only (type checkers are blocked on the dev Mac); --tighten-from runs no checker, so it works
anywhere. Config: pyrightconfig.json (standard mode over backend/calcgraph, backend/tests, scripts, synth;
generated clients excluded). Pyright runs through uvx at the version pinned below, against this project's venv
(`--pythonpath sys.executable`). An error is identified by (file, rule, message) - not its line, so moving code
does not make old errors look new; a key whose count grows is new.

Why a committed baseline: the ratchet used to take pyright on the previous pushed tip (github.event.before) as
the baseline, so errors that went out in a red push became the next push's baseline and were never blamed again
(1c4c055 pushed 14 new errors red; had they not been fixed, 2ef4e4e would have passed). A committed file does
not move when a push is red. The run fails (exit 1) when:
- NEW: an error occurs more often than the baseline allows;
- STALE: the baseline allows an error that no longer occurs (or more of it than occur) - it is kept tight, so a
  fixed error cannot come back unnoticed. The run prints the entries to drop and writes the shrunk baseline to
  <derived>/pyright_baseline_tightened.json (CI uploads it): commit it as eval/pyright_baseline.json, or run
  --tighten-from on the downloaded pyright_current.json;
- GREW: the committed baseline allows more of some error than ANY earlier committed version of it with the same
  pyright pin (git log of the file, CI checks out full history) - so the file can only shrink, whatever a red
  push did. A pyright upgrade starts a new history: a baseline with a different "pyright" pin is not compared;
- the canary fails.
Every run writes HEAD's errors to <derived>/pyright_current.json (data/eval/, store_root.derived_path).

Canary: scripts/typecheck_canary.py lines marked `# CANARY` must get a reportArgumentType error and lines
marked `# CLEAN` none, or this fails - proof on every run that the configured checker (venv resolution,
FastAPI's decorator typing, pydantic models) still reports a dict passed where a model is required, the
a410607 inbox -> impact_timeline bug.

Exit 0 = no new errors, the baseline is tight and never grew, the canary holds; 1 = any of those failed;
2 = pyright did not run.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
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


def load_counts(path_or_obj) -> tuple[str, Counter]:
    """(pyright pin, Counter of (file, rule, message) -> count) from a baseline / pyright_current.json."""
    d = json.load(open(path_or_obj)) if isinstance(path_or_obj, str) else path_or_obj
    return d.get("pyright", ""), Counter({(e["file"], e["rule"], e["message"]): e["count"] for e in d["errors"]})


def snapshot(counts: Counter) -> list[dict]:
    return [{"file": f, "rule": r, "message": m, "count": c} for (f, r, m), c in sorted(counts.items()) if c > 0]


def write_baseline(path: str, counts: Counter) -> None:
    with open(path, "w") as fh:
        json.dump({"about": "pyright errors still allowed (scripts/check_types.py). It only ever shrinks: CI fails on "
                            "an error not in it, on an entry that no longer occurs, and on any count above an earlier "
                            "committed version.", "pyright": PYRIGHT, "errors": snapshot(counts)}, fh, indent=1)
        fh.write("\n")


def history_floor() -> tuple[Counter | None, int]:
    """Pointwise minimum over every committed version of the baseline with this pyright pin (a key absent from
    a version counts 0), and how many versions were read. None when the file has no committed history."""
    rel = os.path.relpath(BASELINE, ROOT)
    log = git("log", "--format=%H", "--", rel, check=False)
    floor: Counter | None = None
    n = 0
    for sha in log.stdout.split():
        show = git("show", f"{sha}:./{rel}", check=False)
        if show.returncode:
            continue   # the commit deleted the file
        pin, counts = load_counts(json.loads(show.stdout))
        if pin != PYRIGHT:
            continue
        n += 1
        floor = counts if floor is None else Counter({k: min(c, counts.get(k, 0)) for k, c in floor.items()})
    return floor, n


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


def tighten_from(current_path: str) -> None:
    """Shrink the committed baseline to a pyright_current.json (CI artifact): drop what no longer occurs, lower
    counts that fell. Never adds an entry or raises a count."""
    if not os.path.exists(BASELINE):
        sys.exit(f"no {os.path.relpath(BASELINE, ROOT)} to tighten")
    bpin, base = load_counts(BASELINE)
    cpin, cur = load_counts(current_path)
    if not cpin == bpin == PYRIGHT:
        sys.exit(f"{current_path} is from {cpin or 'an unknown pyright'}, the baseline from {bpin or 'an unknown pyright'}, "
                 f"this script pins {PYRIGHT}: not comparable")
    tight = base & cur   # pointwise min
    write_baseline(BASELINE, tight)
    print(f"{os.path.relpath(BASELINE, ROOT)}: {sum(base.values())} -> {sum(tight.values())} errors "
          f"({sum((base - tight).values())} dropped; {sum((cur - base).values())} NEW errors in {current_path} not admitted)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tighten-from", default="", metavar="PYRIGHT_CURRENT_JSON",
                    help=f"shrink {os.path.relpath(BASELINE, ROOT)} to a CI pyright_current.json (runs no checker)")
    a = ap.parse_args()
    if a.tighten_from:
        tighten_from(a.tighten_from)
        return

    head = pyright(ROOT)
    cur = errors(head)
    counts = Counter(map(key, cur))
    out = derived_path("pyright_current.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as fh:
        json.dump({"pyright": PYRIGHT, "errors": snapshot(counts)}, fh, indent=1)
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

    rel = os.path.relpath(BASELINE, ROOT)
    if not os.path.exists(BASELINE):
        print(f"NO BASELINE: {rel} is missing - it is committed and only ever shrinks; restore it from git")
        sys.exit(1)
    pin, base = load_counts(BASELINE)
    if pin != PYRIGHT:
        print(f"BASELINE PIN MISMATCH: {rel} was recorded with {pin}, this run uses {PYRIGHT} - a pyright upgrade "
              f"needs a new baseline from this run's pyright_current.json, committed with the pin change")
        sys.exit(1)
    print(f"baseline: {rel}, {sum(base.values())} errors")

    new = counts - base
    if new:
        failed = True
        print(f"NEW TYPE ERRORS: {sum(new.values())} (not in {rel})")
        for (f, r, m), c in sorted(new.items()):
            where = ", ".join(str(d["line"]) for d in cur if key(d) == (f, r, m))
            print(f"  {f}:{where}  [{r}] {m}" + (f"  ({c} new of {counts[(f, r, m)]})" if counts[(f, r, m)] > c else ""))
    else:
        print("no new type errors")

    stale = base - counts
    if stale:
        failed = True
        tight_path = derived_path("pyright_baseline_tightened.json")
        write_baseline(tight_path, base & counts)
        print(f"BASELINE NOT TIGHT: {sum(stale.values())} allowed errors no longer occur - drop them from {rel} "
              f"(the shrunk baseline is {os.path.relpath(tight_path, ROOT)}, uploaded with the scorecard artifact; "
              f"or: uv run python scripts/check_types.py --tighten-from <downloaded pyright_current.json>):")
        for (f, r, m), c in sorted(stale.items()):
            print(f"  - {f}  [{r}] {(m.splitlines() or [''])[0][:160]}" + (f"  (x{c})" if c > 1 else ""))
    else:
        print("baseline is tight (every allowed error still occurs)")

    floor, versions = history_floor()
    grew = (base - floor) if floor is not None else Counter()
    if grew:
        failed = True
        print(f"BASELINE GREW: {rel} allows {sum(grew.values())} errors that an earlier committed version (of "
              f"{versions} with {PYRIGHT}) did not - the baseline only shrinks; fix the errors instead:")
        for (f, r, m), c in sorted(grew.items()):
            print(f"  + {f}  [{r}] {(m.splitlines() or [''])[0][:160]}" + (f"  (x{c})" if c > 1 else ""))
    else:
        print(f"baseline never grew ({versions} committed versions with {PYRIGHT} checked)")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
