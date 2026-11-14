"""Lateral design: ASCE 7-16 ELF seismic + simplified MWFRS wind, PyNite analysis of every
SFRS line, drift, SMF strength + strong-column/weak-beam, SCBF braces, collectors.

Site (fictional): SDS = 1.00, SD1 = 0.60, site class D, risk category II, Ie = 1.0, SDC D.
X: steel SMF with RBS (R 8, Cd 5.5, Omega0 3), Y: steel SCBF (R 6, Cd 5, Omega0 2).
Redundancy: rho = 1.0 in X (two lines, two bays each, 12.3.4.2 b); rho = 1.3 in Y (kept at the
conservative value for the perimeter SCBF layout too).
Rigid (composite deck) diaphragm: line forces by relative stiffness, torsion resisted by BOTH
directions' lines (J = sum k d^2 over the X and the Y lines), 5% accidental torsion, amplified
by Ax (12.8.4.3) when the torsional irregularity ratio exceeds 1.2. Wind: 110 mph exp. C, MWFRS
taken as 21 psf net on the projected area (simplified).
Drift: 0.020 hsx (12.12-1) with Cd/Ie at each frame line (the edges), from the line's share of
the storey force (direct + torsion); stability coefficient theta checked (12.8.7).
Analysis units: kip, ft. In-plane 2D frames inside PyNite 3D (out-of-plane restrained;
Iy = Iz = Ix so in-plane bending always uses the strong axis). Shear deformation: PyNite's
member is Euler-Bernoulli; the etabs-reviewed basis replaces the bending terms of every beam and
column with the Timoshenko terms (shear area d tw, the area ETABS uses), see _timoshenko_ke_unc. ETABS
23.3.2 showed the Euler-Bernoulli frames ~14% too stiff in the columns, which made the design's
SMF drift unconservative (ETABS 1.053 / 1.033 of the limit against the design's 0.981 / 0.978).
"""
from __future__ import annotations

import math

from Pynite import FEModel3D

from . import aisc
from .gravity import E_KSF, V, vadd
from .model import GX, GY, LEVELS, PARAPET_FT, STOREY_H, Topology, wall_klf, wall_trib_h  # noqa: F401

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
def _timoshenko_ke_unc(self):
    """Member3D._ke_unc with shear deformation when the member's section carries `shear_area`
    (ft^2): the bending terms become the Timoshenko beam (phi = 12 E I / (G As L^2):
    12 EI / (L^3 (1+phi)), 6 EI / (L^2 (1+phi)), (4+phi) EI / (L (1+phi)), (2-phi) EI / (L (1+phi)))
    about both local axes. A section without `shear_area` gets PyNite's own Euler-Bernoulli matrix,
    so nothing outside these frames changes. Installed on the class (not per member) because
    PyNite analyses the sub-members it splits each physical member into, which share its section.
    Fixed-end forces stay Euler-Bernoulli, which is exact for the uniform loads these frames carry
    (a uniform load's fixed-end moment does not depend on phi); point loads are applied at nodes
    (see _frame), so they need no fixed-end forces at all."""
    k = _EB_KE_UNC(self)
    a_s = getattr(self.section, "shear_area", None)
    if not a_s:
        return k
    k = k.astype(float, copy=True)
    E, G, L = self.material.E, self.material.G, self.L()
    for I, (t, r, sgn) in ((self.section.Iz, (1, 5, 1.0)), (self.section.Iy, (2, 4, -1.0))):
        phi = 12 * E * I / (G * a_s * L ** 2)
        c = E * I / (1 + phi)
        ti, ri, tj, rj = t, r, t + 6, r + 6
        kt, kr = 12 * c / L ** 3, 6 * c / L ** 2 * sgn
        for p_, q_, v in ((ti, ti, kt), (tj, tj, kt), (ti, tj, -kt),
                          (ti, ri, kr), (ti, rj, kr), (tj, ri, -kr), (tj, rj, -kr),
                          (ri, ri, (4 + phi) * c / L), (rj, rj, (4 + phi) * c / L), (ri, rj, (2 - phi) * c / L)):
            k[p_, q_] = k[q_, p_] = v
    return k


from Pynite.Member3D import Member3D as _Member3D  # noqa: E402

_EB_KE_UNC = getattr(_Member3D._ke_unc, "_euler_bernoulli", _Member3D._ke_unc)
_timoshenko_ke_unc._euler_bernoulli = _EB_KE_UNC
_Member3D._ke_unc = _timoshenko_ke_unc


def shear_area_ft2(size: str) -> float:
    """Strong-axis shear area of a W shape, d tw (ft^2) - what ETABS assigns as AS2."""
    s = aisc.get(size)
    return s["d"] * s["tw"] / 144


def _frame(cols: list[tuple[str, float]], beam_loads: dict, beam: str, col: str, fx: dict, base_fixed: bool,
           pinned_beams: bool = False, braces: list | None = None, brace_size: str | None = None,
           shear_def: bool = False, beam_sizes: dict | None = None):
    """cols: [(col id, position along line)], fx: {case: {level: F}} lateral forces applied at the
    first column node. beam_loads: {(level, bay idx): load} with load either (wD, wL) klf uniform
    (the original basis, and every SMF beam), or {"w": (wD, wL), "pts": [(a ft from the bay's
    first column, D, L), ...]} - the real infill reactions, applied at nodes so the girder sees
    point loads exactly. shear_def: Timoshenko beams and columns (see _timoshenko_ke_unc).
    beam_sizes: {(level, bay idx): size} overrides `beam` per bay (SCBF girders sized per bay).
    Beam members are named B_<lv>_<bay> (SMF) or B_<lv>_<bay><k> for the segments between
    nodes (k = a, b, c ... from the first column; a braced bay always has a node at mid-span)."""
    m = FEModel3D()
    m.add_material("S", E_KSF, G_KSF, 0.3, 0.49)
    bs, cs = aisc.get(beam), aisc.get(col)
    m.add_section("B", bs["A"] / 144, bs["Ix"] / 20736, bs["Ix"] / 20736, max(bs["J"], 0.1) / 20736)
    m.add_section("C", cs["A"] / 144, cs["Ix"] / 20736, cs["Ix"] / 20736, max(cs["J"], 0.1) / 20736)
    beam_sizes = beam_sizes or {}
    for bsz in sorted(set(beam_sizes.values()) - {beam}):
        b2 = aisc.get(bsz)
        m.add_section(f"B:{bsz}", b2["A"] / 144, b2["Ix"] / 20736, b2["Ix"] / 20736, max(b2["J"], 0.1) / 20736)
    shear_members: list[tuple[str, str]] = []
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
            shear_members.append((f"C_{c}_{zi}", col))
    for zi, lv in enumerate(LV, start=1):
        for bi in range(len(cols) - 1):
            (ca, xa), (cb, xb) = cols[bi], cols[bi + 1]
            name = f"B_{lv}_{bi}"
            bsz = beam_sizes.get((lv, bi), beam)
            sec = "B" if bsz == beam else f"B:{bsz}"
            sw = aisc.get(bsz)["W"] / 1000
            load = beam_loads.get((lv, bi), (0.0, 0.0))
            if isinstance(load, dict):
                (wd, wl), pts = load["w"], load["pts"]
            else:
                (wd, wl), pts = load, []
            braced = bool(braces and bi in braces)
            span = xb - xa
            stations = sorted({round(a, 6) for a, _, _ in pts if 1e-6 < a < span - 1e-6} |
                              ({round(span / 2, 6)} if braced else set()))
            nodes = [f"{ca}_{zi}"]
            for k, a in enumerate(stations):
                nn = f"M_{lv}_{bi}" if braced and abs(a - span / 2) < 1e-6 else f"P_{lv}_{bi}_{k}"
                m.add_node(nn, xa + a, 0.0, zs[zi])
                m.def_support(nn, False, True, False, True, False, True)
                nodes.append(nn)
            nodes.append(f"{cb}_{zi}")
            if len(nodes) == 2:
                parts = [name]
            else:
                parts = [name + "abcdefghijklmnop"[k] for k in range(len(nodes) - 1)]
            for p, ni, nj in zip(parts, nodes, nodes[1:]):
                m.add_member(p, ni, nj, "S", sec)
                shear_members.append((p, bsz))
            if braced:
                for side, (cc, zz) in enumerate(((ca, zi - 1), (cb, zi - 1))):
                    bn = f"BR_{lv}_{bi}_{side}"
                    m.add_member(bn, f"{cc}_{zz}", f"M_{lv}_{bi}", "S", "BR")
                    m.def_releases(bn, Ryi=True, Rzi=True, Ryj=True, Rzj=True)
            for pi, p in enumerate(parts):
                if pinned_beams:
                    if len(parts) == 1:
                        m.def_releases(p, Ryi=True, Rzi=True, Ryj=True, Rzj=True)
                    elif pi == 0:   # beam stays continuous through the brace work point / load points
                        m.def_releases(p, Ryi=True, Rzi=True)
                    elif pi == len(parts) - 1:
                        m.def_releases(p, Ryj=True, Rzj=True)
                m.add_member_dist_load(p, "FZ", -wd - sw, -wd - sw, case="D")
                m.add_member_dist_load(p, "FZ", -wl, -wl, case="L")
            for a, pd, pl in pts:
                if round(a, 6) not in stations:
                    continue   # a load at a column face goes straight into the column
                k = stations.index(round(a, 6))
                nn = nodes[k + 1]
                if pd:
                    m.add_node_load(nn, "FZ", -pd, case="D")
                if pl:
                    m.add_node_load(nn, "FZ", -pl, case="L")
    if shear_def:   # sections are per size, so the shear area goes on the section (see _timoshenko_ke_unc)
        for mn, sz in shear_members:
            m.members[mn].section.shear_area = shear_area_ft2(sz)
    first = cols[0][0]
    for case, f in fx.items():
        for zi, lv in enumerate(LV, start=1):
            m.add_node_load(f"{first}_{zi}", "FX", f[lv], case=case)
    return m


def _mmax(mem, combo):
    return max(abs(mem.max_moment("Mz", combo)), abs(mem.min_moment("Mz", combo)),
               abs(mem.max_moment("My", combo)), abs(mem.min_moment("My", combo)))


def _axial(mem, combo):
    return mem.max_axial(combo), mem.min_axial(combo)


def analyse_smf(line: str, cols: list[tuple[str, float]], beam_loads: dict, beam: str, col: str, f_e: dict,
                f_w: dict, rho: float, o0: float, shear_def: bool = False) -> dict:
    m = _frame(cols, beam_loads, beam, col, {"E": f_e, "W": f_w}, base_fixed=True, shear_def=shear_def)
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


def design_smf(line: str, cols, beam_loads, f_e, f_w, gravity_p: dict, keep: tuple[str, str] | None = None,
               shear_def: bool = False) -> dict:
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
        r = analyse_smf(line, cols, beam_loads, b, c, f_e, f_w, s["rho"], s["O0"], shear_def=shear_def)
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
            return {"beam": b, "col": c, "analysis": r, "checks": checks, "ok": True, "scwb_ratio": sc, "shear_def": shear_def}
    b, c, r, checks = last
    return {"beam": b, "col": c, "analysis": r, "checks": checks, "ok": False, "infeasible": True, "shear_def": shear_def}


SCBF_COMBOS = {"G1": {"D": 1.4}, "G2": {"D": 1.2, "L": 1.6},
               "S1": {"D": 1.2 + 0.2 * SDS, "L": 0.5, "E": SYS["y"]["rho"]},
               "S2": {"D": 0.9 - 0.2 * SDS, "E": SYS["y"]["rho"]},
               "S3": {"D": 1.2 + 0.2 * SDS, "L": 0.5, "E": -SYS["y"]["rho"]},
               "S4": {"D": 0.9 - 0.2 * SDS, "E": -SYS["y"]["rho"]}}
SCBF_COMBO_TXT = {"G1": "1.4D", "G2": "1.2D+1.6L (L = floor live or roof live)", "S1": "(1.2+0.2SDS)D+0.5L+rho E",
                  "S2": "(0.9-0.2SDS)D+rho E", "S3": "(1.2+0.2SDS)D+0.5L-rho E", "S4": "(0.9-0.2SDS)D-rho E"}


def _brace_expected(br: str, L_ft: float) -> dict:
    """AISC 341-16 F2.3: expected tension Ry Fy Ag, expected compression min(Ry Fy Ag, 1.14 Fcre Ag)
    (Fcre = Fcr with Ry Fy), post-buckling 0.3 x that."""
    b = aisc.get(br)
    ry_fy = RY_HSS * aisc.FY_HSS
    kl_r = L_ft * 12 / b["rx"] if b.get("rx") else aisc.phi_pn(br, L_ft)["kl_r"]
    t = ry_fy * b["A"]
    c = min(t, 1.14 * aisc.fcr(kl_r, ry_fy) * b["A"])
    return {"T": t, "C": c, "C_post": 0.3 * c}


def _simple_m_mid(span: float, w: float, pts: list[tuple[float, float]]) -> tuple[float, float]:
    """Simple-span (moment at mid-span, max end reaction) of a uniform w + point loads [(a, P)]."""
    m = w * span ** 2 / 8 + sum(p * min(a, span - a) / 2 for a, p in pts)
    ri = w * span / 2 + sum(p * (span - a) / span for a, p in pts)
    rj = w * span / 2 + sum(p * a / span for a, p in pts)
    return m, max(ri, rj)


def _check_scbf_girders(m, cols, beam_loads, sizes: dict, girder_lb: dict, braced: list[int], br: str) -> dict:
    """Every SCBF-line girder (braced bays and the collector bay) under the full combo set, from the
    frame itself (real point loads), plus the AISC 341 F2.3 / F2.4a chevron check of each braced-bay
    girder: braces at expected tension / post-buckling compression, the girder spanning between
    columns with the unbalanced vertical force at mid-span plus 1.2D + 0.5L gravity."""
    out = {}
    s1 = 1.2 + 0.2 * SDS
    for zi, lv in enumerate(LV, start=1):
        for bi in range(len(cols) - 1):
            size = sizes[(lv, bi)]
            span = cols[bi + 1][1] - cols[bi][1]
            parts = sorted(n for n in m.members if n.startswith(f"B_{lv}_{bi}") and
                           (len(n) == len(f"B_{lv}_{bi}") or n[len(f"B_{lv}_{bi}")].isalpha()))
            lb = girder_lb.get((lv, bi), span)
            phimn = aisc.phi_mn(size, lb)["phi_mn"]
            phivn = aisc.phi_vn(size)
            phipn = aisc.phi_pn(size, span, lb)["phi_pn"]
            best = None
            for cb in SCBF_COMBOS:
                mu = max(_mmax(m.members[p], cb) for p in parts)
                vu = max(max(abs(m.members[p].max_shear(d, cb)), abs(m.members[p].min_shear(d, cb)))
                         for p in parts for d in ("Fy", "Fz"))
                pu = max(max(abs(x) for x in _axial(m.members[p], cb)) for p in parts)
                h1, eq = aisc.h1_interaction(pu, phipn, mu, phimn)
                uc = max(h1, vu / phivn)
                if best is None or uc > best["uc"]:
                    best = {"lc": cb, "mu": mu, "vu": vu, "pu": pu, "h1": h1, "eq": eq, "uc": uc}
            rec = {"size": size, "span": span, "lb": lb, "phi_mn": phimn, "phi_vn": phivn, "phi_pn": phipn, **best,
                   "combo_txt": SCBF_COMBO_TXT[best["lc"]]}
            if bi in braced:
                load = beam_loads.get((lv, bi), (0.0, 0.0))
                (wd, wl), pts = (load["w"], load["pts"]) if isinstance(load, dict) else (load, [])
                sw = aisc.get(size)["W"] / 1000
                mg, rg = _simple_m_mid(span, s1 * (wd + sw) + 0.5 * wl, [(a, s1 * pd + 0.5 * pl) for a, pd, pl in pts])
                brm = m.members[f"BR_{lv}_{bi}_0"]
                Lb_ = brm.L()
                ex = _brace_expected(br, Lb_)
                h = ZS[lv] - ([0.0] + [ZS[l] for l in LV])[zi - 1]
                sin_t, cos_t = h / Lb_, (span / 2) / Lb_
                pv = (ex["T"] - ex["C_post"]) * sin_t
                ph = (ex["T"] + ex["C_post"]) * cos_t / 2
                mu23 = mg + pv * span / 4
                vu23 = rg + pv / 2
                phipn_full = aisc.phi_pn(size, span, lb)["phi_pn"]
                h1_23, eq23 = aisc.h1_interaction(ph, phipn_full, mu23, phimn)
                uc23 = max(h1_23, vu23 / phivn)
                rec["f23"] = {"T_exp": ex["T"], "C_exp": ex["C"], "C_post": ex["C_post"], "Pv_unbalanced": pv,
                              "P_axial": ph, "Mu": mu23, "Vu": vu23, "M_gravity": mg, "h1": h1_23, "eq": eq23, "uc": uc23}
                if uc23 > rec["uc"]:
                    rec.update(uc=uc23, lc="F2.3", combo_txt="AISC 341 F2.3 unbalanced (Ry Fy Ag / 0.3 x 1.14 Fcre Ag) + 1.2D+0.5L")
            out[(lv, bi)] = rec
    return out


def design_scbf(cols, beam_loads, f_e, beam_size: str, col_size: str, braced_bays: list[int], keep: str | None = None,
                basis: str = "original", girder_sizes: dict | None = None, girder_lb: dict | None = None,
                keep_girders: dict | None = None) -> dict:
    """Chevron SCBF: lightest square HSS brace (KL = full length, K = 1, KL/r <= 200, AISC 341
    F2.5b b/t limit already in the candidate filter); braces + pinned beams in PyNite.

    basis "etabs-reviewed": Timoshenko members, the girders' real point loads (beam_loads as
    {"w", "pts"}), braces checked under every combo (gravity too: braces carry gravity at the work
    point), and every girder sized in the frame per bay (girder_sizes = the gravity sizes to start
    from) for the full combo set plus the AISC 341 F2.3 chevron check; the lightest brace whose
    frame passes with its girders wins. "original": the first-issue method, unchanged."""
    if basis != "original":
        return _design_scbf_reviewed(cols, beam_loads, f_e, col_size, braced_bays, keep, girder_sizes or {},
                                     girder_lb or {}, keep_girders or {})
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


def _brace_screen_fails(m, br: str, cols) -> bool:
    """Any brace over capacity under any combo (compression E3 / tension D2 / KL/r 200), or storey
    drift over the limit - none of which a heavier girder fixes."""
    pt = aisc.phi_pn_tension(br)
    for name, mem in m.members.items():
        if not name.startswith("BR_"):
            continue
        pn = aisc.phi_pn(br, mem.L())
        if pn["kl_r"] > 200:
            return True
        for cb in SCBF_COMBOS:
            amax, amin = _axial(mem, cb)
            if max(-amin, 0.0) > pn["phi_pn"] or max(amax, 0.0) > pt:
                return True
    dxe = [0.0] + [max(abs(m.nodes[f"{c}_{z}"].DX["EUN"]) for c, _ in cols) for z in (1, 2, 3)]
    return any(SYS["y"]["Cd"] * (dxe[zi] - dxe[zi - 1]) / IE > DRIFT_LIM * STOREY_H[lv] for zi, lv in enumerate(LV, start=1))


def _design_scbf_reviewed(cols, beam_loads, f_e, col_size, braced, keep, girder_sizes, girder_lb, keep_girders) -> dict:
    s = SYS["y"]
    cands = aisc.hss_candidates()
    if keep:
        cands = [keep] + [c for c in cands if c != keep and aisc.get(c)["W"] >= aisc.get(keep)["W"]]
    beams = aisc.beam_candidates()
    last = None
    for br in cands:
        b = aisc.get(br)
        sizes = {k: v for k, v in girder_sizes.items()}
        for k, v in keep_girders.items():   # minimum change: a kept girder never gets lighter
            if k in sizes and aisc.get(v)["W"] > aisc.get(sizes[k])["W"]:
                sizes[k] = v
        screened_out = False
        for _it in range(12):
            base = max(sizes.values(), key=lambda z: aisc.get(z)["W"])
            m = _frame(cols, beam_loads, base, col_size, {"E": f_e}, base_fixed=False, pinned_beams=True,
                       braces=braced, brace_size=br, shear_def=True, beam_sizes=sizes)
            for k, v in SCBF_COMBOS.items():
                m.add_load_combo(k, v)
            m.add_load_combo("EUN", {"E": 1.0})
            m.analyze_linear(check_statics=False, check_stability=False)
            if _it == 0 and _brace_screen_fails(m, br, cols):
                screened_out = True   # brace strength / drift fail: girder sizing cannot fix it
                break
            girders = _check_scbf_girders(m, cols, beam_loads, sizes, girder_lb, braced, br)
            bad = [k for k, g in girders.items() if g["uc"] > 1.0]
            if not bad:
                break
            for k in bad:   # lightest heavier shape whose capacity covers this girder's current demands
                g = girders[k]
                w0 = aisc.get(sizes[k])["W"]
                nxt = [c for c in beams if aisc.get(c)["W"] > w0]
                for c in nxt:
                    pmn, pvn, ppn = aisc.phi_mn(c, g["lb"])["phi_mn"], aisc.phi_vn(c), aisc.phi_pn(c, g["span"], g["lb"])["phi_pn"]
                    ucs = [max(aisc.h1_interaction(g["pu"], ppn, g["mu"], pmn)[0], g["vu"] / pvn)]
                    if "f23" in g:
                        f = g["f23"]
                        ucs.append(max(aisc.h1_interaction(f["P_axial"], ppn, f["Mu"], pmn)[0], f["Vu"] / pvn))
                    if max(ucs) <= 0.97:   # small margin for the girder's own weight / stiffness change
                        sizes[k] = c
                        break
                else:
                    if nxt:
                        sizes[k] = nxt[-1]
        if screened_out:
            continue
        worst, forces = 0.0, {}
        for name, mem in m.members.items():
            if not name.startswith("BR_"):
                continue
            L = mem.L()
            pn = aisc.phi_pn(br, L)
            pt = aisc.phi_pn_tension(br)
            best = None
            for cb in SCBF_COMBOS:
                amax, amin = _axial(mem, cb)
                pc, ptn = max(-amin, 0.0), max(amax, 0.0)   # PyNite: compression negative
                uc = max(pc / pn["phi_pn"], ptn / pt)
                if best is None or uc > best[0]:
                    best = (uc, cb, max(abs(amax), abs(amin)))
            uc = max(best[0], pn["kl_r"] / 200.0)
            forces[name] = {"pu": best[2], "lc": best[1], "L": L, "phi_pn": pn["phi_pn"], "kl_r": pn["kl_r"], "uc": uc,
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
        g_ok = all(g["uc"] <= 1.0 for g in girders.values())
        last = {"brace": br, "forces": forces, "uc": worst, "drifts": drifts, "col_e": col_e,
                "expected_t": RY_HSS * aisc.FY_HSS * b["A"], "k": sum(f_e.values()) / max(dxe[3], 1e-9),
                "girders": girders, "girder_sizes": dict(sizes), "basis": "etabs-reviewed", "shear_def": True}
        if worst <= 1.0 and g_ok and max(d["ratio"] for d in drifts) <= 1.0:
            last["ok"] = True
            return last
    last["ok"] = False
    last["infeasible"] = True
    return last


def rigid_diaphragm(v: float, d: str, lines_x: dict[str, tuple[float, float]], lines_y: dict[str, tuple[float, float]],
                    cm: tuple[float, float], dims: tuple[float, float], amplify: bool = True) -> dict:
    """Rigid diaphragm, force v in direction d ("x" | "y"). lines_x: {name: (k, y)} of the X lines,
    lines_y: {name: (k, x)} of the Y lines. Torsion is resisted by both directions' lines
    (J = sum kx (y - cry)^2 + sum ky (x - crx)^2). Each line in direction d gets the worse of
    +/- 5% accidental eccentricity (x Ax). Ax (ASCE 7-16 12.8.4.3) = (dmax / 1.2 davg)^2,
    1 <= Ax <= 3, from the edge-line displacements of the rigid-body motion; the torsional
    irregularity ratio dmax / davg is returned (Table 12.3-1 1a > 1.2, 1b > 1.4)."""
    same, other = (lines_x, lines_y) if d == "x" else (lines_y, lines_x)
    cm_d = cm[1] if d == "x" else cm[0]          # coordinate perpendicular to the force
    dim = dims[1] if d == "x" else dims[0]
    ks = sum(k for k, _ in same.values())
    cr = sum(k * c for k, c in same.values()) / ks
    ko = sum(k for k, _ in other.values()) or 1.0
    cro = sum(k * c for k, c in other.values()) / ko if other else 0.0
    j = sum(k * (c - cr) ** 2 for k, c in same.values()) + sum(k * (c - cro) ** 2 for k, c in other.values())
    j = j or 1.0

    def solve(ax: float) -> tuple[dict, float]:
        shares, ratio = {}, 1.0
        for sgn in (1, -1):
            e = cm_d - cr + sgn * 0.05 * ax * dim
            dl = {n: (v / ks + v * e * (c - cr) / j) for n, (k, c) in same.items()}   # line displacement x k / k
            disp = list(dl.values())
            if len(disp) >= 2:
                ratio = max(ratio, max(abs(x) for x in disp) / (sum(abs(x) for x in disp) / len(disp)))
            for n, (k, c) in same.items():
                shares[n] = max(shares.get(n, 0.0), k * dl[n])
        return shares, ratio

    shares, ratio = solve(1.0)
    ax = 1.0
    if amplify and ratio > 1.2:
        ax = min(3.0, max(1.0, (ratio / 1.2) ** 2))
        shares, _ = solve(ax)
    return {"shares": shares, "cr": cr, "j": j, "torsion_ratio": ratio, "Ax": ax,
            "irregularity": "1b extreme" if ratio > 1.4 else ("1a" if ratio > 1.2 else "none")}


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
