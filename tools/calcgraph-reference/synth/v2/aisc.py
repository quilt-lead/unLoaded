"""AISC shapes (v16.0 database values) and AISC 360-16 member strengths.

The table is a subset of the AISC Shapes Database v16.0 (W8..W36 and square HSS 4..12),
obtained via github.com/cmccomb/structural-shapes (`data/aisc-v16.csv`). The CSV is AISC
data (AISC Shapes Database v16.0, (C) American Institute of Steel Construction), NOT MIT
licensed: the MIT licence in that repository covers only its author's code. Provenance and
status in data/SOURCES.md. `verify()` checks it against values quoted
independently from the AISC Steel Construction Manual for 14 shapes.

Units: kip, in, ksi unless a name says ft or kip-ft. All strengths are LRFD (phi).
"""
from __future__ import annotations

import csv
import math
import os
from functools import lru_cache

E = 29000.0
G = 11200.0
FY_W = 50.0      # A992
FY_HSS = 50.0    # A500 Gr C rectangular HSS
_HERE = os.path.dirname(__file__)
TABLE = os.path.join(_HERE, "data", "aisc_v16_subset.csv")

# Independent check values (AISC Manual, 16th ed., Table 1-1 / 1-12): A in2, d in, Ix in4, Zx in3, ry in
REFERENCE = {
    "W14X90": (26.5, 14.0, 999, 157, 3.70),
    "W16X26": (7.68, 15.7, 301, 44.2, 1.12),
    "W18X35": (10.3, 17.7, 510, 66.5, 1.22),
    "W21X44": (13.0, 20.7, 843, 95.4, 1.26),
    "W24X55": (16.2, 23.6, 1350, 134, 1.34),
    "W12X53": (15.6, 12.1, 425, 77.9, 2.48),
    "W14X68": (20.0, 14.0, 722, 115, 2.46),
    "W12X19": (5.57, 12.2, 130, 24.7, 0.822),
    "W24X68": (20.1, 23.7, 1830, 177, 1.87),
    "W16X31": (9.13, 15.9, 375, 54.0, 1.17),
    "W10X33": (9.71, 9.73, 171, 38.8, 1.94),
    "W27X84": (24.8, 26.7, 2850, 244, 2.07),
    "W8X31": (9.13, 8.00, 110, 30.4, 2.02),
    "HSS6X6X3/8": (7.58, 6.0, 39.5, 15.8, 2.28),
}


def _f(v):
    return float(v) if v not in ("", None, "–", "-") else None


@lru_cache(maxsize=1)
def shapes() -> dict[str, dict]:
    out = {}
    with open(TABLE, newline="") as fh:
        for r in csv.DictReader(fh):
            s = {k: (_f(v) if k not in ("Type", "AISC_Manual_Label") else v) for k, v in r.items()}
            s["name"] = r["AISC_Manual_Label"]
            if s["Type"] == "HSS":
                s["d"] = s["Ht"]
                s["bf"] = s["B"]
            out[s["name"]] = s
    return out


def get(name: str) -> dict:
    return shapes()[name.upper()]


def verify() -> list[dict]:
    rows = []
    for name, ref in REFERENCE.items():
        s = get(name)
        got = (s["A"], s["d"], s["Ix"], s["Zx"], s["ry"])
        errs = [abs(g - r) / r for g, r in zip(got, ref)]
        rows.append({"shape": name, "ref": ref, "table": got, "max_rel_err": max(errs), "ok": max(errs) <= 0.01})
    return rows


# ----------------------------------------------------------------- candidate lists
def beam_candidates() -> list[str]:
    """Beam/girder shapes, lightest first (W10..W36, ties broken by depth)."""
    c = [s for s in shapes().values() if s["Type"] == "W" and 10 <= s["d"] <= 37.5 and s["bf"] <= 1.05 * s["d"]]
    return [s["name"] for s in sorted(c, key=lambda s: (s["W"], s["d"]))]


def column_candidates() -> list[str]:
    """Column shapes: W10/W12/W14 whose web and flange are non-slender in axial compression
    (h/tw taken as (d - 2 tf)/tw, which overstates h, so the screen is conservative)."""
    out = []
    for s in shapes().values():
        if s["Type"] != "W" or not s["name"].startswith(("W10X", "W12X", "W14X")):
            continue
        if (s["d"] - 2 * s["tf"]) / s["tw"] > 1.49 * math.sqrt(E / FY_W) or s["bf"] / (2 * s["tf"]) > 0.56 * math.sqrt(E / FY_W):
            continue
        out.append(s)
    return [s["name"] for s in sorted(out, key=lambda s: (s["W"], -s["d"]))]


def hss_candidates() -> list[str]:
    c = [s for s in shapes().values() if s["Type"] == "HSS" and s["b"] / s["tdes"] <= 1.40 * math.sqrt(E / FY_HSS)]
    return [s["name"] for s in sorted(c, key=lambda s: (s["W"], s["B"]))]


# ----------------------------------------------------------------- AISC 360-16 strengths
def phi_mn(name: str, lb_ft: float, cb: float = 1.0) -> dict:
    """Chapter F2 (LTB) and F3 (noncompact flange) strong-axis flexure, phi = 0.90. kip-ft."""
    s = get(name)
    fy = FY_W
    mp = fy * s["Zx"]
    lam_f = s["bf"] / (2 * s["tf"])
    lpf, lrf = 0.38 * math.sqrt(E / fy), 1.0 * math.sqrt(E / fy)
    lb = lb_ft * 12.0
    lp = 1.76 * s["ry"] * math.sqrt(E / fy)
    c = 1.0
    jc = s["J"] * c / (s["Sx"] * s["ho"])
    lr = 1.95 * s["rts"] * (E / (0.7 * fy)) * math.sqrt(jc + math.sqrt(jc**2 + 6.76 * (0.7 * fy / E) ** 2))
    if lb <= lp:
        mn_ltb, ltb = mp, "yielding (Lb <= Lp)"
    elif lb <= lr:
        mn_ltb = min(mp, cb * (mp - (mp - 0.7 * fy * s["Sx"]) * (lb - lp) / (lr - lp)))
        ltb = "inelastic LTB (F2-2)"
    else:
        fcr = cb * math.pi**2 * E / (lb / s["rts"]) ** 2 * math.sqrt(1 + 0.078 * jc * (lb / s["rts"]) ** 2)
        mn_ltb, ltb = min(mp, fcr * s["Sx"]), "elastic LTB (F2-3)"
    if lam_f > lpf:  # F3-1 noncompact flange
        mn_flb = mp - (mp - 0.7 * fy * s["Sx"]) * (lam_f - lpf) / (lrf - lpf)
    else:
        mn_flb = mp
    mn = min(mn_ltb, mn_flb)
    gov = ltb if mn_ltb <= mn_flb else "flange local buckling (F3-1)"
    return {"phi_mn": 0.9 * mn / 12.0, "mp_kft": mp / 12.0, "lp_ft": lp / 12, "lr_ft": lr / 12, "lb_ft": lb_ft,
            "limit": gov, "eq": "F2-1" if gov.startswith("yield") else gov.split("(")[-1].rstrip(")")}


def phi_vn(name: str) -> float:
    """G2.1(a): rolled I-shapes with h/tw <= 2.24 sqrt(E/Fy): phi = 1.0, Cv1 = 1.0. kips."""
    s = get(name)
    return 1.0 * 0.6 * FY_W * s["d"] * s["tw"]


def fcr(kl_r: float, fy: float) -> float:
    fe = math.pi**2 * E / kl_r**2
    return (0.658 ** (fy / fe)) * fy if kl_r <= 4.71 * math.sqrt(E / fy) else 0.877 * fe


def phi_pn(name: str, klx_ft: float, kly_ft: float | None = None) -> dict:
    """Chapter E3 flexural buckling, phi = 0.90 (non-slender sections only). kips."""
    s = get(name)
    kly_ft = klx_ft if kly_ft is None else kly_ft
    fy = FY_HSS if s["Type"] == "HSS" else FY_W
    klr = max(klx_ft * 12 / s["rx"], kly_ft * 12 / s["ry"])
    return {"phi_pn": 0.9 * fcr(klr, fy) * s["A"], "kl_r": klr}


def phi_pn_tension(name: str) -> float:
    s = get(name)
    fy = FY_HSS if s["Type"] == "HSS" else FY_W
    return 0.9 * fy * s["A"]


def h1_interaction(pu: float, phi_pn_: float, mux: float, phi_mnx: float, muy: float = 0.0, phi_mny: float = 1e9) -> tuple[float, str]:
    r = pu / phi_pn_
    if r >= 0.2:
        return r + 8 / 9 * (mux / phi_mnx + muy / phi_mny), "H1-1a"
    return r / 2 + (mux / phi_mnx + muy / phi_mny), "H1-1b"


def phi_mny(name: str) -> float:
    s = get(name)
    return 0.9 * min(FY_W * s["Zy"], 1.6 * FY_W * s["Sy"]) / 12.0
