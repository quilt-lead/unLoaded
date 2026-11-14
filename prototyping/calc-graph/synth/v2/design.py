"""Full design of a layout: gravity framing -> columns -> lateral (ELF, wind, SMF, SCBF,
collectors) -> columns again -> connections -> foundations -> clashes.

`run(layout)` is deterministic and is what the move scenarios re-run end to end.
"""
from __future__ import annotations

import math

from . import aisc, gravity as G, lateral as LAT
from .model import (BF_LINE, GX, GY, LEVELS, MF_LINES, STOREY_H, Layout, Topology, build)

LV = [l for l, _, _ in LEVELS]
DRAG_TYPES = {"DC-1": 60.0, "DC-2": 120.0, "DC-3": 200.0}
BRACE_GUSSETS = {"BG-1": 250.0, "BG-2": 450.0, "BG-3": 700.0}


def _assign(types: dict, demand: float) -> dict:
    for t, cap in types.items():
        if cap >= demand:
            return {"type": t, "phi_rn": cap, "ru": demand, "uc": demand / cap, "special": False}
    t = list(types)[-1]
    return {"type": t + "*", "phi_rn": types[t], "ru": demand, "uc": demand / types[t], "special": True}


def _seis_fac(v) -> float:
    return (1.2 + 0.2 * LAT.SDS) * v[0] + 0.5 * v[1] + 0.5 * v[2]


def _centre_of_mass(layout: Layout) -> tuple[float, float]:
    sw = sx = sy = 0.0
    for ar in layout.areas:
        a = (ar.x1 - ar.x0) * (ar.y1 - ar.y0)
        if ar.kind == "roof":
            a -= sum((o.x1 - o.x0) * (o.y1 - o.y0) for o in layout.areas if o.level == ar.level and o.kind == "mech")
            w = a * ar.d_psf
            cx, cy = (ar.x0 + ar.x1) / 2, (ar.y0 + ar.y1) / 2
        else:
            w = a * (ar.d_psf + ar.seis_extra_psf)
            cx, cy = (ar.x0 + ar.x1) / 2, (ar.y0 + ar.y1) / 2
        sw += w
        sx += w * cx
        sy += w * cy
    return sx / sw, sy / sw


def run(layout: Layout, keep: dict | None = None) -> dict:
    """keep = {element id: element dict} of a CURRENT design: minimum-change re-design (keep
    each surviving element's size / detail if it still passes, else the next heavier one) -
    how an engineer re-designs after a move. None = fresh lightest-passing design."""
    keep = keep or {}
    topo = build(layout)
    ksize = {k: v["size"] for k, v in keep.items() if v.get("type") in ("beam", "girder") and k in topo.members}
    framing = G.design_framing(topo, keep=ksize)
    infeasible = [k for k, r in framing.items() if r.get("infeasible")]

    # ---------- lateral
    col_sizes0 = {c: "W14X90" for c in topo.columns}
    weights = LAT.seismic_weights(topo, framing, col_sizes0)
    ex, ey = LAT.elf(weights, "x"), LAT.elf(weights, "y")
    wx, wy = LAT.wind("x"), LAT.wind("y")
    cmx, cmy = _centre_of_mass(layout)
    rx_all = G.reactions_to_columns(topo, framing)

    def grav_p_seis(c: str, exclude_roles=("smf_beam",)) -> dict[int, float]:
        out = {}
        for si in range(3):
            tot = 0.0
            for lv in LV[si:]:
                for k, _, _, r in rx_all[c].get(lv, []):
                    if any(rl in topo.members[k].roles for rl in exclude_roles):
                        continue
                    tot += _seis_fac(r)
            out[si + 1] = tot
        return out

    smf = {}
    lines_x = {}
    for yl in MF_LINES:
        cols = sorted(((c, topo.columns[c]["x"]) for c in topo.columns if c[-1] == yl and c[:-1] in MF_LINES[yl]),
                      key=lambda t: t[1])
        if len(cols) < 2:
            continue
        bl = {}
        for k, m in topo.members.items():
            if "smf_beam" in m.roles and m.line == yl:
                bi = [c for c, _ in cols].index(m.i["col"]) if "col" in m.i else 0
                w = G.line_loads(m, topo)
                bl[(m.level, bi)] = (w[0], w[1] + w[2])
        lines_x[yl] = {"cols": cols, "bl": bl, "y": sum(topo.columns[c]["y"] for c, _ in cols) / len(cols)}
    ydim = GY[-1][1] - GY[0][1]
    kx = {yl: 1.0 for yl in lines_x}
    for _it in range(2):
        shares = LAT.distribute(1.0, {yl: (kx[yl], lines_x[yl]["y"]) for yl in lines_x}, cmy, ydim)
        for yl, L in lines_x.items():
            fe = {lv: ex["Fx"][lv] * shares[yl] for lv in LV}
            fw = {lv: wx["Fx"][lv] * shares[yl] for lv in LV}
            gp = {c: grav_p_seis(c) for c, _ in L["cols"]}
            kp = None
            kc = [keep.get(f"COL-{c}") for c, _ in L["cols"]]
            kb = [keep.get(k) for k, m in topo.members.items() if "smf_beam" in m.roles and m.line == yl]
            if keep and all(kc) and all(kb) and kb:
                kp = (max((b["size"] for b in kb), key=lambda z: aisc.get(z)["W"]),
                      max((c["size"] for c in kc), key=lambda z: aisc.get(z)["W"]))
            smf[yl] = LAT.design_smf(yl, L["cols"], L["bl"], fe, fw, gp, keep=kp)
            smf[yl].update(share=shares[yl], fe=fe, fw=fw, gp=gp)
            kx[yl] = smf[yl]["analysis"]["k"]
    # SCBF line
    xl = BF_LINE[0]
    bcols = sorted(((c, topo.columns[c]["y"]) for c in topo.columns if c[:-1] == xl), key=lambda t: t[1])
    braced = [i for i in range(len(bcols) - 1) if (bcols[i][0][-1], bcols[i + 1][0][-1]) in BF_LINE[1]]
    bl3 = {}
    for k, m in topo.members.items():
        if m.kind == "girder" and m.line == xl:
            r = framing[k]
            tot = [r["Ri"][n] + r["Rj"][n] for n in range(3)]
            bi = [c for c, _ in bcols].index(m.i["col"])
            bl3[(m.level, bi)] = (tot[0] / r["span"] - r["sw"], (tot[1] + tot[2]) / r["span"])
    fy = {lv: ey["Fx"][lv] for lv in LV}
    scbf_beam = max((framing[k]["size"] for k, m in topo.members.items() if "scbf_beam" in m.roles),
                    key=lambda s: aisc.get(s)["W"], default="W18X35")
    kbr = next((v["size"] for k, v in keep.items() if v.get("type") == "brace"), None)
    scbf = LAT.design_scbf(bcols, bl3, fy, scbf_beam, "W14X90", braced, keep=kbr) if braced else {"ok": True, "forces": {}, "col_e": {}, "drifts": []}

    # ---------- smf beams sized by the frame -> recheck those members with fixed size for reactions
    fixed = {}
    for k, m in topo.members.items():
        if "smf_beam" in m.roles and m.line in smf:
            fixed[k] = smf[m.line]["beam"]
    # collectors
    coll = {}
    for k, m in topo.members.items():
        if "collector" not in m.roles:
            continue
        if m.kind == "beam":   # along X on an SMF line
            line_f = smf.get(m.line, {}).get("fe")
            if not line_f:
                continue
            lbld = GX[-1][1] - GX[0][1]
            o0 = LAT.SYS["x"]["O0"]
            pu = o0 * line_f[m.level] * m.span / lbld
        else:                  # girder on the SCBF line
            o0 = LAT.SYS["y"]["O0"]
            pu = o0 * fy[m.level] * (m.span / 2) / ydim
        r0 = framing[k]
        size = r0["size"]
        cands = [c for c in aisc.beam_candidates() if aisc.get(c)["W"] >= aisc.get(size)["W"]]
        if size in cands:
            cands = [size] + [c for c in cands if c != size]
        for cand in cands:
            r = G.check_beam(cand, m.span, r0["w"], r0["pts"], r0["lb"], m.level == "RF")
            pn = aisc.phi_pn(cand, m.span, 0.5)
            mu_seis = r["mu"] * (1.4 / 1.6)
            h1, eq = aisc.h1_interaction(pu, pn["phi_pn"], mu_seis, r["phi_mn"])
            if r["ok"] and h1 <= 1.0:
                break
        coll[k] = {"pu": pu, "o0": o0, "size": cand, "h1": h1, "eq": eq, "phi_pn": pn["phi_pn"], "mu": mu_seis,
                   "phi_mn": r["phi_mn"], "gravity_size": size, "ok": h1 <= 1.0}
        if cand != size:
            fixed[k] = cand
    if fixed:
        framing = G.design_framing(topo, fixed_sizes=fixed, keep=ksize)
    rx_all = G.reactions_to_columns(topo, framing)

    # ---------- columns
    columns = {}
    for c, info in topo.columns.items():
        rx = rx_all[c]
        if "smf_column" in info["roles"] and c[-1] in smf:
            size = smf[c[-1]]["col"]
            segs = G.column_demands(topo, rx, size)
            fr = smf[c[-1]]["analysis"]["columns"]
            st = max((s for s in (1, 2, 3)), key=lambda s: fr[(c, s)]["uc_frame"])
            v = fr[(c, st)]
            pg = smf[c[-1]]["gp"].get(c, {}).get(st, 0.0)
            pu = v["pu_frame"] + pg
            pn = aisc.phi_pn(size, STOREY_H[LV[st - 1]])["phi_pn"]
            mn = aisc.phi_mn(size, STOREY_H[LV[st - 1]])["phi_mn"]
            uc, eq = aisc.h1_interaction(pu, pn, v["mu"], mn)
            r = {"size": size, "uc": uc, "eq": eq, "lc": v["lc"], "storey": st, "pu": pu, "mux": v["mu"], "muy": 0.0,
                 "phi_pn": pn, "phi_mnx": mn, "phi_mny": aisc.phi_mny(size), "segs": segs, "ok": uc <= 1.0,
                 "source": "SMF frame analysis"}
        elif "scbf_column" in info["roles"] and scbf.get("col_e"):
            o0 = LAT.SYS["y"]["O0"]

            def extra(size, c=c):
                segs = G.column_demands(topo, rx, size)
                out = {}
                for sg in segs:
                    pe = scbf["col_e"].get((c, sg["storey"]), 0.0)
                    pg = _seis_fac(sg["P"])
                    out[sg["storey"]] = {"OM": (pg + o0 * pe, sg["combos"]["LC2"]["mux"] * 0.6, sg["combos"]["LC2"]["muy"] * 0.6)}
                return out
            r = G.size_column(topo, rx, extra, min_size=keep.get(f"COL-{c}", {}).get("size"))
            r["source"] = "gravity + Omega0 x SCBF axial"
        else:
            r = G.size_column(topo, rx, min_size=keep.get(f"COL-{c}", {}).get("size"))
            r["source"] = "gravity (eccentric reactions)"
        r["roles"] = info["roles"]
        columns[c] = r

    # ---------- connections
    conns = {}
    for k, m in topo.members.items():
        rr = framing[k]
        for end, s in (("i", m.i), ("j", m.j)):
            ru = max(G.fac(rr["R" + end], lc) for lc in G.COMBOS)
            cid = f"CX-{k}-{end}"
            to = s.get("col") or s.get("member")
            if "smf_beam" in m.roles:
                b = aisc.get(rr["size"])
                clear = m.span - aisc.get(columns[s["col"]]["size"])["d"] / 12 if "col" in s else m.span
                ratio = 7 * b["d"] / 12 / clear
                conns[cid] = {"id": cid, "member": k, "end": end, "to": to, "type": "MC-1", "ru": ru,
                              "phi_rn": None, "uc": ratio, "check": "RBS prequalification: clear span/depth >= 7 (AISC 358 5.3.1)",
                              "special": ratio > 1.0}
            elif "collector" in m.roles and "col" in s and s["col"] in topo.columns and \
                    any(r in topo.columns[s["col"]]["roles"] for r in ("smf_column", "scbf_column")):
                a = _assign(DRAG_TYPES, coll[k]["pu"]) if k in coll else _assign(DRAG_TYPES, 0)
                conns[cid] = {"id": cid, "member": k, "end": end, "to": to, **a,
                              "check": "drag force Omega0 x Fx share vs typical drag connection"}
            else:
                old = keep.get(cid, {}).get("conn_type", "")
                n_min = int(old.split("-")[1].rstrip("*")) if old.startswith("ST-") else 2
                a = G.assign_tab(rr["size"], ru, n_min)
                conns[cid] = {"id": cid, "member": k, "end": end, "to": to, **{x: a[x] for x in ("type", "phi_rn", "ru", "uc", "special", "bolts", "governs")},
                              "check": "end reaction vs typical shear tab capacity"}
    for bid, b in topo.braces.items():
        exp_t = scbf.get("expected_t", 0.0)
        for end in ("i", "j"):
            cid = f"CX-{bid}-{end}"
            a = _assign(BRACE_GUSSETS, exp_t)
            conns[cid] = {"id": cid, "member": bid, "end": end, "to": b["base"] if end == "i" else b["beam"], **a,
                          "check": "expected brace tension Ry Fy Ag (AISC 341 F2.6c) vs typical gusset"}

    # ---------- foundations
    footings, piers, plates = {}, {}, {}
    for c, info in topo.columns.items():
        r = columns[c]
        p = r["segs"][0]["P"]
        pe = 0.0
        if "smf_column" in info["roles"] and c[-1] in smf:
            pe = smf[c[-1]]["analysis"]["columns"][(c, "base")]["p_e"]
        if "scbf_column" in info["roles"]:
            pe = max(pe, scbf.get("col_e", {}).get((c, 1), 0.0))
        p_serv = max(p[0] + p[1] + p[2], p[0] + 0.75 * p[1] + 0.75 * p[2] + 0.75 * 0.7 * pe)
        pu = max(max(G.fac(p, lc) for lc in G.COMBOS), _seis_fac(p) + (LAT.SYS["y"]["O0"] if "scbf_column" in info["roles"] else 1.0) * pe)
        pier = "P-2" if info["roles"] != ["gravity"] else "P-1"
        kf = keep.get(f"F-{c}", {})
        f = G.design_footing(p_serv, pu, pier, kf.get("B_ft", 0.0), kf.get("h_in", 18))
        footings[c] = {**f, "x": info["x"], "y": info["y"], "P": p, "pe": pe}
        pc = G.pier_capacity(pier)
        piers[c] = {"type": pier, "pu": pu, "phi_pn": pc, "uc": pu / pc, **G.PIERS[pier]}
        bp = G.assign_base_plate(r["size"], pu, info["roles"], pier)
        plates[c] = bp
    gbs = {}
    for gid, g in topo.grade_beams.items():
        L = math.dist(g["p1"], g["p2"])
        m_end = 0.0
        if g["smf"] and g["line"] in smf:
            fr = smf[g["line"]]["analysis"]["columns"]
            m_end = max(fr.get((g["a"], "base"), {}).get("m_base", 0.0), fr.get((g["b"], "base"), {}).get("m_base", 0.0)) / 2
        tie = 0.0
        if g["line"] == BF_LINE[0]:
            # brace base shear of one braced bay, shared into the line by the tie grade beam
            tie = LAT.SYS["y"]["rho"] * ey["V"] / 4
        gbs[gid] = {**G.design_grade_beam(L, g["wall"], m_end, tie), "a": g["a"], "b": g["b"], "line": g["line"],
                    "p1": g["p1"], "p2": g["p2"]}

    clashes = find_clashes(footings, gbs)
    return {"layout": layout, "topo": topo, "framing": framing, "columns": columns, "connections": conns,
            "footings": footings, "piers": piers, "base_plates": plates, "grade_beams": gbs, "clashes": clashes,
            "seismic": {"x": ex, "y": ey, "weights": weights, "cm": (cmx, cmy)}, "wind": {"x": wx, "y": wy},
            "smf": smf, "scbf": scbf, "collectors": coll, "infeasible": infeasible,
            "shear_tabs": G.SHEAR_TABS}


def find_clashes(footings: dict, gbs: dict) -> list[dict]:
    out = []
    keys = sorted(footings)
    for i, a in enumerate(keys):
        fa = footings[a]
        for b in keys[i + 1:]:
            fb = footings[b]
            gapx = abs(fa["x"] - fb["x"]) - (fa["B"] + fb["B"]) / 2
            gapy = abs(fa["y"] - fb["y"]) - (fa["B"] + fb["B"]) / 2
            if gapx < 0 and gapy < 0:
                out.append({"kind": "footing-footing", "a": f"F-{a}", "b": f"F-{b}", "overlap_ft": round(-max(gapx, gapy), 2)})
        for gid, g in gbs.items():
            if a in (g["a"], g["b"]):
                continue
            (x1, y1), (x2, y2) = g["p1"], g["p2"]
            half = fa["B"] / 2
            w = 0.75
            # axis-aligned grade beam strip vs footing square
            gx0, gx1 = min(x1, x2) - w, max(x1, x2) + w
            gy0, gy1 = min(y1, y2) - w, max(y1, y2) + w
            if fa["x"] + half > gx0 and fa["x"] - half < gx1 and fa["y"] + half > gy0 and fa["y"] - half < gy1:
                out.append({"kind": "footing-grade_beam", "a": f"F-{a}", "b": gid})
    return out
