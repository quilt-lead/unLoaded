"""Regenerated calc pages for "redo calcs directly".

    render(rerun_result, base, new, path) -> {record id: {"page", "bbox", "recomputed", "mismatches"}}

Writes a Mathcad Prime style PDF of re-run calc sheets: one block per re-run record, grouped by
calc sheet. The math on the page is rendered FROM the Python that computes it: every check is a
handcalcs-decorated function (AISC 360-16 / ACI 318-19 equations, the same formulas as
synth/v2/aisc.py and synth/v2/gravity.py), called with pint quantities built from the record's
NEW values. handcalcs turns each function body + its substituted values into LaTeX, KaTeX
(the pinned npm package, run by node: WeasyPrint does not run JavaScript) turns the LaTeX into
HTML, and WeasyPrint lays the HTML out as the PDF.

Every recomputed demand / capacity / UC is compared with the re-run record (which is rounded:
values to 0.1, demand/capacity/uc to 0.001). A difference beyond rounding is printed loudly to
stderr AND shown in red on the block - never hidden.

The method label on every block is rerun_result["method"] (the calc-graph re-run of the synth v2
design code - not ETABS / RAM / RISA). Output is byte-deterministic for the same input: fixed
PDF metadata and identifier, no clock reads (the date is taken from rerun_result["created_at"]).

Setup: `npm ci` in backend/calcgraph/recalc_pages_assets (katex 0.19.1; run automatically on
first use if node_modules is missing). WeasyPrint needs pango/cairo (Homebrew on macOS: found in
/opt/homebrew/lib or /usr/local/lib without DYLD_* variables, see recalc_pages_layout.import_weasyprint).
Layout (parallel, batched, cached by content) is recalc_pages_layout.py.
"""
from __future__ import annotations

import html
import json
import math
import os
import subprocess
import sys
from math import pi, sqrt

import handcalcs
import handcalcs.handcalcs as _hc_core
import pint
from handcalcs.decorator import handcalc

from synth.v2 import aisc
from synth.v2 import gravity as G

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "recalc_pages_assets")
KATEX_DIST = os.path.join(ASSETS, "node_modules", "katex", "dist")

# Title block: the same fictional firm / project as the calc package (synth/v2/calc_pdf_v2.py).
# Copied, not imported, so this module does not pull matplotlib in; _title_block_matches() in
# the self-check below asserts they still agree.
FIRM_FULL = "Corliss Vane Structural Engineers"
FIRM_ADDR = "410 Wharf Street, Suite 300, Port Ellery, CA"
PROJECT = "Harbor View Office"
CITY = "Port Ellery, CA"
JOB = "2611-04"
BY, CHK = "JTR", "MOL"

# ---------------------------------------------------------------------------------- units
U = pint.UnitRegistry(auto_reduce_dimensions=True)
U.formatter.default_format = "~L"   # handcalcs str()s quantities nested inside sqrt(): keep them as LaTeX symbols
kip, ft, inch, psi, lbf = U.kip, U.ft, U.inch, U.psi, U.lbf
ksi = kip / inch**2
ksf = kip / ft**2
klf = kip / ft
kcf = kip / ft**3


def Q(v, unit):
    return U.Quantity(float(v), unit)


# preferred display unit per dimensionality: keep a value in any listed unit, otherwise convert
# to the first one (e.g. ksi * in^3 -> kip*ft, psi * in^2 -> kip, ft / in -> plain number)
_PREF = [(kip, [kip]), (inch, [ft, inch]), (kip * ft, [kip * ft]), (ksi, [ksi, ksf, psi]), (klf, [klf]),
         (inch**2, [inch**2, ft**2]), (inch**3, [inch**3]), (inch**4, [inch**4]), (kcf, [kcf])]
_PREF = [((1.0 * d).dimensionality, [U.Unit(str(x)) if not isinstance(x, pint.Unit) else x for x in opts]) for d, opts in _PREF]


def pref(q):
    if not isinstance(q, U.Quantity):
        return q
    if q.dimensionless:
        return q.to("dimensionless")
    dim = q.dimensionality
    for d, opts in _PREF:
        if d == dim:
            if q.units in opts:
                return q
            return q.to(opts[0])
    return q


_UNIT_TEX = [
    (r"\frac{\mathrm{kip}}{\mathrm{in}^{2}}", r"\mathrm{ksi}"),
    (r"\frac{\mathrm{kip}}{\mathrm{ft}^{2}}", r"\mathrm{ksf}"),
    (r"\frac{\mathrm{kip}}{\mathrm{ft}^{3}}", r"\mathrm{kcf}"),
    (r"\frac{\mathrm{kip}}{\mathrm{ft}}", r"\mathrm{klf}"),
    (r"\mathrm{ft} \cdot \mathrm{kip}", r"\mathrm{kip} \cdot \mathrm{ft}"),
    (r"\mathrm{in} \cdot \mathrm{kip}", r"\mathrm{kip} \cdot \mathrm{in}"),
]


def tex_units(s: str) -> str:
    for a, b in _UNIT_TEX:
        s = s.replace(a, b)
    return s


def fq(q, n=2) -> str:
    """LaTeX for a value with its unit (the same formatting handcalcs uses, after pref())."""
    if isinstance(q, U.Quantity):
        q = pref(q)
        mag = float(q.magnitude)
        if q.dimensionless:
            return f"{mag:.{n}f}"
        return tex_units(f"{mag:.{n}f}\\ {q.units:~L}")
    if isinstance(q, (int, float)):
        return f"{float(q):.{n}f}"
    return r"\text{" + str(q).replace("_", r"\_") + "}"


def mag(q, unit=None) -> float:
    if isinstance(q, U.Quantity):
        return float(q.to(unit).magnitude) if unit is not None else float(q.to("dimensionless").magnitude)
    return float(q)


# handcalcs configuration (global for this process; this module is its only user)
handcalcs.set_option("preferred_string_formatter", "~L")
handcalcs.set_option("greek_exclusions", ["psi"])
handcalcs.set_option("custom_symbols", {
    "phiM_n": r"\phi M_{n}", "phiV_n": r"\phi V_{n}", "phiP_n": r"\phi P_{n}", "phiR_n": r"\phi R_{n}",
    "phiP_p": r"\phi P_{p}", "phiP_t": r"\phi P_{t}", "phiM_nx": r"\phi M_{nx}", "phiM_ny": r"\phi M_{ny}",
    "phiR_nv": r"\phi r_{nv}", "phiR_bolt": r"\phi R_{n,bolt}", "phiR_y": r"\phi R_{n,yield}",
    "phiR_rup": r"\phi R_{n,rupt}", "phiR_brg": r"\phi R_{n,brg}", "phiV_cp": r"\phi V_{c,punch}",
    "phiV_c1": r"\phi V_{c,1way}", "phiP_nt": r"\phi P_{n,tension}",
    "KL_r": r"KL/r", "KL_lim": r"4.71\sqrt{E/F_{y}}",
    "M_n_LTB": r"M_{n,LTB}", "M_n_FLB": r"M_{n,FLB}", "M_n2": r"M_{n,F2\text{-}2}", "F_cr_b": r"F_{cr,LTB}",
    "f_c": r"f'_{c}", "lambda_c": r"\lambda", "V_up": r"V_{u,punch}", "V_u1": r"V_{u,1way}",
    "w_u1": r"w_{u,1.4D}", "w_u2": r"w_{u,1.2D+1.6L+0.5Lr}", "w_u3": r"w_{u,1.2D+1.6Lr+0.5L}",
    "w_live": r"w_{live}", "w_tot": r"w_{total}", "w_SW": r"w_{sw}", "Delta_L": r"\Delta_{live}",
    "Delta_T": r"\Delta_{total}", "Delta_Lall": r"\Delta_{live,allow}", "Delta_Tall": r"\Delta_{total,allow}",
    "A_bolt": r"A_{b}", "I_p": r"I_{p}", "c_unit": r"c_{1}", "UC": r"\mathrm{UC}",
    "rho_max": r"\rho_{max}", "lambda_f": r"\lambda_{f}", "lambda_pf": r"\lambda_{pf}", "lambda_rf": r"\lambda_{rf}", "w_wall": r"w_{wall}", "w_conc": r"w_{c}", "A_st": r"A_{st}",
})

_orig_latex_repr = _hc_core.latex_repr


def _latex_repr(item, use_scientific_notation, precision, preferred_formatter):
    if isinstance(item, U.Quantity):
        item = pref(item)
        if isinstance(item.magnitude, int):
            item = item * 1.0
    return _orig_latex_repr(item, use_scientific_notation, precision, preferred_formatter)


_hc_core.latex_repr = _latex_repr   # display-only: pick readable units (values are unchanged)


def hc(fn, *args):
    """Call a handcalcs function -> (LaTeX body without $$, locals)."""
    latex, loc = fn(*args)
    body = latex.strip()
    if body.startswith("$$"):
        body = body[2:]
    if body.endswith("$$"):
        body = body[:-2]
    return tex_units(body.strip()), loc


def split_lines(body: str) -> list[str]:
    """handcalcs puts every line of a function in one aligned block, so one long line widens the
    result column of all the others; give each line its own aligned block instead."""
    inner = body
    if inner.startswith("\\begin{aligned}"):
        inner = inner[len("\\begin{aligned}"):]
    if inner.rstrip().endswith("\\end{aligned}"):
        inner = inner.rstrip()[: -len("\\end{aligned}")]
    lines, cur = [], []
    for ln in inner.split("\n"):
        if ln.strip() == "\\\\":
            if cur:
                lines.append("\n".join(cur))
            cur = []
        else:
            cur.append(ln)
    if any(c.strip() for c in cur):
        lines.append("\n".join(cur))
    out = []
    for ln in lines:
        ln = ln.strip()
        while ln.endswith("\\\\"):
            ln = ln[:-2].rstrip()
        if ln:
            out.append("\\begin{aligned}" + ln + "\\end{aligned}")
    return out


# ================================================================ handcalcs check functions
# Each body is the equation as printed. Branching (which equation applies) is decided in Python
# around these calls and printed as a governing-case line, exactly like a Mathcad worksheet.
P = dict(jupyter_display=False)


@handcalc(**P, precision=3)
def beam_loads_uniform(w_D, w_SW, w_L, w_Lr, L):
    w_u1 = 1.4 * (w_D + w_SW)
    w_u2 = 1.2 * (w_D + w_SW) + 1.6 * w_L + 0.5 * w_Lr
    w_u3 = 1.2 * (w_D + w_SW) + 1.6 * w_Lr + 0.5 * w_L
    w_u = max(w_u1, w_u2, w_u3)
    M_u = w_u * L**2 / 8
    V_u = w_u * L / 2
    return locals()


@handcalc(**P, precision=2)
def beam_deflection_uniform(w_live, w_tot, L, E, I_x, n_L):
    Delta_L = 5 * w_live * L**4 / (384 * E * I_x)
    Delta_Lall = L / n_L
    Delta_T = 5 * w_tot * L**4 / (384 * E * I_x)
    Delta_Tall = L / 240
    return locals()


@handcalc(**P, precision=2)
def f2_plastic(F_y, Z_x, S_x):
    M_p = F_y * Z_x
    M_r = 0.7 * F_y * S_x
    return locals()


@handcalc(**P, precision=2)
def f2_lp(r_y, E, F_y):
    L_p = 1.76 * r_y * sqrt(E / F_y)
    return locals()


@handcalc(**P, precision=2)
def f2_lengths(r_y, r_ts, E, F_y, J, c, S_x, h_o):
    L_p = 1.76 * r_y * sqrt(E / F_y)
    L_r = 1.95 * r_ts * (E / (0.7 * F_y)) * sqrt(J * c / (S_x * h_o) + sqrt((J * c / (S_x * h_o))**2 + 6.76 * (0.7 * F_y / E)**2))
    return locals()


@handcalc(**P, precision=2)
def f2_1(M_p):
    M_n_LTB = M_p
    return locals()


@handcalc(**P, precision=2)
def f2_2(C_b, M_p, M_r, L_b, L_p, L_r):
    M_n2 = C_b * (M_p - (M_p - M_r) * (L_b - L_p) / (L_r - L_p))
    M_n_LTB = min(M_n2, M_p)
    return locals()


@handcalc(**P, precision=2)
def f2_3(C_b, E, L_b, r_ts, J, c, S_x, h_o, M_p):
    F_cr_b = C_b * pi**2 * E / (L_b / r_ts)**2 * sqrt(1 + 0.078 * J * c / (S_x * h_o) * (L_b / r_ts)**2)
    M_n_LTB = min(F_cr_b * S_x, M_p)
    return locals()


@handcalc(**P, precision=2)
def f3_slenderness(b_f, t_f, E, F_y):
    lambda_f = b_f / (2 * t_f)
    lambda_pf = 0.38 * sqrt(E / F_y)
    lambda_rf = 1.0 * sqrt(E / F_y)
    return locals()


@handcalc(**P, precision=2)
def f3_1(M_p, M_r, lambda_f, lambda_pf, lambda_rf):
    M_n_FLB = M_p - (M_p - M_r) * (lambda_f - lambda_pf) / (lambda_rf - lambda_pf)
    return locals()


@handcalc(**P, precision=2)
def flexure_design(phi_b, M_n_LTB, M_n_FLB):
    M_n = min(M_n_LTB, M_n_FLB)
    phiM_n = phi_b * M_n
    return locals()


@handcalc(**P, precision=2)
def g2_1(phi_v, F_y, d, t_w, C_v1):
    A_w = d * t_w
    phiV_n = phi_v * 0.6 * F_y * A_w * C_v1
    return locals()


@handcalc(**P, precision=2)
def e3_slenderness(K, L, r_x, r_y, E, F_y):
    KL_rx = K * L / r_x
    KL_ry = K * L / r_y
    KL_r = max(KL_rx, KL_ry)
    F_e = pi**2 * E / KL_r**2
    KL_lim = 4.71 * sqrt(E / F_y)
    return locals()


@handcalc(**P, precision=2)
def e3_2(F_y, F_e, A_g, phi_c):
    F_cr = 0.658**(F_y / F_e) * F_y
    phiP_n = phi_c * F_cr * A_g
    return locals()


@handcalc(**P, precision=2)
def e3_3(F_e, A_g, phi_c):
    F_cr = 0.877 * F_e
    phiP_n = phi_c * F_cr * A_g
    return locals()


@handcalc(**P, precision=2)
def f6_minor(phi_b, F_y, Z_y, S_y):
    M_ny = min(F_y * Z_y, 1.6 * F_y * S_y)
    phiM_ny = phi_b * M_ny
    return locals()


@handcalc(**P, precision=3)
def h1_1a(P_u, phiP_n, M_ux, phiM_nx, M_uy, phiM_ny):
    r_P = P_u / phiP_n
    UC = r_P + 8 / 9 * (M_ux / phiM_nx + M_uy / phiM_ny)
    return locals()


@handcalc(**P, precision=3)
def h1_1b(P_u, phiP_n, M_ux, phiM_nx, M_uy, phiM_ny):
    r_P = P_u / phiP_n
    UC = r_P / 2 + (M_ux / phiM_nx + M_uy / phiM_ny)
    return locals()


@handcalc(**P, precision=2)
def d2_1(phi_t, F_y, A_g):
    phiP_nt = phi_t * F_y * A_g
    return locals()


@handcalc(**P, precision=3)
def ftg_bearing(P_s, B, q_a):
    q = P_s / B**2
    return locals()


@handcalc(**P, precision=2)
def ftg_punching(P_u, B, c, h, cover, f_c, psi, phi_v):
    d = h - cover
    q_u = P_u / B**2
    b_o = 4 * (c + d)
    V_up = P_u - q_u * (c + d)**2
    phiV_cp = phi_v * 4 * sqrt(f_c / psi) * psi * b_o * d
    return locals()


@handcalc(**P, precision=2)
def ftg_oneway(q_u, B, c, d, f_c, psi, phi_v):
    x = (B - c) / 2 - d
    V_u1 = q_u * B * x
    phiV_c1 = phi_v * 2 * sqrt(f_c / psi) * psi * B * d
    return locals()


@handcalc(**P, precision=2)
def j8_bearing(phi_c, f_c, B_p, N_p, b_pier):
    A_1 = B_p * N_p
    A_2 = b_pier**2
    phiP_p = phi_c * 0.85 * f_c * A_1 * min(2, sqrt(A_2 / A_1))
    return locals()


@handcalc(**P, precision=2)
def aci_22_4(phi_c, f_c, f_y, b, A_st):
    A_g = b**2
    phiP_n = phi_c * 0.80 * (0.85 * f_c * (A_g - A_st) + f_y * A_st)
    return locals()


@handcalc(**P, precision=2)
def gb_demand(w_wall, w_conc, b, h, L, M_end):
    w_D = w_wall + w_conc * b * h
    w_u = 1.2 * w_D
    M_u = w_u * L**2 / 8 + M_end
    V_u = w_u * L / 2 + 2 * M_end / L
    return locals()


@handcalc(**P, precision=4)
def gb_capacity(b, h, cover, rho_max, f_y, f_c, psi, A_v, s, phi_b, phi_v):
    d = h - cover
    phiM_n = phi_b * rho_max * b * d * f_y * (d - 0.59 * rho_max * f_y * d / f_c)
    phiV_n = phi_v * (2 * sqrt(f_c / psi) * psi * b * d + A_v * f_y * d / s)
    return locals()


@handcalc(**P, precision=3)
def tab_bolt_group(n, s, e, phiR_nv):
    y_max = s * (n - 1) / 2
    I_p = s**2 * n * (n**2 - 1) / 12
    c_unit = sqrt((1 / n)**2 + (e * y_max / I_p)**2)
    phiR_bolt = phiR_nv / c_unit
    return locals()


@handcalc(**P, precision=2)
def tab_plate(n, s, t_p, F_yp, F_up, d_h, d_b, c_unit):
    L_pl = s * n
    phiR_y = 1.00 * 0.6 * F_yp * L_pl * t_p
    A_nv = (L_pl - n * d_h) * t_p
    phiR_rup = 0.75 * 0.6 * F_up * A_nv
    phiR_brg = n * 0.75 * 2.4 * d_b * t_p * F_up / c_unit
    return locals()


# ================================================================ block model
class Block:
    """One record's sheet region: inputs (with was-values), calc math, checks, old/new table."""

    def __init__(self, res: dict, method: str):
        self.res = res
        self.rid = res["record"]
        self.method = method
        self.inputs: list[tuple[str, str, str]] = []      # (latex def, was text, source)
        self.sections: list[tuple[str, str]] = []         # (heading, latex body)
        self.notes: list[str] = []                         # plain text lines (governing case etc.)
        self.checks: list[dict] = []
        self.asserts: list[dict] = []
        self.table_only = False
        self.values_rows: list[tuple[str, str, str]] = []

    # -- inputs
    def inp(self, sym: str, q, was=None, src: str = "", n=2, text=False):
        if text:
            d = rf"{sym} := \text{{{_tex_text(q)}}}"
        else:
            d = rf"{sym} := {fq(q, n)}"
        w = ""
        if was is not None:
            ws = was if isinstance(was, str) else _plain(was, n)
            now = q if isinstance(q, str) else _plain(q, n)
            if ws != now:
                w = f"was {ws}"
        self.inputs.append((d, w, src))

    def calc(self, heading: str, fn, *args):
        body, loc = hc(fn, *args)
        self.sections.append((heading, split_lines(body)))
        return loc

    def note(self, s: str):
        self.notes.append(s)

    def check(self, label: str, dem_sym: str, dem, cap_sym: str, cap, ref: str, n=1, was_uc=None):
        if isinstance(dem, U.Quantity):
            c = mag(cap, dem.units) if isinstance(cap, U.Quantity) else float(cap)
            d = float(dem.magnitude)
        else:
            d, c = float(dem), mag_any(cap)
        uc = d / c if c else float("inf")
        self.checks.append({"label": label, "tex": rf"{dem_sym} = {fq(dem, n)} \;\le\; {cap_sym} = {fq(cap, n)}",
                            "ok": uc <= 1.0 + 1e-9, "ref": ref, "uc": uc, "was_uc": was_uc})
        return uc

    def expect(self, what: str, got: float, want, tol_rel=0.01, tol_abs=0.11):
        if want is None:
            return
        ok = abs(got - want) <= max(tol_abs, tol_rel * abs(want))
        self.asserts.append({"what": what, "got": got, "want": want, "ok": ok})
        if not ok:
            print(f"RECALC MISMATCH {self.rid}: {what} recomputed {got:.4f} vs record {want:.4f}", file=sys.stderr)


def mag_any(q) -> float:
    if isinstance(q, U.Quantity):
        q = pref(q)
        return float(q.magnitude)
    return float(q)


def _plain(q, n=2) -> str:
    if isinstance(q, U.Quantity):
        q = pref(q)
        u = f"{q.units:~P}".replace("kip/in²", "ksi").replace("kip/ft²", "ksf").replace("kip/ft", "klf").replace("ft·kip", "kip·ft")
        return f"{float(q.magnitude):,.{n}f} {u}".strip()
    if isinstance(q, (int, float)):
        return f"{float(q):,.{n}f}"
    return str(q)


def _tex_text(s) -> str:
    return str(s).replace("\\", "").replace("{", "").replace("}", "").replace("_", r"\_").replace("#", r"\#").replace("%", r"\%").replace("&", r"\&").replace("\"", "''")


def _v(rec: dict | None, key: str):
    return ((rec or {}).get("values") or {}).get(key)


# ---------------------------------------------------------------- per-kind recomputation
E_S = Q(aisc.E, ksi)
FY = Q(aisc.FY_W, ksi)


def _section_inputs(b: Block, size: str, old_size: str | None, keys: list[tuple[str, str, str]]):
    s = aisc.get(size)
    so = aisc.get(old_size) if old_size and old_size != size and old_size.rstrip("*") in aisc.shapes() else None
    out = {}
    for sym, key, unit in keys:
        q = Q(s[key], unit)
        out[key] = q
        b.inp(sym, q, was=(Q(so[key], unit) if so else None), src=f"AISC Shapes v16.0, {size}", n=3 if s[key] < 10 else 1)
    return out


def flexure_block(b: Block, size: str, old_size: str | None, Lb_ft: float, cb: float = 1.0, Fy=FY) -> object:
    """AISC 360-16 F2 (LTB) + F3 (flange local buckling) for a W shape, phi_b = 0.90."""
    s = aisc.get(size)
    sx, zx = Q(s["Sx"], inch**3), Q(s["Zx"], inch**3)
    l1 = b.calc("Plastic and yield moments (F2-1, F2-2)", f2_plastic, Fy, zx, sx)
    Lb = Q(Lb_ft, ft)
    lp = f2_lp(Q(s["ry"], inch), E_S, Fy)[1]["L_p"]
    if mag(Lb, inch) <= mag(lp, inch):
        l2 = b.calc("Limiting laterally unbraced length for yielding (F2-5)", f2_lp, Q(s["ry"], inch), E_S, Fy)
    else:
        l2 = b.calc("Limiting unbraced lengths (F2-5, F2-6), c = 1.0", f2_lengths, Q(s["ry"], inch), Q(s["rts"], inch), E_S, Fy,
                    Q(s["J"], inch**4), 1.0, sx, Q(s["ho"], inch))
    lb_in, lp_in = mag(Lb, inch), mag(l2["L_p"], inch)
    lr_in = mag(l2["L_r"], inch) if "L_r" in l2 else float("inf")
    if lb_in <= lp_in:
        b.note(f"L_b = {Lb_ft:.2f} ft <= L_p = {lp_in / 12:.2f} ft: yielding governs LTB (AISC 360-16 Eq. F2-1)")
        l3 = b.calc("Lateral-torsional buckling - yielding (F2-1)", f2_1, l1["M_p"])
        eq = "F2-1"
    elif lb_in <= lr_in:
        b.note(f"L_p = {lp_in / 12:.2f} ft < L_b = {Lb_ft:.2f} ft <= L_r = {lr_in / 12:.2f} ft: inelastic LTB (AISC 360-16 Eq. F2-2)")
        l3 = b.calc(f"Lateral-torsional buckling - inelastic (F2-2), C_b = {cb:.2f}", f2_2, cb, l1["M_p"], l1["M_r"], Lb, l2["L_p"], l2["L_r"])
        eq = "F2-2"
    else:
        b.note(f"L_b = {Lb_ft:.2f} ft > L_r = {lr_in / 12:.2f} ft: elastic LTB (AISC 360-16 Eq. F2-3, F2-4)")
        l3 = b.calc(f"Lateral-torsional buckling - elastic (F2-3, F2-4), C_b = {cb:.2f}", f2_3, cb, E_S, Lb, Q(s["rts"], inch),
                    Q(s["J"], inch**4), 1.0, sx, Q(s["ho"], inch), l1["M_p"])
        eq = "F2-3"
    l4 = b.calc("Flange slenderness (Table B4.1b case 10)", f3_slenderness, Q(s["bf"], inch), Q(s["tf"], inch), E_S, Fy)
    lf, lpf = mag(l4["lambda_f"]), mag(l4["lambda_pf"])
    if lf > lpf:
        b.note(f"lambda_f = {lf:.2f} > lambda_pf = {lpf:.2f}: noncompact flange, FLB per AISC 360-16 Eq. F3-1")
        l5 = b.calc("Flange local buckling (F3-1)", f3_1, l1["M_p"], l1["M_r"], l4["lambda_f"], l4["lambda_pf"], l4["lambda_rf"])
        m_flb = l5["M_n_FLB"]
    else:
        b.note(f"lambda_f = {lf:.2f} <= lambda_pf = {lpf:.2f}: compact flange, FLB does not apply (M_n,FLB = M_p)")
        m_flb = l1["M_p"]
    l6 = b.calc("Design flexural strength, phi_b = 0.90", flexure_design, 0.9, l3["M_n_LTB"], m_flb)
    if mag(m_flb, kip * inch) < mag(l3["M_n_LTB"], kip * inch):
        eq = "F3-1"
    return l6["phiM_n"], eq


def do_beam(b: Block, res: dict):
    new, old = res["new"], res["old"]
    v, vo = new["values"], (old or {}).get("values") or {}
    size, osz = v["size"], vo.get("size")
    roof = res["calc"] in ("B3", "B4")
    b.inp("\\text{Section}", size, was=osz, src="re-run (minimum-change re-design)", text=True)
    L = Q(v["span_ft"], ft)
    b.inp("L", L, was=_q(vo.get("span_ft"), ft), src="span, re-run geometry")
    wD, wL, wLr = Q(v["w_D_klf"], klf), Q(v["w_L_klf"], klf), Q(v["w_Lr_klf"], klf)
    wsw = Q(v["self_wt_klf"], klf)
    for sym, q, k in (("w_{D}", wD, "w_D_klf"), ("w_{L}", wL, "w_L_klf"), ("w_{Lr}", wLr, "w_Lr_klf"), ("w_{sw}", wsw, "self_wt_klf")):
        b.inp(sym, q, was=_q(vo.get(k), klf), src="tributary area loads (A2)" if k != "self_wt_klf" else f"self weight {size}", n=3)
    b.inp("L_{b}", Q(v["Lb_ft"], ft), was=_q(vo.get("Lb_ft"), ft),
          src="deck braces top flange" if v["Lb_ft"] == 0 else "max spacing of framing points")
    props = _section_inputs(b, size, osz, [("d", "d", inch), ("t_{w}", "tw", inch), ("I_{x}", "Ix", inch**4)])
    E = E_S
    b.inp("F_{y}", FY, src="ASTM A992"); b.inp("E", E, src="AISC 360-16", n=0)
    npt = int(v.get("point_loads") or 0)
    if npt == 0:
        lo = b.calc("Factored uniform load and simple-span demands (ASCE 7-16 2.3.1)", beam_loads_uniform, wD, wsw, wL, wLr, L)
        Mu, Vu = lo["M_u"], lo["V_u"]
        wlive = wLr if roof else wL
        nl = 240 if roof else 360
        dl = b.calc(f"Deflection, simple span uniform load (live limit L/{nl}{' roof' if roof else ''}, total L/240)",
                    beam_deflection_uniform, wlive, wD + wsw + wL + wLr, L.to(inch), E, props["Ix"], nl)
        dL, dLa, dT, dTa = dl["Delta_L"], dl["Delta_Lall"], dl["Delta_T"], dl["Delta_Tall"]
    else:
        src = (f"re-run analysis: calc-graph gravity statics, simple span with uniform load + {npt} point load(s) "
               f"from framing members (governing combination {new.get('lc')})")
        Mu, Vu = Q(v["Mu_kft"], kip * ft), Q(v["Vu_k"], kip)
        b.inp("M_{u}", Mu, was=_q(vo.get("Mu_kft"), kip * ft), src=src, n=1)
        b.inp("V_{u}", Vu, was=_q(vo.get("Vu_k"), kip), src="re-run analysis: max end reaction, governing combination", n=1)
        dL, dT = Q(v["defl_L_in"], inch), Q(v["defl_T_in"], inch)
        dLa, dTa = Q(v["defl_L_allow_in"], inch), Q(v["defl_T_allow_in"], inch)
        b.inp(r"\Delta_{live}", dL, was=_q(vo.get("defl_L_in"), inch), src="re-run analysis: elastic deflection (superposed loads)")
        b.inp(r"\Delta_{total}", dT, was=_q(vo.get("defl_T_in"), inch), src="re-run analysis: elastic deflection (superposed loads)")
        b.note(f"Deflection limits: live L/{240 if roof else 360}, total L/240 (IBC 2021 Table 1604.3)")
    phiMn, eq = flexure_block(b, size, osz, v["Lb_ft"])
    sh = b.calc("Shear, rolled I-shape web (G2-1), h/t_w <= 2.24 sqrt(E/F_y): phi_v = 1.00, C_v1 = 1.0", g2_1, 1.0, FY,
                props["d"], props["tw"], 1.0)
    phiVn = sh["phiV_n"]
    ucs = {
        "flexure": b.check("Flexure", "M_{u}", Mu, r"\phi M_{n}", phiMn, f"AISC 360-16 Eq. {eq}", was_uc=_ratio(vo, "Mu_kft", "phiMn_kft")),
        "shear": b.check("Shear", "V_{u}", Vu, r"\phi V_{n}", phiVn, "AISC 360-16 Eq. G2-1", was_uc=_ratio(vo, "Vu_k", "phiVn_k")),
        "defl_live": b.check("Live deflection", r"\Delta_{live}", dL, r"\Delta_{allow}", dLa, f"IBC 2021 Table 1604.3 (L/{240 if roof else 360})", n=2,
                             was_uc=_ratio(vo, "defl_L_in", "defl_L_allow_in")),
        "defl_total": b.check("Total deflection", r"\Delta_{total}", dT, r"\Delta_{allow}", dTa, "IBC 2021 Table 1604.3 (L/240)", n=2,
                              was_uc=_ratio(vo, "defl_T_in", "defl_T_allow_in")),
    }
    b.expect("phiMn (kip-ft)", mag(phiMn, kip * ft), new["capacity"])
    b.expect("Mu (kip-ft)", mag(Mu, kip * ft), new["demand"])
    b.expect("Vu (kip)", mag(Vu, kip), v["Vu_k"])
    b.expect("phiVn (kip)", mag(phiVn, kip), v["phiVn_k"])
    b.expect("live deflection (in)", mag(dL, inch), v["defl_L_in"], tol_rel=0.02, tol_abs=0.011)
    b.expect("total deflection (in)", mag(dT, inch), v["defl_T_in"], tol_rel=0.02, tol_abs=0.011)
    b.expect("flexure equation", 1.0 if eq == v.get("flex_eq") else 0.0, 1.0, tol_abs=0)
    b.expect("UC (governing " + max(ucs, key=ucs.get) + ")", max(ucs.values()), new["uc"], tol_rel=0.01, tol_abs=0.006)


def do_column(b: Block, res: dict):
    new, old = res["new"], res["old"]
    v, vo = new["values"], (old or {}).get("values") or {}
    size, osz = v["size"], vo.get("size")
    s = aisc.get(size)
    hss = s["Type"] == "HSS"
    Fy = Q(aisc.FY_HSS if hss else aisc.FY_W, ksi)
    b.inp("\\text{Section}", size, was=osz, src="re-run (minimum-change re-design)", text=True)
    b.inp("KL", Q(v["KL_ft"], ft), was=_q(vo.get("KL_ft"), ft), src=f"K = 1.0, storey {v.get('storey')} height")
    src = f"re-run: {v.get('source', 'analysis')}, storey {v.get('storey')}, combination {new.get('lc')}"
    Pu, Mux, Muy = Q(v["Pu_k"], kip), Q(v["Mux_kft"], kip * ft), Q(v["Muy_kft"], kip * ft)
    b.inp("P_{u}", Pu, was=_q(vo.get("Pu_k"), kip), src=src, n=1)
    b.inp("M_{ux}", Mux, was=_q(vo.get("Mux_kft"), kip * ft), src=src, n=1)
    b.inp("M_{uy}", Muy, was=_q(vo.get("Muy_kft"), kip * ft), src=src, n=1)
    props = _section_inputs(b, size, osz, [("A_{g}", "A", inch**2), ("r_{x}", "rx", inch), ("r_{y}", "ry", inch),
                                           ("Z_{y}", "Zy", inch**3), ("S_{y}", "Sy", inch**3)])
    b.inp("F_{y}", Fy, src="ASTM A500 Gr C" if hss else "ASTM A992")
    sl = b.calc("Flexural buckling slenderness (E3-4), K = 1.0 both axes", e3_slenderness, 1.0, Q(v["KL_ft"], ft),
                props["rx"], props["ry"], E_S, Fy)
    if mag(sl["KL_r"]) <= mag(sl["KL_lim"]):
        b.note(f"KL/r = {mag(sl['KL_r']):.1f} <= 4.71 sqrt(E/Fy) = {mag(sl['KL_lim']):.1f}: inelastic buckling, Eq. E3-2")
        ax = b.calc("Critical stress (E3-2) and design axial strength (E3-1), phi_c = 0.90", e3_2, Fy, sl["F_e"], props["A"], 0.9)
        aeq = "E3-2"
    else:
        b.note(f"KL/r = {mag(sl['KL_r']):.1f} > 4.71 sqrt(E/Fy) = {mag(sl['KL_lim']):.1f}: elastic buckling, Eq. E3-3")
        ax = b.calc("Critical stress (E3-3) and design axial strength (E3-1), phi_c = 0.90", e3_3, sl["F_e"], props["A"], 0.9)
        aeq = "E3-3"
    phiPn = ax["phiP_n"]
    phiMnx, feq = flexure_block(b, size, osz, v["KL_ft"], 1.0, Fy)
    mn = b.calc("Minor-axis flexure (F6-1), phi_b = 0.90", f6_minor, 0.9, Fy, props["Zy"], props["Sy"])
    phiMny = mn["phiM_ny"]
    r = mag(Pu, kip) / mag(phiPn, kip)
    if r >= 0.2:
        b.note(f"P_u / phi P_n = {r:.3f} >= 0.2: interaction per AISC 360-16 Eq. H1-1a")
        h1 = b.calc("Combined axial and flexure (H1-1a)", h1_1a, Pu, phiPn, Mux, phiMnx, Muy, phiMny)
        heq = "H1-1a"
    else:
        b.note(f"P_u / phi P_n = {r:.3f} < 0.2: interaction per AISC 360-16 Eq. H1-1b")
        h1 = b.calc("Combined axial and flexure (H1-1b)", h1_1b, Pu, phiPn, Mux, phiMnx, Muy, phiMny)
        heq = "H1-1b"
    uc = mag(h1["UC"])
    b.check("Axial", "P_{u}", Pu, r"\phi P_{n}", phiPn, f"AISC 360-16 Eq. {aeq}, E3-1", was_uc=_ratio(vo, "Pu_k", "phiPn_k"))
    b.checks.append({"label": "Interaction", "tex": rf"\mathrm{{UC}} = {uc:.3f} \;\le\; 1.0", "ok": uc <= 1.0 + 1e-9,
                     "ref": f"AISC 360-16 Eq. {heq}", "uc": uc, "was_uc": (old or {}).get("uc")})
    b.expect("phiPn (kip)", mag(phiPn, kip), new["capacity"])
    b.expect("phiMnx (kip-ft)", mag(phiMnx, kip * ft), v["phiMnx_kft"])
    b.expect("phiMny (kip-ft)", mag(phiMny, kip * ft), v["phiMny_kft"])
    b.expect("KL/r", mag(sl["KL_r"]), v.get("KL_r"))
    b.expect("H1 equation", 1.0 if heq == v.get("eq") else 0.0, 1.0, tol_abs=0)
    b.expect("UC (H1)", uc, new["uc"], tol_rel=0.01, tol_abs=0.006)


def do_brace(b: Block, res: dict):
    new, old = res["new"], res["old"]
    v, vo = new["values"], (old or {}).get("values") or {}
    size, osz = v["size"], vo.get("size")
    Fy = Q(aisc.FY_HSS, ksi)
    b.inp("\\text{Section}", size, was=osz, src="SCBF brace (lateral design)", text=True)
    L = Q(v["L_ft"], ft)
    b.inp("L", L, was=_q(vo.get("L_ft"), ft), src="work-point length, K = 1.0")
    Pu = Q(v["Pu_k"], kip)
    b.inp("P_{u}", Pu, was=_q(vo.get("Pu_k"), kip), src=f"re-run: PyNite frame analysis, {new.get('lc')}", n=1)
    props = _section_inputs(b, size, osz, [("A_{g}", "A", inch**2), ("r_{x}", "rx", inch), ("r_{y}", "ry", inch)])
    b.inp("F_{y}", Fy, src="ASTM A500 Gr C")
    sl = b.calc("Flexural buckling slenderness (E3-4), K = 1.0", e3_slenderness, 1.0, L, props["rx"], props["ry"], E_S, Fy)
    if mag(sl["KL_r"]) <= mag(sl["KL_lim"]):
        ax = b.calc("Critical stress (E3-2) and design axial strength (E3-1), phi_c = 0.90", e3_2, Fy, sl["F_e"], props["A"], 0.9)
        aeq = "E3-2"
    else:
        ax = b.calc("Critical stress (E3-3) and design axial strength (E3-1), phi_c = 0.90", e3_3, sl["F_e"], props["A"], 0.9)
        aeq = "E3-3"
    tn = b.calc("Tensile yielding (D2-1), phi_t = 0.90", d2_1, 0.9, Fy, props["A"])
    u1 = b.check("Compression", "P_{u}", Pu, r"\phi P_{n}", ax["phiP_n"], f"AISC 360-16 Eq. {aeq}", was_uc=_ratio(vo, "Pu_k", "phiPn_k"))
    u2 = b.check("Tension", "P_{u}", Pu, r"\phi P_{n,t}", tn["phiP_nt"], "AISC 360-16 Eq. D2-1")
    klr = mag(sl["KL_r"])
    b.checks.append({"label": "Slenderness", "tex": rf"KL/r = {klr:.1f} \;\le\; 200", "ok": klr <= 200,
                     "ref": "AISC 341-16 F2.5b (KL/r <= 200)", "uc": klr / 200, "was_uc": None})
    b.expect("phiPn (kip)", mag(ax["phiP_n"], kip), new["capacity"])
    b.expect("KL/r", klr, v.get("KL_r"))
    b.expect("UC", max(u1, u2, klr / 200), new["uc"], tol_rel=0.01, tol_abs=0.006)


def _pier_of(new_recs: dict, rid: str) -> tuple[str, float, float]:
    col = rid.split(":", 1)[1]
    pr = new_recs.get(f"D-PIER:{col}")
    t = ((pr or {}).get("values") or {}).get("type") or "P-1"
    return t, G.PIERS[t]["b"], G.PIERS[t]["as"]


def do_footing(b: Block, res: dict, new_recs: dict):
    new, old = res["new"], res["old"]
    v, vo = new["values"], (old or {}).get("values") or {}
    ptype, pb, _ = _pier_of(new_recs, b.rid)
    B, h = Q(v["B_ft"], ft), Q(v["h_in"], inch)
    b.inp("B", B, was=_q(vo.get("B_ft"), ft), src="square footing, re-run (kept unless it fails)")
    b.inp("h", h, was=_q(vo.get("h_in"), inch), src="thickness, 2 in steps", n=0)
    Ps, Pu = Q(v["P_service_k"], kip), Q(v["Pu_k"], kip)
    b.inp("P_{s}", Ps, was=_q(vo.get("P_service_k"), kip), src="re-run: column base D+L+Lr (ASD; + 0.525 E where seismic)", n=1)
    b.inp("P_{u}", Pu, was=_q(vo.get("Pu_k"), kip), src="re-run: governing factored column base load", n=1)
    c = Q(pb, inch)
    b.inp("c", c, src=f"pier {ptype} ({pb:.0f} in square)", n=1)
    qa = Q(G.QA, ksf)
    b.inp("q_{a}", qa, src="geotechnical: net allowable", n=1)
    fc = Q(G.FC * 1000, psi)
    b.inp("f'_{c}", fc, src="concrete", n=0)
    b.inp("\\text{cover}", Q(4.0, inch), src="to centroid of bars", n=1)
    br = b.calc("Soil bearing (ASD, net)", ftg_bearing, Ps, B, qa)
    pu = b.calc("Two-way (punching) shear at d/2 from pier (ACI 318-19 22.6.5.2(a), beta = 1), phi = 0.75", ftg_punching,
                Pu, B, c, h, Q(4.0, inch), fc, Q(1.0, psi), 0.75)
    ow = b.calc("One-way shear at d from pier face (ACI 318-19 22.5.5.1), phi = 0.75", ftg_oneway, pu["q_u"], B, c, pu["d"], fc,
                Q(1.0, psi), 0.75)
    v1 = ow["V_u1"] if mag(ow["V_u1"], kip) > 0 else Q(0.0, kip)
    if mag(ow["V_u1"], kip) <= 0:
        b.note("critical section for one-way shear lies outside the footing: V_u,1way = 0")
    u1 = b.check("Bearing", "q", br["q"], "q_{a}", qa, "ASD net bearing, geotechnical report", n=3, was_uc=_ratio(vo, "q_ksf", "qa_ksf"))
    u2 = b.check("Punching", r"V_{u,punch}", pu["V_up"], r"\phi V_{c}", pu["phiV_cp"], "ACI 318-19 Table 22.6.5.2(a)",
                 was_uc=_ratio(vo, "vu_punch_k", "phiVc_punch_k"))
    u3 = b.check("One-way shear", r"V_{u,1way}", v1, r"\phi V_{c}", ow["phiV_c1"], "ACI 318-19 Eq. 22.5.5.1(a)",
                 was_uc=_ratio(vo, "vu_oneway_k", "phiVc_oneway_k"))
    b.expect("q (ksf)", mag(br["q"], ksf), v["q_ksf"], tol_abs=0.002)
    b.expect("Vu punching (kip)", mag(pu["V_up"], kip), v["vu_punch_k"])
    b.expect("phiVc punching (kip)", mag(pu["phiV_cp"], kip), v["phiVc_punch_k"])
    b.expect("Vu one-way (kip)", mag(v1, kip), v["vu_oneway_k"])
    b.expect("phiVc one-way (kip)", mag(ow["phiV_c1"], kip), v["phiVc_oneway_k"])
    b.expect("capacity qa B^2 (kip)", mag(qa * B**2, kip), new["capacity"])
    b.expect("UC", max(u1, u2, u3), new["uc"], tol_rel=0.01, tol_abs=0.006)


def do_base_plate(b: Block, res: dict, new_recs: dict):
    new, old = res["new"], res["old"]
    v, vo = new["values"], (old or {}).get("values") or {}
    t = v["type"].rstrip("*")
    d = G.BASE_PLATES[t]
    ptype, pb, _ = _pier_of(new_recs, b.rid)
    b.inp("\\text{Type}", f"{v['type']} {v.get('plate', '')}, {v.get('rods', '')}", was=(f"{vo.get('type')} {vo.get('plate', '')}, {vo.get('rods', '')}" if vo else None),
          src="typical base plate (E5)", text=True)
    Pu = Q(v["Pu_k"], kip)
    b.inp("P_{u}", Pu, was=_q(vo.get("Pu_k"), kip), src="re-run: column base factored load", n=1)
    b.inp("B_{p}", Q(d["B"], inch), src=f"{t}", n=1); b.inp("N_{p}", Q(d["N"], inch), src=f"{t}", n=1)
    b.inp("b_{pier}", Q(pb, inch), src=f"pier {ptype}", n=1)
    b.inp("f'_{c}", Q(G.FC, ksi), src="pier concrete", n=1)
    bb = b.calc("Concrete bearing on the pier (J8-2), phi_c = 0.65", j8_bearing, 0.65, Q(G.FC, ksi), Q(d["B"], inch), Q(d["N"], inch), Q(pb, inch))
    u = b.check("Concrete bearing", "P_{u}", Pu, r"\phi P_{p}", bb["phiP_p"], "AISC 360-16 Eq. J8-2", was_uc=_ratio(vo, "Pu_k", "phiPp_k"))
    b.expect("phiPp (kip)", mag(bb["phiP_p"], kip), new["capacity"])
    b.expect("UC", u, new["uc"], tol_rel=0.01, tol_abs=0.006)


def do_pier(b: Block, res: dict):
    new, old = res["new"], res["old"]
    v, vo = new["values"], (old or {}).get("values") or {}
    t = v["type"]
    d = G.PIERS[t]
    b.inp("\\text{Type}", f"{t} {d['b']:.0f}x{d['b']:.0f}, {d['bars']}", was=(f"{vo.get('type')} {vo.get('b_in', 0):.0f}x{vo.get('b_in', 0):.0f}, {vo.get('bars')}" if vo else None),
          src="pier schedule (D2)", text=True)
    Pu = Q(v["Pu_k"], kip)
    b.inp("P_{u}", Pu, was=_q(vo.get("Pu_k"), kip), src="re-run: column base factored load", n=1)
    b.inp("A_{st}", Q(d["as"], inch**2), src=d["bars"], n=2)
    b.inp("f'_{c}", Q(G.FC, ksi), src="concrete", n=1); b.inp("f_{y}", Q(G.FY_R, ksi), src="ASTM A615 Gr 60", n=0)
    pc = b.calc("Tied column axial strength (ACI 318-19 22.4.2.2, Table 22.4.2.1), phi = 0.65", aci_22_4, 0.65, Q(G.FC, ksi),
                Q(G.FY_R, ksi), Q(d["b"], inch), Q(d["as"], inch**2))
    u = b.check("Axial", "P_{u}", Pu, r"\phi P_{n,max}", pc["phiP_n"], "ACI 318-19 Eq. 22.4.2.2", was_uc=_ratio(vo, "Pu_k", "phiPn_k"))
    b.expect("phiPn (kip)", mag(pc["phiP_n"], kip), new["capacity"])
    b.expect("UC", u, new["uc"], tol_rel=0.01, tol_abs=0.006)


def do_grade_beam(b: Block, res: dict, topo_gbs: dict):
    new, old = res["new"], res["old"]
    v, vo = new["values"], (old or {}).get("values") or {}
    gid = b.rid.split(":", 1)[1]
    # whether the beam carries the perimeter wall is a fact of the re-run design's topology (the
    # lateral scheme decides the grade-beam lines), never a module constant restated here
    if gid not in topo_gbs:
        raise KeyError(f"grade beam {gid} is not in the re-run design's topology")
    wall = bool(topo_gbs[gid]["wall"])
    bw, h = Q(v["b_in"], inch), Q(v["h_in"], inch)
    L = Q(v["span_ft"], ft)
    b.inp("b", bw, was=_q(vo.get("b_in"), inch), src="grade beam width", n=0)
    b.inp("h", h, was=_q(vo.get("h_in"), inch), src="depth (24/30/36/42/48)", n=0)
    b.inp("L", L, was=_q(vo.get("span_ft"), ft), src="re-run geometry: footing to footing")
    Mend = Q(v["M_end_kft"], kip * ft)
    b.inp("M_{end}", Mend, was=_q(vo.get("M_end_kft"), kip * ft), src="re-run: SMF base moment shared to adjacent segments" if v["M_end_kft"] else "no frame base moment", n=1)
    ww = Q(G.WALL_PSF * 7.0 / 1000 if wall else 0.0, klf)
    b.inp("w_{wall}", ww, src="15 psf x 7 ft perimeter wall" if wall else "interior line: no wall", n=3)
    b.inp("w_{c}", Q(G.CONC, kcf), src="normal-weight concrete", n=3)
    dm = b.calc("Demands: 1.2D + end moment (ASCE 7-16 2.3.1)", gb_demand, ww, Q(G.CONC, kcf), bw, h, L, Mend)
    cp = b.calc("Capacity at rho_max (tension-controlled) and shear with #4 2-leg @ 6 in (ACI 318-19 22.2, 22.5), phi_b = 0.90, phi_v = 0.75",
                gb_capacity, bw, h, Q(3.5, inch), G_RHO, Q(G.FY_R, ksi), Q(G.FC * 1000, psi), Q(1.0, psi), Q(0.40, inch**2), Q(6.0, inch), 0.9, 0.75)
    u1 = b.check("Flexure", "M_{u}", dm["M_u"], r"\phi M_{n}", cp["phiM_n"], "ACI 318-19 22.2 (rho_max, 21.2.2)", was_uc=_ratio(vo, "Mu_kft", "phiMn_kft"))
    u2 = b.check("Shear", "V_{u}", dm["V_u"], r"\phi V_{n}", cp["phiV_n"], "ACI 318-19 Eq. 22.5.1.1, 22.5.8.5.3", was_uc=_ratio(vo, "Vu_k", "phiVn_k"))
    if v.get("tie_k"):
        b.note(f"tie axial {v['tie_k']:.1f} k carried by {v.get('tie_bars')} (0.9 x 60 ksi x 0.79 in2 each)")
    b.expect("Mu (kip-ft)", mag(dm["M_u"], kip * ft), new["demand"])
    b.expect("phiMn (kip-ft)", mag(cp["phiM_n"], kip * ft), new["capacity"])
    b.expect("Vu (kip)", mag(dm["V_u"], kip), v["Vu_k"])
    b.expect("phiVn (kip)", mag(cp["phiV_n"], kip), v["phiVn_k"])
    b.expect("UC", max(u1, u2), new["uc"], tol_rel=0.01, tol_abs=0.006)


G_RHO = 0.0181   # gravity.design_grade_beam: tension-controlled rho for f'c 4 / fy 60


def do_connection(b: Block, res: dict, shown: set, sheet: str):
    new, old = res["new"], res["old"]
    v, vo = new["values"], (old or {}).get("values") or {}
    t = str(v.get("type") or "")
    if not t.startswith("ST-"):
        return do_values(b, res)
    n = int(t.split("-")[1].rstrip("*"))
    b.inp("\\text{Connection}", f"{v.get('member')} end {v.get('end')} to {v.get('to')}: {t}",
          was=(f"{vo.get('member')} end {vo.get('end')} to {vo.get('to')}: {vo.get('type')}" if vo else None), src="connection schedule (E2)", text=True)
    Ru = Q(v["Ru_k"], kip)
    b.inp("R_{u}", Ru, was=_q(vo.get("Ru_k"), kip), src=f"re-run: max factored end reaction of {v.get('member')}", n=1)
    key = (sheet, n)
    bg_args = (float(n), Q(3.0, inch), Q(G.SHEAR_TABS[n]["e_in"], inch), Q(G.BOLT_PHI_RN, kip))
    if key not in shown:
        shown.add(key)
        b.inp("n", float(n), src=f"typical ST-{n}: 3/4 in A325-N bolts, 3 in pitch", n=0)
        b.inp(r"\phi r_{nv}", Q(G.BOLT_PHI_RN, kip), src="0.75 x 54 ksi x 0.442 in2 (J3.6, single shear)", n=2)
        b.inp("t_{p}", Q(G.PLATE_T, inch), src="PL 3/8 A36", n=3)
        bg = b.calc(f"Typical ST-{n}: eccentric bolt group, elastic method (Manual Part 7), e = 3 in", tab_bolt_group, *bg_args)
        pl = b.calc(f"Typical ST-{n}: plate shear yield (J4-3), rupture (J4-4), bolt bearing (J3-6a)", tab_plate, float(n), Q(3.0, inch),
                    Q(G.PLATE_T, inch), Q(G.PLATE_FY, ksi), Q(G.PLATE_FU, ksi), Q(13 / 16 + 1 / 16, inch), Q(0.75, inch), bg["c_unit"])
    else:
        bg, _ = tab_bolt_group(*bg_args)[1], None
        pl = tab_plate(float(n), Q(3.0, inch), Q(G.PLATE_T, inch), Q(G.PLATE_FY, ksi), Q(G.PLATE_FU, ksi), Q(13 / 16 + 1 / 16, inch),
                       Q(0.75, inch), bg["c_unit"])[1]
        b.note(f"phi R_n of typical ST-{n} recomputed with the same functions; derivation printed at its first use on sheet {sheet}")
    caps = {"bolt shear (J3.6)": bg["phiR_bolt"], "plate shear yield (J4-3)": pl["phiR_y"],
            "plate shear rupture (J4-4)": pl["phiR_rup"], "bolt bearing (J3-6a)": pl["phiR_brg"]}
    gov = min(caps, key=lambda k: mag(caps[k], kip))
    phiRn = caps[gov]
    b.note(f"phi R_n = min(bolt shear, plate yield, plate rupture, bearing) = {mag(phiRn, kip):.1f} kip, governed by {gov}")
    u = b.check("End reaction", "R_{u}", Ru, r"\phi R_{n}", phiRn, f"AISC 360-16 {gov.split('(')[-1].rstrip(')')}, ST-{n}",
                was_uc=_ratio(vo, "Ru_k", "phiRn_k"))
    b.expect("phiRn (kip)", mag(phiRn, kip), new["capacity"])
    b.expect("UC", u, new["uc"], tol_rel=0.01, tol_abs=0.006)


def do_values(b: Block, res: dict):
    b.table_only = True
    new, old = res.get("new") or {}, res.get("old") or {}
    v, vo = new.get("values") or {}, old.get("values") or {}
    for k in sorted(set(v) | set(vo)):
        b.values_rows.append((k, _fmt_val(vo.get(k)) if old else "", _fmt_val(v.get(k)) if new else "(removed)"))
    b.note("values block: no closed-form recomputation is printed for this kind; values are the re-run results")


def _fmt_val(x) -> str:
    if x is None:
        return "-"
    if isinstance(x, float):
        return f"{x:,.3f}".rstrip("0").rstrip(".") if abs(x) < 1000 else f"{x:,.1f}"
    if isinstance(x, (list, dict)):
        s = json.dumps(x, sort_keys=True)
        return s if len(s) < 160 else s[:157] + "..."
    return str(x)


def _q(x, unit):
    return None if x is None else Q(x, unit)


def _ratio(vals: dict, a: str, b: str):
    try:
        return vals[a] / vals[b]
    except (KeyError, TypeError, ZeroDivisionError):
        return None


KIND_FN = {"beam_design": do_beam, "column_design": do_column, "brace": do_brace, "pier": do_pier}
KIND_LABEL = {"beam_design": "Steel beam - AISC 360-16 F2/F3/G2", "column_design": "Steel column - AISC 360-16 E3/F2/H1",
              "footing": "Spread footing - ACI 318-19 22.5/22.6", "connection": "Shear tab - AISC 360-16 J3/J4",
              "base_plate": "Base plate bearing - AISC 360-16 J8", "pier": "Concrete pier - ACI 318-19 22.4",
              "grade_beam": "Grade beam - ACI 318-19 22.2/22.5", "brace": "SCBF brace - AISC 360-16 E3/D2, AISC 341-16 F2"}


def build_block(res: dict, method: str, new_recs: dict, shown: set, sheet: str, topo_gbs: dict) -> Block:
    b = Block(res, method)
    if res.get("new") is None:
        b.table_only = True
        do_values(b, {**res, "new": None})
        b.notes = ["record removed: the element no longer exists in the re-run design"]
        return b
    kind = res["kind"]
    try:
        if kind in KIND_FN:
            KIND_FN[kind](b, res)
        elif kind == "footing":
            do_footing(b, res, new_recs)
        elif kind == "base_plate":
            do_base_plate(b, res, new_recs)
        elif kind == "grade_beam":
            do_grade_beam(b, res, topo_gbs)
        elif kind == "connection":
            do_connection(b, res, shown, sheet)
        else:
            do_values(b, res)
    except Exception as e:   # loud: a block that cannot be recomputed says so on the page
        print(f"RECALC ERROR {b.rid}: {type(e).__name__}: {e}", file=sys.stderr)
        b2 = Block(res, method)
        do_values(b2, res)
        b2.asserts.append({"what": f"recomputation raised {type(e).__name__}: {e}", "got": 0, "want": 0, "ok": False})
        return b2
    return b


# ================================================================ HTML
def _change_text(change: dict) -> str:
    parts = []
    for c, (dx, dy) in sorted((change.get("moved") or {}).items()):
        segs = []
        if dx:
            segs.append(f"{_ftin(abs(dx))} {'east' if dx > 0 else 'west'}")
        if dy:
            segs.append(f"{_ftin(abs(dy))} {'north' if dy > 0 else 'south'}")
        parts.append(f"column {c.replace('COL-', '')} moved {' and '.join(segs) or 'in place'}")
    for c in sorted(change.get("removed") or []):
        parts.append(f"column {c.replace('COL-', '')} removed")
    if change.get("label"):
        parts.append(str(change["label"]))
    return "; ".join(parts) or json.dumps(change, sort_keys=True)


def _ftin(x: float) -> str:
    tot = round(x * 12 * 4) / 4
    f, i = divmod(tot, 12)
    return f"{int(f)}'-{i:g}\""


def _date_et(rr: dict) -> str:
    s = str(rr.get("created_at") or "")
    try:
        y, m, d = s[:10].split("-")
        return f"{m}/{d}/{y} ET"
    except ValueError:
        return "11/14/2026 ET"


def _esc(s) -> str:
    return html.escape(str(s), quote=True)


class TexPool:
    """Collect LaTeX, render all of it in one node/KaTeX call, substitute placeholders."""

    def __init__(self):
        self.items: list[str] = []

    def add(self, tex: str) -> str:
        self.items.append(tex)
        return f"\x00TEX{len(self.items) - 1}\x00"

    def render(self, doc: str) -> tuple[str, list[str]]:
        _ensure_katex()
        out = subprocess.run(["node", os.path.join(ASSETS, "katex_render.js")], input=json.dumps(self.items),
                             capture_output=True, text=True, check=True).stdout
        htmls = json.loads(out)
        errors = []
        for i, h in enumerate(htmls):
            if h.startswith("__KATEX_ERROR__"):
                errors.append(f"{h[15:]} in: {self.items[i][:120]}")
                print(f"KATEX ERROR: {errors[-1]}", file=sys.stderr)
                htmls[i] = f"<code class='katex-err'>{_esc(self.items[i])}</code>"
        parts = doc.split("\x00")
        res = []
        for p in parts:
            if p.startswith("TEX") and p[3:].isdigit():
                res.append(htmls[int(p[3:])])
            else:
                res.append(p)
        return "".join(res), errors


def _block_html(b: Block, tp: TexPool, rev: str) -> str:
    res = b.res
    new, old = res.get("new") or {}, res.get("old") or {}
    st = res.get("status", "")
    chips = [f"<span class='chip st'>{_esc(st)}</span>"]
    if res.get("ng_to_ok"):
        chips.append("<span class='chip ngok'>NG &rarr; OK</span>")
    elif res.get("ok_new") is False:
        chips.append("<span class='chip ng'>STILL NG</span>")
    els = ", ".join(res.get("elements") or [])
    h = [f"<div class='blk' id='blk-{_slug(b.rid)}'>",
         f"<div class='bh'><span class='delta'>{_esc(rev)}</span><span class='rid'>{_esc(b.rid)}</span>"
         f"<span class='el'>{_esc(els)}</span><span class='kind'>{_esc(KIND_LABEL.get(res['kind'], res['kind'].replace('_', ' ')))}</span>{''.join(chips)}</div>",
         f"<div class='method'>Method: {_esc(b.method)}</div>"]
    if b.inputs:
        h.append("<div class='inputs'><div class='rh'>Inputs (re-run values; <i>was</i> = previous issue)</div><table class='defs'>")
        half = (len(b.inputs) + 1) // 2
        cols = [b.inputs[:half], b.inputs[half:]]
        for i in range(half):
            h.append("<tr>")
            for col in cols:
                if i < len(col):
                    d, w, s = col[i]
                    h.append(f"<td class='def'>{tp.add(d)}</td><td class='was'>{_esc(w)}<div class='src'>{_esc(s)}</div></td>")
                else:
                    h.append("<td></td><td></td>")
            h.append("</tr>")
        h.append("</table></div>")
    for head, lines in b.sections:
        h.append(f"<div class='sec'><div class='sh'>{_esc(head)}</div>" + "".join(f"<div class='ln'>{tp.add(x)}</div>" for x in lines) + "</div>")
    if b.notes:
        h.append("<div class='notes'>" + "".join(f"<div>{_esc(n)}</div>" for n in b.notes) + "</div>")
    if b.values_rows:
        h.append("<table class='vals'><tr><th>value</th><th>was</th><th>now (re-run)</th></tr>")
        for k, o, nw in b.values_rows:
            cls = " class='chg'" if o != nw and o else ""
            h.append(f"<tr{cls}><td>{_esc(k)}</td><td>{_esc(o)}</td><td>{_esc(nw)}</td></tr>")
        h.append("</table>")
    if b.checks:
        h.append("<table class='checks'>")
        for c in b.checks:
            ok = "<span class='ok'>OK</span>" if c["ok"] else "<span class='ngc'>NG</span>"
            was = f"was {c['was_uc']:.3f}" if c.get("was_uc") is not None else ""
            h.append(f"<tr><td class='cl'>{_esc(c['label'])}</td><td class='ct'>{tp.add(c['tex'])}</td><td class='cu'>UC = {c['uc']:.3f}"
                     f"<div class='was'>{_esc(was)}</div></td><td class='co'>{ok}</td><td class='cr'>{_esc(c['ref'])}</td></tr>")
        h.append("</table>")
    # old vs new summary (one compact table: rows was / now)
    unit = new.get("unit") or old.get("unit") or ""
    oks = {True: "OK", False: "NG", None: "-"}
    cols = [("size / type", res.get("size_old"), res.get("size_new"), ""), ("check", old.get("check"), new.get("check"), ""),
            ("demand", old.get("demand"), new.get("demand"), unit), ("capacity", old.get("capacity"), new.get("capacity"), unit),
            ("UC", old.get("uc"), new.get("uc"), ""), ("status", oks[res.get("ok_old")], oks[res.get("ok_new")], "")]
    def fv(x, u):
        f = _fmt_val(x)
        return f + (" " + u if u and x is not None else "")
    h.append("<table class='sum'><tr><th></th>" + "".join(f"<th>{c[0]}</th>" for c in cols) + "</tr>")
    for lab, i in (("was", 1), ("now", 2)):
        h.append(f"<tr><td class='lab'>{lab}</td>" + "".join(
            f"<td{' class=chg' if i == 2 and fv(c[1], c[3]) != fv(c[2], c[3]) else ''}>{_esc(fv(c[i], c[3]))}</td>" for c in cols) + "</tr>")
    h.append("</table>")
    bad = [a for a in b.asserts if not a["ok"]]
    if b.asserts:
        if bad:
            h.append("<div class='mism'>RECOMPUTATION MISMATCH: " + "; ".join(
                _esc(f"{a['what']}: recomputed {a['got']:.3f} vs record {a['want']:.3f}" if a["want"] or a["got"] else a["what"]) for a in bad) + "</div>")
        else:
            h.append(f"<div class='verified'>Recomputed on this sheet: {len(b.asserts)} values agree with the re-run record "
                     f"(within record rounding).</div>")
    h.append(f"<div class='endmark'>end {_esc(b.rid)}</div></div>")
    return "".join(h)


def _slug(s: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in s)


def _ensure_katex():
    if not os.path.exists(os.path.join(KATEX_DIST, "katex.css")):
        subprocess.run(["npm", "ci", "--no-audit", "--no-fund"], cwd=ASSETS, check=True, capture_output=True)


SECTION_SEP = "\x01SECTION\x01"
BLOCK_SEP = "\x01BLOCK\x01"


def build_html(rerun_result: dict, base: dict, new: dict, topo_gbs: dict, rev_no: int = 1):
    """-> (head html, [(calc id, body html)], chunks, blocks, KaTeX errors).

    One body per calc sheet (the .html beside the PDF). `chunks` = [(chunk head, chunk body, [block
    element ids])]: each calc sheet cut at record-block boundaries into pieces of about
    recalc_pages_layout.CHUNK_BYTES, every piece its own document (the running title block on every
    page, the REVISED banner on the first piece of a calc), so pieces lay out in parallel and are
    cached by content. A piece's text depends only on its records and the date (the revision id is
    stamped into the PDF footer after layout, and is in the .html title only), so unchanged blocks
    are laid out once.
    topo_gbs: the re-run design's topology grade beams ({id: {"wall", ...}})."""
    from .recalc_pages_layout import CHUNK_BYTES
    method = rerun_result.get("method") or "calc-graph re-run"
    new_recs = {r["id"]: r for r in (new or {}).get("records", [])}
    calcs = {c["id"]: c for c in (new or {}).get("calcs", []) or (base or {}).get("calcs", [])}
    order = [c["id"] for c in (new or {}).get("calcs", [])] or sorted({r["calc"] for r in rerun_result["results"]})
    by_calc: dict[str, list[dict]] = {}
    for r in rerun_result["results"]:
        by_calc.setdefault(r["calc"], []).append(r)
    order = [c for c in order if c in by_calc] + sorted(c for c in by_calc if c not in order)
    rev = f"R{rev_no}"
    change = _change_text(rerun_result.get("change") or {})
    date = _date_et(rerun_result)
    tp = TexPool()
    blocks: list[Block] = []
    shown: set = set()
    bodies, pageheads, block_ids = [], {}, {}
    for calc in order:
        info = calcs.get(calc, {"title": calc, "software": ""})
        sheet = f"{calc}-{rev}"
        pageheads[calc] = _pagehead(sheet, info.get("title", calc), date, rev, rerun_result["rev_id"])
        nrec = len(by_calc[calc])
        nres = sum(1 for r in by_calc[calc] if str(r.get("status", "")).startswith("re-sized"))
        parts = ["<section class='calc'>" + pageheads[calc]
                 + f"<div class='banner'><b>REVISED - re-run after {_esc(change)}</b> &nbsp; "
                 f"Replaces the {_esc(info.get('software', ''))} output of calc {calc} for the {nrec} record(s) below ({nres} re-sized); "
                 f"{date} (the calc revision id is in every page footer). Math printed from the same Python that recomputed it (handcalcs).</div>"]
        block_ids[calc] = []
        for r in by_calc[calc]:
            b = build_block(r, method, new_recs, shown, sheet, topo_gbs)
            blocks.append(b)
            block_ids[calc].append(f"blk-{_slug(b.rid)}")
            parts.append(_block_html(b, tp, rev))
        parts.append("</section>")
        bodies.append(BLOCK_SEP.join(parts))
    css = open(os.path.join(HERE, "recalc_pages.css")).read()
    style = (f"<meta name='author' content='{_esc(FIRM_FULL)}'><meta name='generator' content='calc-graph recalc_pages'>"
             f"<style>{_katex_css()}</style><style>{css}</style>"
             f"<style>@page {{ @bottom-left {{ content: 'Method: {_esc(method)}'; }} }}</style></head>")
    head = f"<!doctype html><html lang='en'><head><meta charset='utf-8'><title>Re-run calc sheets {_esc(rerun_result['rev_id'])}</title>" + style
    chunk_head = "<!doctype html><html lang='en'><head><meta charset='utf-8'><title>Re-run calc sheet</title>" + style
    joined, errors = tp.render(SECTION_SEP.join(bodies))
    sheets, chunks = [], []
    for calc, body in zip(order, joined.split(SECTION_SEP)):
        prefix, *blks, suffix = body.split(BLOCK_SEP)
        sheets.append((calc, prefix + "".join(blks) + suffix))
        groups: list[list[int]] = []
        size = CHUNK_BYTES
        for i, h in enumerate(blks):
            if size + len(h) > CHUNK_BYTES and (not groups or groups[-1]):
                groups.append([])
                size = 0
            groups[-1].append(i)
            size += len(h)
        for gi, g in enumerate(groups):
            lead = prefix if gi == 0 else "<section class='calc'>" + pageheads[calc]
            chunks.append((chunk_head, lead + "".join(blks[i] for i in g) + suffix, [block_ids[calc][i] for i in g]))
    return head, sheets, chunks, blocks, errors


def _katex_css() -> str:
    _ensure_katex()
    css = open(os.path.join(KATEX_DIST, "katex.css")).read()
    # absolute font URLs so the HTML is self-sufficient wherever it is written
    return css.replace("url(fonts/", "url(file://" + os.path.join(KATEX_DIST, "fonts") + "/")


def _pagehead(sheet: str, title: str, date: str, rev: str, rev_id: str) -> str:
    return (f"<div class='pagehead'><table class='tb'><tr>"
            f"<td class='logo' rowspan='3'><div class='firm'>{_esc(FIRM_FULL.upper())}</div><div class='addr'>{_esc(FIRM_ADDR)}</div></td>"
            f"<td class='k'>project</td><td class='v'>{_esc(PROJECT)}</td><td class='k'>job no.</td><td class='v'>{_esc(JOB)}</td>"
            f"<td class='sheet' rowspan='3'><div class='k'>sheet no.</div><div class='sn'>{_esc(sheet)}</div><div class='rv'>&#9651; {rev} re-run</div></td></tr>"
            f"<tr><td class='k'>subject</td><td class='v'>{_esc(title)} (re-run)</td><td class='k'>date</td><td class='v nw'>{_esc(date)}</td></tr>"
            f"<tr><td class='k'>location</td><td class='v'>{_esc(CITY)}</td><td class='k'>by / chk</td><td class='v'>{BY} / {CHK}</td></tr>"
            f"</table></div>")


# ================================================================ render
def render(rerun_result: dict, base: dict, new: dict, path: str, topo_gbs: dict, rev_no: int = 1, workers: int | None = None,
           progress=None) -> tuple[dict, dict]:
    """Write the re-run calc sheets PDF to `path` (and the HTML beside it). Returns (pages, layout):
    pages = {record id: {"page": n (1-based), "bbox": [x0, y0, x1, y1] (PDF points, top-left origin,
    the record's block), "sheet", "split_across_pages", "recomputed", "asserts", "mismatches"}};
    layout = {chunks, cached, laid_out, workers, seconds, pages, katex_errors}.
    progress(stage, done, total) is called as the sheets are built ("math") and laid out ("layout")."""
    import pymupdf
    from . import recalc_pages_layout as LAY
    if progress:
        progress("math", 0, 1)
    head, sheets, chunks, blocks, katex_errors = build_html(rerun_result, base, new, topo_gbs, rev_no)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(os.path.splitext(path)[0] + ".html", "w") as fh:
        fh.write(head + "<body>" + "".join(b for _, b in sheets) + "</body></html>")
    jobs = [(ch + "<body>" + body + "</body></html>", want) for ch, body, want in chunks]
    parts, stats = LAY.layout_all(jobs, KATEX_DIST + "/", workers,
                                  progress=(lambda d, t: progress("layout", d, t)) if progress else None)
    out_doc = pymupdf.open()
    found: dict[str, dict] = {}
    for pdf, f in parts:
        off = out_doc.page_count
        with pymupdf.open("pdf", pdf) as d:
            out_doc.insert_pdf(d)
        for bid, v in f.items():
            found[bid] = {**v, "page": v["page"] + off, "parts": [{**p, "page": p["page"] + off} for p in v["parts"]]}
    total = out_doc.page_count
    for i, pg in enumerate(out_doc, 1):
        # stamped after layout (with the page count): the laid-out chunks carry nothing per-revision,
        # so their layout is reused from the content cache by any revision with the same records
        s = f"calc revision {rerun_result['rev_id']} - page {i} of {total}"
        pg.insert_text((pg.rect.width - 30 - pymupdf.get_text_length(s, "helv", 6.5), pg.rect.height - 22), s, fontname="helv", fontsize=6.5,
                       color=(0.2, 0.2, 0.2))
    out_doc.set_metadata({"title": f"Re-run calc sheets {rerun_result['rev_id']}", "author": FIRM_FULL, "subject": rerun_result.get("method", ""),
                          "creator": "calc-graph recalc_pages (handcalcs + KaTeX + WeasyPrint)", "producer": "calc-graph",
                          "creationDate": "", "modDate": "", "keywords": "", "trapped": ""})
    out_doc.save(path, garbage=3, deflate=True, no_new_id=True)
    out_doc.close()
    out = {}
    for b in blocks:
        f = found.get(f"blk-{_slug(b.rid)}")
        mism = [f"{a['what']}: recomputed {a['got']:.4f} vs record {a['want']:.4f}" if (a["want"] or a["got"]) else a["what"]
                for a in b.asserts if not a["ok"]]
        out[b.rid] = {"page": f["page"] if f else None, "bbox": f["bbox"] if f else None,
                      "sheet": f"{b.res['calc']}-R{rev_no}",
                      # a block taller than one page continues on the next page(s): every part is listed
                      "parts": f["parts"] if f else [], "split_across_pages": bool(f and len(f["parts"]) > 1),
                      "recomputed": bool(b.asserts) and not b.table_only, "asserts": len(b.asserts), "mismatches": mism}
    if katex_errors:
        print(f"recalc_pages: {len(katex_errors)} KaTeX error(s)", file=sys.stderr)
    return out, {**stats, "pages": total, "katex_errors": katex_errors[:20]}


def _title_block_matches() -> bool:
    from synth.v2 import calc_pdf_v2 as C
    return (C.FIRM_FULL, C.FIRM_ADDR, C.PROJECT, C.CITY, C.JOB, C.BY, C.CHK) == (FIRM_FULL, FIRM_ADDR, PROJECT, CITY, JOB, BY, CHK)
