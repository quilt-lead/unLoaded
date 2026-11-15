"""Ground truth for "move a column": re-run the FULL design for each scenario and diff it
against the base design record by record. This is the answer key the impact engine is
scored against - it is computed only from re-running the design, never from the engine.

    cd tools/calcgraph-reference
    uv run python -m synth.v2.scenarios [--jobs 4] [--only S01,S02]

Writes data/synthetic_v2/scenarios/<id>.json (moved design export) and
data/synthetic_v2/answer_key.json.

Per scenario the key records:
- changed_records: record ids whose primary demand moved by > 5 % (or whose size / detail
  changed, or that appeared / disappeared) - the true stale set
- resized: elements whose size / connection type / footing size changed in the MINIMUM-CHANGE
  re-design (design.run(keep=current): keep every surviving size unless it fails, else the next
  heavier) - lightest-passing from scratch would also "downsize" members, which no engineer does
  for a column move
- over_at_current: elements that exceed UC 1.0 if left at their CURRENT size under the new
  layout (gravity members, columns, footings, connections, SMF drift)
- lateral_changed: lateral records (ELF, frames, drift, braces, collectors) changed > 5 %
  or SFRS geometry changed
- clashes: new footing clashes; difficulty: easy / moderate / hard / do-not-move (rules below)
"""
from __future__ import annotations

import argparse
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor

from . import aisc, gravity as G, lateral as LAT, model, records
from .generate import OUT, _clean, build, write_json_atomic

THRESH = 0.05
LATERAL_KINDS = {"seismic", "wind", "frame_analysis", "brace"}   # the lateral ANALYSIS (frame members are SFRS demand, see resized)

# id, label, kind, column, dx, dy
SCENARIOS = [
    ("S01", "Gravity column 2/B moved +2 ft in x", "move", "2B", 2, 0),
    ("S02", "Gravity column 2/B moved +5 ft in x", "move", "2B", 5, 0),
    ("S03", "Gravity column 2/B moved +10 ft in x", "move", "2B", 10, 0),
    ("S04", "Gravity column 2/B moved +2 ft in y", "move", "2B", 0, 2),
    ("S05", "Gravity column 2/B moved +5 ft in y", "move", "2B", 0, 5),
    ("S06", "Gravity column 2/B moved -5 ft in y", "move", "2B", 0, -5),
    ("S07", "Gravity column 4/C moved -2 ft in x", "move", "4C", -2, 0),
    ("S08", "Gravity column 4/C moved -5 ft in x", "move", "4C", -5, 0),
    ("S09", "Gravity column 4/C moved -10 ft in x", "move", "4C", -10, 0),
    ("S10", "Gravity column 4/C moved +5 ft in y", "move", "4C", 0, 5),
    ("S11", "Gravity column 4/C moved -10 ft in y", "move", "4C", 0, -10),
    ("S12", "Gravity column 2/B removed", "remove", "2B", 0, 0),
    ("S13", "Gravity column 4/C removed", "remove", "4C", 0, 0),
    ("S14", "Gravity column 2/C removed", "remove", "2C", 0, 0),
    ("S15", "SMF column 2/A moved +2 ft in x (along frame line A)", "move", "2A", 2, 0),
    ("S16", "SMF column 4/D moved -5 ft in x (along frame line D)", "move", "4D", -5, 0),
    ("S17", "SCBF column 5/B moved +3 ft in y (braced bay A-B, line 5)", "move", "5B", 0, 3),
    ("S18", "Corner column 1/A (SCBF line 1) moved +5 ft in x", "move", "1A", 5, 0),
    ("S19", "Corner column 5/D (SCBF line 5) moved -5 ft in y", "move", "5D", 0, -5),
    ("S20", "SCBF column 1/B moved +5 ft in y (braced bay A-B, line 1, along the line-1 grade beam)", "move", "1B", 0, 5),
    ("S21", "Gravity column 2/B moved -25 ft in y (footing onto the line-A grade beam)", "move", "2B", 0, -25),
    ("S22", "Column 4/B under the roof mech area moved -5 ft in x", "move", "4B", -5, 0),
    ("S23", "Column 4/B under the roof mech area moved +5 ft in y", "move", "4B", 0, 5),
    ("S24", "Column 4/B under the roof mech area moved +10 ft in x", "move", "4B", 10, 0),
    ("S25", "Gravity column 2/C moved +5 ft in x", "move", "2C", 5, 0),
]


# The hackathon also wrote "design scenarios" (a different lateral system, exported to ETABS .e2k)
# into answer_key.json["design_scenarios"]. They are never scored as a move and need the ETABS
# adapter, so this standalone copy leaves them out; design_scenarios is written as [].


def layout_for(sc) -> model.Layout:
    sid, label, kind, col, dx, dy = sc
    L = model.base_layout()
    L.label = f"{sid}: {label}"
    if kind == "remove":
        L.removed.add(col)
    else:
        x, y = L.cols[col]
        L.cols[col] = (x + dx, y + dy)
    return L


def _size_of(e: dict) -> str | None:
    t = e["type"]
    if t in ("beam", "girder", "column", "brace"):
        return e["size"]
    if t == "connection":
        return e.get("conn_type")
    if t == "footing":
        return f"{e['B_ft']}ft x {e['h_in']}in"
    if t == "grade_beam":
        return f"{e['b_in']}x{e['h_in']}"
    if t == "pier":
        return e.get("pier_type")
    return None


def _demand_vec(r: dict) -> list[float]:
    """Primary demand(s) of a record: the scalar demand plus, for beams, the end reactions
    (a beam whose moment is unchanged but whose reaction moves still changes its connection)."""
    v = [r["demand"]] if r.get("demand") is not None else []
    vals = r["values"]
    for k in ("R_i_k", "R_j_k", "Pu_k", "Mux_kft", "P_service_k"):
        if isinstance(vals.get(k), (int, float)):
            v.append(vals[k])
    return v


def _rel(a: float, b: float) -> float:
    return abs(b - a) / max(abs(a), 1e-6) if abs(a) > 1e-6 else (0.0 if abs(b) < 1e-6 else 1.0)


def at_current_sizes(L: model.Layout, base: dict) -> dict:
    """UC of every surviving gravity member / column / footing / connection if it stays at its
    CURRENT size under the new layout (what an engineer checks before deciding to resize)."""
    topo = model.build(L)
    sizes = {e["id"]: e for e in base["elements"]}
    fixed = {k: sizes[k]["size"] for k in topo.members if k in sizes}
    fr = G.design_framing(topo, fixed_sizes=fixed)
    out = {}
    for k, r in fr.items():
        if k in fixed:
            out[k] = {"uc": r["uc"], "governs": r["governs"], "mu": r["mu"], "size": r["size"]}
    rx = G.reactions_to_columns(topo, fr)
    for c, info in topo.columns.items():
        cid = f"COL-{c}"
        if cid not in sizes or info["roles"] != ["gravity"]:
            continue
        size = sizes[cid]["size"]
        segs = G.column_demands(topo, rx[c], size, topo.columns[c]["roles"])
        r = G.check_column(size, segs)
        out[cid] = {"uc": r["uc"], "pu": r["pu"], "size": size}
        fid = f"F-{c}"
        if fid in sizes:
            p = segs[0]["P"]
            ps = max(p[0] + p[1] + p[2], p[0] + 0.75 * p[1] + 0.75 * p[2])
            out[fid] = {"uc": ps / (G.QA * sizes[fid]["B_ft"] ** 2), "p_service": ps, "size": _size_of(sizes[fid])}
    for k, m in topo.members.items():
        for end, s in (("i", m.i), ("j", m.j)):
            cid = f"CX-{k}-{end}"
            e = sizes.get(cid)
            if not e or not e["conn_type"].startswith("ST-"):
                continue
            n = int(e["conn_type"].split("-")[1].rstrip("*"))
            ru = max(G.fac(fr[k]["R" + end], lc) for lc in G.COMBOS)
            out[cid] = {"uc": ru / G.SHEAR_TABS[n]["phi_rn"], "ru": ru, "size": e["conn_type"]}
    return out


def smf_drift_at_current(L: model.Layout, base: dict, d_new: dict) -> dict:
    """Drift of each SMF line with the CURRENT frame sizes in the new geometry."""
    out = {}
    for yl, s in d_new["smf"].items():
        old = next((r for r in base["records"] if r["id"] == f"C-SMF:{yl}"), None)
        if not old:
            continue
        ob, oc = old["values"]["beam"], old["values"]["column"]
        cols = [c for c, _ in sorted(((c, d_new["topo"].columns[c]["x"]) for c in d_new["topo"].columns
                                      if c[-1] == yl and c[:-1] in d_new["topo"].scheme.MF[yl]), key=lambda t: t[1])]
        cl = [(c, d_new["topo"].columns[c]["x"]) for c in cols]
        bl = {}
        for k, m in d_new["topo"].members.items():
            if "smf_beam" in m.roles and m.line == yl:
                w = G.line_loads(m, d_new["topo"])
                bl[(m.level, cols.index(m.i["col"]))] = (w[0], w[1] + w[2])
        a = LAT.analyse_smf(yl, cl, bl, ob, oc, s["fe"], s["fw"], 1.0, 3.0, shear_def=s.get("shear_def", False))
        out[yl] = max(x["ratio"] for x in a["drifts"])
    return out


def difficulty(key: dict, sc) -> tuple[str, list[str]]:
    why = []
    col = f"COL-{sc[3]}"
    sfrs_col = any(r in ("smf_column", "scbf_column") for r in key.get("moved_roles", []))
    if key["infeasible"]:
        why.append(f"no passing shape for {', '.join(key['infeasible'][:3])}")
    over_drift = [yl for yl, v in key.get("smf_drift_at_current", {}).items() if v > 1.0]
    if over_drift:
        why.append(f"SMF line {', '.join(over_drift)} drift > limit at current sizes")
    frame_resized = [e for e in key["resized"] if e["sfrs"]]
    if key["infeasible"] or over_drift or (sfrs_col and frame_resized):
        return "do-not-move", why + [f"SFRS member(s) re-sized: {', '.join(e['id'] for e in frame_resized[:4])}"] if frame_resized else why
    hard = []
    if sc[2] == "remove":
        hard.append("column removed - transfer framing")
    if sfrs_col:
        hard.append("column is part of the lateral system - frame re-analysis")
    if key["lateral_changed"]:
        hard.append("lateral analysis changes")
    must = {k for k, v in key["over_at_current"].items()}
    if any(e["type"] == "column" and e["change"] == "resized" for e in key["resized"]):
        hard.append("column re-sized")
    if key["clashes"]:
        hard.append("new foundation clash: " + ", ".join(f"{c['a']} vs {c['b']}" for c in key["clashes"][:2]))
    if any(e.get("special") for e in key["resized"] if e["type"] == "connection"):
        hard.append("connection beyond the typical details")
    if hard:
        return "hard", hard
    mod = []
    n_up = sum(1 for k in must if not k.startswith(("CX-", "F-", "COL-")))
    if n_up:
        mod.append(f"{n_up} beam/girder over capacity at current size - upsize")
    if any(k.startswith("CX-") for k in must):
        mod.append("connection exceeds its typical detail - next typical")
    if any(k.startswith("F-") for k in must) or any(e["type"] in ("footing", "grade_beam", "pier") and e["change"] == "resized"
                                                     and e["new"] and e["old"] and e["new"] > e["old"] for e in key["resized"]):
        mod.append("footing enlarges")
    if mod:
        return "moderate", mod
    return "easy", ["demand changes only - recalc, no size or detail change required"]


def run_one(sc) -> dict:
    t = time.time()
    base = json.load(open(os.path.join(OUT, "design.json")))
    L = layout_for(sc)
    # minimum-change re-design: every surviving element keeps its size/detail unless it fails
    d_new, exp = build(L, keep={e["id"]: e for e in base["elements"]})
    os.makedirs(os.path.join(OUT, "scenarios"), exist_ok=True)
    write_json_atomic(os.path.join(OUT, "scenarios", f"{sc[0]}.json"), exp, sort_keys=True)
    b_rec = {r["id"]: r for r in base["records"]}
    n_rec = {r["id"]: r for r in exp["records"]}
    b_el = {e["id"]: e for e in base["elements"]}
    n_el = {e["id"]: e for e in exp["elements"]}
    changed = {}
    for rid in sorted(set(b_rec) | set(n_rec)):
        a, b = b_rec.get(rid), n_rec.get(rid)
        if a is None:
            changed[rid] = "new record"
            continue
        if b is None:
            changed[rid] = "record removed"
            continue
        va, vb = _demand_vec(a), _demand_vec(b)
        d = max((_rel(x, y) for x, y in zip(va, vb)), default=0.0)
        if d > THRESH:
            changed[rid] = f"demand {d * 100:.0f}%"
        elif a["values"].get("size") != b["values"].get("size") or a["values"].get("type") != b["values"].get("type"):
            changed[rid] = "size/detail changed"
    resized = []
    for eid in sorted(set(b_el) | set(n_el)):
        a, b = b_el.get(eid), n_el.get(eid)
        if a is None or b is None:
            if (a or b)["type"] in ("beam", "girder", "column", "footing", "connection", "grade_beam", "pier", "brace"):
                resized.append({"id": eid, "type": (a or b)["type"], "old": _size_of(a) if a else None,
                                "new": _size_of(b) if b else None, "sfrs": bool((a or b).get("sfrs")),
                                "special": bool((b or {}).get("special")), "change": "added" if a is None else "removed"})
            continue
        sa, sb = _size_of(a), _size_of(b)
        if sa != sb and sa is not None:
            resized.append({"id": eid, "type": a["type"], "old": sa, "new": sb, "sfrs": bool(a.get("sfrs")),
                            "special": bool(b.get("special")), "change": "resized"})
    cur = at_current_sizes(L, base)
    base_clash = {(c["a"], c["b"]) for c in base["clashes"]}
    clashes = [c for c in exp["clashes"] if (c["a"], c["b"]) not in base_clash]
    lat = [rid for rid in changed if (b_rec.get(rid) or n_rec.get(rid))["kind"] in LATERAL_KINDS]
    moved_roles = next((e.get("roles", []) for e in base["elements"] if e["id"] == f"COL-{sc[3]}"), [])
    if any(r in ("smf_column", "scbf_column") for r in moved_roles):
        lat.append(f"SFRS geometry: {sc[3]} is a frame column")
    key = {"id": sc[0], "label": sc[1], "kind": sc[2], "column": f"COL-{sc[3]}", "dx": sc[4], "dy": sc[5],
           "changed_records": changed, "resized": resized,
           "over_at_current": {k: {kk: (round(vv, 4) if isinstance(vv, float) else vv) for kk, vv in v.items()}
                               for k, v in cur.items() if v["uc"] > 1.0},
           "uc_at_current": {k: round(v["uc"], 4) for k, v in cur.items()},
           "lateral_changed": sorted(lat), "clashes": clashes, "infeasible": exp["infeasible"],
           "moved_roles": moved_roles, "seconds": None}
    if any(r in ("smf_column",) for r in moved_roles):
        key["smf_drift_at_current"] = {k: round(v, 4) for k, v in smf_drift_at_current(L, base, d_new).items()}
    key["difficulty"], key["difficulty_why"] = difficulty(key, sc)
    # new demand per record for screening-error evaluation
    key["new_demand"] = {rid: n_rec[rid]["demand"] for rid in changed if rid in n_rec and n_rec[rid]["demand"] is not None}
    key["new_uc"] = {rid: n_rec[rid]["uc"] for rid in changed if rid in n_rec and n_rec[rid]["uc"] is not None}
    key["seconds"] = round(time.time() - t, 1)
    return _clean(key)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    if not os.path.exists(os.path.join(OUT, "design.json")):
        raise SystemExit("run `uv run python -m synth.v2.generate` first")
    scs = [s for s in SCENARIOS if not a.only or s[0] in a.only.split(",")]
    if a.only and not scs:
        scs = []
    t = time.time()
    with ProcessPoolExecutor(max_workers=a.jobs) as ex:
        keys = list(ex.map(run_one, scs))
    dkeys: list[dict] = []
    path = os.path.join(OUT, "answer_key.json")
    old = json.load(open(path)) if a.only and os.path.exists(path) else {"scenarios": [], "design_scenarios": []}
    merged = {k["id"]: k for k in old["scenarios"]}
    merged.update({k["id"]: k for k in keys})
    dmerged = {k["id"]: k for k in old.get("design_scenarios", [])}
    dmerged.update({k["id"]: k for k in dkeys})
    write_json_atomic(path, {"threshold": THRESH, "scenarios": [merged[k] for k in sorted(merged)],
                             "design_scenarios": [dmerged[k] for k in sorted(dmerged)]}, indent=1, sort_keys=True)
    for k in dkeys:
        print(f"{k['id']} design scenario: {k['label']} -> {k['file']}, {k['e2k']}")
    for k in keys:
        print(f"{k['id']} {k['difficulty']:<11} stale {len(k['changed_records']):>4}  resized {len(k['resized']):>3}  "
              f"over@cur {len(k['over_at_current']):>3}  lateral {len(k['lateral_changed']):>3}  clashes {len(k['clashes'])}  "
              f"{k['label']}  ({k['seconds']} s)")
    print(f"{len(keys)} scenarios in {time.time() - t:.0f} s -> {path}")


if __name__ == "__main__":
    main()
