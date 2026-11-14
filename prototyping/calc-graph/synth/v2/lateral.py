"""Lateral design: ASCE 7-16 ELF seismic + simplified MWFRS wind, PyNite analysis of every
SFRS line, drift, SMF strength + strong-column/weak-beam, SCBF braces, collectors.

Site (fictional): SDS = 1.00, SD1 = 0.60, site class D, risk category II, Ie = 1.0, SDC D.
X: steel SMF with RBS (R 8, Cd 5.5, Omega0 3), Y: steel SCBF (R 6, Cd 5, Omega0 2).
Redundancy: rho = 1.0 in X (two lines, two bays each, 12.3.4.2 b); rho = 1.3 in Y (one line).
Rigid (composite deck) diaphragm: line forces by relative stiffness with 5% accidental
torsion. Wind: 110 mph exp. C, MWFRS taken as 21 psf net on the projected area (simplified).
Drift: 0.020 hsx (12.12-1) with Cd/Ie; stability coefficient theta checked (12.8.7).
Analysis units: kip, ft. In-plane 2D frames inside PyNite 3D (out-of-plane restrained;
Iy = Iz = Ix so in-plane bending always uses the strong axis).
"""
from __future__ import annotations

import math

from Pynite import FEModel3D

from . import aisc
from .gravity import E_KSF, V, vadd
from .model import GX, GY, LEVELS, MF_LINES, PARAPET_FT, STOREY_H, Topology, wall_klf, wall_trib_h  # noqa: F401

SDS, SD1, IE = 1.0, 0.6, 1.0
SYS = {"x": {"name": "Steel special moment frame (RBS)", "R": 8.0, "Cd": 5.5, "O0": 3.0, "Ct": 0.028, "xexp": 0.8, "rho": 1.0},
       "y": {"name": "Steel special concentrically braced frame", "R": 6.0, "Cd": 5.0, "O0": 2.0, "Ct": 0.02, "xexp": 0.75, "rho": 1.3}}
WIND_PSF = 21.0
DRIFT_LIM = 0.020
G_KSF = aisc.G * 144.0
RY = 1.1          # A992 W shapes (AISC 341 Table A3.1)
RY_HSS = 1.3      # A500 Gr C rectangular HSS
LV = [l for l, _, _ in LEVELS]
ZS = {l: z for l, _, z in LEVELS}


STEEL_ALLOW_PSF = {"L2": 8.0, "L3": 8.0, "RF": 6.0}   # framing + columns allowance (design-office practice)


def seismic_weights(topo: Topology, framing: dict, col_sizes: dict) -> dict:
    """W per level (kip): area dead + partition allowance + a steel framing allowance (psf,
    not the as-designed tonnage - so a member re-size does not re-trigger the ELF) +
    exterior walls. framing / col_sizes are accepted for the record but not used."""
    out = {}
    lx, ly = GX[-1][1] - GX[0][1], GY[-1][1] - GY[0][1]
    for lv in LV:
        w = 0.0
        for ar in topo.layout.areas:
            if ar.level != lv:
                continue
            a = (ar.x1 - ar.x0) * (ar.y1 - ar.y0)
            if ar.kind == "roof":
                a = lx * ly - sum((o.x1 - o.x0) * (o.y1 - o.y0) for o in topo.layout.areas if o.level == lv and o.kind == "mech")
            w += a * (ar.d_psf + ar.seis_extra_psf) / 1000
        w += lx * ly * STEEL_ALLOW_PSF[lv] / 1000
        w += 2 * (lx + ly) * wall_klf(lv)
        out[lv] = w
    return out


def elf(weights: dict, d: str) -> dict:
    s = SYS[d]
    hn = ZS[LV[-1]]
    ta = s["Ct"] * hn ** s["xexp"]
    cs = min(SDS / (s["R"] / IE), SD1 / (ta * s["R"] / IE))
    cs = max(cs, 0.044 * SDS * IE, 0.01)
    w = sum(weights.values())
    v = cs * w
    k = 1.0 if ta <= 0.5 else (2.0 if ta >= 2.5 else 1 + (ta - 0.5) / 2)
    den = sum(weights[l] * ZS[l] ** k for l in LV)
    fx = {l: v * weights[l] * ZS[l] ** k / den for l in LV}
    return {"dir": d, "system": s["name"], "R": s["R"], "Cd": s["Cd"], "O0": s["O0"], "rho": s["rho"], "Ta": ta, "Cs": cs,
            "W": w, "V": v, "k": k, "Fx": fx, "eq": "12.8-2/12.8-3, 12.8-11/12.8-12"}


def wind(d: str) -> dict:
    width = (GY[-1][1] - GY[0][1]) if d == "x" else (GX[-1][1] - GX[0][1])
    fx = {l: WIND_PSF * width * wall_trib_h(l) / 1000 for l in LV}   # same exposed height as the wall
    return {"dir": d, "psf": WIND_PSF, "Fx": fx, "V": sum(fx.values())}


# ------------------------------------------------------------------ PyNite frames
def _frame(cols: list[tuple[str, float]], beam_loads: dict, beam: str, col: str, fx: dict, base_fixed: bool,
           pinned_beams: bool = False, braces: list | None = None, brace_size: str | None = None):
    """cols: [(col id, position along line)], beam_loads: {(level, bay idx): (wD, wL)} klf,
    fx: {case: {level: F}} lateral forces applied at the first column node."""
    m = FEModel3D()
    m.add_material("S", E_KSF, G_KSF, 0.3, 0.49)
    bs, cs = aisc.get(beam), aisc.get(col)
    m.add_section("B", bs["A"] / 144, bs["Ix"] / 20736, bs["Ix"] / 20736, max(bs["J"], 0.1) / 20736)
    m.add_section("C", cs["A"] / 144, cs["Ix"] / 20736, cs["Ix"] / 20736, max(cs["J"], 0.1) / 20736)
    if brace_size:
        br = aisc.get(brace_size)
        m.add_section("BR", br["A"] / 144, br["Ix"] / 20736, br["Ix"] / 20736, br["J"] / 20736)
    zs = [0.0] + [ZS[l] for l in LV]
    for ci, (c, x) in enumerate(cols):
        for zi, z in enumerate(zs):
            n = f"{c}_{zi}"
            m.add_node(n, x, 0.0, z)
            if zi == 0:
                m.def_support(n, True, True, True, True, base_fixed, True)
            else:
                m.def_support(n, False, True, False, True, False, True)
        for zi in range(3):
            m.add_member(f"C_{c}_{zi}", f"{c}_{zi}", f"{c}_{zi + 1}", "S", "C")
    for zi, lv in enumerate(LV, start=1):
        for bi in range(len(cols) - 1):
            (ca, xa), (cb, xb) = cols[bi], cols[bi + 1]
            name = f"B_{lv}_{bi}"
            if braces and bi in braces:
                mid = f"M_{lv}_{bi}"
                m.add_node(mid, (xa + xb) / 2, 0.0, zs[zi])
                m.def_support(mid, False, True, False, True, False, True)
                m.add_member(name + "a", f"{ca}_{zi}", mid, "S", "B")
                m.add_member(name + "b", mid, f"{cb}_{zi}", "S", "B")
                parts = [name + "a", name + "b"]
                for side, (cc, zz) in enumerate(((ca, zi - 1), (cb, zi - 1))):
                    bn = f"BR_{lv}_{bi}_{side}"
                    m.add_member(bn, f"{cc}_{zz}", mid, "S", "BR")
                    m.def_releases(bn, Ryi=True, Rzi=True, Ryj=True, Rzj=True)
            else:
                m.add_member(name, f"{ca}_{zi}", f"{cb}_{zi}", "S", "B")
                parts = [name]
            for pi, p in enumerate(parts):
                if pinned_beams:
                    if len(parts) == 1:
                        m.def_releases(p, Ryi=True, Rzi=True, Ryj=True, Rzj=True)
                    elif pi == 0:   # beam stays continuous through the brace work point
                        m.def_releases(p, Ryi=True, Rzi=True)
                    else:
                        m.def_releases(p, Ryj=True, Rzj=True)
                wd, wl = beam_loads.get((lv, bi), (0.0, 0.0))
                m.add_member_dist_load(p, "FZ", -wd - bs["W"] / 1000, -wd - bs["W"] / 1000, case="D")
                m.add_member_dist_load(p, "FZ", -wl, -wl, case="L")
    first = cols[0][0]
    for case, f in fx.items():
        for zi, lv in enumerate(LV, start=1):
            m.add_node_load(f"{first}_{zi}", "FX", f[lv], case=case)
    sds = SDS
    return m


def _mmax(mem, combo):
    return max(abs(mem.max_moment("Mz", combo)), abs(mem.min_moment("Mz", combo)),
               abs(mem.max_moment("My", combo)), abs(mem.min_moment("My", combo)))


def _axial(mem, combo):
    return mem.max_axial(combo), mem.min_axial(combo)


def analyse_smf(line: str, cols: list[tuple[str, float]], beam_loads: dict, beam: str, col: str, f_e: dict,
                f_w: dict, rho: float, o0: float) -> dict:
    m = _frame(cols, beam_loads, beam, col, {"E": f_e, "W": f_w}, base_fixed=True)
    combos = {"S1": {"D": 1.2 + 0.2 * SDS, "L": 0.5, "E": rho}, "S2": {"D": 0.9 - 0.2 * SDS, "E": rho},
              "S3": {"D": 1.2 + 0.2 * SDS, "L": 0.5, "E": -rho}, "W1": {"D": 1.2, "L": 0.5, "W": 1.0},
              "G2": {"D": 1.2, "L": 1.6}, "EUN": {"E": 1.0}, "WSV": {"W": 0.42}}   # 0.42 W ~ 10-yr service wind
    for k, v in combos.items():
        m.add_load_combo(k, v)
    m.analyze_linear(check_statics=False, check_stability=False)
    zs = range(1, 4)
    first = cols[0][0]
    dxe = [0.0] + [max(abs(m.nodes[f"{c}_{z}"].DX["EUN"]) for c, _ in cols) for z in zs]
    dw = [0.0] + [max(abs(m.nodes[f"{c}_{z}"].DX["WSV"]) for c, _ in cols) for z in zs]
    cd = SYS["x"]["Cd"]
    drifts = []
    for zi, lv in enumerate(LV, start=1):
        h = STOREY_H[lv]
        dx = cd * (dxe[zi] - dxe[zi - 1]) / IE
        drifts.append({"level": lv, "h": h, "delta_in": dx * 12, "allow_in": DRIFT_LIM * h * 12,
                       "ratio": dx / (DRIFT_LIM * h), "wind_in": (dw[zi] - dw[zi - 1]) * 12,
                       "wind_allow_in": h * 12 / 400})
    k_line = sum(f_e.values()) / max(dxe[3], 1e-9)
    # member forces
    beams, columns = {}, {}
    for zi, lv in enumerate(LV, start=1):
        for bi in range(len(cols) - 1):
            mem = m.members[f"B_{lv}_{bi}"]
            mu = max(_mmax(mem, c) for c in ("S1", "S2", "S3", "W1", "G2"))
            vu = max(max(abs(mem.max_shear("Fz", c)), abs(mem.min_shear("Fz", c)), abs(mem.max_shear("Fy", c)),
                         abs(mem.min_shear("Fy", c))) for c in ("S1", "S3", "G2"))
            beams[(lv, bi)] = {"mu": mu, "vu": vu, "span": cols[bi + 1][1] - cols[bi][1]}
    for c, _ in cols:
        for zi in range(3):
            mem = m.members[f"C_{c}_{zi}"]
            for cb in ("S1", "S2", "S3", "W1", "G2"):
                amax, amin = _axial(mem, cb)
                pu = max(abs(amax), abs(amin))
                mu = _mmax(mem, cb)
                key = (c, zi + 1)
                prev = columns.get(key)
                pn = aisc.phi_pn(col, STOREY_H[LV[zi]])["phi_pn"]
                mn = aisc.phi_mn(col, STOREY_H[LV[zi]])["phi_mn"]
                uc, eq = aisc.h1_interaction(pu, pn, mu, mn)
                if not prev or uc > prev["uc_frame"]:
                    columns[key] = {"pu_frame": pu, "mu": mu, "lc": cb, "uc_frame": uc, "eq": eq}
        base = m.nodes[f"{c}_0"]
        columns[(c, "base")] = {"m_base": max(abs(base.RxnMY["S1"]), abs(base.RxnMY["S3"])),
                                "p_e": abs(base.RxnFZ["EUN"]), "v_e": abs(base.RxnFX["EUN"])}
    return {"line": line, "beam": beam, "col": col, "drifts": drifts, "k": k_line, "beams": beams, "columns": columns,
            "dxe_roof_in": dxe[3] * 12}


def scwb(beam: str, col: str, n_beams: int, pu: float) -> float:
    """AISC 341 E3.4a: sum M*pc / sum M*pb at an interior joint (RBS, c = 0.25 bf)."""
    b, c = aisc.get(beam), aisc.get(col)
    z_rbs = b["Zx"] - 2 * 0.25 * b["bf"] * b["tf"] * (b["d"] - b["tf"])
    mpb = 1.1 * RY * aisc.FY_W * z_rbs * 1.15        # + shear amplification allowance
    mpc = 2 * c["Zx"] * (aisc.FY_W - pu / c["A"])
    return mpc / (n_beams * mpb)


def smf_candidates():
    lim = 0.32 * math.sqrt(aisc.E / (RY * aisc.FY_W))
    beams = [n for n in aisc.beam_candidates() if 21 <= aisc.get(n)["d"] <= 31
             and aisc.get(n)["bf"] / (2 * aisc.get(n)["tf"]) <= lim]
    cols = [n for n in aisc.column_candidates() if n.startswith("W14X") and aisc.get(n)["W"] >= 68
            and aisc.get(n)["bf"] / (2 * aisc.get(n)["tf"]) <= lim]
    return beams, cols


def design_smf(line: str, cols, beam_loads, f_e, f_w, gravity_p: dict, keep: tuple[str, str] | None = None) -> dict:
    """Lightest (beam, column) pair, uniform up the frame, passing drift, member strength
    (with gravity column axial added), SCWB and RBS span/depth >= 7."""
    beams, columns = smf_candidates()
    beam_len = 3 * (cols[-1][1] - cols[0][1])
    col_len = len(cols) * ZS[LV[-1]]
    pairs = sorted(((b, c) for b in beams for c in columns),
                   key=lambda bc: aisc.get(bc[0])["W"] * beam_len + aisc.get(bc[1])["W"] * col_len)
    if keep:   # minimum change: current pair first, then only pairs no lighter in either member
        kb, kc = aisc.get(keep[0])["W"], aisc.get(keep[1])["W"]
        pairs = [keep] + [p for p in pairs if p != keep and aisc.get(p[0])["W"] >= kb and aisc.get(p[1])["W"] >= kc]
    s = SYS["x"]
    last = None
    failed_drift: list[tuple[float, float]] = []
    for b, c in pairs:
        ib, ic = aisc.get(b)["Ix"], aisc.get(c)["Ix"]
        if any(ib <= fb and ic <= fc for fb, fc in failed_drift):
            continue   # stiffness-dominated by a pair that already failed drift
        min_span = min(cols[i + 1][1] - cols[i][1] for i in range(len(cols) - 1))
        clear = min_span - aisc.get(c)["d"] / 12
        if clear / (aisc.get(b)["d"] / 12) < 7:
            continue
        r = analyse_smf(line, cols, beam_loads, b, c, f_e, f_w, s["rho"], s["O0"])
        drift = max(d["ratio"] for d in r["drifts"])
        if drift > 1.0:
            failed_drift.append((ib, ic))
            last = (b, c, r, {"drift": drift})
            continue
        phimn = aisc.phi_mn(b, 0)["phi_mn"]
        beam_uc = max(v["mu"] / phimn for v in r["beams"].values())
        vb = max(v["vu"] / aisc.phi_vn(b) for v in r["beams"].values())
        col_uc = 0.0
        for (cid, st), v in r["columns"].items():
            if st == "base":
                continue
            pg = gravity_p.get(cid, {}).get(st, 0.0)
            pu = v["pu_frame"] + pg
            uc, _ = aisc.h1_interaction(pu, aisc.phi_pn(c, STOREY_H[LV[st - 1]])["phi_pn"], v["mu"],
                                        aisc.phi_mn(c, STOREY_H[LV[st - 1]])["phi_mn"])
            col_uc = max(col_uc, uc)
        sc = min(scwb(b, c, 2 if i not in (0, len(cols) - 1) else 1, gravity_p.get(cid, {}).get(1, 0.0))
                 for i, (cid, _) in enumerate(cols))
        checks = {"drift": drift, "beam_flexure": beam_uc, "beam_shear": vb, "column": col_uc, "scwb": 1.0 / sc}
        last = (b, c, r, checks)
        if max(checks.values()) <= 1.0:
            return {"beam": b, "col": c, "analysis": r, "checks": checks, "ok": True, "scwb_ratio": sc}
    b, c, r, checks = last
    return {"beam": b, "col": c, "analysis": r, "checks": checks, "ok": False, "infeasible": True}


def design_scbf(cols, beam_loads, f_e, beam_size: str, col_size: str, braced_bays: list[int], keep: str | None = None) -> dict:
    """Chevron SCBF: lightest square HSS brace (KL = full length, K = 1, KL/r <= 200, AISC 341
    F2.5b b/t limit already in the candidate filter); braces + pinned beams in PyNite."""
    s = SYS["y"]
    last = None
    cands = aisc.hss_candidates()
    if keep:
        cands = [keep] + [c for c in cands if c != keep and aisc.get(c)["W"] >= aisc.get(keep)["W"]]
    for br in cands:
        b = aisc.get(br)
        m = _frame(cols, beam_loads, beam_size, col_size, {"E": f_e}, base_fixed=False, pinned_beams=True,
                   braces=braced_bays, brace_size=br)
        m.add_load_combo("S1", {"D": 1.2 + 0.2 * SDS, "L": 0.5, "E": s["rho"]})
        m.add_load_combo("EUN", {"E": 1.0})
        m.analyze_linear(check_statics=False, check_stability=False)
        worst = 0.0
        forces = {}
        for name, mem in m.members.items():
            if not name.startswith("BR_"):
                continue
            amax, amin = _axial(mem, "S1")
            pu = max(abs(amax), abs(amin))
            L = mem.L()
            pn = aisc.phi_pn(br, L)
            klr = pn["kl_r"]
            uc = max(pu / pn["phi_pn"], pu / aisc.phi_pn_tension(br), klr / 200.0)
            forces[name] = {"pu": pu, "L": L, "phi_pn": pn["phi_pn"], "kl_r": klr, "uc": uc,
                            "pe": max(abs(x) for x in _axial(mem, "EUN"))}
            worst = max(worst, uc)
        dxe = [0.0] + [max(abs(m.nodes[f"{c}_{z}"].DX["EUN"]) for c, _ in cols) for z in (1, 2, 3)]
        drifts = []
        for zi, lv in enumerate(LV, start=1):
            h = STOREY_H[lv]
            dx = s["Cd"] * (dxe[zi] - dxe[zi - 1]) / IE
            drifts.append({"level": lv, "h": h, "delta_in": dx * 12, "allow_in": DRIFT_LIM * h * 12,
                           "ratio": dx / (DRIFT_LIM * h)})
        col_e = {}
        for c, _ in cols:
            for zi in range(3):
                amax, amin = _axial(m.members[f"C_{c}_{zi}"], "EUN")
                col_e[(c, zi + 1)] = max(abs(amax), abs(amin))
        last = {"brace": br, "forces": forces, "uc": worst, "drifts": drifts, "col_e": col_e,
                "expected_t": RY_HSS * aisc.FY_HSS * b["A"], "k": sum(f_e.values()) / max(dxe[3], 1e-9)}
        if worst <= 1.0 and max(d["ratio"] for d in drifts) <= 1.0:
            last["ok"] = True
            return last
    last["ok"] = False
    last["infeasible"] = True
    return last


def distribute(v: float, lines: dict[str, tuple[float, float]], cm: float, dim: float) -> dict[str, float]:
    """Rigid diaphragm: lines {name: (k, coordinate)}; returns force share with the worse of
    +/- 5% accidental eccentricity added (direct + torsional)."""
    ksum = sum(k for k, _ in lines.values())
    cr = sum(k * y for k, y in lines.values()) / ksum
    j = sum(k * (y - cr) ** 2 for k, y in lines.values()) or 1.0
    out = {}
    for n, (k, y) in lines.items():
        best = 0.0
        for sgn in (1, -1):
            e = cm - cr + sgn * 0.05 * dim
            best = max(best, v * k / ksum + v * e * k * (y - cr) / j)
        out[n] = best
    return out
