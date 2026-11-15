"""Turn the comparator report of a REAL ETABS run into a small numbers-only fixture the app serves.

    uv run python scripts/build_etabs_run_fixture.py --report report.md --design ORIG \
        --e2k data/synthetic_v2/scenarios/ORIG.e2k --run-at 2026-11-14T17:41:47-05:00 \
        --etabs-source "real ETABS 23.3.2 via CSI OAPI" --run-id etabs-real-ORIG-20261114-1741 \
        --how "..." [--out data/fixtures/etabs_runs/<run-id>.json]

`report.md` is what scripts/compare_etabs_pynite.py wrote for the run (its `report()` format: label
mapping, load totals, base shear, modes, lateral force per line, story drift per line, per-member
governing-combo rows). Only numbers and calc-graph's own synthetic ids are kept (element ids, ETABS
labels, line / level names); no text from ETABS or any document. `--e2k` is the e2k ETABS opened; its
sha1 is the key the app matches a run to a design by (calcgraph.etabs_runs), so a run is shown for a
design only while that design's e2k is byte-identical to the one ETABS ran.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import statistics
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT_DIR = os.path.join(ROOT, "data", "fixtures", "etabs_runs")


def _sections(md: str) -> dict[str, list[str]]:
    out, cur = {}, None
    for line in md.splitlines():
        if line.startswith("### "):
            cur = line[4:].strip()
            out[cur] = []
        elif cur is not None:
            out[cur].append(line)
    return out


def _table(lines: list[str]) -> list[list[str]]:
    rows = [ln for ln in lines if ln.startswith("|")]
    return [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows[2:]]   # skip header + rule


def _num(s: str) -> float | None:
    s = s.strip().rstrip("%")
    return None if s in ("", "-") else float(s)


def _num_req(s: str) -> float:
    v = _num(s)
    if v is None:
        raise SystemExit(f"report has an empty cell where a number is required: {s!r}")
    return v


def _find(secs: dict, prefix: str) -> tuple[str, list[str]]:
    k = next((k for k in secs if k.startswith(prefix)), None)
    if k is None:
        raise SystemExit(f"report has no section starting {prefix!r}")
    return k, secs[k]


def parse(md: str) -> dict:
    secs = _sections(md)
    _, lab = _find(secs, "Label mapping")
    m = re.search(r"ETABS frames (\d+), adapter frames (\d+), unmapped (\d+), missing (\d+)", " ".join(lab))
    if not m:
        raise SystemExit("label mapping line not found")
    mapping = dict(zip(("etabs_frames", "adapter_frames", "unmapped", "missing"), map(int, m.groups())))
    totals = [{"case": r[0], "etabs_kip": _num(r[1]), "design_kip": _num(r[2])} for r in _table(_find(secs, "Load totals")[1])]
    shear = [{"case": r[0], "etabs_kip": _num(r[1]), "design_kip": _num(r[2])} for r in _table(_find(secs, "Base shear")[1])]
    mk, ml = _find(secs, "Modes")
    ta = re.search(r"X ([\d.]+) s, Y ([\d.]+) s", mk)
    if not ta:
        raise SystemExit(f"modes heading has no 'X <n> s, Y <n> s' code period: {mk!r}")
    modes = [{"mode": int(r[0]), "period_s": _num(r[1]), "ux": _num(r[2]), "uy": _num(r[3]), "rz": _num(r[4]),
              "sum_ux": _num(r[5]), "sum_uy": _num(r[6]), "sum_rz": _num(r[7])} for r in _table(ml)]
    lines = [{"line": r[0], "etabs_pos_ecc_kip": _num(r[1]), "etabs_neg_ecc_kip": _num(r[2]), "design_kip": _num(r[3]),
              "design_share_of_v": _num_req(r[4]) / 100, "etabs_wind_kip": _num(r[5]), "design_wind_kip": _num(r[6])}
             for r in _table(_find(secs, "Lateral force")[1])]
    drift = [{"line": r[0], "level": r[1], "etabs_in": _num(r[2]), "design_in": _num(r[3]), "pct": _num(r[4]),
              "allow_in": _num(r[5]), "etabs_ratio": _num(r[6])} for r in _table(_find(secs, "Story drift")[1])]
    pk, pl = _find(secs, "Per member, governing")
    rows = []
    for r in _table(pl):
        label, _, story = r[2].partition("@")
        rows.append({"line": r[0], "element": r[1], "label": label, "story": story, "at": r[3], "sta_ft": _num(r[4]),
                     "qty": r[5], "combo": r[6], "etabs": _num(r[7]), "pynite": _num(r[8]), "pct": _num(r[9]),
                     "flag": r[10] == "FLAG", "flaggable": flaggable(r[-1]), "note": r[-1]})   # last cell: "ETABS gov" may hold a "|"
    n = re.search(r"(\d+) comparisons, (\d+) flagged \(> ([\d.]+)%\)", pk)
    if not n or int(n.group(1)) != len(rows) or int(n.group(2)) != sum(r["flag"] for r in rows):
        raise SystemExit(f"per-member header {pk!r} disagrees with its {len(rows)} rows")
    return {"mapping": mapping, "totals": totals, "base_shear": shear,
            "code_ta_s": {"x": float(ta.group(1)), "y": float(ta.group(2))}, "modes": modes, "lines": lines,
            "drift": drift, "members": {"flag_pct": float(n.group(3)), "rows": rows, "agreement": agreement(rows)}}


# the comparator's notes on rows it reports but never flags (compare_etabs_pynite.compare: flaggable = False)
NOT_LIKE_FOR_LIKE = ("2D frame axial only", "SCBF frame:", "ETABS rigid diaphragm:")


def flaggable(note: str) -> bool:
    return not note.startswith(NOT_LIKE_FOR_LIKE)


def member_kind(eid: str) -> str:
    return "columns" if eid.startswith("COL-") else "braces" if eid.startswith("BR-") else "beams"


def agreement(rows: list[dict]) -> list[dict]:
    """ETABS vs PyNite per (line, member kind, qty) over the like-for-like rows that carry a %: n, within
    the flag %, median / max |%| (the comparator's own flag rule; the rest are counted, not scored)."""
    groups: dict[tuple, list[dict]] = {}
    for r in rows:
        groups.setdefault((r["line"], member_kind(r["element"]), r["qty"]), []).append(r)
    out = []
    for (line, kind, qty), rs in groups.items():
        scored = [r for r in rs if r["flaggable"] and r["pct"] is not None]
        p = [abs(r["pct"]) for r in scored]
        out.append({"line": line, "members": kind, "qty": qty, "rows": len(rs), "n": len(scored),
                    "within": sum(1 for r in scored if not r["flag"]), "flagged": sum(r["flag"] for r in rs),
                    "median_abs_pct": round(statistics.median(p), 1) if p else None,
                    "max_abs_pct": round(max(p), 1) if p else None})
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    ap.add_argument("--report", required=True, help="compare_etabs_pynite.py report markdown of the run")
    ap.add_argument("--design", required=True, help="'current' (data/synthetic_v2/model.e2k) or a design scenario id (answer_key)")
    ap.add_argument("--e2k", required=True, help="the e2k ETABS opened (its sha1 keys the run to the design)")
    ap.add_argument("--run-at", required=True, help="when ETABS analysed it, ISO with the US Eastern offset")
    ap.add_argument("--etabs-source", required=True, help="the source string the bridge returned, e.g. 'real ETABS 23.3.2 via CSI OAPI'")
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--how", required=True, help="how the e2k / design identity of this run was established")
    ap.add_argument("--out", help=f"default {OUT_DIR}/<run-id>.json")
    a = ap.parse_args()
    ver = re.search(r"ETABS ([\d.]+)", a.etabs_source)
    if not ver:
        raise SystemExit("--etabs-source must name the ETABS version")
    body = parse(open(a.report, encoding="utf-8").read())
    fx = {"schema": 1, "run_id": a.run_id, "etabs_version": ver.group(1), "etabs_source": a.etabs_source,
          "run_at": a.run_at, "design": a.design, "e2k_sha1": hashlib.sha1(open(a.e2k, "rb").read()).hexdigest(),
          "identity": a.how, "comparator": "scripts/compare_etabs_pynite.py", **body}
    out = a.out or os.path.join(OUT_DIR, f"{a.run_id}.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(fx, fh, indent=1)
        fh.write("\n")
    print(out, os.path.getsize(out), "bytes;", len(body["members"]["rows"]), "member rows")


if __name__ == "__main__":
    sys.exit(main())
