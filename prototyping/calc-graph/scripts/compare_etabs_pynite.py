"""Compare a REAL ETABS run of the .e2k scripts/build_etabs.py writes (data/eval/synthetic_v2/model.e2k) with calc-graph's PyNite frame analysis.

    uv run python scripts/compare_etabs_pynite.py --etabs DIR [--out report.md] [--json rows.json]
    uv run python scripts/compare_etabs_pynite.py --bridge http://127.0.0.1:8765 --save DIR ...

DIR holds what the Windows bridge returned for the analysed model (``--bridge`` fetches it live
and ``--save`` keeps it). Every file is checked to be in kip / ft (the bridge sets and echoes
the units on every /csi/results read):
  results_cases.json   /csi/results kinds frame_forces, joint_reactions, story_drifts,
                       joint_displacements, base_reactions, modal_mass; cases CASES
  results_combos.json  /csi/results kinds frame_forces, base_reactions; combos COMBOS
  labels.json          /csi/call SapModel.FrameObj.GetLabelNameList
  point_labels.json    /csi/call SapModel.PointObj.GetLabelNameList

The e2k (analysis.etabs.build_objects + analysis.e2k.write_e2k) carries the design's loads: area
SDL / L / Lr on zero-weight membrane decks, perimeter wall line loads, the rigid diaphragm, a
mass source from loads (SDL + SeisWt = lateral.seismic_weights), EQX/EQY as +ecc / -ecc patterns
with Envelope combos, wind story forces as point loads, and the 15 design combos.

The PyNite side is the production analysis, not a re-typed model: synth.v2.design.run is run on
the design's layout with synth.v2.lateral._frame wrapped, which captures the exact frames the
design solved (every 2D SMF and SCBF line the layout has: their beam loads, line shares of the ELF and
wind, sizes). Those frames are re-solved per load case (D, L, E, W) and combined with the
design's own combos (analyse_smf: S1 S2 S3 W1 G2; design_scbf: S1). ETABS case results are
combined with the same factors (D = Dead + SDL, L = Live + Lr as the 2D frames lump them,
E = the worse of the +ecc / -ecc cases, W = WX), so each combo compares like with like.

Matching: every PyNite member is located in the 3D model by geometry (line plane + end
coordinates) against the adapter's ETABS frame objects; ETABS labels / stories come from the
real run (GetLabelNameList). PyNite is evaluated at the stations ETABS reports (its automatic end
offsets put end stations at the support faces). In-plane components: X frames M3 / V2 for beams
and columns (all columns have their depth along X), Y frames (SCBF lines) M3 / V2 beams, M2 / V3
columns, braces axial.

Not like-for-like and therefore reported but not flagged: SMF column axial outside S1 / S3 (the
2D frame excludes gravity from transverse framing; the design adds it as gp for seismic combos,
and that sum is compared, signed, compression positive), SCBF column axial / bending (the
design's SCBF frame uses W14X90 columns whatever was designed, with weak-axis stiffness =
strong-axis, pinned bases), beam axial (ETABS's rigid diaphragm reports 0 axial in beams).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path[:0] = [os.path.join(ROOT, "backend"), ROOT]

from calcgraph.analysis.base import layout_from_design, load_design  # noqa: E402
from calcgraph.analysis.etabs import EtabsAdapter  # noqa: E402
from synth.v2 import design as DSN, lateral as LAT  # noqa: E402
from synth.v2.model import LEVELS, STOREY_H  # noqa: E402

FLAG_PCT = 5.0
TINY = 1.0          # kip / kip-ft: below this PyNite value no % is computed (absolute values shown)
TOL = 1e-3
CASES = ["Modal", "Dead", "SDL", "Live", "Lr", "EQX+ecc", "EQX-ecc", "EQY+ecc", "EQY-ecc", "WX", "WY"]
COMBOS = ["EQX", "EQY", "1.4D", "1.2D+1.6L+0.5Lr", "1.2D+1.6Lr+0.5L", "1.4D+0.5L+1EQX", "0.7D+1EQX",
          "1.4D+0.5L-1EQX", "0.7D-1EQX", "1.2D+0.5L+1.0WX", "1.4D+0.5L+3EQX (Omega0)", "1.4D+0.5L+1.3EQY",
          "0.7D+1.3EQY", "1.4D+0.5L-1.3EQY", "0.7D-1.3EQY", "1.2D+0.5L+1.0WY", "1.4D+0.5L+2EQY (Omega0)"]
SDS = LAT.SDS
RHO = {"x": LAT.SYS["x"]["rho"], "y": LAT.SYS["y"]["rho"]}
# the design's 2D-frame combos (synth.v2.lateral.analyse_smf / design_scbf), as factors on D, L, E, W
SMF_COMBOS = {"S1": {"D": 1.2 + 0.2 * SDS, "L": 0.5, "E": RHO["x"]}, "S2": {"D": 0.9 - 0.2 * SDS, "E": RHO["x"]},
              "S3": {"D": 1.2 + 0.2 * SDS, "L": 0.5, "E": -RHO["x"]}, "W1": {"D": 1.2, "L": 0.5, "W": 1.0},
              "G2": {"D": 1.2, "L": 1.6}}
SCBF_COMBOS_ORIGINAL = {"S1": {"D": 1.2 + 0.2 * SDS, "L": 0.5, "E": RHO["y"]}}   # the first issue ran S1 only
SCBF_COMBOS_REVIEWED = LAT.SCBF_COMBOS                                         # every combo, gravity included


# ------------------------------------------------------------------ ETABS input
def _post(url: str, body: dict) -> dict:
    req = urllib.request.Request(url, json.dumps(body).encode(), {"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as r:
        return json.load(r)


def fetch(bridge: str) -> dict:
    return {
        "results_cases": _post(f"{bridge}/csi/results", {"kinds": ["frame_forces", "joint_reactions", "story_drifts",
                                                                   "joint_displacements", "base_reactions", "modal_mass"],
                                                         "cases": CASES}),
        "results_combos": _post(f"{bridge}/csi/results", {"kinds": ["frame_forces", "base_reactions"], "combos": COMBOS}),
        "labels": _post(f"{bridge}/csi/call", {"path": "SapModel.FrameObj", "method": "GetLabelNameList"}),
        "point_labels": _post(f"{bridge}/csi/call", {"path": "SapModel.PointObj", "method": "GetLabelNameList"}),
    }


def check_units(d: dict) -> None:
    for k in ("results_cases", "results_combos"):
        u = (d[k].get("units") or {}).get("name")
        if u != "kip_ft_F":
            raise SystemExit(f"{k}: units {u!r}, expected kip_ft_F (bridge /csi/results must declare its units)")


def frame_rows(res: dict, labels: dict) -> dict:
    """{(label, story): {case: [rows sorted by ObjSta]}}; envelope combos keep Max / Min steps."""
    name_to = {n: (l, s) for n, l, s in zip(labels["MyName"], labels["MyLabel"], labels["MyStory"])}
    out: dict = {}
    for r in res["frame_forces"]:
        key = r["LoadCase"] if r["StepType"] in ("Single Value", "") else f"{r['LoadCase']}|{r['StepType']}"
        out.setdefault(name_to[r["Obj"]], {}).setdefault(key, []).append(r)
    for d in out.values():
        for rows in d.values():
            rows.sort(key=lambda r: r["ObjSta"])
    return out


# ------------------------------------------------------------------ PyNite (production)
def capture_design_frames(exp: dict) -> tuple[dict, dict]:
    """Run synth.v2.design.run on the design's layout with lateral._frame wrapped; return
    ({line: args} of the frames the design kept - every SMF and every SCBF line, the design result)."""
    calls = []
    orig = LAT._frame

    def spy(cols, beam_loads, beam, col, fx, base_fixed, pinned_beams=False, braces=None, brace_size=None,
            shear_def=False, beam_sizes=None):
        calls.append(dict(cols=list(cols), beam_loads=dict(beam_loads), beam=beam, col=col,
                          fx={k: dict(v) for k, v in fx.items()}, base_fixed=base_fixed,
                          pinned_beams=pinned_beams, braces=braces, brace_size=brace_size,
                          shear_def=shear_def, beam_sizes=dict(beam_sizes or {})))
        return orig(cols, beam_loads, beam, col, fx, base_fixed, pinned_beams, braces, brace_size, shear_def, beam_sizes)

    LAT._frame = spy
    try:
        d = DSN.run(layout_from_design(exp))
    finally:
        LAT._frame = orig
    frames = {}
    for yl, s in d["smf"].items():
        hit = [c for c in calls if not c["brace_size"] and c["beam"] == s["beam"] and c["col"] == s["col"]
               and c["fx"].get("E") == s["fe"] and c["cols"][0][0][-1] == yl]
        if not hit:
            raise RuntimeError(f"SMF line {yl}: the kept frame was not among the captured _frame calls")
        frames[yl] = hit[-1]
    for xl, sc in d["scbf"].items():
        hit = [c for c in calls if c["brace_size"] and c["brace_size"] == sc.get("brace") and c["cols"][0][0][:-1] == xl
               and (sc.get("fy") is None or c["fx"].get("E") == sc["fy"])]
        if hit:
            frames[xl] = hit[-1]
    return frames, d


def solve(args: dict, with_w: bool):
    m = LAT._frame(**args)
    for k in ("D", "L", "E") + (("W",) if with_w else ()):
        m.add_load_combo("c" + k, {k: 1.0})
    m.analyze_linear(check_statics=False, check_stability=False)
    return m


def pn_at(mem, x: float, case: str) -> dict:
    x = min(max(x, 0.0), mem.L())
    return {"M": float(max((mem.moment(d, x, "c" + case) for d in ("My", "Mz")), key=abs)),
            "V": float(max((mem.shear(d, x, "c" + case) for d in ("Fy", "Fz")), key=abs)),
            "P": float(mem.axial(x, "c" + case))}


# ------------------------------------------------------------------ geometry match
def _g(plane: tuple, pos: float, z: float) -> tuple:
    """In-plane (pos, z) of a 2D frame -> global xyz. plane = ("X", y) or ("Y", x)."""
    return (pos, plane[1], z) if plane[0] == "X" else (plane[1], pos, z)


def _near(a, b) -> bool:
    return all(abs(u - v) < TOL for u, v in zip(a, b))


def match_members(m, plane: tuple, frames: list) -> dict:
    """{(label, story): [(pynite member, offset along ETABS object, +1/-1), ...]} for every PyNite
    member that lies on an ETABS frame object (exactly, or as a sub-segment of a split beam)."""
    out: dict = {}
    for name, mem in m.members.items():
        a = _g(plane, mem.i_node.X, mem.i_node.Z)
        b = _g(plane, mem.j_node.X, mem.j_node.Z)
        for o in frames:
            i, j = o.props["xyz_i"], o.props["xyz_j"]
            L = math.dist(i, j)
            u = [(q - p) / L for p, q in zip(i, j)]

            def along(pt):
                t = sum((pt[k] - i[k]) * u[k] for k in range(3))
                on = math.dist(pt, [i[k] + t * u[k] for k in range(3)]) < TOL
                return t if on and -TOL <= t <= L + TOL else None
            ta, tb = along(a), along(b)
            if ta is None or tb is None or abs(ta - tb) < TOL:
                continue
            out.setdefault((o.label, o.story), []).append((name, min(ta, tb), 1 if tb > ta else -1, o))
            break
    return out


# ------------------------------------------------------------------ compare
def pct(e: float, p: float) -> float | None:
    return None if abs(p) < TINY else (abs(e) - abs(p)) / abs(p) * 100.0


def comp(row: dict, qty: str, plane: str, etype: str) -> float:
    if qty == "P":
        return row["P"]
    col_y = etype == "COLUMN" and plane == "Y"
    if qty == "M":
        return row["M2"] if col_y else row["M3"]
    return row["V3"] if col_y else row["V2"]


def compare(d: dict, exp: dict) -> dict:
    check_units(d)
    ad = EtabsAdapter(exp)
    objs = ad.model_objects()
    frames3d = [o for o in objs if o.kind == "frame"]
    rc, rcombo = d["results_cases"], d["results_combos"]
    fr = frame_rows(rc, d["labels"])
    frc = frame_rows(rcombo, d["labels"])
    etabs_keys = set(zip(d["labels"]["MyLabel"], d["labels"]["MyStory"]))
    adapter_keys = {(o.label, o.story) for o in frames3d}
    mapping = {"etabs_frames": len(etabs_keys), "adapter_frames": len(adapter_keys),
               "unmapped_in_etabs": sorted(f"{l}@{s}" for l, s in etabs_keys - adapter_keys),
               "missing_in_etabs": sorted(f"{l}@{s}" for l, s in adapter_keys - etabs_keys)}

    pf, des = capture_design_frames(exp)
    by_el = {e["id"]: e for e in exp["elements"]}
    sizes_ok = {yl: {"beam": a["beam"], "col": a["col"], "brace": a.get("brace_size")} for yl, a in pf.items()}
    rows, case_rows = [], []
    reviewed = (exp.get("building", {}).get("lateral") or {}).get("basis", "original") != "original"
    scbf_combos = SCBF_COMBOS_REVIEWED if reviewed else SCBF_COMBOS_ORIGINAL
    for yl, args in pf.items():
        is_smf = yl in des["smf"]
        if is_smf:
            yv = by_el[f"COL-{args['cols'][0][0]}"]["y"]
            plane = ("X", yv)
        else:
            xv = by_el[f"COL-{args['cols'][0][0]}"]["x"]
            plane = ("Y", xv)
        m = solve(args, with_w=is_smf)
        combos = SMF_COMBOS if is_smf else scbf_combos
        eq = ("EQX+ecc", "EQX-ecc") if is_smf else ("EQY+ecc", "EQY-ecc")
        line_name = f"SMF line {yl}" if is_smf else f"SCBF line {yl}"
        for (lab, story), parts in match_members(m, plane, frames3d).items():
            o = parts[0][3]
            etype = o.props["etabs_type"]
            cases = fr.get((lab, story), {})
            if "Dead" not in cases:
                continue
            n = len(cases["Dead"])
            mid = min(range(n), key=lambda k: abs(cases["Dead"][k]["ObjSta"] - math.dist(o.props["xyz_i"], o.props["xyz_j"]) / 2))
            # columns: both ends; braces: mid (axial); beams: both ends + mid (for a line-3 girder
            # "mid" is the chevron work point, an interior support: shear jumps there, so only M / P
            # are compared at it)
            stations = {"mid": mid} if etype == "BRACE" else {"i": 0, "j": n - 1}
            if etype == "BEAM":
                stations["mid"] = mid
            for where, k in stations.items():
                sta = cases["Dead"][k]["ObjSta"]
                part = next((p for p in parts if p[1] - TOL <= sta <= p[1] + m.members[p[0]].L() + TOL), None)
                if part is None:
                    continue
                mem = m.members[part[0]]
                x = sta - part[1] if part[2] > 0 else part[1] + mem.L() - sta
                pn = {c: pn_at(mem, x, c) for c in ("D", "L", "E") + (("W",) if is_smf else ())}

                def et(case, qty):
                    return comp(cases[case][k], qty, plane[0], etype)
                et_case = {"D": {q: et("Dead", q) + et("SDL", q) for q in "MVP"},
                           "L": {q: et("Live", q) + et("Lr", q) for q in "MVP"},
                           "Lr": {q: et("Lr", q) for q in "MVP"},
                           "E+": {q: et(eq[0], q) for q in "MVP"}, "E-": {q: et(eq[1], q) for q in "MVP"}}
                if is_smf:
                    et_case["W"] = {q: et("WX", q) for q in "MVP"}
                if etype == "BRACE":
                    qtys = ["P"]
                elif etype == "BEAM" and o.props["release"] and where == "mid":
                    qtys = ["M", "P"]
                elif etype == "BEAM" and o.props["release"]:
                    qtys = ["V"]          # pinned ends: M = 0
                else:
                    qtys = ["M", "V", "P"]
                # per-case table (E = the larger of +ecc / -ecc)
                for q in qtys:
                    for c in ("D", "L", "E") + (("W",) if is_smf else ()):
                        e = et_case[c][q] if c != "E" else max((et_case["E+"][q], et_case["E-"][q]), key=abs)
                        case_rows.append({"line": line_name, "element": o.element_id, "label": lab, "story": story,
                                          "type": etype, "where": where, "sta": sta, "qty": q, "case": c,
                                          "etabs": e, "pynite": pn[c][q], "pct": pct(e, pn[c][q]),
                                          "etabs_Lr": et_case["Lr"][q] if c == "L" else None})
                # governing design-frame combo (PyNite), compared with ETABS under the same factors
                for q in qtys:
                    best = None
                    for cn, fac in combos.items():
                        p_val = sum(f * pn[c][q] for c, f in fac.items())
                        e_opts = []
                        for ek in ("E+", "E-"):
                            e_opts.append(sum(f * (et_case[ek][q] if c == "E" else et_case[c][q]) for c, f in fac.items()))
                        e_val = max(e_opts, key=abs) if "E" in fac else e_opts[0]
                        if best is None or abs(p_val) > abs(best[1]):
                            best = (cn, p_val, e_val)
                    cn, p_val, e_val = best
                    note, flaggable = "", True
                    if q == "P" and etype == "COLUMN":
                        flaggable = False
                        note = "2D frame axial only"
                        if is_smf and cn in ("S1", "S3"):
                            # signed, compression positive: PyNite axial is compression-positive,
                            # ETABS compression-negative; gp is the design's seismic-factored
                            # gravity from transverse framing (compression)
                            storey = int(story[-1])
                            gp = des["smf"][yl]["gp"].get(o.element_id[4:], {}).get(storey, 0.0)
                            p_val = p_val + gp
                            e_val = -e_val
                            note, flaggable = f"PyNite + design gp {gp:.1f} (compression +)", True
                    if etype == "COLUMN" and not is_smf and q in ("M", "V"):
                        flaggable, note = False, "SCBF frame: W14X90 columns, Iy = Ix"
                    if q == "P" and etype == "BEAM":
                        # a rigid diaphragm constrains in-plane axial deformation, so ETABS reports
                        # 0 axial in every beam it touches; the 2D frames carry drag axial instead
                        flaggable, note = False, "ETABS rigid diaphragm: beam axial 0"
                    # ETABS's own governing design combo (from the 15 combos it ran) for reference
                    gov_e, gov_v = None, 0.0
                    for ck, crows in frc.get((lab, story), {}).items():
                        if ck.split("|")[0] in ("EQX", "EQY") or k >= len(crows):
                            continue
                        v = comp(crows[k], q, plane[0], etype)
                        if abs(v) > abs(gov_v):
                            gov_e, gov_v = ck, v
                    pc = pct(e_val, p_val)
                    rows.append({"line": line_name, "element": o.element_id, "label": lab, "story": story, "type": etype,
                                 "where": where, "sta": sta, "qty": q, "combo": cn, "etabs": e_val, "pynite": p_val,
                                 "pct": pc, "flag": bool(flaggable and pc is not None and abs(pc) > FLAG_PCT), "note": note,
                                 "etabs_gov_combo": gov_e, "etabs_gov_value": gov_v})
    return {"mapping": mapping, "rows": rows, "case_rows": case_rows, "sizes": sizes_ok,
            "globals": global_checks(d, exp, des, objs)}


# ------------------------------------------------------------------ globals
def global_checks(d: dict, exp: dict, des: dict, objs) -> dict:
    rc = d["results_cases"]
    recs = {r["id"]: r for r in exp["records"]}
    cols = [r for r in exp["records"] if r["kind"] == "column_design"]
    base = {r["LoadCase"]: r for r in rc["base_reactions"] if r["StepType"] in ("Single Value", "")}
    totals = {"Dead+SDL": (base["Dead"]["FZ"] + base["SDL"]["FZ"], sum(r["values"].get("P_base_D") or 0 for r in cols)),
              "Live": (base["Live"]["FZ"], sum(r["values"].get("P_base_L") or 0 for r in cols)),
              "Lr": (base["Lr"]["FZ"], sum(r["values"].get("P_base_Lr") or 0 for r in cols))}
    shear = {c: (abs(base[c]["FX"] if c.startswith(("EQX", "WX")) else base[c]["FY"]), recs[rid]["values"]["V_k"])
             for c, rid in (("EQX+ecc", "C-ELF:X"), ("EQX-ecc", "C-ELF:X"), ("EQY+ecc", "C-ELF:Y"),
                            ("EQY-ecc", "C-ELF:Y"), ("WX", "C-WIND:X"), ("WY", "C-WIND:Y"))}
    modal = [{k: r.get(k) for k in ("Mode", "Period", "UX", "UY", "RZ", "SumUX", "SumUY", "SumRZ")} for r in rc["modal_mass"]]
    ta = {k: LAT.SYS[k]["Ct"] * LEVELS[-1][2] ** LAT.SYS[k]["xexp"] for k in ("x", "y")}
    # line base shear: ETABS reactions at the base points on the line vs the design's line share
    pts = {o.label: o for o in objs if o.kind == "point" and o.story == "Base"}
    lines = {}
    topo = des["topo"]
    line_defs = [(f"SMF line {yl}", ("EQX+ecc", "EQX-ecc"), "y",
                  next(topo.columns[c]["y"] for c in sorted(topo.columns) if c[-1] == yl and c[:-1] in topo.scheme.MF[yl]), yl)
                 for yl in des["smf"]]
    line_defs += [(f"SCBF line {xl}", ("EQY+ecc", "EQY-ecc"), "x",
                   next(topo.columns[c]["x"] for c in sorted(topo.columns) if c[:-1] == xl), xl)
                  for xl, s in des["scbf"].items() if s.get("forces")]
    for name, case_pair, coord, val, ln in line_defs:
        labels = {lab for lab, o in pts.items() if abs(o.props[f"{coord}_ft"] - val) < TOL}
        pl = d["point_labels"]
        names = {n for n, l, s in zip(pl["MyName"], pl["MyLabel"], pl["MyStory"]) if l in labels and s == "Base"}
        f = "F1" if coord == "y" else "F2"
        vals = {}
        for c in case_pair:
            vals[c] = abs(sum(r[f] for r in rc["joint_reactions"] if r["LoadCase"] == c and r["Obj"] in names))
        if coord == "y":
            design_v = sum(des["smf"][ln]["fe"].values())
            wind_v = sum(des["smf"][ln]["fw"].values())
            w_et = abs(sum(r[f] for r in rc["joint_reactions"] if r["LoadCase"] == "WX" and r["Obj"] in names))
        else:
            sc = des["scbf"][ln]
            design_v = sum(sc["fy"].values()) if sc.get("fy") else sum(LAT.elf(des["seismic"]["weights"], "y")["Fx"].values())
            wind_v, w_et = None, None
        lines[name] = {"etabs": vals, "design": design_v, "share_of_V": design_v / recs["C-ELF:X" if coord == "y" else "C-ELF:Y"]["values"]["V_k"],
                       "wind_etabs": w_et, "wind_design": wind_v}
    # drifts on the lateral lines: ETABS joint displacements at the line's column points x Cd / Ie
    lm = EtabsAdapter(exp).label_map()["points"]
    pl = d["point_labels"]
    lab_story_name = {(l, s): n for n, l, s in zip(pl["MyName"], pl["MyLabel"], pl["MyStory"])}
    disp = {}
    for r in rc["joint_displacements"]:
        disp[(r["Obj"], r["LoadCase"])] = r
    drifts = []
    stories = ["Base"] + [f"Story{i + 1}" for i in range(len(LEVELS))]
    sch = topo.scheme
    drift_defs = [(f"C-SMF:{yl}", yl, "x", ("EQX+ecc", "EQX-ecc"), [f"{n}{yl}" for n in sch.MF[yl]]) for yl in des["smf"]]
    drift_defs += [(f"C-SCBF:{xl}", xl, "y", ("EQY+ecc", "EQY-ecc"), sorted(c for c in topo.columns if c[:-1] == xl))
                   for xl, s in des["scbf"].items() if s.get("forces")]
    for rid, line, d_, cases, cols_on in drift_defs:
        cd = LAT.SYS[d_]["Cd"]
        comp_ = "U1" if d_ == "x" else "U2"
        for row in recs[rid]["values"]["drifts"]:
            si = [lv for lv, _, _ in LEVELS].index(row["level"]) + 1
            best = 0.0
            for c in cases:
                for col in cols_on:
                    lab = lm.get(f"col:{col}")
                    top = disp.get((lab_story_name.get((lab, stories[si])), c))
                    bot = disp.get((lab_story_name.get((lab, stories[si - 1])), c)) if si > 1 else None
                    if top is None:
                        continue
                    dd = abs(top[comp_] - (bot[comp_] if bot else 0.0))
                    best = max(best, dd)
            et_in = cd * best / LAT.IE * 12
            drifts.append({"line": line, "level": row["level"], "h_ft": row["h"], "etabs_delta_in": et_in,
                           "design_delta_in": row["delta_in"],
                           "pct": (et_in - row["delta_in"]) / row["delta_in"] * 100 if row["delta_in"] >= 0.05 else None,
                           "allow_in": row["allow_in"], "etabs_ratio": et_in / row["allow_in"]})
    return {"totals": totals, "shear": shear, "modal": modal, "Ta": ta, "lines": lines, "drifts": drifts,
            "story_drifts": [r for r in rc["story_drifts"] if r["LoadCase"].startswith("EQ")]}


# ------------------------------------------------------------------ report
def f(v, nd=1):
    return "-" if v is None else f"{v:.{nd}f}"


def report(c: dict) -> str:
    g = c["globals"]
    m = c["mapping"]
    o = ["### Label mapping", "",
         f"ETABS frames {m['etabs_frames']}, adapter frames {m['adapter_frames']}, unmapped {len(m['unmapped_in_etabs'])}, "
         f"missing {len(m['missing_in_etabs'])}. 2D frames the design kept (captured from design.run): "
         + "; ".join(f"line {k}: {v}" for k, v in c["sizes"].items()), "",
         "### Load totals (base reactions) vs design", "", "| case | ETABS kip | design kip | % |", "|---|---|---|---|"]
    for k, (e, dsg) in g["totals"].items():
        o.append(f"| {k} | {e:.1f} | {dsg:.1f} | {pct(e, dsg):+.2f} |")
    o += ["", "### Base shear vs design", "", "| case | ETABS kip | design kip | % |", "|---|---|---|---|"]
    for k, (e, dsg) in g["shear"].items():
        o.append(f"| {k} | {e:.1f} | {dsg:.1f} | {pct(e, dsg):+.2f} |")
    o += ["", f"### Modes (code Ta: X {g['Ta']['x']:.3f} s, Y {g['Ta']['y']:.3f} s)", "",
          "| mode | T s | UX | UY | RZ | sum UX | sum UY | sum RZ |", "|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(g["modal"][:6], 1):
        o.append(f"| {i} | {r['Period']:.3f} | {r['UX']:.3f} | {r['UY']:.3f} | {r['RZ']:.3f} | {r['SumUX']:.3f} | {r['SumUY']:.3f} | {r['SumRZ']:.3f} |")
    o += ["", "### Lateral force reaching each line (base shear at the line's base points)", "",
          "| line | ETABS +ecc | ETABS -ecc | design 2D frame (worse ecc, rigid-diaphragm hand split) | design share of V | ETABS WX | design wind |",
          "|---|---|---|---|---|---|---|"]
    for k, v in g["lines"].items():
        e = list(v["etabs"].values())
        o.append(f"| {k} | {e[0]:.1f} | {e[1]:.1f} | {v['design']:.1f} | {v['share_of_V'] * 100:.1f}% | {f(v['wind_etabs'])} | {f(v['wind_design'])} |")
    o += ["", "### Story drift on the lateral lines (Cd x elastic / Ie, worse ecc, max over the line's columns)", "",
          "| line | level | ETABS in | design in | % | allow in | ETABS ratio |", "|---|---|---|---|---|---|---|"]
    for r in g["drifts"]:
        o.append(f"| {r['line']} | {r['level']} | {r['etabs_delta_in']:.3f} | {r['design_delta_in']:.3f} | {f(r['pct'])} | {r['allow_in']:.2f} | {r['etabs_ratio']:.3f} |")
    rows = c["rows"]
    nf = [r for r in rows if r["flag"]]
    o += ["", f"### Per member, governing design-frame combo: {len(rows)} comparisons, {len(nf)} flagged (> {FLAG_PCT:g}%)", "",
          "kip, kip-ft. Combo = the design's 2D-frame combo that governs PyNite at that station (SMF S1 = 1.4D+0.5L+E, "
          "S2 = 0.7D+E, S3 = 1.4D+0.5L-E, W1 = 1.2D+0.5L+W, G2 = 1.2D+1.6L; SCBF S1 = 1.4D+0.5L+1.3E); ETABS is the same "
          "factors on its case results, E = worse of +/-ecc. `ETABS gov` = ETABS's own governing combo of its 15 at that "
          f"station. % = (|ETABS| - |PyNite|) / |PyNite|, `-` when |PyNite| < {TINY:g}.", "",
          "| line | element | ETABS label@story | at | sta ft | qty | combo | ETABS | PyNite | % | flag | ETABS gov | note |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        o.append(f"| {r['line']} | {r['element']} | {r['label']}@{r['story']} | {r['where']} | {r['sta']:.2f} | {r['qty']} | {r['combo']} | "
                 f"{r['etabs']:.1f} | {r['pynite']:.1f} | {f(r['pct'])} | {'FLAG' if r['flag'] else ''} | "
                 f"{r['etabs_gov_combo'] or ''} {f(r['etabs_gov_value'])} | {r['note']} |")
    o += ["", "### Per member, per load case (D = Dead+SDL, L = Live+Lr, E = worse ecc, W = WX)", "",
          "| line | element | label@story | at | qty | case | ETABS | PyNite | % | ETABS Lr part |", "|---|---|---|---|---|---|---|---|---|---|"]
    for r in c["case_rows"]:
        o.append(f"| {r['line']} | {r['element']} | {r['label']}@{r['story']} | {r['where']} | {r['qty']} | {r['case']} | "
                 f"{r['etabs']:.2f} | {r['pynite']:.2f} | {f(r['pct'])} | {f(r['etabs_Lr'], 2)} |")
    return "\n".join(o) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--etabs", help="dir with the saved bridge JSON (see module docstring)")
    ap.add_argument("--bridge", help="bridge URL to fetch live (e.g. http://127.0.0.1:8765)")
    ap.add_argument("--save", help="with --bridge: write the fetched JSON here")
    ap.add_argument("--out", help="markdown report (default stdout)")
    ap.add_argument("--json", help="comparison rows as JSON")
    ap.add_argument("--design", help="design export the e2k was written from (default data/synthetic_v2/design.json); "
                                     "e.g. data/synthetic_v2/scenarios/ORIG.json")
    a = ap.parse_args()
    names = ("results_cases", "results_combos", "labels", "point_labels")
    if a.bridge:
        d = fetch(a.bridge)
        if a.save:
            os.makedirs(a.save, exist_ok=True)
            for n in names:
                with open(os.path.join(a.save, n + ".json"), "w") as fh:
                    json.dump(d[n], fh)
    elif a.etabs:
        d = {}
        for n in names:
            with open(os.path.join(a.etabs, n + ".json")) as fh:
                d[n] = json.load(fh)
    else:
        ap.error("give --etabs DIR or --bridge URL")
    c = compare(d, load_design(a.design) if a.design else load_design())
    md = report(c)
    if a.json:
        with open(a.json, "w") as fh:
            json.dump(c, fh, indent=1, default=str)
    if a.out:
        with open(a.out, "w") as fh:
            fh.write(md)
    else:
        sys.stdout.write(md)


if __name__ == "__main__":
    main()
