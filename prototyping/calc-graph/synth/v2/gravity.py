"""Gravity design: beams, girders, columns, footings, piers, base plates, shear tabs.

Every load is carried as unfactored components (D, L, Lr) all the way down, and combined
only at the member being checked (ASCE 7-16 2.3.1: 1.4D, 1.2D+1.6L+0.5Lr, 1.2D+1.6Lr+0.5L;
service D+L and L for deflection). Beams and girders are simple spans (shear-tab ends),
designed non-composite (the deck braces the top flange of beams; girders are braced at
the infill framing points) - composite action conservatively ignored for strength and
stiffness. No live load reduction (conservative). Lightest passing W shape is chosen.
"""
from __future__ import annotations

import math

from . import aisc
from .model import (FTG_TOP, LEVELS, PARAPET_FT, PIER_TOP, STOREY_H, WALL_PSF, Member, Topology, area_at)

E_KSF = aisc.E * 144.0
COMBOS = {"LC1": (1.4, 0.0, 0.0), "LC2": (1.2, 1.6, 0.5), "LC3": (1.2, 0.5, 1.6)}  # D, L, Lr
COMBO_TXT = {"LC1": "1.4D", "LC2": "1.2D+1.6L+0.5Lr", "LC3": "1.2D+1.6Lr+0.5L"}
LV_Z = {l: z for l, _, z in LEVELS}


def V(d=0.0, l=0.0, lr=0.0):
    return [d, l, lr]


def vadd(a, b, k=1.0):
    return [a[0] + k * b[0], a[1] + k * b[1], a[2] + k * b[2]]


def fac(v, c):
    f = COMBOS[c]
    return v[0] * f[0] + v[1] * f[1] + v[2] * f[2]


def gov(v) -> tuple[float, str]:
    best = max(COMBOS, key=lambda c: fac(v, c))
    return fac(v, best), best


# ------------------------------------------------------------------ member loads
def line_loads(m: Member, topo: Topology) -> list[float]:
    """Distributed load components (klf) from area strips + perimeter wall (no self-weight)."""
    w = V()
    for width, x, y in m.trib:
        ar = area_at(topo.layout.areas, m.level, x, y)
        if ar:
            w = vadd(w, V(ar.d_psf * width / 1000, ar.l_psf * width / 1000, ar.lr_psf * width / 1000))
    if m.wall:
        h = (STOREY_H[m.level] / 2 + (STOREY_H.get(_above(m.level), 0) / 2 if _above(m.level) else PARAPET_FT))
        w = vadd(w, V(WALL_PSF * h / 1000))
    return w


def _above(lv: str) -> str | None:
    order = [l for l, _, _ in LEVELS]
    i = order.index(lv)
    return order[i + 1] if i + 1 < len(order) else None


def simple_beam(L: float, w: list[float], pts: list[tuple[float, list[float]]], n: int = 48) -> dict:
    """Simple span: reactions, moment and deflection shape PER UNIT EI, per load component."""
    xs = [L * k / n for k in range(n + 1)]
    out = {"xs": xs, "Ri": [0.0, 0.0, 0.0], "Rj": [0.0, 0.0, 0.0], "M": [[0.0] * 3 for _ in xs],
           "d": [[0.0] * 3 for _ in xs]}
    for c in range(3):
        wc = w[c]
        out["Ri"][c] += wc * L / 2
        out["Rj"][c] += wc * L / 2
        for k, x in enumerate(xs):
            out["M"][k][c] += wc * x * (L - x) / 2
            out["d"][k][c] += wc * x * (L**3 - 2 * L * x**2 + x**3) / 24
        for a, p in pts:
            pc = p[c]
            if not pc:
                continue
            b = L - a
            out["Ri"][c] += pc * b / L
            out["Rj"][c] += pc * a / L
            for k, x in enumerate(xs):
                out["M"][k][c] += pc * b * x / L if x <= a else pc * a * (L - x) / L
                if x <= a:
                    out["d"][k][c] += pc * b * x * (L**2 - b**2 - x**2) / (6 * L)
                else:
                    xr = L - x
                    out["d"][k][c] += pc * a * xr * (L**2 - a**2 - xr**2) / (6 * L)
    return out


_SB_CACHE: dict = {}


def _sb_pair(L, w, pts):
    key = (round(L, 6), tuple(round(x, 9) for x in w), tuple((round(a, 6), tuple(round(x, 9) for x in p)) for a, p in pts))
    hit = _SB_CACHE.get(key)
    if hit is None:
        if len(_SB_CACHE) > 20000:
            _SB_CACHE.clear()
        hit = _SB_CACHE[key] = (simple_beam(L, w, pts), simple_beam(L, V(1.0), []))
    return hit


def check_beam(size: str, L: float, w: list[float], pts: list, lb: float, roof: bool, cb: float = 1.0) -> dict:
    s = aisc.get(size)
    sw = s["W"] / 1000.0
    base, unit = _sb_pair(L, w, pts)
    Mk = [[bm[0] + sw * um[0], bm[1], bm[2]] for bm, um in zip(base["M"], unit["M"])]
    dk = [[bd[0] + sw * ud[0], bd[1], bd[2]] for bd, ud in zip(base["d"], unit["d"])]
    Ri = [base["Ri"][0] + sw * unit["Ri"][0], base["Ri"][1], base["Ri"][2]]
    Rj = [base["Rj"][0] + sw * unit["Rj"][0], base["Rj"][1], base["Rj"][2]]
    best = {}
    for c in COMBOS:
        f = COMBOS[c]
        mu = max(f[0] * m[0] + f[1] * m[1] + f[2] * m[2] for m in Mk)
        vu = max(fac(Ri, c), fac(Rj, c))
        if not best or mu > best["mu"]:
            best.update(mu=mu, lc_m=c)
        if vu > best.get("vu", 0):
            best.update(vu=vu, lc_v=c)
    flex = aisc.phi_mn(size, lb, cb)
    phivn = aisc.phi_vn(size)
    ei = E_KSF * s["Ix"] / 20736.0
    d_l = max(d[2] if roof else d[1] for d in dk) / ei * 12
    d_t = max(sum(d) for d in dk) / ei * 12
    d_d = max(d[0] for d in dk) / ei * 12
    lim_l, lim_t = L * 12 / (240 if roof else 360), L * 12 / 240
    ratios = {"flexure": best["mu"] / flex["phi_mn"], "shear": best["vu"] / phivn,
              "defl_live": d_l / lim_l, "defl_total": d_t / lim_t}
    g = max(ratios, key=ratios.get)
    return {"size": size, "span": L, "w": w, "sw": sw, "mu": best["mu"], "lc_m": best["lc_m"], "vu": best["vu"],
            "lc_v": best["lc_v"], "phi_mn": flex["phi_mn"], "flex_limit": flex["limit"], "flex_eq": flex["eq"],
            "lb": lb, "lp": flex["lp_ft"], "lr": flex["lr_ft"], "phi_vn": phivn, "d_live": d_l, "d_total": d_t,
            "d_dead": d_d, "lim_live": lim_l, "lim_total": lim_t, "live_ratio": "L/240" if roof else "L/360",
            "ratios": ratios, "uc": ratios[g], "governs": g,
            "lc": best["lc_m"] if g == "flexure" else (best["lc_v"] if g == "shear" else "D+L" if g == "defl_total" else "L"),
            "Ri": Ri, "Rj": Rj, "ok": ratios[g] <= 1.0}


def camber_studs(r: dict) -> tuple[float, int]:
    cam = 0.0
    if r["span"] >= 25 and r["d_dead"] > 0.75:
        cam = max(0.75, math.floor(0.8 * r["d_dead"] * 4) / 4)
    return cam, int(round(r["span"]))


def size_beam(L, w, pts, lb, roof, candidates=None, start: str | None = None) -> dict:
    cands = candidates or aisc.beam_candidates()
    if start:
        sw = aisc.get(start)["W"]
        cands = [c for c in cands if aisc.get(c)["W"] >= sw]
    # lower-bound screen (exact checks still decide): phiMp >= Mu and Ix >= live-deflection need,
    # both evaluated with the lightest candidate's self-weight (self-weight only grows from there)
    r0 = check_beam(cands[0], L, w, pts, lb, roof)
    zx_min = r0["mu"] / (0.9 * aisc.FY_W / 12.0) * 0.98
    s0 = aisc.get(cands[0])
    ix_min = s0["Ix"] * r0["d_live"] / r0["lim_live"] * 0.98
    screened = [c for c in cands if aisc.get(c)["Zx"] >= zx_min and aisc.get(c)["Ix"] >= ix_min] or cands
    last = None
    for c in screened:
        r = check_beam(c, L, w, pts, lb, roof)
        last = r
        if r["ok"]:
            return r
    last["ok"] = False
    last["infeasible"] = True
    return last


# ------------------------------------------------------------------ shear tabs (typical families)
BOLT_PHI_RN = 0.75 * 54.0 * 0.4418   # 3/4" A325-N single shear, J3.6: 17.9 k
PLATE_T, PLATE_FY, PLATE_FU = 0.375, 36.0, 58.0


def shear_tab_capacity(n: int) -> dict:
    """Conventional single-plate shear tab, 3/8" A36 plate, (n) 3/4" A325-N in std holes,
    3" pitch, 1-1/2" edge, e = 3" from the weld line (elastic method, Manual Part 7)."""
    e, s = 3.0, 3.0
    ys = [s * (k - (n - 1) / 2) for k in range(n)]
    ip = sum(y * y for y in ys) or 1.0
    ymax = max(abs(y) for y in ys) if n > 1 else 0.0
    # per unit R: direct 1/n vertical, moment e*ymax/ip horizontal
    per = math.hypot(1.0 / n, e * ymax / ip) if n > 1 else 1.0
    bolts = BOLT_PHI_RN / per
    lp = 3.0 * n
    yld = 1.0 * 0.6 * PLATE_FY * lp * PLATE_T
    anv = (lp - n * (13 / 16 + 1 / 16)) * PLATE_T
    rup = 0.75 * 0.6 * PLATE_FU * anv
    brg = n * 0.75 * 2.4 * 0.75 * PLATE_T * PLATE_FU / per * (1.0 / n) * n  # bearing on plate, eccentric group
    cap = min(bolts, yld, rup, brg)
    gov = min((("bolt shear (J3.6)", bolts), ("plate shear yield (J4-3)", yld), ("plate shear rupture (J4-4)", rup),
               ("bolt bearing (J3-6a)", brg)), key=lambda t: t[1])[0]
    return {"type": f"ST-{n}", "bolts": n, "phi_rn": cap, "governs": gov, "plate": f"PL3/8x{lp:.0f}", "e_in": e}


SHEAR_TABS = {n: shear_tab_capacity(n) for n in range(2, 8)}


def max_bolts(size: str) -> int:
    s = aisc.get(size)
    t_in = s["d"] - 2 * (s["tf"] + 0.75)    # approx. T distance
    return max(2, min(7, int((t_in - 1.0) // 3)))


def assign_tab(size: str, ru: float) -> dict:
    nmax = max_bolts(size)
    for n in range(2, nmax + 1):
        if SHEAR_TABS[n]["phi_rn"] >= ru:
            return {**SHEAR_TABS[n], "uc": ru / SHEAR_TABS[n]["phi_rn"], "ru": ru, "special": False}
    t = SHEAR_TABS[nmax]
    return {**t, "type": f"ST-{nmax}*", "uc": ru / t["phi_rn"], "ru": ru, "special": True}


# ------------------------------------------------------------------ gravity framing
def design_framing(topo: Topology, fixed_sizes: dict[str, str] | None = None) -> dict:
    """Design every gravity-designed member (smf_beam members get loads only; their size
    comes from the lateral design). Returns {member id: result}."""
    fixed_sizes = fixed_sizes or {}
    mem = topo.members
    supported_on: dict[str, list[str]] = {k: [] for k in mem}
    for m in mem.values():
        for s in (m.i, m.j):
            if "member" in s:
                supported_on[s["member"]].append(m.id)
    order, seen = [], set()

    def visit(k):
        if k in seen:
            return
        seen.add(k)
        for c in supported_on[k]:
            visit(c)
        order.append(k)

    for k in sorted(mem):
        visit(k)
    pts: dict[str, list] = {k: [] for k in mem}
    res: dict[str, dict] = {}
    for k in order:
        m = mem[k]
        w = line_loads(m, topo)
        roof = m.level == "RF"
        if m.kind == "girder":
            ats = sorted(a for a, _ in pts[k])
            stops = [0.0] + ats + [m.span]
            lb = max(b - a for a, b in zip(stops, stops[1:]))
        else:
            lb = 0.0
        if k in fixed_sizes:
            r = check_beam(fixed_sizes[k], m.span, w, pts[k], lb, roof)
        else:
            r = size_beam(m.span, w, pts[k], lb, roof)
        r["pts"] = [(a, p) for a, p in pts[k]]
        r["camber"], r["studs"] = camber_studs(r)
        res[k] = r
        for end, s in (("Ri", m.i), ("Rj", m.j)):
            if "member" in s:
                pts[s["member"]].append((s["a"], r[end]))
    return res


def reactions_to_columns(topo: Topology, framing: dict) -> dict[str, dict]:
    """col -> level -> list of (member id, direction 'x'|'y', side sign, reaction vector)."""
    out: dict[str, dict] = {c: {} for c in topo.columns}
    for k, m in topo.members.items():
        r = framing[k]
        for end, s, other in (("Ri", m.i, m.p2), ("Rj", m.j, m.p1)):
            if "col" not in s:
                continue
            c = s["col"]
            cx, cy = topo.columns[c]["x"], topo.columns[c]["y"]
            dx, dy = other[0] - cx, other[1] - cy
            direction = "x" if abs(dx) >= abs(dy) else "y"
            side = 1 if (dx if direction == "x" else dy) > 0 else -1
            out[c].setdefault(m.level, []).append((k, direction, side, r[end]))
    return out


# ------------------------------------------------------------------ columns
def column_demands(topo: Topology, rx: dict, size: str) -> list[dict]:
    """Per storey segment (1 = L1-L2 ...): Pu, Mux, Muy for each combo; eccentric shear-tab
    reactions (e = d/2 + 3 in to flanges / 3 in to web), pattern live on one side."""
    s = aisc.get(size)
    ex, ey = (s["d"] / 2 + 3.0) / 12, 3.0 / 12
    levels = [l for l, _, _ in LEVELS]
    sw = s["W"] / 1000.0
    joint_m: dict[str, dict] = {}
    p_at: dict[str, list] = {}
    for lv in levels:
        tot = V()
        sides = {("x", 1): V(), ("x", -1): V(), ("y", 1): V(), ("y", -1): V()}
        for _, d, sd, r in rx.get(lv, []):
            tot = vadd(tot, r)
            sides[(d, sd)] = vadd(sides[(d, sd)], r)
        p_at[lv] = tot
        jm = {}
        for c in COMBOS:
            fd, fl, flr = COMBOS[c]
            mm = {}
            for d, e in (("x", ex), ("y", ey)):
                a, b = sides[(d, 1)], sides[(d, -1)]
                # dead balanced, live/roof live on the heavier side only (pattern)
                ua = fd * a[0] + fl * a[1] + flr * a[2] - fd * b[0]
                ub = fd * b[0] + fl * b[1] + flr * b[2] - fd * a[0]
                mm[d] = max(abs(ua), abs(ub)) * e
            jm[c] = mm
        joint_m[lv] = jm
    segs = []
    for si in range(len(levels)):
        above = levels[si:]
        p = V()
        for lv in above:
            p = vadd(p, p_at[lv])
        h_above = sum(STOREY_H[l] for l in above)
        p = vadd(p, V(sw * h_above))
        top = levels[si]
        share = 0.5 if si < len(levels) - 1 else 1.0
        rows = {}
        for c in COMBOS:
            rows[c] = {"pu": fac(p, c), "mux": joint_m[top][c]["x"] * share, "muy": joint_m[top][c]["y"] * share}
        segs.append({"storey": si + 1, "h": STOREY_H[top], "P": p, "combos": rows, "top": top})
    return segs


def check_column(size: str, segs: list[dict], extra: dict | None = None) -> dict:
    """H1-1 per storey and combo, K = 1.0, KL = storey height both axes. extra = seismic
    axial etc. added by the lateral design: {storey: {combo name: (pu, mux, muy)}}."""
    worst = None
    for sg in segs:
        pn = aisc.phi_pn(size, sg["h"])
        flex = aisc.phi_mn(size, sg["h"], 1.0)
        mny = aisc.phi_mny(size)
        combos = {c: (v["pu"], v["mux"], v["muy"]) for c, v in sg["combos"].items()}
        if extra and sg["storey"] in extra:
            combos.update(extra[sg["storey"]])
        for c, (pu, mux, muy) in combos.items():
            ratio, eq = aisc.h1_interaction(pu, pn["phi_pn"], mux, flex["phi_mn"], muy, mny)
            if not worst or ratio > worst["uc"]:
                worst = {"uc": ratio, "eq": eq, "lc": c, "storey": sg["storey"], "pu": pu, "mux": mux, "muy": muy,
                         "phi_pn": pn["phi_pn"], "kl_r": pn["kl_r"], "phi_mnx": flex["phi_mn"], "phi_mny": mny}
    return {"size": size, **worst, "ok": worst["uc"] <= 1.0}


def size_column(topo, rx, extra_fn=None, candidates=None, min_size: str | None = None) -> dict:
    cands = candidates or aisc.column_candidates()
    if min_size:
        cands = [c for c in cands if aisc.get(c)["W"] >= aisc.get(min_size)["W"]]
    last = None
    for c in cands:
        segs = column_demands(topo, rx, c)
        r = check_column(c, segs, extra_fn(c) if extra_fn else None)
        r["segs"] = segs
        last = r
        if r["ok"]:
            return r
    last["infeasible"] = True
    return last


# ------------------------------------------------------------------ foundations
FC = 4.0          # ksi
FY_R = 60.0
QA = 4.0          # ksf net allowable
CONC = 0.150
PIERS = {"P-1": {"b": 24.0, "bars": "8-#8", "as": 6.32}, "P-2": {"b": 30.0, "bars": "12-#9", "as": 12.0}}
BASE_PLATES = {  # A1 in2, plate, rods
    "BP-1": {"B": 14.0, "N": 14.0, "t": 0.75, "rods": "(4) 3/4\" F1554 Gr 36", "use": "gravity"},
    "BP-2": {"B": 18.0, "N": 18.0, "t": 1.0, "rods": "(4) 3/4\" F1554 Gr 36", "use": "gravity"},
    "BP-3": {"B": 24.0, "N": 26.0, "t": 1.5, "rods": "(8) 1-1/4\" F1554 Gr 55", "use": "SMF fixed base"},
    "BP-4": {"B": 20.0, "N": 20.0, "t": 1.25, "rods": "(4) 1\" F1554 Gr 55 + shear lug", "use": "SCBF base"},
}


def pier_capacity(p: str) -> float:
    d = PIERS[p]
    ag = d["b"] ** 2
    return 0.65 * 0.80 * (0.85 * FC * (ag - d["as"]) + FY_R * d["as"])


def base_plate_capacity(bp: str, pier: str) -> float:
    d = BASE_PLATES[bp]
    a1 = d["B"] * d["N"]
    a2 = PIERS[pier]["b"] ** 2
    return 0.65 * 0.85 * FC * a1 * min(2.0, math.sqrt(max(1.0, a2 / a1)))


def assign_base_plate(size: str, pu: float, roles: list[str], pier: str) -> dict:
    s = aisc.get(size)
    if "smf_column" in roles:
        opts = ["BP-3"]
    elif "scbf_column" in roles:
        opts = ["BP-4"]
    else:
        opts = ["BP-1", "BP-2"]
    for bp in opts:
        d = BASE_PLATES[bp]
        if d["B"] >= s["bf"] + 3 - 1e-6 and d["N"] >= s["d"] + 3 - 1e-6:
            cap = base_plate_capacity(bp, pier)
            if cap >= pu:
                return {"type": bp, "phi_pp": cap, "pu": pu, "uc": pu / cap, "special": False, **d}
    bp = opts[-1]
    cap = base_plate_capacity(bp, pier)
    return {"type": bp + "*", "phi_pp": cap, "pu": pu, "uc": pu / cap, "special": True, **BASE_PLATES[bp]}


def design_footing(p_service: float, pu: float, pier: str) -> dict:
    """Square spread footing: bearing (ASD, net qa), punching (ACI 318-19 22.6, beta=1) and
    one-way shear (22.5) at factored qu, thickness in 2" steps from 18"."""
    c = PIERS[pier]["b"] / 12
    b = max(4.0, math.ceil(math.sqrt(p_service / QA) * 2) / 2)
    q = p_service / b**2
    qu = pu / b**2
    for h_in in range(18, 62, 2):
        d = (h_in - 4.0) / 12
        bo = 4 * (c + d)
        vu_p = pu - qu * (c + d) ** 2
        phivc_p = 0.75 * 4 * math.sqrt(FC * 1000) * bo * 12 * d * 12 / 1000
        x = (b - c) / 2 - d
        vu_1 = qu * b * max(0.0, x)
        phivc_1 = 0.75 * 2 * math.sqrt(FC * 1000) * b * 12 * d * 12 / 1000
        if vu_p <= phivc_p and vu_1 <= phivc_1:
            break
    mu = qu * b * ((b - c) / 2) ** 2 / 2
    as_req = max(mu * 12 / (0.9 * FY_R * 0.9 * d * 12), 0.0018 * b * 12 * h_in)
    nbar = max(4, math.ceil(as_req / 0.60))   # #7 bars
    ratios = {"bearing": q / QA, "punching": vu_p / phivc_p, "one_way": vu_1 / phivc_1}
    g = max(ratios, key=ratios.get)
    return {"B": b, "h_in": h_in, "q": q, "qa": QA, "qu": qu, "vu_p": vu_p, "phivc_p": phivc_p, "vu_1": vu_1,
            "phivc_1": phivc_1, "mu": mu, "as": as_req, "bars": f"({nbar}) #7 EW", "ratios": ratios, "uc": ratios[g],
            "governs": g, "p_service": p_service, "pu": pu, "pier": pier, "ok": ratios[g] <= 1.0 + 1e-9}


def design_grade_beam(L: float, wall: bool, m_end: float, axial_t: float = 0.0) -> dict:
    """18" wide grade beam, depth from 24/30/36/42/48: wall load (15 psf x 7 ft) + self
    weight, SMF base moment shared to the adjacent segments, tie axial."""
    for h in (24, 30, 36, 42, 48):
        wd = (WALL_PSF * 7.0 / 1000 if wall else 0.0) + CONC * 1.5 * h / 12
        wu = 1.2 * wd
        mu = wu * L**2 / 8 + m_end
        vu = wu * L / 2 + (2 * m_end / L if L else 0)
        d = h - 3.5
        rho_max = 0.0181   # tension-controlled for f'c 4 / fy 60
        phimn_max = 0.9 * rho_max * 18 * d * FY_R * (d - 0.59 * rho_max * FY_R * d / FC) / 12
        phivn = 0.75 * (2 * math.sqrt(FC * 1000) * 18 * d / 1000 + 0.40 * FY_R * d / 6)   # + #4 2-leg @ 6"
        ratios = {"flexure": mu / phimn_max, "shear": vu / phivn}
        n_tie = 0
        if axial_t:   # continuous #8 tie bars, phi 0.9, at least 4
            n_tie = max(4, math.ceil(axial_t / (0.9 * FY_R * 0.79)))
        if max(ratios.values()) <= 1.0:
            break
    g = max(ratios, key=ratios.get)
    return {"b_in": 18, "h_in": h, "span": L, "mu": mu, "vu": vu, "phimn": phimn_max, "phivn": phivn,
            "ratios": ratios, "uc": ratios[g], "governs": g, "m_end": m_end, "axial_t": axial_t,
            "tie_bars": f"({n_tie}) #8 cont." if axial_t else "", "ok": ratios[g] <= 1.0}


def pier_height() -> float:
    return PIER_TOP - FTG_TOP
