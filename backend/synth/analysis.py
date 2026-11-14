"""Member forces with PyNite (open-source FEA), plus the simple capacity checks the
synthetic calc package reports. Units inside: kN, m. Reports convert to kips/ft.

Every beam, girder and the cantilever is its own small PyNite model (two nodes, one
member). Infill-beam reactions are applied to the girders as point loads, girder and
beam reactions are summed onto the columns, and each column is a PyNite stick model
braced at every level. Footings are sized from the column service reactions.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from Pynite import FEModel3D

from . import shapes
from .building import Building, El

E_KPA = 200e6
G_KPA = 77e6
STEEL_KN_M3 = 77.0
FLOOR_D, FLOOR_L = 5.5, 2.39  # kPa (8" PT slab 100 psf + 15 psf SDL; 50 psf office)
ROOF_D, ROOF_L = 1.2, 0.96  # kPa (deck + roofing; 20 psf roof live)
Q_ALLOW = 143.6  # kPa = 3,000 psf
FTG_THK = {"F1": 0.457, "F2": 0.508, "F3": 0.610}  # 18", 20", 24"


@dataclass
class MemberResult:
    key: str
    mark: str
    section: str
    span: float
    mu: float  # kN m (factored, max abs)
    vu: float  # kN
    r_u: dict[str, float]  # end -> factored reaction kN
    r_s: dict[str, float]  # end -> service reaction kN
    phi_mn: float  # kN m
    ratio: float
    wu: float  # kN/m factored line load


@dataclass
class Results:
    members: dict[str, MemberResult] = field(default_factory=dict)
    columns: dict[str, dict] = field(default_factory=dict)
    footings: dict[str, dict] = field(default_factory=dict)  # by mark
    st1: dict = field(default_factory=dict)
    mf1: dict = field(default_factory=dict)
    brace: dict = field(default_factory=dict)
    base_plate: dict = field(default_factory=dict)
    cant: dict = field(default_factory=dict)


def _supports(b: Building) -> dict[str, dict[str, str]]:
    """member key -> {'i': support key, 'j': support key} from the load-path truth."""
    nxt: dict[str, list[str]] = {}
    for s, d in b.load_path:
        nxt.setdefault(s, []).append(d)
    out: dict[str, dict[str, str]] = {}
    for s, ds in nxt.items():
        for d in ds:
            if d.startswith("cx:"):
                end = d.rsplit(":", 1)[1]
                out.setdefault(s, {})[end] = nxt[d][0]
            elif s.startswith("cant:"):
                out.setdefault(s, {})["i"] = d
    return out


def _beam_model(span: float, sec: dict, wd: float, wl: float, pts: list[tuple[float, float, float]],
                cantilever: bool = False, tip: tuple[float, float] = (0.0, 0.0)):
    m = FEModel3D()
    m.add_node("I", 0, 0, 0)
    m.add_node("J", span, 0, 0)
    m.add_material("A992", E_KPA, G_KPA, 0.3, STEEL_KN_M3)
    m.add_section("S", sec["A"], sec.get("Iy", sec.get("I")), sec.get("Ix", sec.get("I")), sec["J"])
    m.add_member("M", "I", "J", "A992", "S")
    if cantilever:
        m.def_support("I", True, True, True, True, True, True)
    else:
        m.def_support("I", True, True, True, True, False, False)
        m.def_support("J", False, True, True, False, False, False)
    m.add_member_dist_load("M", "FY", -wd, -wd, case="D")
    if wl:
        m.add_member_dist_load("M", "FY", -wl, -wl, case="L")
    for x, pd, pl in pts:
        m.add_member_pt_load("M", "FY", -pd, x, case="D")
        if pl:
            m.add_member_pt_load("M", "FY", -pl, x, case="L")
    if cantilever and (tip[0] or tip[1]):
        m.add_node_load("J", "FY", -tip[0], case="D")
        if tip[1]:
            m.add_node_load("J", "FY", -tip[1], case="L")
    if not wl and not any(pl for _, _, pl in pts) and not tip[1]:
        m.add_member_dist_load("M", "FY", 0.0, 0.0, case="L")
    m.add_load_combo("U", {"D": 1.2, "L": 1.6})
    m.add_load_combo("S", {"D": 1.0, "L": 1.0})
    m.analyze_linear(check_statics=False)
    mem = m.members["M"]
    mu = max(abs(mem.max_moment("Mz", "U")), abs(mem.min_moment("Mz", "U")))
    vu = max(abs(mem.max_shear("Fy", "U")), abs(mem.min_shear("Fy", "U")))
    r_u = {"i": m.nodes["I"].RxnFY["U"], "j": m.nodes["J"].RxnFY["U"]}
    r_s = {"i": m.nodes["I"].RxnFY["S"], "j": m.nodes["J"].RxnFY["S"]}
    return mu, vu, r_u, r_s


def run(b: Building) -> Results:
    res = Results()
    sup = _supports(b)
    members = [e for e in b.elements if e.ifc_class == "IfcBeam"]
    order = {"infill": 0, "grid": 1, "girder": 2, "cant": 1}
    members.sort(key=lambda e: order[e.meta["kind"]])
    girder_pts: dict[str, list[tuple[float, float, float]]] = {}

    def loads(e: El) -> tuple[float, float]:
        sec = shapes.w_si(e.geom["section"])
        sw = sec["A"] * STEEL_KN_M3
        roof = e.meta["level"] == "R"
        trib = e.meta.get("trib", 0.0)
        d, l = (ROOF_D, ROOF_L) if roof else (FLOOR_D, FLOOR_L)
        return d * trib + sw, l * trib

    for e in members:
        sec_name = e.geom["section"]
        sec = shapes.w_si(sec_name)
        span = e.meta["span"]
        wd, wl = loads(e)
        if e.meta["kind"] == "cant":
            mu, vu, r_u, r_s = _beam_model(span, sec, wd, wl, [], cantilever=True, tip=(5.0, 0.0))
        else:
            pts = girder_pts.get(e.key, [])
            mu, vu, r_u, r_s = _beam_model(span, sec, wd, wl, pts)
        phi_mn = shapes.phi_mn_kft(sec_name) / shapes.KNM_TO_KFT
        res.members[e.key] = MemberResult(e.key, e.mark or "", sec_name, span, mu, vu, r_u, r_s, phi_mn, mu / phi_mn,
                                          1.2 * wd + 1.6 * wl)
        if e.meta["kind"] == "infill":
            # push reactions onto the supporting girders as point loads (D and L split by ratio)
            for end in ("i", "j"):
                g = sup[e.key][end]
                gel = b.by_key[g]
                x = e.geom["p1"][1] - gel.geom["p1"][1]
                rs = r_s[end]
                d_frac = wd / (wd + wl)
                girder_pts.setdefault(g, []).append((x, rs * d_frac, rs * (1 - d_frac)))

    # ---- columns: collect reactions by level ----
    col_loads: dict[str, dict[str, list[float]]] = {}
    z_of = {"2": 4.2, "3": 8.4, "R": 12.6}
    for e in members:
        r = res.members[e.key]
        for end, s in sup.get(e.key, {}).items():
            if s.startswith("col:"):
                lv = e.meta["level"]
                slot = col_loads.setdefault(s, {}).setdefault(lv, [0.0, 0.0])
                slot[0] += r.r_u[end]
                slot[1] += r.r_s[end]
    mf_mu = 0.0
    for e in members:
        if e.meta["kind"] == "grid" and e.meta["j"] == 3:
            r = res.members[e.key]
            mf_mu = max(mf_mu, r.wu * r.span**2 / 12.0)
    for c in (e for e in b.elements if e.ifc_class == "IfcColumn"):
        sec_name = c.geom["section"]
        sec = shapes.w_si(sec_name)
        m = FEModel3D()
        zs = [0.0, 4.2, 8.4, 12.6]
        for n, z in enumerate(zs):
            m.add_node(f"N{n}", 0, 0, z)
        m.add_material("A992", E_KPA, G_KPA, 0.3, STEEL_KN_M3)
        m.add_section("S", sec["A"], sec["Iy"], sec["Ix"], sec["J"])
        for n in range(3):
            m.add_member(f"M{n}", f"N{n}", f"N{n + 1}", "A992", "S")
        m.def_support("N0", True, True, True, True, False, False)
        for n in (1, 2, 3):
            m.def_support(f"N{n}", True, True, False, False, False, False)
        lv = col_loads.get(c.key, {})
        sw = sec["A"] * STEEL_KN_M3 * 12.6
        for n, key in ((1, "2"), (2, "3"), (3, "R")):
            pu, ps = lv.get(key, [0.0, 0.0])
            # split service into D/L so the U combo reproduces the factored sum: D = (1.6 S - U) / 0.4
            d = (1.6 * ps - pu) / 0.4
            l_ = ps - d
            m.add_node_load(f"N{n}", "FZ", -d, case="D")
            m.add_node_load(f"N{n}", "FZ", -l_, case="L")
        m.add_node_load("N1", "FZ", -sw, case="D")
        m.add_load_combo("U", {"D": 1.2, "L": 1.6})
        m.add_load_combo("S", {"D": 1.0, "L": 1.0})
        m.analyze_linear(check_statics=False)
        pu = m.nodes["N0"].RxnFZ["U"]
        ps = m.nodes["N0"].RxnFZ["S"]
        d, bf, tw, tf, A, Ix, Iy, Zx, rx, ry = shapes.W[sec_name]
        phi_pn = shapes.phi_pn_kips(A, ry, 4.2 / 0.0254) / shapes.KN_TO_KIP
        ratio = pu / phi_pn
        info = {"mark": c.mark, "section": sec_name, "pu": pu, "ps": ps, "phi_pn": phi_pn, "ratio": ratio,
                "grid": c.psets["Structural"]["Grid"], "mf": c.meta["j"] == 3}
        if info["mf"]:
            phi_mn = shapes.phi_mn_kft(sec_name) / shapes.KNM_TO_KFT
            mu = mf_mu * 0.5
            info["mu"] = mu
            info["pm"] = ratio + 8 / 9 * mu / phi_mn if ratio >= 0.2 else ratio / 2 + mu / phi_mn
        res.columns[c.key] = info

    # ---- footings, sized per mark from the largest service reaction ----
    for f in (e for e in b.elements if e.ifc_class == "IfcFooting"):
        ck = "col:" + f.key.split(":", 1)[1]
        ps = res.columns[ck]["ps"]
        slot = res.footings.setdefault(f.mark, {"ps": 0.0, "pu": 0.0, "count": 0})
        slot["count"] += 1
        if ps > slot["ps"]:
            slot.update(ps=ps, pu=res.columns[ck]["pu"], col=res.columns[ck]["mark"])
    for mark, s in res.footings.items():
        thk = FTG_THK[mark]
        need = (s["ps"] + 0.0) / (Q_ALLOW - thk * 23.6)
        side_ft = math.ceil(math.sqrt(need) * shapes.M_TO_FT * 2) / 2  # round up to 6"
        s.update(side_ft=side_ft, side=side_ft / shapes.M_TO_FT, thk=thk,
                 q=s["ps"] / (side_ft / shapes.M_TO_FT) ** 2 + thk * 23.6)

    # ---- connections ----
    st_members = [k for k in res.members if any(
        e.mark == "ST-1" and e.key.startswith(f"cx:{k}:") for e in b.elements if e.ifc_class == "IfcPlate")]
    gov = max(st_members, key=lambda k: max(res.members[k].r_u.values()))
    ru = max(res.members[gov].r_u.values())
    bolts = 4 if ru * shapes.KN_TO_KIP <= 4 * 17.9 else 5
    res.st1 = {"ru": ru, "gov": res.members[gov].mark, "gov_level": b.by_key[gov].storey, "bolts": bolts,
               "phi_rn": bolts * 17.9 / shapes.KN_TO_KIP, "count": sum(1 for e in b.elements if e.mark == "ST-1")}
    mf_members = [e for e in members if e.meta["kind"] == "grid" and e.meta["j"] == 3]
    res.mf1 = {"mu": mf_mu, "vu": max(max(res.members[e.key].r_u.values()) for e in mf_members),
               "count": sum(1 for e in b.elements if e.mark == "MF-1")}

    # ---- bracing: wind story shear on the grid A frame (half the building width) ----
    q_wind = 1.10  # kPa design wind pressure, simplified
    theta = math.atan2(4.2 - 0.8, 7.0 - 0.26)
    shears = []
    for s in range(3):
        height_above = 12.6 - [0.0, 4.2, 8.4][s] - 2.1
        v = 1.6 * q_wind * height_above * 32.0 / 2 / 2  # two braced bays share the frame line
        shears.append(v)
    pu_br = max(shears) / math.cos(theta) / 2
    hs = shapes.HSS["HSS6X6X3/8"]
    kl = math.hypot(4.2 - 0.8, 7.0 - 0.26) / 0.0254
    res.brace = {"pu": pu_br, "phi_pn": shapes.phi_pn_kips(hs[2], hs[4], kl) / shapes.KN_TO_KIP, "klr": kl / hs[4],
                 "shears": shears}

    # ---- base plates ----
    pmax = max(c["pu"] for c in res.columns.values())
    res.base_plate = {"pu": pmax, "a1": 0.4572**2, "phi_pp": 0.65 * 0.85 * 27.58e3 * 0.4572**2}  # f'c 4 ksi
    cr = res.members.get("cant:2:E/2")
    if cr:
        res.cant = {"mu": cr.mu, "vu": cr.vu, "phi_mn": cr.phi_mn, "r": cr.r_u["i"]}
    return res


def apply_footing_sizes(b: Building, res: Results) -> None:
    """Footing geometry comes from the footing calc - keeps model and calc consistent."""
    for f in (e for e in b.elements if e.ifc_class == "IfcFooting"):
        s = res.footings[f.mark]
        x, y = f.geom["centre"]
        top = f.geom["top"]
        half = s["side"] / 2
        f.geom = {"kind": "box", "min": (x - half, y - half, top - s["thk"]), "max": (x + half, y + half, top)}
        ft = int(s["side_ft"])
        inch = int(round((s["side_ft"] - ft) * 12))
        f.object_type = f"Spread footing {ft}'-{inch}\" x {ft}'-{inch}\""
        f.psets["Structural"]["Size"] = f"{ft}'-{inch}\" x {ft}'-{inch}\" x {round(s['thk'] / 0.0254)}\""
