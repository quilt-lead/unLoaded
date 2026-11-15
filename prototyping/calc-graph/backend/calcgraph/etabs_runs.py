"""Saved REAL ETABS runs (data/fixtures/etabs_runs/*.json, written by scripts/build_etabs_run_fixture.py
from the comparator report of each run) and which design each one belongs to.

A run names the design it analysed ("current" = data/eval/synthetic_v2/model.e2k, the derived export
scripts/build_etabs.py writes; or a design scenario id of
the answer key, e.g. "ORIG") and the sha1 of the e2k ETABS opened. It counts as the results OF a design
only while that design's e2k is byte-identical to it: regenerate the design and the run is reported as
`stale` (with why), never shown as if it were this design's analysis. Everything here is read-only.

finding(run) words what the run found from its own numbers (first mode shape, drift over the limit),
so no figure in the UI is typed by hand.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os

from . import store_root

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RUNS_DIR = os.path.join(ROOT, "data", "fixtures", "etabs_runs")
V2 = store_root.SYNTH_V2_DIR
CURRENT = "current"
REQUIRED = ("schema", "run_id", "etabs_version", "etabs_source", "run_at", "design", "e2k_sha1", "identity",
            "mapping", "modes", "lines", "drift", "members")
_CACHE: dict = {}


class RunFixtureError(ValueError):
    pass


def runs() -> list[dict]:
    """Every saved run, validated, newest first; cached while the directory listing and mtimes are unchanged."""
    names = sorted(n for n in os.listdir(RUNS_DIR) if n.endswith(".json")) if os.path.isdir(RUNS_DIR) else []
    key = tuple((n, os.stat(os.path.join(RUNS_DIR, n)).st_mtime_ns) for n in names)
    if _CACHE.get("key") != key:
        out = []
        for n in names:
            r = json.load(open(os.path.join(RUNS_DIR, n), encoding="utf-8"))
            validate(r, n)
            out.append(r)
        _CACHE.update(key=key, runs=sorted(out, key=lambda r: r["run_at"], reverse=True))
    return _CACHE["runs"]


def validate(r: dict, name: str = "?") -> None:
    miss = [k for k in REQUIRED if k not in r]
    if miss:
        raise RunFixtureError(f"{name}: missing {miss}")
    if r["schema"] != 1:
        raise RunFixtureError(f"{name}: unknown schema {r['schema']!r}")
    if f"{r['run_id']}.json" != name and name != "?":
        raise RunFixtureError(f"{name}: run_id {r['run_id']!r} does not match the file name")
    t = dt.datetime.fromisoformat(r["run_at"])
    if t.utcoffset() is None:
        raise RunFixtureError(f"{name}: run_at needs its US Eastern offset")
    if not r["modes"] or not r["drift"]:
        raise RunFixtureError(f"{name}: no modes or no drift rows")


def get(run_id: str) -> dict | None:
    return next((r for r in runs() if r["run_id"] == run_id), None)


def design_scenarios() -> list[dict]:
    """The answer key's design scenarios (the ONE list the API and the UI picker read)."""
    p = os.path.join(V2, "answer_key.json")
    if not os.path.exists(p):
        return []
    return json.load(open(p, encoding="utf-8")).get("design_scenarios", [])


def e2k_path(design: str) -> str | None:
    """The e2k of a design: the current model.e2k (a derived output of scripts/build_etabs.py, never source
    data), or the design scenario's own e2k (answer key, written by synth.v2.scenarios)."""
    if design == CURRENT:
        return store_root.derived_for(V2, "model.e2k")
    s = next((x for x in design_scenarios() if x["id"] == design), None)
    return os.path.join(V2, s["e2k"]) if s and s.get("e2k") else None


def _sha1(p: str | None) -> str | None:
    if not p or not os.path.exists(p):
        return None
    k = ("sha1", p, os.stat(p).st_mtime_ns)
    if k not in _CACHE:
        _CACHE[k] = hashlib.sha1(open(p, "rb").read()).hexdigest()
    return _CACHE[k]


def label(r: dict) -> str:
    return f"Real ETABS {r['etabs_version']} run, {dt.datetime.fromisoformat(r['run_at']).date().isoformat()}"


def _line_systems(r: dict) -> dict[str, str]:
    """drift-table line id -> its system, from the lateral-force table's names ("SMF line A" -> A: SMF)."""
    out = {}
    for ln in r["lines"]:
        sysname, _, lid = ln["line"].partition(" line ")
        out[lid] = sysname
    return out


def finding(r: dict) -> dict:
    """What the run found, from its numbers: the first mode's shape and every story drift over the limit
    (ETABS ratio > 1), with the design's own ratio at the same line and level (design in / allow in)."""
    m1 = r["modes"][0]
    parts = {"X translation": m1["ux"], "Y translation": m1["uy"], "torsional": m1["rz"]}
    shape = max(parts, key=lambda k: parts[k])
    systems = _line_systems(r)
    ng = [{"line": d["line"], "system": systems.get(d["line"], "?"), "level": d["level"], "etabs_ratio": d["etabs_ratio"],
           "design_ratio": round(d["design_in"] / d["allow_in"], 3)} for d in r["drift"] if d["etabs_ratio"] > 1.0]
    worst = max(r["drift"], key=lambda d: d["etabs_ratio"])
    bits = []
    if shape == "torsional":
        bits.append(f"torsion (mode 1 {m1['period_s']:.3f} s torsional)")
    groups: dict[tuple, list[dict]] = {}
    for x in ng:
        groups.setdefault((x["system"], x["level"]), []).append(x)
    for (sysname, lev), xs in groups.items():
        e = " / ".join(f"{x['etabs_ratio']:.3f}" for x in xs)
        dsg = " / ".join(f"{x['design_ratio']:.3f}" for x in xs)
        bits.append(f"{sysname} {lev} drift NG ({e} vs design {dsg})")
    if bits:
        headline = "Real ETABS found " + " + ".join(bits)
    else:
        headline = (f"Real ETABS: mode 1 {m1['period_s']:.3f} s {shape}; every story drift within the limit "
                    f"(worst {systems.get(worst['line'], '?')} line {worst['line']} {worst['level']} {worst['etabs_ratio']:.3f})")
    return {"mode1": {**m1, "shape": shape}, "drift_ng": ng,
            "worst_drift": {**worst, "system": systems.get(worst["line"], "?")}, "headline": headline,
            "flagged": sum(a["flagged"] for a in r["members"]["agreement"]),
            "compared": len(r["members"]["rows"])}


def summary(r: dict) -> dict:
    return {"run_id": r["run_id"], "label": label(r), "etabs_version": r["etabs_version"], "etabs_source": r["etabs_source"],
            "run_at": r["run_at"], "design": r["design"], "e2k_sha1": r["e2k_sha1"], "identity": r["identity"],
            "finding": finding(r)}


def for_design(design: str) -> dict:
    """The saved runs of a design: `runs` = those whose e2k is byte-identical to the design's e2k now
    (the design's real ETABS results), `stale` = runs of that design name whose e2k no longer matches."""
    p = e2k_path(design)
    sha = _sha1(p)
    mine = [r for r in runs() if r["design"] == design]
    cur = [summary(r) for r in mine if sha and r["e2k_sha1"] == sha]
    why = "the design's e2k is not built here" if sha is None else "the design's e2k changed since this run (different sha1)"
    stale = [{**summary(r), "stale_reason": why} for r in mine if not (sha and r["e2k_sha1"] == sha)]
    return {"design": design, "e2k": os.path.relpath(p, ROOT) if p else None, "e2k_sha1": sha, "runs": cur, "stale": stale}
