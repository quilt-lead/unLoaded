"""Write the synthetic calc package PDF with PyMuPDF.

Styles, one per calc, to mimic a real mixed package:
- contents page with dot leaders (front matter, must never be mapped)
- RAM Concept / RAM Structural System style monospaced tabular reports
- Mathcad-style worksheets: ``name := value`` text plus formula images rendered
  with matplotlib mathtext (no LaTeX needed)
- Excel / VBA style tables drawn as a spreadsheet grid
- one rasterised "scanned hand calc" page with NO text layer

Byte-stable: fixed metadata and ``reproducible`` save; images are rendered from a
seeded RNG with matplotlib metadata stripped.
"""
from __future__ import annotations

import io

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pymupdf  # noqa: E402
from PIL import Image, ImageFilter  # noqa: E402

from . import building as B  # noqa: E402
from . import shapes  # noqa: E402
from .analysis import Results  # noqa: E402

W_PT, H_PT = 612, 792
KIP = shapes.KN_TO_KIP
KFT = shapes.KNM_TO_KFT
FT = shapes.M_TO_FT

# page plan: calc id -> (title in contents, pages)
PLAN = [
    (B.K_FRONT, "Front matter / contents", [1], "", ""),
    (B.K_CRIT, "Design criteria", [2], "", ""),
    (B.K_SLAB, "PT slab design (RAM Concept)", [3, 4], "RAM Concept", "Slab"),
    (B.K_BEAM, "Floor beam & girder design (RAM Structural System)", [5, 6, 7], "RAM Structural System", "Beam"),
    (B.K_ROOF, "Roof framing - typical", [8], "", "Beam"),
    (B.K_CANT, "Cantilever balcony beam 2CB1 (hand calc)", [9], "Hand calc", "Beam"),
    (B.K_ST1, "Shear tab connection ST-1 (MathCAD)", [10, 11], "MathCAD", "Connection"),
    (B.K_MF1, "Moment connection MF-1 (MathCAD)", [12], "MathCAD", "Connection"),
    (B.K_COL, "Column design (RAM Structural System)", [13, 14], "RAM Structural System", "Column"),
    (B.K_BP, "Column base plate design (MathCAD)", [15], "MathCAD", "Connection"),
    (B.K_BR, "Lateral bracing BR1 (Excel)", [16], "Excel", "Brace"),
    (B.K_FTG, "Spread footing design (VBA)", [17], "VBA / Excel", "Footing"),
]
N_PAGES = 17

# calc dependency truth: output of src feeds input of dst
CALC_EDGES = [
    (B.K_SLAB, B.K_BEAM), (B.K_BEAM, B.K_ST1), (B.K_ROOF, B.K_ST1), (B.K_BEAM, B.K_MF1),
    (B.K_ROOF, B.K_MF1), (B.K_BEAM, B.K_COL), (B.K_ROOF, B.K_COL), (B.K_CANT, B.K_COL), (B.K_MF1, B.K_COL),
    (B.K_BR, B.K_COL), (B.K_COL, B.K_BP), (B.K_COL, B.K_FTG),
]


def _mathtext_png(lines: list[str], fontsize: int = 13, width_in: float = 5.6) -> bytes:
    fig = plt.figure(figsize=(width_in, 0.42 * len(lines) + 0.1), dpi=200)
    for n, s in enumerate(lines):
        fig.text(0.01, 1 - (n + 0.75) / len(lines), s, fontsize=fontsize, color="#0b2a6b")
    buf = io.BytesIO()
    fig.savefig(buf, format="png", metadata={"Software": None}, facecolor="white")
    plt.close(fig)
    return buf.getvalue()


def _scanned_png(seed: int, res: Results) -> bytes:
    rng = np.random.default_rng(seed)
    fig = plt.figure(figsize=(8.5, 11), dpi=110)
    fig.patch.set_facecolor("#f4f1e8")
    ink = "#2b2b33"
    mu = res.cant["mu"] * KFT
    pmn = res.cant["phi_mn"] * KFT
    r = res.cant["r"] * KIP
    txt = [
        "JOB 2611      SHEET 9      BY: EOR",
        "CANTILEVER BALCONY BEAM  2CB1",
        "W16x31  L = 8'-10\"   trib 11.5'",
        "w = 1.2(115)(11.5) + 1.6(50)(11.5)",
        f"   = {res.members['cant:2:E/2'].wu * KIP / FT:.2f} k/ft  + rail 1.1 k",
        f"Mu = wL^2/2 + PL = {mu:.0f} k-ft",
        f"phiMn = {pmn:.0f} k-ft  >  Mu   OK",
        f"Ru = {r:.1f} k  -> to col C10",
        "defl. L/240 at tip  OK",
        "fixed to column - full pen. flange welds",
    ]
    for n, s in enumerate(txt):
        jitter = rng.normal(0, 0.003)
        fig.text(0.09 + jitter, 0.92 - n * 0.062, s, fontsize=17 if n else 12, color=ink, family="DejaVu Sans",
                 style="italic", rotation=rng.normal(0, 0.6))
    ax = fig.add_axes((0.15, 0.1, 0.7, 0.2))
    ax.axis("off")
    ax.plot([0, 0], [-1, 1], color=ink, lw=3)
    ax.plot([0, 6], [0.3, 0.3], color=ink, lw=2)
    for x in np.linspace(0.5, 5.5, 9):
        ax.annotate("", xy=(x, 0.32), xytext=(x, 0.8), arrowprops=dict(arrowstyle="->", color=ink, lw=1))
    ax.plot([6, 6], [0.3, -0.4], color=ink, lw=1, ls="--")
    ax.set_xlim(-1, 7)
    ax.set_ylim(-1.2, 1.2)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", metadata={"Software": None}, facecolor=fig.get_facecolor())
    plt.close(fig)
    img = Image.open(io.BytesIO(buf.getvalue())).convert("L").rotate(0.7, fillcolor=236, resample=Image.BICUBIC)
    arr = np.asarray(img).astype(np.float32)
    arr += rng.normal(0, 9, arr.shape)
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.6))
    out = io.BytesIO()
    img.save(out, format="PNG", optimize=False)
    return out.getvalue()


class Pkg:
    def __init__(self):
        self.doc = pymupdf.open()
        self.page = None
        self.n = 0

    def new(self, title: str | None, header: bool = True):
        self.page = self.doc.new_page(width=W_PT, height=H_PT)
        self.n += 1
        if header:
            self.text(40, 34, f"JOB 2611 - SAMPLE OFFICE BUILDING     SHEET {self.n} OF {N_PAGES}     BY: EOR   CHK: PE   "
                              f"DATE: 2026-11-02", font="helv", size=7.5)
            self.page.draw_line((40, 40), (W_PT - 40, 40), color=(0.6, 0.6, 0.6), width=0.5)
        if title:
            self.text(40, 66, title, font="hebo", size=12.5)
        return self.page

    def text(self, x, y, s, font="cour", size=9.0, color=(0, 0, 0)):
        self.page.insert_text((x, y), s, fontname=font, fontsize=size, color=color)

    def lines(self, x, y, rows, font="cour", size=8.5, lead=None):
        lead = lead or size * 1.45
        for n, s in enumerate(rows):
            self.text(x, y + n * lead, s, font=font, size=size)
        return y + len(rows) * lead

    def image(self, x, y, png: bytes, width: float):
        pix = pymupdf.Pixmap(png)
        h = width * pix.height / pix.width
        self.page.insert_image(pymupdf.Rect(x, y, x + width, y + h), stream=png)
        return y + h

    def grid(self, x, y, cols: list[float], rows: list[list[str]], head_fill=(0.86, 0.9, 0.95), size=8.0, rh=15):
        """Spreadsheet-style table: each cell is its own text run."""
        xs = [x]
        for w in cols:
            xs.append(xs[-1] + w)
        for r, row in enumerate(rows):
            top = y + r * rh
            if r == 0:
                self.page.draw_rect(pymupdf.Rect(xs[0], top, xs[-1], top + rh), color=None, fill=head_fill)
            for c, val in enumerate(row):
                self.page.draw_rect(pymupdf.Rect(xs[c], top, xs[c + 1], top + rh), color=(0.7, 0.7, 0.7), width=0.4)
                self.text(xs[c] + 3, top + rh - 4.5, val, font="helv" if r else "hebo", size=size)
        return y + len(rows) * rh

    def save(self, path: str):
        self.doc.set_metadata({
            "title": "Structural calculations - Sample Office Building (synthetic)",
            "author": "calc-graph synth", "subject": "Synthetic calc package with ground truth",
            "creator": "calc-graph synth generator", "producer": "PyMuPDF",
            "creationDate": "D:20261114090000-05'00'", "modDate": "D:20261114090000-05'00'", "keywords": "",
        })
        self.doc.save(path, garbage=3, deflate=True, no_new_id=True)


def _ftin(m: float) -> str:
    ft_total = m * FT
    ft = int(ft_total)
    inch = int(round((ft_total - ft) * 12))
    if inch == 12:
        ft, inch = ft + 1, 0
    return f"{ft}'-{inch}\""


def write(b: B.Building, res: Results, path: str, seed: int = 7) -> dict:
    pk = Pkg()
    mem = res.members
    by_mark = {e.mark: e for e in b.elements if e.mark}

    # ---------------- 1. front matter ----------------
    pk.new(None)
    pk.text(40, 120, "STRUCTURAL CALCULATIONS", font="hebo", size=22)
    pk.lines(40, 150, ["Sample Office Building - 3 storey steel frame", "Issued for Permit - Rev 1",
                       "Prepared by: Engineer of Record (synthetic sample)"], font="helv", size=11)
    pk.text(40, 240, "CONTENTS", font="hebo", size=12)
    rows = []
    for cid, title, pages, *_ in PLAN[1:]:
        dots = "." * max(4, 62 - len(title))
        rows.append(f"{title} {dots} {pages[0]}")
    pk.lines(40, 262, rows, font="cour", size=9, lead=16)

    # ---------------- 2. design criteria ----------------
    pk.new("DESIGN CRITERIA")
    pk.lines(40, 92, [
        "Codes: IBC 2021 / ASCE 7-16 / AISC 360-16 / ACI 318-19",
        "Dead load: PT slab self weight 100 psf + 15 psf superimposed",
        "Live load: 50 psf office, 20 psf roof",
        "Roof dead load: 25 psf (deck, insulation, membrane)",
        "Wind: 115 mph, Exposure B.  Seismic: SDC B",
        "Steel: ASTM A992 (W shapes), A500 Gr C (HSS), A36 plates",
        "Concrete: f'c 5,000 psi (PT slabs), 4,000 psi (footings)",
        "Allowable soil bearing: 3,000 psf (geotechnical report GR-01)",
        "Load combinations: 1.2D + 1.6L (strength), D + L (service)",
    ], font="helv", size=10, lead=17)

    # ---------------- 3-4. PT slab (RAM Concept) ----------------
    pk.new("PT SLAB DESIGN - RAM CONCEPT")
    pk.lines(40, 92, [
        "Model: L2_L3_PT.cpt          RAM Concept v8.2",
        "Slabs designed: SL2 (Level 2), SL3 (Level 3)",
        "Thickness 200 mm (8\"), f'c 5,000 psi, balanced load 75% DL",
        "Span/depth: 8.0 m / 0.20 m = 40   OK",
        "Tendons: banded N-S on grid lines A to E, distributed E-W",
        "",
        "Design strip   Dir   Mu+ (k-ft/ft)   phiMn   Ratio",
        "Strip 1        N-S        9.8         14.1    0.70",
        "Strip 2        N-S       11.2         14.1    0.79",
        "Strip 3        E-W        7.4         12.6    0.59",
        "Strip 4        E-W        8.1         12.6    0.64",
        "",
        "Punching shear at interior columns C7, C8, C12, C13:",
        "   vu / phi vc = 0.82   OK",
    ], size=9)
    pk.new("PT SLAB DESIGN - RAM CONCEPT (cont.)")
    pk.lines(40, 92, [
        "Long-term deflection SL2 bay B-C/1-2: 14 mm < L/480 = 16.7 mm   OK",
        "SL3 similar - see strip summary on previous sheet.",
        "Reactions to supporting beams exported to RAM Structural System (page 5).",
    ], size=9)

    # ---------------- 5-7. floor beams & girders (RAM Structural System) ----------------
    def beam_rows(level: str):
        out = []
        prefix = level
        items = [e for e in b.elements if e.ifc_class == "IfcBeam" and e.mark and e.storey == f"Level {level}"
                 and e.meta.get("kind") != "cant"]
        items.sort(key=lambda e: (e.mark[len(prefix)], int(e.mark[len(prefix) + 1:])))
        for e in items:
            r = mem[e.key]
            out.append(f"{e.mark:<7}{r.section:<9}{r.span * FT:>8.1f}{r.wu * KIP / FT:>9.2f}{r.mu * KFT:>10.1f}"
                       f"{r.phi_mn * KFT:>9.1f}{r.ratio:>8.2f}{max(r.r_u.values()) * KIP:>8.1f}")
        return out

    head = f"{'Member':<7}{'Size':<9}{'Span ft':>8}{'wu k/ft':>9}{'Mu k-ft':>10}{'phiMn':>9}{'Ratio':>8}{'Ru k':>8}"
    for lv, first in (("2", True), ("3", False)):
        pk.new("FLOOR BEAM & GIRDER DESIGN - RAM STRUCTURAL SYSTEM" + ("" if first else " (cont.)"))
        y = pk.lines(40, 88, [
            f"RAM Structural System v17 - Steel Beam Design Report        Level {lv}",
            "Slab reactions from RAM Concept (page 4)." if first else "Slab reactions as Level 2.",
            f"Level {lv}: beams {lv}B1 - {lv}B28, girders {lv}G1 thru {lv}G15",
            "",
            head,
        ], size=8.5)
        pk.lines(40, y, beam_rows(lv), size=8.0, lead=11.6)
    st = res.st1
    pk.new("FLOOR BEAM & GIRDER DESIGN - RAM STRUCTURAL SYSTEM (cont.)")
    pk.lines(40, 92, [
        "Summary - Levels 2 and 3",
        "All members: deflection L/360 live, L/240 total   OK",
        f"Max end reaction {st['gov']} = {st['ru'] * KIP:.1f} k, carried to ST-1 connection design (page 10).",
        "Moment frame beams 2B13 - 2B16 and 3B13 - 3B16: end moments to MF-1 design (page 12).",
        "Reactions carried to column design (page 13).",
        "CB1 cantilever - designed separately by hand calc.",
    ], size=9)

    # ---------------- 8. roof framing (typical) ----------------
    rb = mem[by_mark["RB17"].key]
    rg = mem[by_mark["RG5"].key]
    pk.new("ROOF FRAMING - TYPICAL")
    pk.lines(40, 92, [
        "Roof beams and girders - typical sizes, no individual marks",
        f"Roof: typical beams W12X19 at {_ftin(rb.span)} span, typical girders W16X26 at {_ftin(rg.span)}",
        f"Beam: wu = 1.2(25) + 1.6(20) = 62 psf x 11.5 ft = {rb.wu * KIP / FT:.2f} k/ft",
        f"      Mu = {rb.mu * KFT:.1f} k-ft  <  phiMn = {rb.phi_mn * KFT:.1f} k-ft   OK",
        f"Girder: Mu = {rg.mu * KFT:.1f} k-ft  <  phiMn = {rg.phi_mn * KFT:.1f} k-ft   OK",
        "Roof deck RF-1: 1.5\" B 20 ga, span 11'-6\", ponding check OK",
        "Reactions carried to column design (page 13).",
    ], font="helv", size=10, lead=17)

    # ---------------- 9. scanned hand calc (no text layer) ----------------
    pk.new(None, header=False)
    png = _scanned_png(seed, res)
    pk.page.insert_image(pymupdf.Rect(0, 0, W_PT, H_PT), stream=png)

    # ---------------- 10-11. ST-1 (Mathcad) ----------------
    pk.new("SHEAR TAB CONNECTION ST-1 - MATHCAD")
    y = pk.lines(40, 90, [
        "Single plate shear connection - AISC Manual Table 10-10a",
        f"Ru := {st['ru'] * KIP:.1f} kip     (max end reaction, {st['gov']}, page 7)",
        "Roof reactions (page 8) are lower and do not govern.",
        f"n_b := {st['bolts']}     d_b := 0.75 in     A325-N threads included",
        "Supporting girder web W24X55:  t_w := 0.395 in",
        "PL 3/8\" x 9\" A36,  E70XX fillet weld w := 0.25 in",
    ], font="helv", size=10, lead=16)
    y = pk.image(40, y + 6, _mathtext_png([
        r"$\phi R_{n,bolt} = \phi\, n_b\, F_{nv}\, A_b = 0.75 \cdot 4 \cdot 54\,\mathrm{ksi} \cdot 0.442\,\mathrm{in}^2$",
        r"$\phi R_{n,bolt} = 71.6\ \mathrm{kip}\ >\ R_u$",
        r"$\phi R_{n,weld} = \phi\, 0.6\, F_{EXX}\, \frac{\sqrt{2}}{2} w\, (2L)$",
    ]), 380)
    pk.lines(40, y + 14, [f"phiRn_bolt := 71.6 kip   >   Ru := {st['ru'] * KIP:.1f} kip     OK",
                          f"Applies to all ST-1 locations ({st['count']} total)."], font="helv", size=10, lead=16)
    pk.new("SHEAR TAB CONNECTION ST-1 - MATHCAD (cont.)")
    y = pk.image(40, 90, _mathtext_png([
        r"$\phi R_{n,yield} = 1.0 \cdot 0.6\, F_y\, A_g = 0.6 \cdot 36 \cdot 3.375 = 72.9\ \mathrm{kip}$",
        r"$\phi R_{n,block} = 0.75\,[0.6 F_u A_{nv} + U_{bs} F_u A_{nt}] = 66.2\ \mathrm{kip}$",
    ]), 400)
    pk.lines(40, y + 14, ["Plate shear yield, rupture and block shear OK.",
                          "Bolt bearing on girder web OK for t_w = 0.395 in."], font="helv", size=10, lead=16)

    # ---------------- 12. MF-1 (Mathcad) ----------------
    mf = res.mf1
    pk.new("MOMENT CONNECTION MF-1 - MATHCAD")
    y = pk.lines(40, 90, [
        "Bolted flange plate moment connection, grid 4 moment frame",
        f"Mu := {mf['mu'] * KFT:.1f} kip ft     Vu := {mf['vu'] * KIP:.1f} kip     (end moments, page 7)",
        "Frame beams 2B13 - 2B16, 3B13 - 3B16, RB13 - RB16",
        "Flange plates PL 3/4\" x 10\" A572-50,  (8) 7/8\" A490-X bolts per flange",
    ], font="helv", size=10, lead=16)
    y = pk.image(40, y + 6, _mathtext_png([
        r"$P_{uf} = \frac{M_u}{d} \qquad \phi R_n = \phi F_y A_g$",
        r"$\phi R_{n,bolt} = 8 \cdot 0.75 \cdot 84\,\mathrm{ksi} \cdot 0.601 = 303\ \mathrm{kip}$",
    ]), 360)
    pk.lines(40, y + 14, ["Panel zone check at columns C16 - C20:  OK",
                          f"Applies to all MF-1 locations ({mf['count']} total)."], font="helv", size=10, lead=16)

    # ---------------- 13-14. columns (RAM Structural System) ----------------
    cols = sorted(res.columns.values(), key=lambda c: int(c["mark"][1:]))
    pk.new("COLUMN DESIGN - RAM STRUCTURAL SYSTEM")
    y = pk.lines(40, 88, [
        "RAM Structural System v17 - Column Design Report",
        f"Columns C1 - C{len(cols) if b.rev == 1 else 20}, continuous Level 1 to Roof, K = 1.0, KL = 13.8 ft",
        f"Beam and girder reactions from pages 5-8; cantilever 2CB1 reaction {res.cant['r'] * KIP:.1f} k (hand calc)",
        "",
        f"{'Member':<8}{'Size':<9}{'Grid':<7}{'Pu k':>8}{'phiPn k':>10}{'Ratio':>8}",
    ], size=8.5)
    pk.lines(40, y, [f"{c['mark']:<8}{c['section']:<9}{c['grid']:<7}{c['pu'] * KIP:>8.0f}{c['phi_pn'] * KIP:>10.0f}"
                     f"{c['ratio']:>8.2f}" for c in cols], size=8.0, lead=11.6)
    pk.new("COLUMN DESIGN - RAM STRUCTURAL SYSTEM (cont.)")
    mfc = [c for c in cols if c.get("mf")]
    pk.lines(40, 92, [
        "Moment frame columns C16 - C20: Mu from MF-1 (page 12)",
        *[f"{c['mark']:<6}{c['section']:<9} combined P-M ratio {c['pm']:.2f}   OK" for c in mfc],
        "Brace forces from BR1 calc (page 16) included at C1, C6.",
        "Base reactions carried to base plate design (page 15).",
        "Base reactions carried to footing design (page 17).",
    ], size=9)

    # ---------------- 15. base plates (Mathcad) ----------------
    bpr = res.base_plate
    pk.new("COLUMN BASE PLATE DESIGN - MATHCAD")
    y = pk.lines(40, 90, [
        "Column base plates - typical at all columns",
        f"Pu := {bpr['pu'] * KIP:.0f} kip     (max column reaction, page 13)",
        "PL 1-1/2\" x 18\" x 18\" A36,  (4) 3/4\" F1554 Gr 36 anchor rods",
        "f'c := 4000 psi     A1 := 324 in^2",
    ], font="helv", size=10, lead=16)
    y = pk.image(40, y + 6, _mathtext_png([
        r"$\phi_c P_p = 0.65 \cdot 0.85\, f'_c\, A_1$",
        rf"$\phi_c P_p = {bpr['phi_pp'] * KIP:.0f}\ \mathrm{{kip}}\ >\ P_u = {bpr['pu'] * KIP:.0f}\ \mathrm{{kip}}$",
    ]), 340)
    pk.lines(40, y + 14, ["Bearing and plate bending OK."], font="helv", size=10)

    # ---------------- 16. bracing (Excel) ----------------
    br = res.brace
    pk.new("LATERAL BRACING BR1 - EXCEL")
    pk.lines(40, 88, ["Concentric X-brace, grid A between 1 and 2, all storeys  (Bracing_v2.xlsx)"], font="helv", size=10)
    rows = [["Storey", "Brace", "Section", "V (k)", "Pu (k)", "KL/r", "phiPn (k)", "Ratio"]]
    for s, v in enumerate(br["shears"]):
        pu = v / 2 / np.cos(np.arctan2(3.4, 6.74))
        rows.append([f"Level {s + 1}", "BR1", "HSS6X6X3/8", f"{v * KIP:.1f}", f"{pu * KIP:.1f}", f"{br['klr']:.0f}",
                     f"{br['phi_pn'] * KIP:.1f}", f"{pu / br['phi_pn']:.2f}"])
    y = pk.grid(40, 104, [62, 46, 82, 52, 52, 46, 66, 50], rows)
    pk.lines(40, y + 18, ["Brace forces carried to column design (page 13)."], font="helv", size=10)

    # ---------------- 17. footings (VBA) ----------------
    pk.new("SPREAD FOOTING DESIGN - VBA")
    pk.lines(40, 88, ["Generated by FTG_Design.xlsm v3.1",
                      "Column reactions from RAM (page 13);  allowable bearing 3,000 psf"], font="helv", size=10, lead=15)
    rows = [["Mark", "Size", "Thk (in)", "Pu (k)", "Ps (k)", "q (psf)", "Count", "Status"]]
    for mark in sorted(res.footings):
        s = res.footings[mark]
        side = f"{int(s['side_ft'])}'-{int(round((s['side_ft'] % 1) * 12))}\""
        rows.append([mark, f"{side} x {side}", f"{round(s['thk'] / 0.0254)}", f"{s['pu'] * KIP:.0f}", f"{s['ps'] * KIP:.0f}",
                     f"{s['q'] * 20.885:.0f}", f"{s['count']}", "OK"])
    pk.grid(40, 122, [42, 104, 52, 52, 52, 56, 46, 50], rows)

    assert pk.n == N_PAGES, pk.n
    pk.save(path)
    return {"pages": N_PAGES}


# ---------------------------------------------------------------- supplement (feature checks)
SUPPLEMENT_FILE = "calc_supplement.pdf"
SUPPLEMENT_PAGES = 3
WRONG_SIZE = "W27X94"  # not a section the model uses: the supplement's deliberate size mismatch


def write_supplement(b: B.Building, path: str) -> dict:
    """A short second calc package that exercises what the main package does not: a calc that starts
    mid-page, a calc that continues after a gap (two spans), a size-only "typical" calc (a typical-group
    link), a loads-only reference (role "loads"), and a calc that designs a member at a different size
    than the model (a size-mismatch finding). Returns its ground truth keyed by element KEY (generate()
    maps keys to GlobalIds)."""
    beams3 = sorted((e for e in b.elements if e.ifc_class == "IfcBeam" and e.storey == "Level 3" and e.mark),
                    key=lambda e: e.mark)
    by_mark = {e.mark: e for e in beams3}
    girder = by_mark["3G1"]
    loads = [by_mark[f"3B{n}"] for n in range(1, 5)]
    wrong = by_mark["3B5"]
    sizes: dict[str, int] = {}
    for e in beams3:
        if e.mark.startswith("3B"):
            sizes[e.object_type] = sizes.get(e.object_type, 0) + 1
    typical = sorted(sizes.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
    slab = next(e for e in b.elements if e.mark == "SL-2")
    assert wrong.object_type != WRONG_SIZE

    pk = Pkg()

    def page(title: str):
        pk.page = pk.doc.new_page(width=W_PT, height=H_PT)
        pk.n += 1
        pk.text(40, 34, f"JOB 2611 - SAMPLE OFFICE BUILDING     SUPPLEMENT S-{pk.n} OF {SUPPLEMENT_PAGES}     BY: EOR   "
                        f"DATE: 2026-11-09", font="helv", size=7.5)
        pk.page.draw_line((40, 40), (W_PT - 40, 40), color=(0.6, 0.6, 0.6), width=0.5)
        pk.text(40, 66, title, font="hebo", size=12.5)

    mid_y = 300.0
    t1 = "LEVEL 3 BEAM VIBRATION CHECK - TYPICAL"
    t2 = f"GIRDER {girder.mark} SPOT CHECK"
    t3 = "PT SLAB TENDON PROFILE CHECK"
    page(t1)
    pk.lines(40, 92, [
        "Walking vibration per AISC Design Guide 11",
        f"Level 3 typical beams {typical}, no individual marks",
        "fn = 6.1 Hz > 4.0 Hz   OK",
        "ap/g = 0.38% < 0.50%   OK",
    ], size=9)
    pk.text(40, mid_y, t2, font="hebo", size=12.5)
    pk.lines(40, mid_y + 26, [
        f"Girder {girder.mark} {girder.object_type}: Mu = 182.4 k-ft < phiMn = 249.0 k-ft   OK",
        f"Infill beam {wrong.mark} {WRONG_SIZE}: Mu = 61.2 k-ft < phiMn = 90.0 k-ft   OK",
        f"Loads: reactions from beams {loads[0].mark} - {loads[-1].mark}",
    ], size=9)
    page(t3)
    pk.lines(40, 92, [
        "Slab SL2 (Level 2): tendon low point at mid-bay, cover 1.0 in   OK",
        "Profile drape 5.5 in, balanced load 75% DL   OK",
    ], size=9)
    page(f"{t2} (cont.)")
    pk.lines(40, 92, [
        f"Deflection {girder.mark}: live load L/412 > L/360   OK",
        "End connection: see shear tab calc in the main package.",
    ], size=9)
    assert pk.n == SUPPLEMENT_PAGES, pk.n
    pk.save(path)

    title_top = mid_y - 12.5  # baseline minus the title's font size: where the mid-page calc starts
    return {
        "file": SUPPLEMENT_FILE,
        "calcs": [
            {"id": "S1", "title": t1, "element_type": "Beam", "spans": [[{"page": 1, "start_y": 0.0}]]},
            {"id": "S2", "title": t2, "element_type": "Beam",
             "spans": [[{"page": 1, "start_y": title_top}], [{"page": 3, "start_y": 0.0}]]},
            {"id": "S3", "title": t3, "element_type": "Slab", "spans": [[{"page": 2, "start_y": 0.0}]]},
        ],
        "roles": [{"key": girder.key, "calc": "S2", "role": "design"},
                  {"key": wrong.key, "calc": "S2", "role": "design"},
                  *({"key": e.key, "calc": "S2", "role": "loads"} for e in loads),
                  {"key": slab.key, "calc": "S3", "role": "design"}],
        "group_links": [{"cat": "Beam", "storey": "Level 3", "profile": typical, "calc": "S1"}],
        "mismatches": [{"key": wrong.key, "calc": "S2", "model_size": wrong.object_type, "calc_size": WRONG_SIZE}],
    }

