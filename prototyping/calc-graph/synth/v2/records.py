"""Design -> machine-readable model (elements, types, relations) + calc RECORDS.

Records follow backend/calcgraph/calc_records.py: the record is the engineer's unit (one
member row, one column stack, one footing, one typical-detail capacity, one ELF), grouped
package -> section (A..E) -> calc (sheet group, e.g. B2) -> table -> record -> values.
`page` / `bbox` are filled in by the calc-package PDF writer (where the row prints).

Ids are stable across layouts for the same element, so a moved design diffs record by record.
"""
from __future__ import annotations

import math

from . import aisc
from .gravity import COMBO_TXT, SHEAR_TABS, BASE_PLATES, PIERS, FTG_TOP, PIER_TOP, fac, COMBOS
from .model import GX, GY, LEVELS, STOREY_H, MF_LINES

LV_Z = {"L1": 0.0, **{l: z for l, _, z in LEVELS}}
LV_NAME = {"L1": "Level 1", **{l: n for l, n, _ in LEVELS}}

CALCS = [
    # calc id, section, title, software, table title
    ("A1", "A", "Design criteria", "Hand / Word", "Design criteria"),
    ("A2", "A", "Gravity loads by area", "Excel", "Area loads"),
    ("B1", "B", "Floor framing - Level 2", "RAM Structural System", "Gravity Beam Design - Level 2"),
    ("B2", "B", "Floor framing - Level 3", "RAM Structural System", "Gravity Beam Design - Level 3"),
    ("B3", "B", "Roof framing", "RAM Structural System", "Gravity Beam Design - Roof"),
    ("B4", "B", "Mechanical area framing (Enercalc)", "Enercalc", "Steel Beam"),
    ("B5", "B", "Gravity column design", "RAM Structural System", "Gravity Column Design"),
    ("C1", "C", "Seismic base shear - ELF", "Mathcad", "ELF procedure"),
    ("C2", "C", "Wind - MWFRS", "Mathcad", "MWFRS"),
    ("C3", "C", "Special moment frame - line A", "RISA-3D", "SMF line A"),
    ("C4", "C", "Special moment frame - line D", "RISA-3D", "SMF line D"),
    ("C5", "C", "Special concentrically braced frame - line 3", "RISA-3D", "SCBF line 3"),
    ("C6", "C", "Collectors and drag struts", "Mathcad", "Collector design"),
    ("D1", "D", "Spread footings", "Excel", "Spread footing schedule"),
    ("D2", "D", "Piers", "Excel", "Pier schedule"),
    ("D3", "D", "Grade beams", "Hand calc", "Grade beam design"),
    ("E1", "E", "Typical shear tab capacities", "Mathcad", "Single-plate shear connection"),
    ("E2", "E", "Connection schedule", "Excel", "Beam end connection schedule"),
    ("E3", "E", "SMF moment connection MC-1 (RBS)", "Mathcad", "RBS prequalification"),
    ("E4", "E", "Drag and brace connections", "Mathcad", "Drag / gusset typicals"),
    ("E5", "E", "Base plates", "Mathcad", "Base plate typicals"),
]
CALC = {c[0]: {"id": c[0], "section": c[1], "title": c[2], "software": c[3], "table": c[4]} for c in CALCS}
SECTIONS = {"A": "Loading criteria", "B": "Gravity framing", "C": "Lateral system", "D": "Foundations", "E": "Connections"}
MECH_BAY = ("3", "4", "AB")    # roof members in bay 3-4 / A-B are designed in Enercalc (B4)


def r1(x, n=2):
    return None if x is None else round(float(x), n)


def _beam_calc(mid: str, m) -> str:
    if m.level == "RF" and ((m.kind == "infill" and mid.split("-")[2] == "34" and mid.endswith(("AB1", "AB2")))
                            or (m.kind == "girder" and m.line in ("3", "4") and mid.endswith("-AB"))):
        return "B4"
    return {"L2": "B1", "L3": "B2", "RF": "B3"}[m.level]


def export(d: dict) -> dict:
    topo, fr = d["topo"], d["framing"]
    els, rels, recs = [], [], []
    types: dict[str, dict] = {}

    def typ(tid, **kw):
        types.setdefault(tid, {"id": tid, **kw})
        return tid

    def rel(src, dst, kind, **kw):
        rels.append({"src": src, "dst": dst, "kind": kind, **kw})

    def rec(rid, calc, elements, kind, values, demand, capacity, uc, check, lc="", unit="", feeds=()):
        c = CALC[calc]
        recs.append({"id": rid, "calc": calc, "section": c["section"], "calc_title": c["title"], "software": c["software"],
                     "table": c["table"], "elements": list(elements), "kind": kind, "values": values,
                     "demand": r1(demand, 3), "capacity": r1(capacity, 3), "unit": unit, "uc": r1(uc, 3),
                     "check": check, "lc": lc, "inputs": list(feeds), "page": None, "bbox": None})
        for e in elements:
            rel(e, rid, "designed-by")

    # ---------------- criteria / loads
    rec("A1-CRIT", "A1", [], "criteria",
        {"codes": "IBC 2021, ASCE 7-16, AISC 360-16, AISC 341-16, AISC 358-16, ACI 318-19",
         "steel": "W: ASTM A992 Fy 50 ksi; HSS: ASTM A500 Gr C Fy 50 ksi; plates A36",
         "bolts": "ASTM F3125 Gr A325-N 3/4 in typ.", "concrete": "f'c 4,000 psi NW footings; 3,000 psi LW on deck",
         "soil": "qa = 4,000 psf net allowable", "seismic": "SDS 1.00, SD1 0.60, Site D, RC II, SDC D",
         "wind": "V = 110 mph, exposure C"}, None, None, None, "criteria")
    for ar in topo.layout.areas:
        from .model import area_record_id
        rid = area_record_id(ar)
        rec(rid, "A2", [], "area_load", {"name": ar.name, "kind": ar.kind, "level": ar.level, "D_psf": ar.d_psf,
                                         "L_psf": ar.l_psf, "Lr_psf": ar.lr_psf,
                                         "extent_ft": [ar.x0, ar.y0, ar.x1, ar.y1]},
            ar.d_psf + ar.l_psf + ar.lr_psf, None, None, "load", unit="psf")

    def area_recs(m):
        from .model import area_at
        out = []
        for _, x, y in m.trib:
            a = area_at(topo.layout.areas, m.level, x, y)
            if a:
                rid = f"A2-{a.name.replace(' ', '_').replace('(', '').replace(')', '')}"
                if rid not in out:
                    out.append(rid)
        return out

    # ---------------- levels / grids / frames (registry groupings)
    for lv in ["L1"] + [l for l, _, _ in LEVELS]:
        els.append({"id": f"LEVEL:{lv}", "type": "level", "name": LV_NAME[lv], "elev_ft": LV_Z[lv]})
    for gl, pos in GX:
        els.append({"id": f"GRID:{gl}", "type": "grid", "name": gl, "axis": "x", "pos_ft": pos})
    for gl, pos in GY:
        els.append({"id": f"GRID:{gl}", "type": "grid", "name": gl, "axis": "y", "pos_ft": pos})
    for yl in MF_LINES:
        els.append({"id": f"FRAME:SMF-{yl}", "type": "frame", "name": f"Special moment frame line {yl}", "system": "SMF"})
    els.append({"id": "FRAME:SCBF-3", "type": "frame", "name": "Special concentrically braced frame line 3", "system": "SCBF"})
    for mat, txt in (("MAT:A992", "ASTM A992 Gr 50 wide flange"), ("MAT:A500C", "ASTM A500 Gr C HSS"),
                     ("MAT:A36", "ASTM A36 plate"), ("MAT:F3125-A325", "ASTM F3125 Gr A325 bolts"),
                     ("MAT:F1554", "ASTM F1554 anchor rods"), ("MAT:CONC-4000", "Concrete f'c 4,000 psi"),
                     ("MAT:CONC-LW3000", "Lightweight concrete f'c 3,000 psi on deck"), ("MAT:DECK-3VLI20", "3\" 20 ga composite deck"),
                     ("MAT:REBAR-A615", "ASTM A615 Gr 60 reinforcing"), ("MAT:STUD", "3/4\" headed shear studs (ASTM A108)"),
                     ("MAT:E70XX", "E70XX weld metal"), ("MAT:SFRM", "Spray-applied fireproofing")):
        typ(mat, kind="material", name=txt)

    # ---------------- members
    for k, m in topo.members.items():
        r = fr[k]
        z = LV_Z[m.level]
        size = r["size"]
        roles = m.roles
        etype = "girder" if m.kind == "girder" else "beam"
        tid = typ(f"TYPE:{size}", kind="section", name=size, material="MAT:A992")
        els.append({"id": k, "type": etype, "kind": m.kind, "size": size, "level": m.level, "line": m.line,
                    "p1": [r1(m.p1[0], 3), r1(m.p1[1], 3), z], "p2": [r1(m.p2[0], 3), r1(m.p2[1], 3), z],
                    "span_ft": r1(m.span, 3), "roles": roles, "frame": m.frame, "camber_in": r["camber"],
                    "studs": r["studs"], "sfrs": any(x in roles for x in ("smf_beam", "scbf_beam", "collector"))})
        rel(k, tid, "instance-of")
        rel(k, f"LEVEL:{m.level}", "member-of")
        if m.line:
            rel(k, f"GRID:{m.line}", "member-of")
        if m.frame:
            rel(k, f"FRAME:{m.frame}", "member-of")
        rel(f"DK-{m.level}", k, "bears-on")
        for end, s in (("i", m.i), ("j", m.j)):
            sup = f"COL-{s['col']}" if "col" in s else s["member"]
            cx = f"CX-{k}-{end}"
            rel(k, cx, "connected-by")
            rel(cx, sup, "connected-by")
            rel(k, sup, "frames-into", via=cx, end=end)
        if "smf_beam" in roles:
            continue   # designed in the SMF frame calc (C3/C4)
        calc = _beam_calc(k, m)
        inputs = area_recs(m) + [f"B-BM:{src}" for src in
                                 [x for x, mm in topo.members.items() for s in (mm.i, mm.j) if s.get("member") == k]]
        vals = {"size": size, "span_ft": r1(m.span), "w_D_klf": r1(r["w"][0], 3), "w_L_klf": r1(r["w"][1], 3),
                "w_Lr_klf": r1(r["w"][2], 3), "self_wt_klf": r1(r["sw"], 3), "Lb_ft": r1(r["lb"]), "Mu_kft": r1(r["mu"], 1),
                "phiMn_kft": r1(r["phi_mn"], 1), "Vu_k": r1(r["vu"], 1), "phiVn_k": r1(r["phi_vn"], 1),
                "defl_L_in": r1(r["d_live"]), "defl_L_allow_in": r1(r["lim_live"]), "defl_T_in": r1(r["d_total"]),
                "defl_T_allow_in": r1(r["lim_total"]), "camber_in": r["camber"], "studs": r["studs"],
                "R_i_k": r1(max(fac(r["Ri"], c) for c in COMBOS), 1), "R_j_k": r1(max(fac(r["Rj"], c) for c in COMBOS), 1),
                "R_i_D": r1(r["Ri"][0]), "R_i_L": r1(r["Ri"][1] + r["Ri"][2]), "R_j_D": r1(r["Rj"][0]), "R_j_L": r1(r["Rj"][1] + r["Rj"][2]),
                "point_loads": len(r["pts"]), "flex_eq": r["flex_eq"], "governs": r["governs"]}
        rec(f"B-BM:{k}", calc, [k], "beam_design", vals, r["mu"], r["phi_mn"], r["uc"], r["governs"],
            COMBO_TXT.get(r["lc"], r["lc"]), "kip-ft", inputs)

    # ---------------- columns, bases, foundations
    for c, info in topo.columns.items():
        r = d["columns"][c]
        cid = f"COL-{c}"
        tid = typ(f"TYPE:{r['size']}", kind="section", name=r["size"], material="MAT:A992")
        frames = info["frames"]
        els.append({"id": cid, "type": "column", "size": r["size"], "grid": info["grid"], "x": r1(info["x"], 3),
                    "y": r1(info["y"], 3), "z0": round(PIER_TOP + d["base_plates"][c]["t"] / 12, 4), "z1": LV_Z["RF"], "roles": info["roles"], "frames": frames,
                    "sfrs": info["roles"] != ["gravity"]})
        rel(cid, tid, "instance-of")
        rel(cid, f"GRID:{c[:-1]}", "member-of")
        rel(cid, f"GRID:{c[-1]}", "member-of")
        for f_ in frames:
            rel(cid, f"FRAME:{f_}", "member-of")
        inputs = sorted({f"B-BM:{k}" if "smf_beam" not in topo.members[k].roles else f"C-MFB:{k}"
                         for lv, lst in _rx(topo, c).items() for k in lst})
        if "smf_column" in info["roles"]:
            calc, rid = ("C3" if c[-1] == "A" else "C4"), f"C-MFC:{c}"
            inputs += [f"C-SMF:{c[-1]}"]
        elif "scbf_column" in info["roles"]:
            calc, rid = "C5", f"C-BFC:{c}"
            inputs += ["C-SCBF:3"]
        else:
            calc, rid = "B5", f"B-COL:{c}"
        rec(rid, calc, [cid], "column_design",
            {"size": r["size"], "storey": r["storey"], "KL_ft": STOREY_H[[l for l, _, _ in LEVELS][r["storey"] - 1]],
             "Pu_k": r1(r["pu"], 1), "phiPn_k": r1(r["phi_pn"], 1), "Mux_kft": r1(r["mux"], 1), "Muy_kft": r1(r["muy"], 1),
             "phiMnx_kft": r1(r["phi_mnx"], 1), "phiMny_kft": r1(r["phi_mny"], 1), "KL_r": r1(r.get("kl_r"), 1),
             "eq": r["eq"], "P_base_D": r1(r["segs"][0]["P"][0], 1), "P_base_L": r1(r["segs"][0]["P"][1], 1),
             "P_base_Lr": r1(r["segs"][0]["P"][2], 1), "source": r["source"]},
            r["pu"], r["phi_pn"], r["uc"], f"axial + flexure ({r['eq']})", r["lc"], "kip", inputs)
        # base plate (connection node), pier, footing
        bp, pr, ft = d["base_plates"][c], d["piers"][c], d["footings"][c]
        bpid, pid, fid = f"BP-{c}", f"P-{c}", f"F-{c}"
        btype = bp["type"].rstrip("*")
        els.append({"id": bpid, "type": "connection", "conn_type": bp["type"], "x": r1(info["x"], 3), "y": r1(info["y"], 3),
                    "z": 0.0, "B_in": bp["B"], "N_in": bp["N"], "t_in": bp["t"], "rods": bp["rods"]})
        typ(f"DETAIL:{btype}", kind="detail", name=f"Base plate {btype}", capacity_k=None, material="MAT:A36")
        rel(bpid, f"DETAIL:{btype}", "instance-of")
        rel(cid, bpid, "connected-by")
        rel(cid, pid, "bears-on", via=bpid)
        rel(bpid, pid, "connected-by")
        rec(f"E-BP:{c}", "E5", [bpid], "base_plate", {"type": bp["type"], "plate": f"PL{bp['t']}x{bp['B']:.0f}x{bp['N']:.0f}",
                                                    "rods": bp["rods"], "Pu_k": r1(bp["pu"], 1), "phiPp_k": r1(bp["phi_pp"], 1)},
            bp["pu"], bp["phi_pp"], bp["uc"], "concrete bearing (J8-2)", "", "kip", [rid, f"E-TYP:{btype}"])
        els.append({"id": pid, "type": "pier", "pier_type": pr["type"], "x": r1(info["x"], 3), "y": r1(info["y"], 3),
                    "z0": FTG_TOP, "z1": PIER_TOP, "b_in": pr["b"], "bars": pr["bars"]})
        typ(f"TYPE:{pr['type']}", kind="pier", name=f"Pier {pr['type']} {pr['b']:.0f}x{pr['b']:.0f}", material="MAT:CONC-4000")
        rel(pid, f"TYPE:{pr['type']}", "instance-of")
        rel(pid, fid, "bears-on")
        rec(f"D-PIER:{c}", "D2", [pid], "pier", {"type": pr["type"], "b_in": pr["b"], "bars": pr["bars"], "Pu_k": r1(pr["pu"], 1),
                                               "phiPn_k": r1(pr["phi_pn"], 1)},
            pr["pu"], pr["phi_pn"], pr["uc"], "axial (ACI 22.4)", "", "kip", [rid])
        els.append({"id": fid, "type": "footing", "B_ft": ft["B"], "h_in": ft["h_in"], "x": r1(info["x"], 3), "y": r1(info["y"], 3),
                    "z_top": FTG_TOP, "bars": ft["bars"], "mark": f"F{ft['B']:.1f}".replace(".0", "").replace(".5", "H")})
        rel(fid, "MAT:CONC-4000", "instance-of")
        rec(f"D-FTG:{c}", "D1", [fid], "footing",
            {"B_ft": ft["B"], "h_in": ft["h_in"], "P_service_k": r1(ft["p_service"], 1), "q_ksf": r1(ft["q"], 3),
             "qa_ksf": ft["qa"], "Pu_k": r1(ft["pu"], 1), "vu_punch_k": r1(ft["vu_p"], 1), "phiVc_punch_k": r1(ft["phivc_p"], 1),
             "vu_oneway_k": r1(ft["vu_1"], 1), "phiVc_oneway_k": r1(ft["phivc_1"], 1), "Mu_kft": r1(ft["mu"], 1),
             "As_in2": r1(ft["as"]), "bars": ft["bars"], "governs": ft["governs"], "P_E_k": r1(ft["pe"], 1)},
            ft["p_service"], ft["qa"] * ft["B"] ** 2, ft["uc"], ft["governs"], "D+L (ASD)", "kip",
            [rid] + ([f"C-SMF:{c[-1]}"] if "smf_column" in info["roles"] else []) + (["C-SCBF:3"] if "scbf_column" in info["roles"] else []))
    for gid, g in d["grade_beams"].items():
        els.append({"id": gid, "type": "grade_beam", "line": g["line"], "p1": [r1(g["p1"][0], 3), r1(g["p1"][1], 3), FTG_TOP],
                    "p2": [r1(g["p2"][0], 3), r1(g["p2"][1], 3), FTG_TOP], "b_in": g["b_in"], "h_in": g["h_in"],
                    "tie_bars": g["tie_bars"]})
        rel(gid, "MAT:CONC-4000", "instance-of")
        rel(gid, f"F-{g['a']}", "frames-into", end="i")
        rel(gid, f"F-{g['b']}", "frames-into", end="j")
        rel(gid, f"GRID:{g['line']}", "member-of")
        rec(f"D-GB:{gid}", "D3", [gid], "grade_beam",
            {"b_in": g["b_in"], "h_in": g["h_in"], "span_ft": r1(g["span"]), "Mu_kft": r1(g["mu"], 1), "phiMn_kft": r1(g["phimn"], 1),
             "Vu_k": r1(g["vu"], 1), "phiVn_k": r1(g["phivn"], 1), "M_end_kft": r1(g["m_end"], 1), "tie_k": r1(g["axial_t"], 1),
             "tie_bars": g["tie_bars"]},
            g["mu"], g["phimn"], g["uc"], g["governs"], "1.2D (+E end moment)", "kip-ft",
            ([f"C-SMF:{g['line']}"] if g["m_end"] else []) + (["C-SCBF:3"] if g["axial_t"] else []))

    # ---------------- lateral
    for dname, cid_ in (("x", "C-ELF:X"), ("y", "C-ELF:Y")):
        e = d["seismic"][dname]
        rec(cid_, "C1", [], "seismic", {"system": e["system"], "R": e["R"], "Cd": e["Cd"], "Omega0": e["O0"], "rho": e["rho"],
                                        "Ta_s": r1(e["Ta"], 3), "Cs": r1(e["Cs"], 4), "W_k": r1(e["W"], 1), "V_k": r1(e["V"], 1),
                                        "k": r1(e["k"], 3), "Fx_k": {k: r1(v, 1) for k, v in e["Fx"].items()},
                                        "W_by_level_k": {k: r1(v, 1) for k, v in d["seismic"]["weights"].items()}},
            e["V"], None, None, "base shear (12.8-1)", "", "kip", [r["id"] for r in recs if r["kind"] == "area_load"])
    for dname in ("x", "y"):
        w = d["wind"][dname]
        rec(f"C-WIND:{dname.upper()}", "C2", [], "wind", {"psf": w["psf"], "V_k": r1(w["V"], 1), "Fx_k": {k: r1(v, 1) for k, v in w["Fx"].items()}},
            w["V"], None, None, "MWFRS base shear", "", "kip", ["A1-CRIT"])
    for yl, s in d["smf"].items():
        a = s["analysis"]
        calc = "C3" if yl == "A" else "C4"
        drift = max(x["ratio"] for x in a["drifts"])
        rec(f"C-SMF:{yl}", calc, [f"FRAME:SMF-{yl}"], "frame_analysis",
            {"beam": s["beam"], "column": s["col"], "share": r1(s["share"], 3), "Fe_k": {k: r1(v, 1) for k, v in s["fe"].items()},
             "drifts": [{k: r1(v, 3) if isinstance(v, float) else v for k, v in x.items()} for x in a["drifts"]],
             "k_kip_per_ft": r1(a["k"], 1), "scwb_ratio": r1(s.get("scwb_ratio"), 3),
             "checks": {k: r1(v, 3) for k, v in s["checks"].items()}},
            drift, 1.0, drift, "story drift (12.12-1)", "E (Cd/Ie)", "ratio", ["C-ELF:X", "C-WIND:X"])
        for k, m in topo.members.items():
            if "smf_beam" in m.roles and m.line == yl:
                cols = [c for c, _ in sorted(((c, topo.columns[c]["x"]) for c in topo.columns if c[-1] == yl and c[:-1] in MF_LINES[yl]), key=lambda t: t[1])]
                bi = cols.index(m.i["col"]) if "col" in m.i and m.i["col"] in cols else 0
                fb = a["beams"].get((m.level, bi), {"mu": 0, "vu": 0})
                pm = aisc.phi_mn(s["beam"], 0)["phi_mn"]
                rec(f"C-MFB:{k}", calc, [k], "smf_beam", {"size": s["beam"], "span_ft": r1(m.span), "Mu_kft": r1(fb["mu"], 1),
                                                          "phiMn_kft": r1(pm, 1), "Vu_k": r1(fb["vu"], 1)},
                    fb["mu"], pm, fb["mu"] / pm, "flexure (frame)", "1.4D+E+0.5L", "kip-ft", [f"C-SMF:{yl}"] + area_recs(m))
    sc = d["scbf"]
    if sc.get("forces"):
        drift = max(x["ratio"] for x in sc["drifts"])
        rec("C-SCBF:3", "C5", ["FRAME:SCBF-3"], "frame_analysis",
            {"brace": sc["brace"], "drifts": [{k: r1(v, 3) if isinstance(v, float) else v for k, v in x.items()} for x in sc["drifts"]],
             "expected_T_k": r1(sc["expected_t"], 1)}, drift, 1.0, drift, "story drift (12.12-1)", "E (Cd/Ie)", "ratio",
            ["C-ELF:Y"])
        for bid, b in topo.braces.items():
            lvs = ["L1"] + [l for l, _, _ in LEVELS]
            els.append({"id": bid, "type": "brace", "size": sc["brace"], "p1": [r1(v, 3) for v in b["p1"]],
                        "p2": [r1(v, 3) for v in b["p2"]], "frame": b["frame"], "roles": ["scbf_brace"], "sfrs": True,
                        "level": lvs[b["storey"]]})
            tid = typ(f"TYPE:{sc['brace']}", kind="section", name=sc["brace"], material="MAT:A500C")
            rel(bid, tid, "instance-of")
            rel(bid, f"FRAME:{b['frame']}", "member-of")
            rel(bid, f"COL-{b['base']}", "frames-into", via=f"CX-{bid}-i", end="i")
            rel(bid, b["beam"], "frames-into", via=f"CX-{bid}-j", end="j")
            for end in ("i", "j"):
                rel(bid, f"CX-{bid}-{end}", "connected-by")
            # PyNite brace name: BR_<level>_<bay idx>_<side>
            cand = [v for n, v in sc["forces"].items() if n.startswith(f"BR_{b['level_top']}_")]
            f = max(cand, key=lambda v: v["uc"]) if cand else {"pu": 0, "phi_pn": 1, "uc": 0, "kl_r": 0, "L": 0}
            rec(f"C-BR:{bid}", "C5", [bid], "brace", {"size": sc["brace"], "L_ft": r1(f["L"]), "Pu_k": r1(f["pu"], 1),
                                                     "phiPn_k": r1(f["phi_pn"], 1), "KL_r": r1(f["kl_r"], 1)},
                f["pu"], f["phi_pn"], f["uc"], "compression (E3) / tension (D2) / KL/r", "1.4D+1.3E+0.5L", "kip", ["C-SCBF:3"])
    for k, cl in d["collectors"].items():
        rec(f"C-COLL:{k}", "C6", [k], "collector", {"size": cl["size"], "Pu_k": r1(cl["pu"], 1), "Omega0": cl["o0"],
                                                   "phiPn_k": r1(cl["phi_pn"], 1), "Mu_kft": r1(cl["mu"], 1),
                                                   "phiMn_kft": r1(cl["phi_mn"], 1), "eq": cl["eq"]},
            cl["pu"], cl["phi_pn"], cl["h1"], f"axial + flexure ({cl['eq']})", "Omega0 E", "kip",
            ["C-ELF:X" if topo.members[k].kind == "beam" else "C-ELF:Y", f"B-BM:{k}"])

    # ---------------- connections
    for n, t in SHEAR_TABS.items():
        typ(f"DETAIL:ST-{n}", kind="detail", name=f"Single-plate shear tab ST-{n}", capacity_k=r1(t["phi_rn"], 1),
            bolts=n, plate=t["plate"], material="MAT:A36")
        rec(f"E-TYP:ST-{n}", "E1", [f"DETAIL:ST-{n}"], "typical_detail",
            {"bolts": n, "plate": t["plate"], "e_in": t["e_in"], "phiRn_k": r1(t["phi_rn"], 1), "governs": t["governs"]},
            None, t["phi_rn"], None, t["governs"], unit="kip")
    from .design import DRAG_TYPES, BRACE_GUSSETS
    for t, cap in {**DRAG_TYPES, **BRACE_GUSSETS}.items():
        typ(f"DETAIL:{t}", kind="detail", name=("Drag connection " if t.startswith("DC") else "Brace gusset ") + t,
            capacity_k=cap, material="MAT:A36")
        rec(f"E-TYP:{t}", "E4", [f"DETAIL:{t}"], "typical_detail", {"phiRn_k": cap}, None, cap, None, "typical capacity", unit="kip")
    typ("DETAIL:MC-1", kind="detail", name="SMF moment connection MC-1 (RBS, AISC 358 Ch. 5)", capacity_k=None, material="MAT:A992")
    rec("E-TYP:MC-1", "E3", ["DETAIL:MC-1"], "typical_detail",
        {"type": "RBS, CJP flange welds, bolted web", "limits": "beam <= W36x302, tf <= 1.75 in, clear span/depth >= 7"},
        None, None, None, "prequalification limits")
    for bp, v in BASE_PLATES.items():
        typ(f"DETAIL:{bp}", kind="detail", name=f"Base plate {bp}", capacity_k=None, material="MAT:A36")
        rec(f"E-TYP:{bp}", "E5", [f"DETAIL:{bp}"], "typical_detail", {**v}, None, None, None, "typical base plate")
    for cid, c in d["connections"].items():
        t = c["type"].rstrip("*")
        els.append({"id": cid, "type": "connection", "conn_type": c["type"], "member": c["member"], "end": c["end"],
                    "to": c["to"], "special": c.get("special", False)})
        rel(cid, f"DETAIL:{t}", "instance-of")
        if t == "MC-1":
            calc, rid = "E3", f"E-MC:{cid}"
        else:
            calc, rid = ("E4" if t.startswith(("DC", "BG")) else "E2"), f"E-CX:{cid}"
        src = c["member"]
        m = topo.members.get(src)
        if m is not None:
            srec = (f"C-MFB:{src}" if "smf_beam" in m.roles else f"B-BM:{src}")
            inp = [srec] + ([f"C-COLL:{src}"] if t.startswith("DC") else [])
        else:
            inp = [f"C-BR:{src}"]
        rec(rid, calc, [cid], "connection", {"type": c["type"], "Ru_k": r1(c.get("ru"), 1), "phiRn_k": r1(c.get("phi_rn"), 1),
                                             "member": src, "end": c["end"], "to": c["to"], "check": c["check"]},
            c.get("ru"), c.get("phi_rn"), c["uc"], c["check"], "", "kip", inp + [f"E-TYP:{t}"])
    for lv in ["L2", "L3", "RF"]:
        els.append({"id": f"DK-{lv}", "type": "deck", "level": lv,
                    "name": "3\" 20 ga composite deck + 3-1/4\" LW concrete" if lv != "RF" else "1-1/2\" 20 ga type B roof deck"})
        rel(f"DK-{lv}", "MAT:DECK-3VLI20", "instance-of")
        rel(f"DK-{lv}", f"LEVEL:{lv}", "member-of")
    # record -> record feeds as relations too
    for r in recs:
        for i in r["inputs"]:
            rel(i, r["id"], "feeds")
    known = {r["id"] for r in recs}
    for r in recs:
        r["inputs"] = [i for i in r["inputs"] if i in known]
    rels = [x for x in rels if x["kind"] != "feeds" or (x["src"] in known and x["dst"] in known)]
    return {"elements": els, "types": list(types.values()), "relations": rels, "records": recs,
            "calcs": [CALC[c[0]] for c in CALCS], "sections": SECTIONS,
            "clashes": d["clashes"], "infeasible": d["infeasible"]}


def _rx(topo, c: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for k, m in topo.members.items():
        for s in (m.i, m.j):
            if s.get("col") == c:
                out.setdefault(m.level, []).append(k)
    return out
