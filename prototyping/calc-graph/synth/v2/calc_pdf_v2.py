"""v2 calc package PDF: a realistic structural calculation submittal for the designed building.

    write(exp, d, path)                       -> full package (cover, TOC, sheets A1..E5); records
                                                 get page / bbox / sheet, exp gets occurrences +
                                                 calc_pages
    write_revision(exp, d, record_ids, path)  -> only the sheets holding those records, clouded,
                                                 with delta tags and a revision list; returns
                                                 {record id: {page, bbox, sheet}} (exp untouched)

Every printed number comes from `exp` (records) or `d` (the raw design); derived arithmetic on
a sheet is recomputed with the same formulas the design used (gravity.py, lateral.py), so a
sheet never disagrees with its record. Styles imitated (layout only, no vendor artwork):
Mathcad Prime worksheets (matplotlib mathtext raster + invisible text layer), RAM Structural
System and RISA-3D report tables, Enercalc "Steel Beam" sheets, Excel schedules, and scanned
hand calcs on engineering pad paper (one page with no text layer at all).

Firm, engineer, project and city are fictional. Byte-stable: fixed metadata, no timestamps,
seeded RNG, PNG metadata stripped, deterministic quantisation / JPEG encoding.
"""
from __future__ import annotations

import io
import math

import matplotlib

matplotlib.use("Agg")
import matplotlib.font_manager as fm  # noqa: E402
import matplotlib.patches as mpatches  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pymupdf  # noqa: E402
from PIL import Image, ImageFilter  # noqa: E402

from . import aisc  # noqa: E402
from . import gravity as G  # noqa: E402
from . import lateral as LAT  # noqa: E402

PW, PH = 612.0, 792.0
DPI = 200
FIRM = "CORLISS VANE"
FIRM2 = "STRUCTURAL ENGINEERS"
FIRM_FULL = "Corliss Vane Structural Engineers"
FIRM_ADDR = "410 Wharf Street, Suite 300, Port Ellery, CA"
PROJECT = "Harbor View Office"
CITY = "Port Ellery, CA"
JOB = "2611-04"
BY, CHK = "JTR", "MOL"
DATE = "11/14/2026"
ENGINEER = "Marisol O. Lindqvist, S.E."
CLIENT = "Ellery Waterfront Partners"
REVS = [("0", "10/30/2026", "Issued for permit"), ("1", "11/14/2026", "Plan check response - footing schedule re-issued")]
TEAL = (0.05, 0.33, 0.38)
GREY = (0.45, 0.45, 0.45)
BLUE = (0.0, 0.0, 0.62)
RED = (0.78, 0.05, 0.05)
BOTTOM = 728.0          # content must end above this (software footers / revision notes below)
RC = {"mathtext.fontset": "stix", "font.family": "STIXGeneral", "svg.hashsalt": "calc-v2"}


def f1(x, n=1):
    return "-" if x is None else f"{x:,.{n}f}"


def tl(s, font="helv", size=8.0):
    return pymupdf.get_text_length(s, fontname=font, fontsize=size)


def R(x0, y0, x1, y1):
    return pymupdf.Rect(x0, y0, x1, y1)


def ftin(ft: float) -> str:
    tot = round(ft * 12 * 4) / 4
    f, i = divmod(tot, 12)
    s = f"{i:g}" if i != int(i) else f"{int(i)}"
    return f"{int(f)}'-{s}\""


# ======================================================================= package core
class Pkg:
    def __init__(self, ctx: dict, rev_label: str | None = None):
        self.doc = pymupdf.open()
        self.ctx = ctx
        self.meta: list[dict] = []
        self.places: list[dict] = []
        self.deferred: list = []          # callables (page_no, total) run at finalize
        self.revs: dict[int, list] = {}   # page no -> [(rect, note)]
        self.calc_n: dict[str, int] = {}
        self.rev_label = rev_label

    # -------- pages
    def new_page(self, calc: str, style: str, landscape=False, text_layer=True, header=True):
        w, h = (PH, PW) if landscape else (PW, PH)
        pg = self.doc.new_page(width=w, height=h)
        if calc in ("COVER", "TOC"):
            sheet = calc
        else:
            k = self.calc_n[calc] = self.calc_n.get(calc, 0) + 1
            sheet = f"{calc}-{k}"
        self.meta.append({"page": len(self.meta) + 1, "sheet": sheet, "calc": calc, "style": style,
                          "text_layer": text_layer, "w": w, "h": h, "header": header})
        if header:
            pad_header(pg, sheet, w, self.ctx["calc_title"].get(calc, calc))
        return pg, sheet

    @property
    def pno(self) -> int:
        return len(self.meta)

    def place(self, rid: str, rect, text: str, elements=(), how="calc_row", page: int | None = None,
              text_layer: bool | None = None):
        p = page or self.pno
        m = self.meta[p - 1]
        self.places.append({"ref": rid, "page": p, "sheet": m["sheet"], "bbox": [round(rect[0], 2), round(rect[1], 2),
                                                                             round(rect[2], 2), round(rect[3], 2)],
                            "how": how, "text": text, "text_layer": m["text_layer"] if text_layer is None else text_layer,
                            "elements": list(elements)})

    def revise(self, page: int, rect, note: str):
        self.revs.setdefault(page, []).append((pymupdf.Rect(rect), note))

    # -------- finish
    def finalize(self, title: str):
        total = len(self.meta)
        for fn in self.deferred:
            fn(total)
        for m in self.meta:
            pg = self.doc[m["page"] - 1]
            if m["header"]:
                txt = f"Page {m['page']} of {total}"
                pg.insert_text((m["w"] - 36 - tl(txt, size=6.5), m["h"] - 14), txt, fontname="helv", fontsize=6.5, color=GREY)
                pg.insert_text((36, m["h"] - 14), f"{JOB}  {PROJECT} - Structural Calculations", fontname="helv",
                               fontsize=6.5, color=GREY)
            if m["page"] in self.revs:
                draw_revisions(pg, m, self.revs[m["page"]], self.rev_label or "1")
        self.doc.set_metadata({"title": title, "author": FIRM_FULL + " (synthetic)", "subject": f"{PROJECT} - job {JOB}",
                               "creator": "calc-graph synth v2", "producer": "PyMuPDF", "keywords": "",
                               "creationDate": "D:20261114090000-05'00'", "modDate": "D:20261114090000-05'00'"})

    def save(self, path: str):
        self.doc.save(path, garbage=3, deflate=True, no_new_id=True)


def pad_header(pg, sheet: str, w: float, subject: str, rev: str | None = None):
    """Firm calc-pad title strip (vector) on every sheet."""
    x0, x1, y0, y1 = 30.0, w - 30.0, 14.0, 60.0
    pg.draw_rect(R(x0, y0, x1, y1), color=(0, 0, 0), width=0.7)
    # logo cell
    lx = x0 + 150
    pg.draw_rect(R(x0 + 7, y0 + 8, x0 + 21, y0 + 22), color=None, fill=TEAL)
    pg.draw_rect(R(x0 + 13, y0 + 14, x0 + 27, y0 + 28), color=TEAL, width=1.1)
    pg.insert_text((x0 + 32, y0 + 17), FIRM, fontname="hebo", fontsize=10.5, color=TEAL)
    pg.insert_text((x0 + 32, y0 + 25), FIRM2, fontname="helv", fontsize=5.6, color=TEAL)
    pg.insert_text((x0 + 7, y0 + 38), FIRM_ADDR, fontname="helv", fontsize=4.6, color=GREY)
    pg.draw_line((lx, y0), (lx, y1), color=(0, 0, 0), width=0.5)
    sx = x1 - 64
    pg.draw_line((sx, y0), (sx, y1), color=(0, 0, 0), width=0.5)
    mid = lx + (sx - lx) * 0.62
    pg.draw_line((mid, y0), (mid, y1), color=(0, 0, 0), width=0.4)
    rows = [("project", PROJECT, "job no.", JOB), ("location", CITY, "date", DATE),
            ("subject", subject[:58], "by / chk", f"{BY}  /  {CHK}")]
    for i, (a, av, b, bv) in enumerate(rows):
        ry = y0 + i * (y1 - y0) / 3
        if i:
            pg.draw_line((lx, ry), (sx, ry), color=(0, 0, 0), width=0.3)
        pg.insert_text((lx + 3, ry + 6.5), a, fontname="helv", fontsize=4.6, color=GREY)
        pg.insert_text((lx + 34, ry + 11.5), av, fontname="helv", fontsize=7.2)
        pg.insert_text((mid + 3, ry + 6.5), b, fontname="helv", fontsize=4.6, color=GREY)
        pg.insert_text((mid + 34, ry + 11.5), bv, fontname="helv", fontsize=7.2)
    pg.insert_text((sx + 3, y0 + 7), "sheet no.", fontname="helv", fontsize=4.6, color=GREY)
    fs = 15 if len(sheet) <= 5 else 11
    pg.insert_text((sx + (64 - tl(sheet, "hebo", fs)) / 2, y0 + 30), sheet, fontname="hebo", fontsize=fs)
    if rev:
        pg.insert_text((sx + 3, y1 - 4), f"rev {rev}", fontname="helv", fontsize=5.5, color=RED)


def cloud(pg, rect, color=RED, bump=6.0):
    """Revision cloud: outward scallops along a rectangle."""
    hh = rect.y1 - rect.y0
    bump = min(bump, max(2.2, hh * 0.22))
    pad = min(3.0, max(1.0, hh * 0.08))
    r = pymupdf.Rect(rect.x0 - pad, rect.y0 - pad, rect.x1 + pad, rect.y1 + pad)
    sh = pg.new_shape()
    pts = []
    for (ax, ay), (bx, by), (nx, ny) in (((r.x0, r.y0), (r.x1, r.y0), (0, -1)), ((r.x1, r.y0), (r.x1, r.y1), (1, 0)),
                                         ((r.x1, r.y1), (r.x0, r.y1), (0, 1)), ((r.x0, r.y1), (r.x0, r.y0), (-1, 0))):
        L = math.hypot(bx - ax, by - ay)
        n = max(1, int(L // (bump * 2)))
        for k in range(n):
            p = (ax + (bx - ax) * k / n, ay + (by - ay) * k / n)
            q = (ax + (bx - ax) * (k + 1) / n, ay + (by - ay) * (k + 1) / n)
            h = min(bump, L / n * 0.55)
            c1 = (p[0] + (q[0] - p[0]) * 0.1 + nx * h, p[1] + (q[1] - p[1]) * 0.1 + ny * h)
            c2 = (p[0] + (q[0] - p[0]) * 0.9 + nx * h, p[1] + (q[1] - p[1]) * 0.9 + ny * h)
            pts.append((p, c1, c2, q))
    for p, c1, c2, q in pts:
        sh.draw_bezier(p, c1, c2, q)
    sh.finish(color=color, width=0.9, closePath=False)
    sh.commit()
    return r


def delta(pg, x, y, label, color=RED, s=10.0):
    sh = pg.new_shape()
    sh.draw_polyline([(x, y + s * 0.5), (x + s * 0.55, y - s * 0.45), (x + s * 1.1, y + s * 0.5), (x, y + s * 0.5)])
    sh.finish(color=color, width=0.9)
    sh.commit()
    fs = 6.5 if len(label) <= 2 else 4.5
    pg.insert_text((x + s * 0.55 - tl(label, "hebo", fs) / 2, y + s * 0.38), label, fontname="hebo", fontsize=fs, color=color)


def _merge(rects):
    out = []
    for r in sorted(rects, key=lambda r: (round(r.x0), r.y0)):
        if out and abs(out[-1].x0 - r.x0) < 2 and abs(out[-1].x1 - r.x1) < 2 and r.y0 - out[-1].y1 < 4:
            out[-1] = out[-1] | r
        else:
            out.append(pymupdf.Rect(r))
    return out


def draw_revisions(pg, m, items, label):
    lab = label.replace("Rev ", "").replace("rev ", "")
    rects = _merge([r for r, _ in items])
    for r in rects:
        c = cloud(pg, r)
        delta(pg, max(3.0, c.x0 - 13), (c.y0 + c.y1) / 2 - 4, lab, s=9)
    notes = [n for _, n in items if n]
    y = m["h"] - (92 if m["style"] == "excel" else 62)
    bx = R(36, y - 2, m["w"] - 36, y + 9 + 7.5 * min(2, max(1, len(notes))))
    pg.draw_rect(bx, color=None, fill=(1, 1, 1))
    pg.draw_rect(bx, color=RED, width=0.5)
    delta(pg, 40, y + 2, lab, s=8)
    pg.insert_text((54, y + 6.5), f"REVISION {lab} - {REVS[-1][1] if lab == '1' else DATE}   (changed rows clouded)",
                   fontname="hebo", fontsize=6, color=RED)
    for i, n in enumerate(notes[:2]):
        t = n if i < 1 or len(notes) <= 2 else f"+ {len(notes) - 1} more changed rows on this sheet (see clouds)"
        pg.insert_text((54, y + 14 + i * 7.5), t[:150], fontname="helv", fontsize=5.6, color=RED)


def table(pg, x, y, cols, rows, *, size=6.4, rh=9.2, font="helv", hfont="hebo", head_rh=None, head_fill=None,
          zebra=None, grid=(0.72, 0.72, 0.72), color=(0, 0, 0), hcolor=(0, 0, 0), index=False, hlines=False,
          head_rule=None, row_colors=None, cell_colors=None):
    """cols: [(title, width, align 'l'|'r'|'c')]; title may hold '\\n'. Returns (y_end, [row rects])."""
    xs = [x]
    if index:
        xs.append(x + 16)
    for _, w_, _ in cols:
        xs.append(xs[-1] + w_)
    ci = 1 if index else 0
    nl = max(c[0].count("\n") + 1 for c in cols)
    hh = head_rh or (rh * nl + 1)
    if head_fill:
        pg.draw_rect(R(xs[0], y, xs[-1], y + hh), color=None, fill=head_fill)
    for k, (t, w_, a) in enumerate(cols):
        lines = t.split("\n")
        for j, ln in enumerate(lines):
            yy = y + hh - (len(lines) - j - 1) * rh - 2.6
            cx0, cx1 = xs[k + ci], xs[k + ci + 1]
            tx = cx0 + 2 if a == "l" else (cx1 - 2 - tl(ln, hfont, size) if a == "r" else (cx0 + cx1 - tl(ln, hfont, size)) / 2)
            pg.insert_text((tx, yy), ln, fontname=hfont, fontsize=size, color=hcolor)
    if not hlines and grid:
        pg.draw_rect(R(xs[0], y, xs[-1], y + hh), color=grid, width=0.4)
    if head_rule:
        pg.draw_line((xs[0], y + hh), (xs[-1], y + hh), color=head_rule, width=0.8)
    out = []
    yy = y + hh
    for i, row in enumerate(rows):
        rr = R(xs[0], yy, xs[-1], yy + rh)
        if row_colors and row_colors[i]:
            pg.draw_rect(rr, color=None, fill=row_colors[i])
        elif zebra and i % 2 == 0:
            pg.draw_rect(rr, color=None, fill=zebra)
        if index:
            s = str(i + 1)
            pg.insert_text((xs[0] + 14 - tl(s, font, size), yy + rh - 2.5), s, fontname=font, fontsize=size)
        for k, (val, (_, w_, a)) in enumerate(zip(row, cols)):
            cx0, cx1 = xs[k + ci], xs[k + ci + 1]
            s = str(val)
            fw = tl(s, font, size)
            tx = cx0 + 2 if a == "l" else (cx1 - 2 - fw if a == "r" else (cx0 + cx1 - fw) / 2)
            col = cell_colors[i][k] if cell_colors and cell_colors[i] and cell_colors[i][k] else color
            pg.insert_text((tx, yy + rh - 2.5), s, fontname=font, fontsize=size, color=col)
        if grid and not hlines:
            for xx in xs:
                pg.draw_line((xx, yy), (xx, yy + rh), color=grid, width=0.3)
            pg.draw_line((xs[0], yy + rh), (xs[-1], yy + rh), color=grid, width=0.3)
        elif hlines and grid:
            pg.draw_line((xs[0], yy + rh), (xs[-1], yy + rh), color=grid, width=0.25)
        out.append(rr)
        yy += rh
    return yy, out


def flow(pkg, calc, style, deco, cols, items, *, rh=9.2, landscape=False, bottom=BOTTOM, first_extra=None,
         tbl_kw=None, x=None):
    """Paginate `items` [{rid, cells, key, elements, color?}] over pages decorated by deco(pg, k, n)
    which returns the y where the table starts. first_extra(pg, y) may draw above the table on
    page 1 and return a new y. Returns (pg, y_end)."""
    tbl_kw = tbl_kw or {}
    w = PH if landscape else PW
    x = 36 if x is None else x
    pages, i = [], 0
    # page count: simulate with a scratch decoration height (deco returns a fixed start y)
    n_est = 1
    remaining = len(items)
    ys = None
    while True:
        pg, sheet = pkg.new_page(calc, style, landscape=landscape)
        k = len(pages) + 1
        y = deco(pg, k, None)
        if k == 1 and first_extra:
            y = first_extra(pg, y)
        nl = max(c[0].count("\n") + 1 for c in cols)
        cap = int((bottom - y - (rh * nl + 1)) // rh)
        chunk = items[i:i + max(cap, 1)]
        _, rects = table(pg, x, y, cols, [it["cells"] for it in chunk], rh=rh,
                         row_colors=[it.get("fill") for it in chunk], **tbl_kw)
        for it, r in zip(chunk, rects):
            pkg.place(it["rid"], r, it["key"], it.get("elements", ()))
            if it.get("rev"):
                pkg.revise(pkg.pno, r, it["rev"])
        pages.append((pg, pkg.pno))
        i += len(chunk)
        ys = rects[-1].y1 if rects else y
        if i >= len(items):
            break
    n = len(pages)
    for k, (pg, pno) in enumerate(pages, start=1):
        deco(pg, k, n)
    _ = (n_est, remaining, w)
    return pages[-1][0], ys


# ======================================================================= Mathcad worksheet
class MC:
    """One Mathcad Prime style page: regions rendered with matplotlib mathtext into a page
    raster (inputs highlighted), each with an invisible text twin; vector tables on top."""

    def __init__(self, pkg: Pkg, calc: str, fname: str):
        self.pkg = pkg
        self.pg, self.sheet = pkg.new_page(calc, "mathcad")
        self.pno = pkg.pno
        self.fig = plt.figure(figsize=(8.5, 11), dpi=DPI)
        self.fig.patch.set_facecolor("white")
        self.r = self.fig.canvas.get_renderer()
        self.inv: list[tuple] = []
        self.y = 76.0
        self.fname = fname

    def _put(self, x, y, s, size, family=None, color="black", weight="normal", style="normal", z=3):
        kw = {"family": family} if family else {}
        t = self.fig.text(x / PW, 1 - y / PH, s, fontsize=size, color=color, va="baseline", ha="left", weight=weight,
                          style=style, zorder=z, **kw)
        bb = t.get_window_extent(self.r)
        return pymupdf.Rect(bb.x0 * 72 / DPI, PH - bb.y1 * 72 / DPI, bb.x1 * 72 / DPI, PH - bb.y0 * 72 / DPI)

    def box(self, r, fc, ec="none", lw=0.6, z=-2):
        self.fig.patches.append(mpatches.Rectangle((r.x0 / PW, 1 - r.y1 / PH), r.width / PW, r.height / PH,
                                                   transform=self.fig.transFigure, facecolor=fc, edgecolor=ec,
                                                   linewidth=lw, zorder=z))

    def text(self, x, y, s, size=9.0, bold=False, color="black", italic=False):
        r = self._put(x, y, s, size, family="Arial", color=color, weight="bold" if bold else "normal",
                      style="italic" if italic else "normal")
        self.inv.append((x, y, s, size))
        return r

    def math(self, x, y, tex, plain, size=10.5, inp=False):
        r = self._put(x, y, f"${tex}$", size)
        if inp:
            self.box(pymupdf.Rect(r.x0 - 2, r.y0 - 1.5, r.x1 + 2, r.y1 + 1.5), "#fff4a3")
        self.inv.append((x, y, plain, size * 0.85))
        return r

    def check(self, x, y, tex, plain, ok: bool, size=10.5):
        r = self.math(x, y, tex, plain, size)
        lab = "OK" if ok else "NG"
        r2 = self._put(r.x1 + 10, y, lab, size * 0.95, family="Arial", weight="bold",
                       color="#127a26" if ok else "#c01818")
        self.box(pymupdf.Rect(r2.x0 - 2, r2.y0 - 1, r2.x1 + 2, r2.y1 + 1), "#e2f4e2" if ok else "#fbe0e0")
        self.inv.append((r.x1 + 10, y, lab, size * 0.85))
        return r | r2

    def heading(self, s, size=11.5):
        self.y += 6
        r = self.text(40, self.y, s, size=size, bold=True)
        self.fig.lines.append(plt.Line2D([40 / PW, 572 / PW], [1 - (self.y + 3) / PH] * 2, transform=self.fig.transFigure,
                                         color="#4a6fa5", linewidth=0.6))
        self.y += 16
        return r

    def area(self, label, collapsed=True):
        """Mathcad area region boundary (collapsed areas show a lock and the area name)."""
        y = self.y
        self.fig.lines.append(plt.Line2D([40 / PW, 572 / PW], [1 - y / PH] * 2, transform=self.fig.transFigure,
                                         color="#7a7a7a", linewidth=0.5, linestyle=(0, (4, 2))))
        tri = [(44, y - 3.5), (44, y + 3.5), (50, y)] if collapsed else [(43, y - 3), (51, y - 3), (47, y + 3)]
        self.fig.patches.append(mpatches.Polygon([(a / PW, 1 - b / PH) for a, b in tri], closed=True,
                                                 transform=self.fig.transFigure, facecolor="#555555", edgecolor="none"))
        r = self._put(56, y + 2.6, label, 7.5, family="Arial", color="#444444", style="italic", z=6)
        self.box(pymupdf.Rect(r.x0 - 2, r.y0 - 0.5, r.x1 + 2, r.y1 + 0.5), "white", z=5)
        self.inv.append((56, y + 2.6, label, 6.5))
        if collapsed:
            lx = 560
            self.box(pymupdf.Rect(lx, y - 3, lx + 7, y + 3), "#9a9a9a", z=1)
            self.fig.patches.append(mpatches.Arc(((lx + 3.5) / PW, 1 - (y - 3) / PH), 5 / PW, 7 / PH, theta1=0, theta2=180,
                                                 transform=self.fig.transFigure, color="#9a9a9a", lw=0.8))
        self.y += 20
        return r

    def rows(self, items, x=46, lead=21.0, size=10.5):
        """items: (tex, plain, kind) kind in 'in' | 'eval' | ('chk', ok); returns union rect."""
        u = None
        for it in items:
            tex, plain, kind = it
            hh = lead * (1.45 if "dfrac" in tex else 1.0)
            if "dfrac" in tex:
                self.y += lead * 0.22
            if isinstance(kind, tuple):
                r = self.check(x, self.y, tex, plain, kind[1], size)
            else:
                r = self.math(x, self.y, tex, plain, size, inp=(kind == "in"))
            u = r if u is None else u | r
            self.y += hh - (lead * 0.22 if "dfrac" in tex else 0)
        return u

    def cols2(self, left, right, x2=320, lead=21.0, size=10.5):
        y0 = self.y
        a = self.rows(left, lead=lead, size=size)
        y1 = self.y
        self.y = y0
        b = self.rows(right, x=x2, lead=lead, size=size)
        self.y = max(y1, self.y)
        return a | b if a and b else (a or b)

    def finish(self):
        self.fig.text(40 / PW, 1 - 766 / PH, f"P:\\{JOB} Harbor View\\Calcs\\Mathcad\\{self.fname}", fontsize=5.5,
                      family="Arial", color="#777777")
        buf = io.BytesIO()
        self.fig.savefig(buf, format="png", metadata={"Software": None}, facecolor="white")
        plt.close(self.fig)
        img = Image.open(io.BytesIO(buf.getvalue())).convert("RGB").quantize(colors=48, method=Image.Quantize.MEDIANCUT,
                                                                               dither=Image.Dither.NONE)
        out = io.BytesIO()
        img.save(out, format="PNG", optimize=False)
        self.pg.insert_image(R(0, 0, PW, PH), stream=out.getvalue(), overlay=False)
        for x, y, s, size in self.inv:
            self.pg.insert_text((x, y), s, fontname="helv", fontsize=max(4.0, size), render_mode=3)
        self.pg.insert_text((40, 766), f"P:\\{JOB} Harbor View\\Calcs\\Mathcad\\{self.fname}", fontname="helv",
                            fontsize=5.5, render_mode=3)


MC_TABLE = {"size": 6.6, "rh": 10.0, "head_fill": (0.90, 0.92, 0.95), "grid": (0.62, 0.66, 0.72)}


# ======================================================================= styles: decorations
def ram_deco(title: str, floor: str, crit: str):
    def deco(pg, k, n):
        if n is None:
            y = 70
            pg.draw_line((36, y), (576, y), color=(0, 0, 0), width=1.2)
            pg.insert_text((38, y + 11), "RAM Steel 21.01.00.00", fontname="hebo", fontsize=8)
            pg.insert_text((38, y + 20), f"DataBase: HVO_{JOB}_R7", fontname="helv", fontsize=6.5)
            pg.insert_text((38, y + 28), "Building Code: IBC 2021", fontname="helv", fontsize=6.5)
            pg.insert_text((330, y + 20), "Steel Code: AISC 360-16 LRFD", fontname="helv", fontsize=6.5)
            pg.insert_text((330, y + 28), "11/12/26 16:42:07", fontname="helv", fontsize=6.5)
            pg.draw_line((36, y + 32), (576, y + 32), color=(0, 0, 0), width=0.6)
            pg.insert_text((306 - tl(title, "hebo", 9.5) / 2, y + 45), title, fontname="hebo", fontsize=9.5)
            pg.insert_text((38, y + 57), floor, fontname="hebo", fontsize=7)
            pg.insert_text((38, y + 66), crit, fontname="helv", fontsize=5.8)
            pg.draw_line((36, 758), (576, 758), color=(0, 0, 0), width=0.6)
            pg.insert_text((38, 766), "RAM Structural System - Gravity Steel Design", fontname="helv", fontsize=6)
            return y + 72
        s = f"Page {k}/{n}"
        pg.insert_text((576 - tl(s, size=6.5), 81), s, fontname="helv", fontsize=6.5)
        return None
    return deco


def risa_deco(model: str, title_fn):
    def deco(pg, k, n):
        if n is None:
            y = 70
            for i, (a, b) in enumerate((("Company", FIRM_FULL), ("Designer", BY), ("Job Number", JOB),
                                        ("Model Name", f"{PROJECT} - {model}"))):
                pg.insert_text((40, y + 9 + i * 8), a, fontname="helv", fontsize=6.6)
                pg.insert_text((92, y + 9 + i * 8), f":  {b}", fontname="helv", fontsize=6.6)
            for i, s in enumerate(("11/12/2026", "4:18 PM", f"Checked By: {CHK}")):
                pg.insert_text((470, y + 9 + i * 8), s, fontname="helv", fontsize=6.6)
            pg.draw_line((36, 757), (576, 757), color=(0, 0, 0), width=0.8)
            pg.insert_text((40, 766), "RISA-3D Version 19.0.2", fontname="helv", fontsize=6.6)
            fp = f"[P:\\{JOB} Harbor View\\Calcs\\RISA\\HVO_{model.replace(' ', '_')}.r3d]"
            pg.insert_text((306 - tl(fp, size=6.3) / 2, 766), fp, fontname="helv", fontsize=6.3)
            return y + 50
        s = f"Page {k}"
        pg.insert_text((572 - tl(s, size=6.6), 766), s, fontname="helv", fontsize=6.6)
        return None
    return deco


def risa_shape(name: str) -> str:
    """RISA prints HSS wall thickness in sixteenths: HSS8X8X5/16 -> HSS8X8X5, HSS6X6X1/8 -> HSS6X6X2."""
    if name.upper().startswith("HSS") and "/" in name:
        head, t = name.rsplit("X", 1)
        a, b = t.split("/")
        return f"{head}X{round(int(a) * 16 / int(b))}"
    return name


def risa_title(pg, y, s):
    pg.insert_text((40, y), s, fontname="hebi", fontsize=8.6)
    pg.draw_line((36, y + 2), (36 + tl(s, "hebi", 8.6) + 8, y + 2), color=(0, 0, 0), width=0.6)
    return y + 7


RISA_TBL = {"size": 6.4, "zebra": (0.88, 0.88, 0.88), "grid": (0.55, 0.55, 0.55), "color": BLUE, "hfont": "helv",
            "index": True}


def excel_cols(n):
    out = []
    for i in range(n):
        s, k = "", i
        while True:
            s = chr(65 + k % 26) + s
            k = k // 26 - 1
            if k < 0:
                break
        out.append(s)
    return out


def excel_grid(pg, x, y, widths, nrows, row0=1, rh=10.5, w=PW):
    """Spreadsheet print with gridlines + headings: column letters and row numbers."""
    xs = [x, x + 20]
    for wd in widths:
        xs.append(xs[-1] + wd)
    hdr = (0.91, 0.91, 0.91)
    pg.draw_rect(R(xs[0], y, xs[-1], y + rh), color=None, fill=hdr)
    pg.draw_rect(R(xs[0], y, xs[1], y + rh * (nrows + 1)), color=None, fill=hdr)
    for i, L in enumerate(excel_cols(len(widths))):
        cx = (xs[i + 1] + xs[i + 2]) / 2
        pg.insert_text((cx - tl(L, size=6.2) / 2, y + rh - 2.8), L, fontname="helv", fontsize=6.2, color=(0.3, 0.3, 0.3))
    for r in range(nrows):
        s = str(row0 + r)
        pg.insert_text((xs[1] - 3 - tl(s, size=6), y + rh * (r + 2) - 2.8), s, fontname="helv", fontsize=6, color=(0.3, 0.3, 0.3))
    g = (0.8, 0.8, 0.8)
    for xx in xs:
        pg.draw_line((xx, y), (xx, y + rh * (nrows + 1)), color=g, width=0.35)
    for r in range(nrows + 2):
        pg.draw_line((xs[0], y + rh * r), (xs[-1], y + rh * r), color=g, width=0.35)
    return xs


def excel_cell(pg, xs, y, rh, row, col, s, bold=False, align="l", color=(0, 0, 0), size=6.6, fill=None, span=1):
    x0, x1 = xs[col + 1], xs[col + 1 + span]
    top = y + rh * (row + 1)
    if fill:
        pg.draw_rect(R(x0 + 0.3, top + 0.3, x1 - 0.3, top + rh - 0.3), color=None, fill=fill)
    f = "hebo" if bold else "helv"
    s = str(s)
    tx = x0 + 2 if align == "l" else (x1 - 2 - tl(s, f, size) if align == "r" else (x0 + x1 - tl(s, f, size)) / 2)
    pg.insert_text((tx, top + rh - 2.8), s, fontname=f, fontsize=size, color=color)
    return R(xs[1], top, xs[-1], top + rh)


def excel_footer(pg, book, tab, tabs, w=PW, h=PH):
    y = h - 58
    x = 36
    for t in tabs:
        tw_ = tl(t, size=6) + 12
        pg.draw_rect(R(x, y, x + tw_, y + 10), color=(0.6, 0.6, 0.6), fill=(1, 1, 1) if t == tab else (0.9, 0.9, 0.9), width=0.4)
        pg.insert_text((x + 6, y + 7.3), t, fontname="hebo" if t == tab else "helv", fontsize=6)
        x += tw_
    pg.insert_text((36, h - 26), f"{book}   {DATE} 9:06 AM", fontname="helv", fontsize=6)
    pg.insert_text((w - 36 - tl(tab, size=6), h - 26), tab, fontname="helv", fontsize=6)


def excel_sheet(pkg, calc, book, tab, tabs, widths, title_rows, head, items, *, landscape=False, rh=10.5, note_rows=()):
    """Paginated Excel print: title rows, header row, data rows (one record each)."""
    w, h = (PH, PW) if landscape else (PW, PH)
    i = 0
    row0 = 1
    while True:
        pg, sheet = pkg.new_page(calc, "excel", landscape=landscape)
        y0 = 70
        cap = int((h - 98 - y0) // rh) - 1
        lines = []
        if i == 0:
            lines += [("title", t) for t in title_rows] + [("blank", "")]
        lines.append(("head", head))
        room = cap - len(lines)
        chunk = items[i:i + room]
        tail = []
        if i + len(chunk) >= len(items):
            tail = [("blank", "")] + [("note", t) for t in note_rows]
            if len(lines) + len(chunk) + len(tail) > cap:
                tail = []
        nrows = len(lines) + len(chunk) + len(tail)
        xs = excel_grid(pg, 36, y0, widths, nrows, row0=row0, rh=rh, w=w)
        r = 0
        for kind, val in lines:
            if kind == "title":
                excel_cell(pg, xs, y0, rh, r, 0, val, bold=r == 0, size=7.4 if r == 0 else 6.6, span=len(widths))
            elif kind == "head":
                for c, s in enumerate(val):
                    excel_cell(pg, xs, y0, rh, r, c, s, bold=True, align="c", fill=(0.84, 0.89, 0.95), size=6.2)
            r += 1
        for it in chunk:
            rect = None
            for c, s in enumerate(it["cells"]):
                al = "l" if c < it.get("left", 2) else "r"
                col = it.get("colors", {}).get(c, (0, 0, 0))
                rect = excel_cell(pg, xs, y0, rh, r, c, s, align=al, color=col, fill=it.get("fill"))
            pkg.place(it["rid"], rect, it["key"], it.get("elements", ()))
            if it.get("rev"):
                pkg.revise(pkg.pno, rect, it["rev"])
            r += 1
        for kind, val in tail:
            if kind == "note":
                excel_cell(pg, xs, y0, rh, r, 0, val, size=6.2, color=(0.25, 0.25, 0.25), span=len(widths))
            r += 1
        excel_footer(pg, book, tab, tabs, w, h)
        row0 += nrows
        i += len(chunk)
        if i >= len(items):
            return pg


# ======================================================================= helpers on data
def _area_rid(name: str) -> str:
    return "A2-" + name.replace(" ", "_").replace("(", "").replace(")", "")


def _uc_col(uc):
    return RED if uc is not None and uc > 1.0 + 1e-9 else (0, 0, 0)


GOV = {"flexure": "Flex", "shear": "Shear", "defl_live": "Defl-L", "defl_total": "Defl-T", "bearing": "Bearing",
       "punching": "Punching", "one_way": "1-way V"}


# ======================================================================= A
def calc_A1(pkg, ctx):
    rec = ctx["recs"]["A1"][0]
    v = rec["values"]
    mc = MC(pkg, "A1", f"{JOB}_A1_Criteria.mcdx")
    mc.heading("DESIGN CRITERIA")
    top = mc.y - 12
    mc.text(40, mc.y, "Governing codes:  " + v["codes"], size=8.6)
    mc.y += 13
    mc.text(40, mc.y, "Steel: " + v["steel"], size=8.6)
    mc.y += 13
    mc.text(40, mc.y, "Bolts: " + v["bolts"] + ".   Concrete: " + v["concrete"], size=8.6)
    mc.y += 13
    mc.text(40, mc.y, "Soil: " + v["soil"] + " (geotechnical report by others).   Seismic: " + v["seismic"] + ".", size=8.6)
    mc.y += 13
    mc.text(40, mc.y, "Wind: " + v["wind"] + "; MWFRS by simplified net pressure, see C2.", size=8.6)
    mc.y += 18
    mc.area("Materials", collapsed=False)
    mc.cols2([(r"F_y \coloneq 50\ \mathrm{ksi}", "F_y := 50 ksi (A992)", "in"),
              (r"F_{y.HSS} \coloneq 50\ \mathrm{ksi}", "F_y.HSS := 50 ksi (A500 C)", "in"),
              (r"F_{y.pl} \coloneq 36\ \mathrm{ksi}\quad F_{u.pl} \coloneq 58\ \mathrm{ksi}", "F_y.pl := 36 ksi  F_u.pl := 58 ksi", "in"),
              (r"E \coloneq 29000\ \mathrm{ksi}\quad G \coloneq 11200\ \mathrm{ksi}", "E := 29000 ksi  G := 11200 ksi", "in")],
             [(r"f^{\prime}_c \coloneq %g\ \mathrm{ksi}" % G.FC, f"f'c := {G.FC:g} ksi (footings, piers)", "in"),
              (r"f_y \coloneq %g\ \mathrm{ksi}" % G.FY_R, f"fy := {G.FY_R:g} ksi (A615 Gr 60)", "in"),
              (r"q_a \coloneq %.1f\ \mathrm{ksf}" % G.QA, f"q_a := {G.QA:.1f} ksf net allowable", "in"),
              (r"\gamma_c \coloneq %g\ \mathrm{pcf}" % (G.CONC * 1000), f"gamma_c := {G.CONC * 1000:g} pcf", "in")])
    mc.area("Site seismic and wind parameters", collapsed=False)
    mc.cols2([(r"S_{DS} \coloneq %.2f\quad S_{D1} \coloneq %.2f" % (LAT.SDS, LAT.SD1), f"S_DS := {LAT.SDS:.2f}  S_D1 := {LAT.SD1:.2f}", "in"),
              (r"I_e \coloneq %.2f\quad \mathrm{Site\ D,\ RC\ II,\ SDC\ D}" % LAT.IE, f"I_e := {LAT.IE:.2f}  Site D, RC II, SDC D", "in"),
              (r"\Delta_a \coloneq %.3f \cdot h_{sx}" % LAT.DRIFT_LIM, f"Delta_a := {LAT.DRIFT_LIM:.3f} hsx (12.12-1)", "in")],
             [(r"V_{ult} \coloneq 110\ \mathrm{mph}\quad \mathrm{Exp.\ C}", "V := 110 mph exposure C", "in"),
              (r"p_{net} \coloneq %.0f\ \mathrm{psf}" % LAT.WIND_PSF, f"p_net := {LAT.WIND_PSF:.0f} psf", "in"),
              (r"h_n \coloneq %.0f\ \mathrm{ft}" % ctx["levels"][-1]["elev_ft"], f"h_n := {ctx['levels'][-1]['elev_ft']:.0f} ft", "in")])
    mc.area("Load combinations (ASCE 7-16 2.3.1, 2.3.6)", collapsed=False)
    s1 = 1.2 + 0.2 * LAT.SDS
    s2 = 0.9 - 0.2 * LAT.SDS
    combos = [f"LC1: {G.COMBO_TXT['LC1']}", f"LC2: {G.COMBO_TXT['LC2']}", f"LC3: {G.COMBO_TXT['LC3']}",
              f"S1/S3: {s1:.1f}D + 0.5L +/- rho E  (rho = 1.0 X, 1.3 Y)", f"S2: {s2:.1f}D +/- rho E",
              "Om: (1.2 + 0.2 SDS)D + 0.5L + Omega0 E (collectors, SCBF columns)", "W1: 1.2D + 0.5L + 1.0W",
              "Service: D + L (total defl. L/240), L or Lr (L/360 floors, L/240 roof)"]
    for i, c in enumerate(combos):
        mc.text(50 + (i % 2) * 265, mc.y + (i // 2) * 13, c, size=8.4)
    mc.y += 13 * 4 + 10
    mc.area("Levels and grid", collapsed=False)
    lv = ctx["levels"]
    gx, gy = ctx["grids"]["x"], ctx["grids"]["y"]
    mc.cols2([(r"z_{%s} \coloneq %.1f\ \mathrm{ft}" % (L["key"], L["elev_ft"]), f"z_{L['key']} := {L['elev_ft']:.1f} ft ({L['name']})", "in")
              for L in lv],
             [(r"L_x \coloneq %.0f\ \mathrm{ft}\ (%d\ \mathrm{bays})" % (gx[-1][1] - gx[0][1], len(gx) - 1),
               f"L_x := {gx[-1][1] - gx[0][1]:.0f} ft", "eval"),
              (r"L_y \coloneq %.0f\ \mathrm{ft}" % (gy[-1][1] - gy[0][1]), f"L_y := {gy[-1][1] - gy[0][1]:.0f} ft", "eval"),
              (r"A_{floor} \coloneq L_x \cdot L_y = %s\ \mathrm{ft}^2" % f"{(gx[-1][1] - gx[0][1]) * (gy[-1][1] - gy[0][1]):,.0f}".replace(",", "{,}"),
               f"A_floor := {(gx[-1][1] - gx[0][1]) * (gy[-1][1] - gy[0][1]):,.0f} ft2", "eval")])
    mc.area("Gravity design basis", collapsed=True)
    mc.text(46, mc.y, "Beams and girders simple span, non-composite for strength and stiffness (conservative); no live load "
                      "reduction.", size=8.4)
    mc.y += 12
    mc.text(46, mc.y, "Columns: K = 1.0, KL = storey height, eccentric shear-tab reactions, pattern live load.", size=8.4)
    mc.y += 8
    pkg.place(rec["id"], R(38, top, 574, mc.y), "Governing codes:  " + v["codes"][:40])
    mc.finish()


def calc_A2(pkg, ctx):
    recs = ctx["recs"]["A2"]
    areas = {a["name"]: a for a in ctx["areas"]}
    items = []
    for r in recs:
        v = r["values"]
        x0, y0, x1, y1 = v["extent_ft"]
        a = (x1 - x0) * (y1 - y0)
        wu = max(G.fac([v["D_psf"], v["L_psf"], v["Lr_psf"]], c) for c in G.COMBOS)
        se = areas.get(v["name"], {}).get("seis_extra_psf", 0.0)
        items.append({"rid": r["id"], "key": f"{v['name']} D {v['D_psf']:g} psf",
                      "cells": [v["name"], v["level"], v["kind"], f"{x0:g}", f"{y0:g}", f"{x1:g}", f"{y1:g}", f"{a:,.0f}",
                                f"{v['D_psf']:.1f}", f"{v['L_psf']:.1f}", f"{v['Lr_psf']:.1f}",
                                f"{v['D_psf'] + v['L_psf'] + v['Lr_psf']:.1f}", f"{wu:.1f}", f"{se:.1f}",
                                f"{a * v['D_psf'] / 1000:,.1f}"], "left": 3})
    excel_sheet(pkg, "A2", f"{JOB}_Gravity Loads.xlsx", "Area loads", ["Area loads", "Wall", "Notes"],
                [74, 26, 40, 24, 24, 24, 24, 38, 32, 32, 32, 34, 36, 34, 36],
                [f"{PROJECT.upper()} - GRAVITY LOADS BY AREA (A2)",
                 "Superimposed dead includes deck + slab; steel self weight added per member (RAM / Enercalc).",
                 "Extents in ft from grid 1 / grid A.  wu = max(1.4D, 1.2D+1.6L+0.5Lr, 1.2D+1.6Lr+0.5L).  No live load reduction."],
                ["Area", "Level", "Use", "x0", "y0", "x1", "y1", "A ft2", "D psf", "L psf", "Lr psf", "Tot psf", "wu psf",
                 "Seis+ psf", "A*D kip"], items,
                note_rows=[f"Perimeter wall: {G.WALL_PSF if hasattr(G, 'WALL_PSF') else 15:g} psf on elevation, "
                           f"parapet {LAT.PARAPET_FT:g} ft.  Seis+ = partition allowance in seismic weight (ASCE 7-16 12.7.2).",
                           "Mech (RTU zone) on the roof replaces the roof area inside its extent (A2 order = precedence)."])


# ======================================================================= B
def _members_at(ctx, level):
    return [e for e in ctx["exp"]["elements"] if e["type"] in ("beam", "girder") and e.get("level") == level]


def ram_plan_page(pkg, ctx, calc, level, lvname):
    pg, sheet = pkg.new_page(calc, "ram_table")
    deco = ram_deco(f"RAM Steel - Floor Plan, Beam Sizes: {lvname}", f"Floor Type: {lvname}",
                    "Sizes shown as SIZE (studs) c=camber.  Thick = SMF beam (designed in RISA, C3/C4).  "
                    "COLL = collector (C6).  [E] = Enercalc (B4).")
    y = deco(pg, 1, None)
    deco(pg, 1, 1)
    gx, gy = ctx["grids"]["x"], ctx["grids"]["y"]
    sc = 3.85
    ox, oy = 72, y + 40
    X = lambda x: ox + x * sc  # noqa: E731
    Y = lambda yy: oy + (gy[-1][1] - yy) * sc  # noqa: E731
    for lab, x in gx:
        pg.draw_line((X(x), oy - 22), (X(x), Y(0) + 14), color=(0.55, 0.55, 0.55), width=0.3, dashes="[6 2 1 2] 0")
        pg.draw_circle((X(x), oy - 30), 7, color=(0, 0, 0), width=0.6)
        pg.insert_text((X(x) - tl(lab, "hebo", 7) / 2, oy - 27.5), lab, fontname="hebo", fontsize=7)
    for lab, yy in gy:
        pg.draw_line((ox - 22, Y(yy)), (X(gx[-1][1]) + 14, Y(yy)), color=(0.55, 0.55, 0.55), width=0.3, dashes="[6 2 1 2] 0")
        pg.draw_circle((ox - 30, Y(yy)), 7, color=(0, 0, 0), width=0.6)
        pg.insert_text((ox - 30 - tl(lab, "hebo", 7) / 2, Y(yy) + 2.5), lab, fontname="hebo", fontsize=7)
    for e in _members_at(ctx, level):
        (x1, y1, _), (x2, y2, _) = e["p1"], e["p2"]
        smf = "smf_beam" in e["roles"]
        pg.draw_line((X(x1), Y(y1)), (X(x2), Y(y2)), color=(0, 0, 0), width=2.2 if smf else 0.8)
        lab = e["size"]
        rid = ("C-MFB:" if smf else "B-BM:") + e["id"]
        rr = ctx["rec"].get(rid)
        if not smf:
            lab += f" ({e['studs']})"
            if e.get("camber_in"):
                lab += f" c={e['camber_in']:g}"
        if "collector" in e["roles"]:
            lab += " COLL"
        if rr and rr["calc"] == "B4":
            lab += " [E]"
        mx, my = (X(x1) + X(x2)) / 2, (Y(y1) + Y(y2)) / 2
        if abs(x2 - x1) >= abs(y2 - y1):
            pg.insert_text((mx - tl(lab, size=4.4) / 2, my - 1.8), lab, fontname="helv", fontsize=4.4)
        else:
            pg.insert_text((mx + 4.6, my + tl(lab, size=4.4) / 2), lab, fontname="helv", fontsize=4.4, rotate=90)
    for e in ctx["exp"]["elements"]:
        if e["type"] == "column":
            pg.draw_rect(R(X(e["x"]) - 3, Y(e["y"]) - 3, X(e["x"]) + 3, Y(e["y"]) + 3), color=(0, 0, 0), fill=(0.2, 0.2, 0.2))
    yb = Y(0) + 34
    pg.insert_text((40, yb), f"Plan origin at grid 1/A.  Scale approx. 1\" = 19'-0\".  Members: "
                             f"{len(_members_at(ctx, level))}.  Deck: {'3\" 20 ga composite + 3-1/4\" LW' if level != 'RF' else '1-1/2\" 20 ga type B roof deck'}.",
                   fontname="helv", fontsize=6)


def calc_B_ram(pkg, ctx, calc):
    level = {"B1": "L2", "B2": "L3", "B3": "RF"}[calc]
    lvname = {"L2": "Level 2", "L3": "Level 3", "RF": "Roof"}[level]
    ram_plan_page(pkg, ctx, calc, level, lvname)
    recs = ctx["recs"][calc]
    order = {"girder": 0, "beam": 1, "infill": 2}
    recs = sorted(recs, key=lambda r: (order.get(ctx["el"][r["elements"][0]].get("kind"), 3), r["elements"][0]))
    roof = level == "RF"
    items = []
    for r in recs:
        v = r["values"]
        mid = r["elements"][0]
        wl = v["w_Lr_klf"] if roof else v["w_L_klf"]
        items.append({"rid": r["id"], "key": f"{mid} {v['size']}", "elements": [mid],
                      "cells": [mid, v["size"], f"{v['span_ft']:.2f}", f"{v['Lb_ft']:.1f}", f"{v['w_D_klf']:.3f}", f"{wl:.3f}",
                                str(v["point_loads"]), f"{v['Mu_kft']:.1f}", f"{v['phiMn_kft']:.1f}", v["flex_eq"],
                                f"{v['Vu_k']:.1f}", f"{v['phiVn_k']:.1f}", f"{v['defl_L_in']:.2f}/{v['defl_L_allow_in']:.2f}",
                                f"{v['defl_T_in']:.2f}/{v['defl_T_allow_in']:.2f}", f"{v['camber_in']:g}" if v["camber_in"] else "-",
                                str(v["studs"]), f"{v['R_i_k']:.1f}", f"{v['R_j_k']:.1f}", f"{r['uc']:.3f}", GOV.get(v["governs"], v["governs"])],
                      "fill": (1.0, 0.85, 0.85) if r["uc"] and r["uc"] > 1 else None})
    cols = [("Beam", 50, "l"), ("Size", 34, "l"), ("Span\nft", 22, "r"), ("Lb\nft", 18, "r"), ("wD\nklf", 24, "r"),
            ("wLr\nklf" if roof else "wL\nklf", 23, "r"), ("Pt\nlds", 14, "r"), ("Mu\nk-ft", 27, "r"), ("phiMn\nk-ft", 28, "r"),
            ("Eq", 20, "c"), ("Vu\nk", 20, "r"), ("phiVn\nk", 23, "r"), ("DefL in\n/allow", 33, "r"), ("DefT in\n/allow", 33, "r"),
            ("Cmbr\nin", 18, "r"), ("Studs", 20, "r"), ("Ri\nk", 20, "r"), ("Rj\nk", 20, "r"), ("Ratio", 24, "r"), ("Ctrl", 25, "l")]
    deco = ram_deco(f"Gravity Beam Design Summary - {lvname}", f"Floor Type: {lvname}     Story: {lvname}",
                    "Non-composite; deck braces beam top flanges, girders braced at framing points.  LL reduction: none.  "
                    f"Defl. limits: {'Lr L/240' if roof else 'L L/360'}, total L/240.  Reactions = max factored (LRFD).")
    flow(pkg, calc, "ram_table", deco, cols, items, rh=9.0,
         tbl_kw={"size": 5.9, "hlines": True, "grid": (0.7, 0.7, 0.7), "head_rule": (0, 0, 0), "hfont": "hebo"}, x=38)


def calc_B5(pkg, ctx):
    recs = ctx["recs"]["B5"]
    items = []
    for r in recs:
        v = r["values"]
        cid = r["elements"][0]
        el = ctx["el"][cid]
        items.append({"rid": r["id"], "key": f"{cid} {v['size']}", "elements": [cid],
                      "cells": [cid, v["size"], str(v["storey"]), f"{v['KL_ft']:.1f}", f1(v["KL_r"]), f"{v['Pu_k']:.1f}",
                                f"{v['phiPn_k']:.1f}", f"{v['Mux_kft']:.1f}", f"{v['phiMnx_kft']:.1f}", f"{v['Muy_kft']:.1f}",
                                f"{v['phiMny_kft']:.1f}", v["eq"], r["lc"], f"{r['uc']:.3f}", f"{v['P_base_D']:.1f}",
                                f"{v['P_base_L']:.1f}", f"{v['P_base_Lr']:.1f}"]})
    cols = [("Column", 34, "l"), ("Size", 36, "l"), ("Stry", 20, "r"), ("KL\nft", 22, "r"), ("KL/r", 24, "r"), ("Pu\nk", 30, "r"),
            ("phiPn\nk", 32, "r"), ("Mux\nk-ft", 28, "r"), ("phiMnx\nk-ft", 32, "r"), ("Muy\nk-ft", 28, "r"),
            ("phiMny\nk-ft", 32, "r"), ("Eq", 30, "c"), ("LC", 24, "c"), ("Ratio", 28, "r"), ("Base D\nk", 30, "r"),
            ("Base L\nk", 30, "r"), ("Base Lr\nk", 32, "r")]
    deco = ram_deco("Gravity Column Design Summary", "All gravity columns (SMF / SCBF columns: see C3 to C5)",
                    "K = 1.0, KL = storey height both axes.  Eccentric shear-tab reactions (d/2 + 3 in strong axis, 3 in weak), "
                    "pattern live load.  Governing storey and combination shown.")

    def notes(pg, y):
        return y
    pg, y = flow(pkg, "B5", "ram_table", deco, cols, items, rh=11.0, first_extra=notes,
                 tbl_kw={"size": 6.2, "hlines": True, "grid": (0.7, 0.7, 0.7), "head_rule": (0, 0, 0), "hfont": "hebo"}, x=38)
    y += 16
    pg.insert_text((40, y), "LC1 = 1.4D;  LC2 = 1.2D+1.6L+0.5Lr;  LC3 = 1.2D+1.6Lr+0.5L.  Base loads are unfactored column "
                            "axial at the base plate (to E5 / D1 / D2).", fontname="helv", fontsize=6)


def _beam_combo_table(d, mid):
    """Per-combo Mu / Vu and deflection location, recomputed with gravity.py's own beam model."""
    r = d["framing"][mid]
    base, unit = G._sb_pair(r["span"], r["w"], r["pts"])
    sw = r["sw"]
    Mk = [[bm[0] + sw * um[0], bm[1], bm[2]] for bm, um in zip(base["M"], unit["M"])]
    dk = [[bd[0] + sw * ud[0], bd[1], bd[2]] for bd, ud in zip(base["d"], unit["d"])]
    out = {}
    for c, f in G.COMBOS.items():
        mu = max(f[0] * m[0] + f[1] * m[1] + f[2] * m[2] for m in Mk)
        vu = max(G.fac(r["Ri"], c), G.fac(r["Rj"], c))
        out[c] = (mu, vu)
    k = max(range(len(dk)), key=lambda i: sum(dk[i]))
    return out, base["xs"][k]


def calc_B4(pkg, ctx):
    d = ctx["d"]
    for r in ctx["recs"]["B4"]:
        v = r["values"]
        mid = r["elements"][0]
        fr = d["framing"][mid]
        el = ctx["el"][mid]
        pg, sheet = pkg.new_page("B4", "enercalc")
        top = 70
        for i, (a, b) in enumerate((("Project Title:", PROJECT), ("Engineer:", BY), ("Project ID:", JOB),
                                    ("Project Descr:", "Roof framing at mechanical (RTU) zone"))):
            pg.insert_text((330, top + 9 + i * 8), a, fontname="helv", fontsize=6.6)
            pg.insert_text((392, top + 9 + i * 8), b, fontname="helv", fontsize=6.6)
        y = top + 46
        pg.insert_text((40, y), "Steel Beam", fontname="hebo", fontsize=12, color=(0.08, 0.15, 0.45))
        pg.insert_text((572 - tl(f"File: HVO_{JOB}_MechRoof.ec6", size=5.6), y + 1), f"File: HVO_{JOB}_MechRoof.ec6", fontname="helv", fontsize=5.6)
        pg.insert_text((150, y + 1), "Software copyright ENERCALC, INC. 1983-2020, Build:12.20.8.24", fontname="helv", fontsize=5.0)
        pg.draw_rect(R(36, y + 3, 576, y + 12), color=None, fill=(0.35, 0.35, 0.38))
        pg.insert_text((40, y + 10), "Lic. # : SAMPLE-000000", fontname="hebo", fontsize=6, color=(1, 1, 1))
        pg.insert_text((572 - tl(FIRM_FULL.upper(), "hebo", 6), y + 10), FIRM_FULL.upper(), fontname="hebo", fontsize=6, color=(1, 1, 1))
        y += 24
        kind = "Girder" if el["kind"] == "girder" else "Infill beam"
        desc = f"{mid}  -  {kind}, roof mech area ({el['size']})"
        pg.insert_text((40, y), "DESCRIPTION:", fontname="helv", fontsize=7.5)
        pg.insert_text((110, y), desc, fontname="helv", fontsize=7.5, color=BLUE)
        blk_top = y - 9
        y += 16
        pg.insert_text((40, y), "CODE REFERENCES", fontname="hebi", fontsize=8.5, color=(0.08, 0.15, 0.45))
        pg.insert_text((40, y + 10), "Calculations per AISC 360-16, IBC 2021, ASCE 7-16", fontname="helv", fontsize=7)
        pg.insert_text((40, y + 19), "Load Combination Set : ASCE 7-16", fontname="helv", fontsize=7)
        y += 32
        pg.insert_text((40, y), "Material Properties", fontname="hebo", fontsize=8, color=(0.08, 0.15, 0.45))
        s = aisc.get(v["size"])
        mp = [("Analysis Method :", "Load Resistance Factor Design"), ("Beam Bracing :", f"Unbraced Lb = {v['Lb_ft']:.1f} ft" if v["Lb_ft"] else "Completely Braced (deck)"),
              ("Bending Axis :", "Major Axis Bending")]
        for i, (a, b) in enumerate(mp):
            pg.insert_text((48, y + 10 + i * 9), a, fontname="helv", fontsize=6.6)
            pg.insert_text((118, y + 10 + i * 9), b, fontname="helv", fontsize=6.6, color=BLUE)
        for i, (a, b) in enumerate((("Fy : Steel Yield :", "50.0 ksi"), ("E: Modulus :", "29,000.0 ksi"),
                                    ("Section d / bf :", f"{s['d']:.2f} / {s['bf']:.2f} in"),
                                    ("Ix / Zx :", f"{s['Ix']:,.0f} in4 / {s['Zx']:.1f} in3"))):
            pg.insert_text((340, y + 10 + i * 9), a, fontname="helv", fontsize=6.6)
            pg.insert_text((420, y + 10 + i * 9), b, fontname="helv", fontsize=6.6, color=BLUE)
        y += 48
        # diagram
        bx0, bx1, by = 70, 540, y + 40
        pg.draw_rect(R(bx0, by - 4, bx1, by + 4), color=(0.4, 0.4, 0.4), fill=(0.82, 0.82, 0.82), width=0.4)
        for sx in (bx0, bx1):
            pg.draw_polyline([(sx, by + 4), (sx - 6, by + 13), (sx + 6, by + 13), (sx, by + 4)], color=(0, 0, 0), width=0.5)
        wtxt = f"D({v['w_D_klf']:.3f})" + (f" L({v['w_L_klf']:.3f})" if v["w_L_klf"] else "") + (f" Lr({v['w_Lr_klf']:.3f})" if v["w_Lr_klf"] else "")
        if v["w_D_klf"] or v["w_L_klf"] or v["w_Lr_klf"]:
            pg.draw_line((bx0, by - 16), (bx1, by - 16), color=(0.3, 0.3, 0.3), width=0.5)
            for k in range(13):
                xx = bx0 + (bx1 - bx0) * k / 12
                pg.draw_line((xx, by - 16), (xx, by - 5), color=(0.3, 0.3, 0.3), width=0.4)
            pg.insert_text(((bx0 + bx1) / 2 - tl(wtxt, size=6) / 2, by - 19), wtxt, fontname="helv", fontsize=6)
        merged = {}
        for a, p in fr["pts"]:
            q = merged.setdefault(round(a, 3), [0.0, 0.0, 0.0])
            for n_ in range(3):
                q[n_] += p[n_]
        for a, p in sorted(merged.items()):
            xx = bx0 + (bx1 - bx0) * a / fr["span"]
            pg.draw_line((xx, by - 34), (xx, by - 5), color=(0, 0, 0), width=0.8)
            pg.draw_polyline([(xx - 2.5, by - 9), (xx, by - 5), (xx + 2.5, by - 9)], color=(0, 0, 0), width=0.8)
            lab = f"D({p[0]:.2f})" + (f" L({p[1]:.2f})" if p[1] else "") + (f" Lr({p[2]:.2f})" if p[2] else "")
            pg.insert_text((xx - tl(lab, size=5.6) / 2, by - 37), lab, fontname="helv", fontsize=5.6)
        pg.insert_text(((bx0 + bx1) / 2 - tl(v["size"], size=6.5) / 2, by + 15), v["size"], fontname="helv", fontsize=6.5)
        sp = f"Span = {v['span_ft']:.2f} ft"
        pg.draw_line((bx0, by + 24), (bx1, by + 24), color=(0, 0, 0), width=0.4)
        pg.insert_text(((bx0 + bx1) / 2 - tl(sp, size=6.5) / 2, by + 32), sp, fontname="helv", fontsize=6.5)
        y = by + 46
        pg.insert_text((40, y), "Applied Loads", fontname="hebo", fontsize=8, color=(0.08, 0.15, 0.45))
        pg.insert_text((330, y), "Service loads entered. Load Factors will be applied for calculations.", fontname="helv", fontsize=6)
        y += 10
        pg.insert_text((48, y), f"Beam self weight calculated and added to loading: {v['self_wt_klf']:.3f} k/ft", fontname="helv", fontsize=6.6)
        y += 9
        pg.insert_text((56, y), f"Uniform Load :  D = {v['w_D_klf']:.3f}, L = {v['w_L_klf']:.3f}, Lr = {v['w_Lr_klf']:.3f} k/ft",
                       fontname="helv", fontsize=6.6, color=BLUE)
        for a, p in fr["pts"]:
            y += 9
            pg.insert_text((56, y), f"Point Load :  D = {p[0]:.3f} k, L = {p[1]:.3f} k, Lr = {p[2]:.3f} k  @ {a:.3f} ft",
                           fontname="helv", fontsize=6.6, color=BLUE)
        y += 16
        ok = r["uc"] <= 1.0
        pg.draw_rect(R(36, y - 9, 576, y + 2), color=None, fill=(0.93, 0.93, 0.96))
        pg.insert_text((40, y), "DESIGN SUMMARY", fontname="hebi", fontsize=8.5, color=(0.08, 0.15, 0.45))
        pg.draw_rect(R(486, y - 9, 576, y + 2), color=None, fill=(0.1, 0.55, 0.15) if ok else (0.75, 0.1, 0.1))
        lab = "Design OK" if ok else "Design N.G."
        pg.insert_text((531 - tl(lab, "hebo", 7.5) / 2, y - 1), lab, fontname="hebo", fontsize=7.5, color=(1, 1, 1))
        combos, xdef = _beam_combo_table(ctx["d"], mid)
        cm = max(combos, key=lambda c: combos[c][0])
        cv = max(combos, key=lambda c: combos[c][1])
        y += 12
        rm, rv = v["Mu_kft"] / v["phiMn_kft"], v["Vu_k"] / v["phiVn_k"]
        L1 = [("Maximum Bending Stress Ratio =", f"{rm:.3f} : 1"), ("Section used for this span", v["size"]),
              ("Mu : Applied", f"{v['Mu_kft']:.1f} k-ft"), ("Mn * Phi : Allowable", f"{v['phiMn_kft']:.1f} k-ft"),
              ("Load Combination", "+" + G.COMBO_TXT[cm].replace("+", "+")), ("Limit state", f"AISC {v['flex_eq']}")]
        L2 = [("Maximum Shear Stress Ratio =", f"{rv:.3f} : 1"), ("Section used for this span", v["size"]),
              ("Vu : Applied", f"{v['Vu_k']:.1f} k"), ("Vn * Phi : Allowable", f"{v['phiVn_k']:.1f} k"),
              ("Load Combination", "+" + G.COMBO_TXT[cv]), ("Location", "at support")]
        for i, ((a, b), (c_, e_)) in enumerate(zip(L1, L2)):
            fnt = "hebo" if i == 0 else "helv"
            pg.insert_text((48, y + i * 9), a, fontname=fnt, fontsize=6.8, color=(0.08, 0.15, 0.45) if i == 0 else (0, 0, 0))
            pg.insert_text((200, y + i * 9), b, fontname=fnt, fontsize=6.8, color=BLUE)
            pg.insert_text((320, y + i * 9), c_, fontname=fnt, fontsize=6.8, color=(0.08, 0.15, 0.45) if i == 0 else (0, 0, 0))
            pg.insert_text((470, y + i * 9), e_, fontname=fnt, fontsize=6.8, color=BLUE)
        y += 6 * 9 + 6
        pg.insert_text((48, y), "Maximum Deflection", fontname="hebo", fontsize=7, color=(0.08, 0.15, 0.45))
        Ls = v["span_ft"] * 12
        lim_l = round(Ls / v["defl_L_allow_in"]) if v["defl_L_allow_in"] else 0
        lim_t = round(Ls / v["defl_T_allow_in"]) if v["defl_T_allow_in"] else 0
        dl = [("Max Downward Transient Deflection", v["defl_L_in"], lim_l), ("Max Upward Transient Deflection", 0.0, lim_l),
              ("Max Downward Total Deflection", v["defl_T_in"], lim_t), ("Max Upward Total Deflection", 0.0, lim_t)]
        for i, (a, dv, lim) in enumerate(dl):
            yy = y + 9 + i * 9
            ratio = int(Ls / dv) if dv > 0 else 0
            pg.insert_text((56, yy), a, fontname="helv", fontsize=6.6)
            pg.insert_text((220, yy), f"{dv:.3f} in", fontname="helv", fontsize=6.6, color=BLUE)
            pg.insert_text((270, yy), "Ratio =", fontname="helv", fontsize=6.6)
            pg.insert_text((300, yy), f"{ratio} {'>=' if ratio else '<'}{lim}", fontname="helv", fontsize=6.6,
                           color=(0.1, 0.5, 0.1) if ratio >= lim or not ratio else RED)
        if v["camber_in"]:
            pg.insert_text((380, y + 9), f"Camber: {v['camber_in']:g} in (~0.8 x dead load deflection)", fontname="helv", fontsize=6.6)
        y += 9 * 5 + 10
        pg.insert_text((40, y), "Maximum Forces & Stresses for Load Combinations", fontname="hebo", fontsize=8, color=(0.08, 0.15, 0.45))
        y += 4
        rows = [[f"+{G.COMBO_TXT[c]}", "1", f"{mu / v['phiMn_kft']:.3f}", f"{vu / v['phiVn_k']:.3f}", f"{mu:.2f}",
                 f"{v['phiMn_kft']:.2f}", "1.00", "1.00", f"{vu:.2f}", f"{v['phiVn_k']:.2f}"] for c, (mu, vu) in combos.items()]
        y, _ = table(pg, 40, y, [("Load Combination", 120, "l"), ("Span #", 30, "r"), ("M ratio", 40, "r"), ("V ratio", 40, "r"),
                                 ("Mu k-ft", 50, "r"), ("phiMn k-ft", 52, "r"), ("Cb", 30, "r"), ("Rm", 30, "r"),
                                 ("Vu k", 44, "r"), ("phiVn k", 46, "r")], rows, size=6.2, rh=9, hlines=True,
                     grid=(0.75, 0.75, 0.75), head_rule=(0.2, 0.2, 0.5), hfont="helv")
        y += 12
        pg.insert_text((40, y), "Overall Maximum Deflections", fontname="hebo", fontsize=8, color=(0.08, 0.15, 0.45))
        y, _ = table(pg, 40, y + 4, [("Load Combination", 120, "l"), ("Span", 30, "r"), ("Max. \"-\" Defl in", 70, "r"),
                                     ("Location in Span ft", 80, "r"), ("Max. \"+\" Defl", 60, "r")],
                     [["D+L+Lr", "1", f"{v['defl_T_in']:.4f}", f"{xdef:.3f}", "0.0000"]], size=6.2, rh=9, hlines=True,
                     grid=(0.75, 0.75, 0.75), head_rule=(0.2, 0.2, 0.5), hfont="helv")
        y += 12
        pg.insert_text((40, y), "Vertical Reactions", fontname="hebo", fontsize=8, color=(0.08, 0.15, 0.45))
        pg.insert_text((300, y), "Support notation : Far left is #1      Values in KIPS", fontname="helv", fontsize=6)
        rx = [["Overall MAXimum (factored)", f"{v['R_i_k']:.2f}", f"{v['R_j_k']:.2f}"],
              ["D Only (incl. self weight)", f"{v['R_i_D']:.2f}", f"{v['R_j_D']:.2f}"],
              ["L + Lr Only", f"{v['R_i_L']:.2f}", f"{v['R_j_L']:.2f}"]]
        rx += [[f"+{G.COMBO_TXT[c]}", f"{G.fac(fr['Ri'], c):.2f}", f"{G.fac(fr['Rj'], c):.2f}"] for c in G.COMBOS]
        y, _ = table(pg, 40, y + 4, [("Load Combination", 140, "l"), ("Support 1", 60, "r"), ("Support 2", 60, "r")], rx,
                     size=6.2, rh=9, hlines=True, grid=(0.75, 0.75, 0.75), head_rule=(0.2, 0.2, 0.5), hfont="helv")
        pkg.place(r["id"], R(36, blk_top, 576, y + 2), f"{mid} {v['size']}", [mid])


# ======================================================================= C (Mathcad)
def calc_C1(pkg, ctx):
    d = ctx["d"]
    wts = d["seismic"]["weights"]
    lv = ctx["levels"]
    for dn in ("x", "y"):
        rec = ctx["rec"][f"C-ELF:{dn.upper()}"]
        e = d["seismic"][dn]
        s = LAT.SYS[dn]
        mc = MC(pkg, "C1", f"{JOB}_C1_ELF.mcdx")
        mc.heading(f"SEISMIC BASE SHEAR - EQUIVALENT LATERAL FORCE ({dn.upper()} DIRECTION)")
        mc.text(40, mc.y, f"ASCE 7-16 12.8.  System: {s['name']} (Table 12.2-1).  Rigid diaphragm (composite deck).", size=8.6)
        mc.y += 20
        top = mc.y - 12
        hn = lv[-1]["elev_ft"]
        mc.cols2([(r"S_{DS} \coloneq %.2f" % LAT.SDS, f"S_DS := {LAT.SDS:.2f}", "in"),
                  (r"S_{D1} \coloneq %.2f" % LAT.SD1, f"S_D1 := {LAT.SD1:.2f}", "in"),
                  (r"I_e \coloneq %.2f" % LAT.IE, f"I_e := {LAT.IE:.2f}", "in"),
                  (r"h_n \coloneq %.1f\ \mathrm{ft}" % hn, f"h_n := {hn:.1f} ft", "in")],
                 [(r"R \coloneq %.1f\quad C_d \coloneq %.1f" % (e["R"], e["Cd"]), f"R := {e['R']:.1f}  Cd := {e['Cd']:.1f}", "in"),
                  (r"\Omega_0 \coloneq %.1f\quad \rho \coloneq %.1f" % (e["O0"], e["rho"]), f"Omega0 := {e['O0']:.1f}  rho := {e['rho']:.1f}", "in"),
                  (r"C_t \coloneq %.3f\quad x \coloneq %.2f" % (s["Ct"], s["xexp"]), f"Ct := {s['Ct']:.3f}  x := {s['xexp']:.2f}", "in")])
        mc.y += 4
        mc.area("Period and seismic response coefficient", collapsed=False)
        c1 = LAT.SDS / (e["R"] / LAT.IE)
        c2 = LAT.SD1 / (e["Ta"] * e["R"] / LAT.IE)
        cmin = max(0.044 * LAT.SDS * LAT.IE, 0.01)
        mc.rows([(r"T_a \coloneq C_t \cdot h_n^{\,x} = %.3f\ \mathrm{s}\qquad (12.8\text{-}7)" % e["Ta"], f"T_a := Ct*hn^x = {e['Ta']:.3f} s (12.8-7)", "eval"),
                 (r"C_{s1} \coloneq \dfrac{S_{DS}}{R / I_e} = %.4f\qquad (12.8\text{-}2)" % c1, f"Cs1 := SDS/(R/Ie) = {c1:.4f} (12.8-2)", "eval"),
                 (r"C_{s2} \coloneq \dfrac{S_{D1}}{T_a \cdot R / I_e} = %.4f\qquad (12.8\text{-}3)" % c2, f"Cs2 := SD1/(Ta R/Ie) = {c2:.4f} (12.8-3)", "eval"),
                 (r"C_{s.min} \coloneq \max(0.044 \cdot S_{DS} \cdot I_e,\ 0.01) = %.4f\qquad (12.8\text{-}5)" % cmin, f"Cs.min := {cmin:.4f} (12.8-5)", "eval"),
                 (r"C_s \coloneq \max(\min(C_{s1}, C_{s2}),\ C_{s.min}) = %.4f" % e["Cs"], f"Cs := {e['Cs']:.4f}", "eval")])
        mc.area("Effective seismic weight (12.7.2) - from A2 areas + steel + walls", collapsed=True)
        mc.rows([(r"W \coloneq \Sigma w_x = " + " + ".join(f"{wts[L['key']]:.1f}" for L in lv) + r" = %.1f\ \mathrm{kip}" % e["W"],
                  f"W := sum wx = {e['W']:.1f} kip", "eval"),
                 (r"V \coloneq C_s \cdot W = %.4f \cdot %.1f\ \mathrm{kip} = %.1f\ \mathrm{kip}\qquad (12.8\text{-}1)" % (e["Cs"], e["W"], e["V"]),
                  f"V := Cs*W = {e['V']:.1f} kip (12.8-1)", "eval"),
                 (r"k \coloneq %.3f\qquad (T_a = %.3f\ \mathrm{s},\ 12.8.3)" % (e["k"], e["Ta"]), f"k := {e['k']:.3f}", "eval")])
        mc.y += 6
        mc.text(40, mc.y, "Vertical distribution (12.8-11, 12.8-12)", size=9, bold=True)
        mc.y += 6
        den = sum(wts[L["key"]] * L["elev_ft"] ** e["k"] for L in lv)
        rows = []
        vcum = 0.0
        for L in reversed(lv):
            wh = wts[L["key"]] * L["elev_ft"] ** e["k"]
            vcum += e["Fx"][L["key"]]
            rows.append([L["name"], f"{L['elev_ft']:.1f}", f"{wts[L['key']]:.1f}", f"{wh:,.0f}", f"{wh / den:.4f}",
                         f"{e['Fx'][L['key']]:.1f}", f"{vcum:.1f}"])
        rows.append(["Sum", "", f"{e['W']:.1f}", f"{den:,.0f}", "1.0000", f"{e['V']:.1f}", ""])
        mc.finish()
        y, rects = table(mc.pg, 46, mc.y, [("Level", 80, "l"), ("hx (ft)", 60, "r"), ("wx (kip)", 70, "r"), ("wx hx^k", 80, "r"),
                                           ("Cvx", 60, "r"), ("Fx (kip)", 70, "r"), ("Vx (kip)", 70, "r")], rows, **MC_TABLE)
        mc.y = y
        pkg.place(rec["id"], R(38, top, 574, y + 2), f"V = {e['V']:.1f} kip ({dn.upper()}) Cs {e['Cs']:.4f}")


def calc_C2(pkg, ctx):
    d = ctx["d"]
    lv = ctx["levels"]
    gx, gy = ctx["grids"]["x"], ctx["grids"]["y"]
    mc = MC(pkg, "C2", f"{JOB}_C2_Wind.mcdx")
    mc.heading("WIND - MAIN WIND FORCE RESISTING SYSTEM")
    mc.text(40, mc.y, "ASCE 7-16 Ch. 27 (directional), simplified to a net design pressure on the projected area; "
                      "seismic governs both directions (see C1).", size=8.4)
    mc.y += 18
    mc.rows([(r"V_{ult} \coloneq 110\ \mathrm{mph}\qquad \mathrm{Exposure\ C},\ K_{zt} = 1.0", "V := 110 mph Exposure C", "in"),
             (r"p_{net} \coloneq %.1f\ \mathrm{psf}" % LAT.WIND_PSF, f"p_net := {LAT.WIND_PSF:.1f} psf (windward + leeward)", "in")])
    hs = {"L2": 14 / 2 + 13 / 2, "L3": 13 / 2 + 13 / 2, "RF": 13 / 2 + LAT.PARAPET_FT}
    mc.rows([(r"h_{trib} \coloneq [\," + r",\ ".join(f"{hs[L['key']]:.1f}" for L in lv) + r"\,]\ \mathrm{ft}",
              "h_trib := " + ", ".join(f"{hs[L['key']]:.1f}" for L in lv) + " ft (L2, L3, Roof incl. parapet)", "eval")])
    for dn in ("x", "y"):
        rec = ctx["rec"][f"C-WIND:{dn.upper()}"]
        w = d["wind"][dn]
        width = (gy[-1][1] - gy[0][1]) if dn == "x" else (gx[-1][1] - gx[0][1])
        mc.area(f"Wind in {dn.upper()}: projected width B = {width:.0f} ft", collapsed=False)
        top = mc.y - 12
        u = mc.rows([(r"B_{%s} \coloneq %.0f\ \mathrm{ft}" % (dn, width), f"B_{dn} := {width:.0f} ft", "in")]
                    + [(r"F_{%s} \coloneq p_{net} \cdot B_{%s} \cdot h_{%s} = %.1f\ \mathrm{psf} \cdot %.0f\ \mathrm{ft} \cdot %.1f\ \mathrm{ft} = %.1f\ \mathrm{kip}"
                        % (L["key"], dn, L["key"], LAT.WIND_PSF, width, hs[L["key"]], w["Fx"][L["key"]]),
                        f"F_{L['key']} := p*B*h = {w['Fx'][L['key']]:.1f} kip", "eval") for L in lv]
                   + [(r"V_{W.%s} \coloneq \Sigma F_x = %.1f\ \mathrm{kip}\ <\ V_{E.%s} = %.1f\ \mathrm{kip}" %
                       (dn, w["V"], dn, d["seismic"][dn]["V"]), f"V_W.{dn} := {w['V']:.1f} kip < V_E = {d['seismic'][dn]['V']:.1f} kip", "eval")])
        pkg.place(rec["id"], R(38, top, 574, u.y1 + 3), f"V_W.{dn} := {w['V']:.1f} kip")
    mc.y += 8
    mc.area("Components and cladding - by others (curtain wall / roofing submittals)", collapsed=True)
    mc.finish()


def calc_C6(pkg, ctx):
    d = ctx["d"]
    recs = ctx["recs"]["C6"]
    topo = d["topo"]
    gx, gy = ctx["grids"]["x"], ctx["grids"]["y"]
    mc = MC(pkg, "C6", f"{JOB}_C6_Collectors.mcdx")
    mc.heading("COLLECTORS AND DRAG STRUTS (ASCE 7-16 12.10.2.1, Omega0 LEVEL)")
    mc.text(40, mc.y, "Collector force = Omega0 x storey force on the line x tributary length / line length.  Gravity moment "
                      "at seismic combination = 1.4/1.6 x RAM Mu.", size=8.4)
    mc.y += 18
    picks = []
    for kind in ("beam", "girder"):
        cand = [r for r in recs if topo.members[r["elements"][0]].kind == kind]
        if cand:
            picks.append(max(cand, key=lambda r: r["uc"]))
    worked = []
    for r in picks:
        v = r["values"]
        mid = r["elements"][0]
        m = topo.members[mid]
        top = mc.y - 6
        mc.area(f"Typical: {mid} ({v['size']})", collapsed=False)
        if m.kind == "beam":
            fe = d["smf"][m.line]["fe"][m.level]
            L = gx[-1][1] - gx[0][1]
            items = [(r"\Omega_0 \coloneq %.1f\qquad F_{x.%s} \coloneq %.1f\ \mathrm{kip}\ (\mathrm{line\ %s,\ C3/C4})" % (v["Omega0"], m.level, fe, m.line),
                      f"Omega0 := {v['Omega0']:.1f}  Fx := {fe:.1f} kip", "in"),
                     (r"P_u \coloneq \Omega_0 \cdot F_x \cdot \dfrac{L_{coll}}{L_{line}} = %.1f \cdot %.1f\ \mathrm{kip} \cdot \dfrac{%.1f\ \mathrm{ft}}{%.0f\ \mathrm{ft}} = %.1f\ \mathrm{kip}"
                      % (v["Omega0"], fe, m.span, L, v["Pu_k"]), f"Pu := Omega0*Fx*Lcoll/Lline = {v['Pu_k']:.1f} kip", "eval")]
        else:
            fy = d["seismic"]["y"]["Fx"][m.level]
            L = gy[-1][1] - gy[0][1]
            items = [(r"\Omega_0 \coloneq %.1f\qquad F_{y.%s} \coloneq %.1f\ \mathrm{kip}\ (\mathrm{C1})" % (v["Omega0"], m.level, fy),
                      f"Omega0 := {v['Omega0']:.1f}  Fy := {fy:.1f} kip", "in"),
                     (r"P_u \coloneq \Omega_0 \cdot F_y \cdot \dfrac{L_{coll} / 2}{L_y} = %.1f \cdot %.1f\ \mathrm{kip} \cdot \dfrac{%.2f\ \mathrm{ft}}{%.0f\ \mathrm{ft}} = %.1f\ \mathrm{kip}"
                      % (v["Omega0"], fy, m.span / 2, L, v["Pu_k"]), f"Pu := {v['Pu_k']:.1f} kip", "eval")]
        pr = v["Pu_k"] / v["phiPn_k"]
        h1 = (pr + 8 / 9 * v["Mu_kft"] / v["phiMn_kft"]) if pr >= 0.2 else (pr / 2 + v["Mu_kft"] / v["phiMn_kft"])
        eqtex = (r"\dfrac{P_u}{\phi P_n} + \dfrac{8}{9} \cdot \dfrac{M_u}{\phi M_n}" if pr >= 0.2
                 else r"\dfrac{P_u}{2 \phi P_n} + \dfrac{M_u}{\phi M_n}")
        items += [(r"\phi P_n \coloneq %.1f\ \mathrm{kip}\ (E3,\ KL = %.1f\ \mathrm{ft})\qquad M_u \coloneq %.1f\ \mathrm{kip \cdot ft}\qquad \phi M_n \coloneq %.1f\ \mathrm{kip \cdot ft}"
                   % (v["phiPn_k"], m.span, v["Mu_kft"], v["phiMn_kft"]),
                   f"phiPn := {v['phiPn_k']:.1f} kip  Mu := {v['Mu_kft']:.1f} kip-ft  phiMn := {v['phiMn_kft']:.1f} kip-ft", "eval"),
                  (r"\dfrac{P_u}{\phi P_n} = %.3f\ \rightarrow\ \mathrm{%s}" % (pr, v["eq"].replace("-", r"\text{-}")), f"Pu/phiPn = {pr:.3f} -> {v['eq']}", "eval"),
                  (r"%s = %.3f\ \leq\ 1.0" % (eqtex, h1), f"{v['eq']} = {h1:.3f} <= 1.0", ("chk", h1 <= 1.0 + 1e-9))]
        u = mc.rows(items)
        worked.append((r, R(38, top, 574, u.y1 + 3)))
        mc.y += 4
    mc.y += 4
    mc.text(40, mc.y, "Collector summary - all segments.  Size = lightest W at or above the RAM size passing RAM and H1 at Omega0 E.",
            size=9, bold=True)
    mc.y += 6
    mc.finish()
    for r, rect in worked:
        pkg.place(r["id"], rect, f"{r['elements'][0]} {r['values']['size']} worked", r["elements"], how="calc_block", page=mc.pno)
    mc2 = mc
    rows, ids = [], []
    for r in recs:
        v = r["values"]
        rows.append([r["elements"][0], v["size"], f"{v['Omega0']:.1f}", f"{v['Pu_k']:.1f}", f"{v['phiPn_k']:.1f}",
                     f"{v['Mu_kft']:.1f}", f"{v['phiMn_kft']:.1f}", v["eq"], f"{r['uc']:.3f}", "OK" if r["uc"] <= 1 else "NG"])
        ids.append(r)
    y, rects = table(mc2.pg, 40, mc2.y, [("Member", 82, "l"), ("Size", 50, "l"), ("Omega0", 40, "r"), ("Pu (kip)", 50, "r"),
                                         ("phiPn (kip)", 56, "r"), ("Mu (k-ft)", 52, "r"), ("phiMn (k-ft)", 58, "r"),
                                         ("Eq.", 40, "c"), ("Ratio", 46, "r"), ("", 30, "c")], rows, **MC_TABLE)
    for r, rect in zip(ids, rects):
        pkg.place(r["id"], rect, f"{r['elements'][0]} {r['values']['size']}", r["elements"])


# ======================================================================= C (RISA)
def _elev(pg, x0, y0, w, h, cols_pos, levels, members, braces=(), fixed=True):
    """Frame elevation: cols_pos [(label, pos ft)], levels [(key, z ft)], members label map."""
    p0, p1 = cols_pos[0][1], cols_pos[-1][1]
    zmax = levels[-1][1]
    sx = w / max(p1 - p0, 1)
    sz = h / zmax
    X = lambda p: x0 + (p - p0) * sx  # noqa: E731
    Z = lambda z: y0 + h - z * sz  # noqa: E731
    for lab, p in cols_pos:
        pg.draw_line((X(p), Z(0)), (X(p), Z(zmax)), color=(0.1, 0.1, 0.6), width=1.4)
        pg.insert_text((X(p) - tl(lab, "hebo", 6.5) / 2, Z(0) + 18), lab, fontname="hebo", fontsize=6.5)
        if fixed:
            pg.draw_rect(R(X(p) - 6, Z(0), X(p) + 6, Z(0) + 3), color=None, fill=(0.2, 0.2, 0.2))
        else:
            pg.draw_polyline([(X(p), Z(0)), (X(p) - 5, Z(0) + 7), (X(p) + 5, Z(0) + 7), (X(p), Z(0))], color=(0, 0, 0), width=0.6)
    for (k, z) in levels:
        pg.draw_line((X(p0), Z(z)), (X(p1), Z(z)), color=(0.1, 0.45, 0.1), width=1.2)
        pg.insert_text((X(p1) + 8, Z(z) + 2), f"{k}  z={z:g}'", fontname="helv", fontsize=6)
    for (a, b, za, zb, lab) in braces:
        pg.draw_line((X(a), Z(za)), (X(b), Z(zb)), color=(0.6, 0.1, 0.1), width=1.0)
    for (pa, pb, z, lab) in members:
        pg.insert_text(((X(pa) + X(pb)) / 2 - tl(lab, size=5) / 2, Z(z) - 3), lab, fontname="helv", fontsize=5)
    return Z(0) + 26


def calc_C_smf(pkg, ctx, calc):
    d = ctx["d"]
    yl = "A" if calc == "C3" else "D"
    fr = ctx["rec"].get(f"C-SMF:{yl}")
    recs = ctx["recs"][calc]
    s = d["smf"][yl]
    a = s["analysis"]
    colpos = sorted(((c, ctx["el"][f"COL-{c}"]["x"]) for c in s["gp"]), key=lambda t: t[1])
    lv = [(L["key"], L["elev_ft"]) for L in ctx["levels"]]
    deco = risa_deco(f"SMF-{yl}", None)
    pg, sheet = pkg.new_page(calc, "risa")
    y = deco(pg, 1, None)
    y = risa_title(pg, y, f"Frame Geometry - Special Moment Frame Line {yl} (elevation)")
    mlabs = [(colpos[i][1], colpos[i + 1][1], z, f"B-{k}-{yl}-{colpos[i][0][:-1]}{colpos[i + 1][0][:-1]}  {s['beam']}")
             for k, z in lv for i in range(len(colpos) - 1)]
    y = _elev(pg, 90, y + 8, 340, 150, colpos, lv, mlabs)
    pg.insert_text((470, y - 160), f"Beams: {s['beam']} (RBS)", fontname="helv", fontsize=6.5)
    pg.insert_text((470, y - 151), f"Columns: {s['col']}", fontname="helv", fontsize=6.5)
    pg.insert_text((470, y - 142), "Bases: fixed (BP-3)", fontname="helv", fontsize=6.5)
    y += 8
    y = risa_title(pg, y, "Load Combinations")
    s1, s2 = 1.2 + 0.2 * LAT.SDS, 0.9 - 0.2 * LAT.SDS
    rho = LAT.SYS["x"]["rho"]
    lc = [["S1", f"{s1:.1f}D + 0.5L + {rho:.1f}E", "Yes"], ["S2", f"{s2:.1f}D + {rho:.1f}E", "Yes"],
          ["S3", f"{s1:.1f}D + 0.5L - {rho:.1f}E", "Yes"], ["W1", "1.2D + 0.5L + 1.0W", "Yes"], ["G2", "1.2D + 1.6L", "Yes"],
          ["EUN", "1.0E (drift, Cd/Ie applied)", "No"], ["WSV", "0.42W (service wind)", "No"]]
    y, _ = table(pg, 40, y, [("Label", 50, "l"), ("Combination", 200, "l"), ("Code check", 60, "c")], lc, **RISA_TBL)
    y += 10
    y = risa_title(pg, y, f"Joint Loads - E (line share {fr['values']['share']:.3f} of V, incl. 5% accidental torsion)")
    jl = [[f"{c0}_{i + 1}", L["name"], f"{fr['values']['Fe_k'][L['key']]:.1f}", f"{s['fw'][L['key']]:.1f}"]
          for i, L in enumerate(ctx["levels"]) for c0 in [colpos[0][0]]]
    y, _ = table(pg, 40, y, [("Joint", 50, "l"), ("Level", 60, "l"), ("FX E (k)", 60, "r"), ("FX W (k)", 60, "r")], jl, **RISA_TBL)
    y += 10
    y = risa_title(pg, y, f"SMF-{yl} Story Drift - ASCE 7-16 12.8.6 / 12.12-1 (Cd = %.1f, Ie = %.1f)" % (LAT.SYS["x"]["Cd"], LAT.IE))
    top = y - 14
    dr = [[x["level"], f"{x['h']:.1f}", f"{x['delta_in']:.3f}", f"{x['allow_in']:.3f}", f"{x['ratio']:.3f}",
           f"{x['wind_in']:.3f}", f"{x['wind_allow_in']:.3f}"] for x in fr["values"]["drifts"]]
    y, _ = table(pg, 40, y, [("Story", 40, "l"), ("h (ft)", 40, "r"), ("Delta x (in)", 60, "r"), ("Allow (in)", 56, "r"),
                             ("Ratio", 44, "r"), ("Wind (in)", 50, "r"), ("h/400 (in)", 52, "r")], dr, **RISA_TBL)
    ch = fr["values"]["checks"]
    y += 10
    summ = (f"Frame summary: k = {fr['values']['k_kip_per_ft']:.1f} kip/ft;  SCWB sum M*pc/sum M*pb = {fr['values']['scwb_ratio']:.3f} "
            f"(>= 1.0, AISC 341 E3.4a);  max ratios - drift {ch['drift']:.3f}, beam flexure {ch['beam_flexure']:.3f}, "
            f"beam shear {ch['beam_shear']:.3f}, column {ch['column']:.3f}.")
    cut = summ.rfind(" ", 0, 125)
    pg.insert_text((40, y), summ[:cut], fontname="helv", fontsize=6.3)
    pg.insert_text((40, y + 8), summ[cut + 1:], fontname="helv", fontsize=6.3)
    pkg.place(fr["id"], R(36, top, 576, y + 11), f"SMF-{yl} story drift ratio {fr['uc']:.3f}", fr["elements"])
    deco(pg, 1, 2)
    # page 2: code checks
    pg, sheet = pkg.new_page(calc, "risa")
    y = deco(pg, 2, None)
    y = risa_title(pg, y, "Member AISC 360-16 (LRFD) Steel Code Checks - Beams")
    bm = [r for r in recs if r["kind"] == "smf_beam"]
    rows = [[r["elements"][0], r["values"]["size"], f"{r['values']['span_ft']:.2f}", f"{r['values']['Mu_kft']:.1f}",
             f"{r['values']['phiMn_kft']:.1f}", f"{r['uc']:.3f}", f"{r['values']['Vu_k']:.1f}",
             f"{aisc.phi_vn(r['values']['size']):.1f}", "S1/S3", "F2-1"] for r in bm]
    y, rects = table(pg, 40, y, [("Label", 72, "l"), ("Shape", 50, "l"), ("L (ft)", 36, "r"), ("Mu (k-ft)", 46, "r"),
                                 ("phi*Mn (k-ft)", 56, "r"), ("UC Max", 40, "r"), ("Vu (k)", 36, "r"), ("phi*Vn (k)", 46, "r"),
                                 ("LC", 36, "c"), ("Eqn", 34, "c")], rows, **RISA_TBL)
    for r, rect in zip(bm, rects):
        pkg.place(r["id"], rect, f"{r['elements'][0]} {r['values']['size']}", r["elements"])
    y += 12
    y = risa_title(pg, y, "Member AISC 360-16 (LRFD) Steel Code Checks - Columns (frame + gravity axial)")
    cm = [r for r in recs if r["kind"] == "column_design"]
    rows = [[r["elements"][0], r["values"]["size"], str(r["values"]["storey"]), f"{r['values']['Pu_k']:.1f}",
             f"{r['values']['phiPn_k']:.1f}", f"{r['values']['Mux_kft']:.1f}", f"{r['values']['phiMnx_kft']:.1f}",
             f"{r['uc']:.3f}", r["lc"], r["values"]["eq"]] for r in cm]
    y, rects = table(pg, 40, y, [("Label", 52, "l"), ("Shape", 50, "l"), ("Story", 32, "r"), ("Pu (k)", 40, "r"),
                                 ("phi*Pnc (k)", 54, "r"), ("Mu (k-ft)", 46, "r"), ("phi*Mn (k-ft)", 56, "r"),
                                 ("UC Max", 40, "r"), ("LC", 30, "c"), ("Eqn", 40, "c")], rows, **RISA_TBL)
    for r, rect in zip(cm, rects):
        pkg.place(r["id"], rect, f"{r['elements'][0]} {r['values']['size']}", r["elements"])
    y += 12
    y = risa_title(pg, y, "Joint Reactions at Base (unfactored E; M from S1/S3)")
    rows = []
    for c, _ in colpos:
        b = a["columns"].get((c, "base"), {})
        rows.append([f"{c}_0", f"COL-{c}", f"{b.get('v_e', 0):.1f}", f"{b.get('p_e', 0):.1f}", f"{b.get('m_base', 0):.1f}"])
    y, _ = table(pg, 40, y, [("Joint", 50, "l"), ("Column", 60, "l"), ("FX E (k)", 60, "r"), ("FZ E (k)", 60, "r"),
                             ("MY S1/S3 (k-ft)", 80, "r")], rows, **RISA_TBL)
    deco(pg, 2, 2)


def calc_C5(pkg, ctx):
    d = ctx["d"]
    sc = d["scbf"]
    fr = ctx["rec"].get("C-SCBF:3")
    recs = ctx["recs"]["C5"]
    deco = risa_deco("SCBF-3", None)
    pg, sheet = pkg.new_page("C5", "risa")
    y = deco(pg, 1, None)
    y = risa_title(pg, y, "Frame Geometry - Special Concentrically Braced Frame Line 3 (elevation, chevron)")
    colpos = sorted(((e["grid"].split("/")[1], e["y"]) for e in ctx["exp"]["elements"]
                     if e["type"] == "column" and e["grid"].startswith("3/")), key=lambda t: t[1])
    lv = [(L["key"], L["elev_ft"]) for L in ctx["levels"]]
    zs = [0.0] + [z for _, z in lv]
    braces = []
    for e in ctx["exp"]["elements"]:
        if e["type"] == "brace":
            braces.append((e["p1"][1], e["p2"][1], e["p1"][2], e["p2"][2], e["id"]))
    mlabs = [(braces[0][0], braces[0][0], 0, "")]
    y = _elev(pg, 90, y + 8, 340, 150, [(f"3{c}", p) for c, p in colpos], lv, mlabs, braces, fixed=False)
    pg.insert_text((470, y - 160), f"Braces: {risa_shape(sc.get('brace', '-'))}", fontname="helv", fontsize=6.5)
    pg.insert_text((470, y - 151), "Beams pinned, continuous at work point", fontname="helv", fontsize=6.5)
    pg.insert_text((470, y - 142), "Bases: pinned (BP-4)", fontname="helv", fontsize=6.5)
    y += 8
    y = risa_title(pg, y, "SCBF-3 Story Drift - ASCE 7-16 12.12-1 (Cd = %.1f, rho = %.1f)" % (LAT.SYS["y"]["Cd"], LAT.SYS["y"]["rho"]))
    top = y - 14
    dr = [[x["level"], f"{x['h']:.1f}", f"{x['delta_in']:.3f}", f"{x['allow_in']:.3f}", f"{x['ratio']:.3f}"] for x in fr["values"]["drifts"]]
    y, _ = table(pg, 40, y, [("Story", 40, "l"), ("h (ft)", 40, "r"), ("Delta x (in)", 60, "r"), ("Allow (in)", 56, "r"),
                             ("Ratio", 44, "r")], dr, **RISA_TBL)
    y += 10
    pg.insert_text((40, y), f"Expected brace tension Ry Fy Ag = {fr['values']['expected_T_k']:.1f} k (AISC 341 F2.6c, Ry = {LAT.RY_HSS}) "
                            "- to brace gussets, E4.", fontname="helv", fontsize=6.3)
    pkg.place(fr["id"], R(36, top, 576, y + 3), f"SCBF-3 story drift ratio {fr['uc']:.3f}", fr["elements"])
    y += 14
    y = risa_title(pg, y, "Load Combinations")
    s1 = 1.2 + 0.2 * LAT.SDS
    y, _ = table(pg, 40, y, [("Label", 50, "l"), ("Combination", 200, "l")],
                 [["S1", f"{s1:.1f}D + 0.5L + {LAT.SYS['y']['rho']:.1f}E"], ["EUN", "1.0E (drift)"]], **RISA_TBL)
    deco(pg, 1, 2)
    pg, sheet = pkg.new_page("C5", "risa")
    y = deco(pg, 2, None)
    y = risa_title(pg, y, "Member AISC 360-16 (LRFD) Steel Code Checks - Braces (E3 / D2 / KL/r <= 200)")
    br = [r for r in recs if r["kind"] == "brace"]
    rows = [[r["elements"][0], risa_shape(r["values"]["size"]), f"{r['values']['L_ft']:.2f}", f"{r['values']['Pu_k']:.1f}",
             f"{r['values']['phiPn_k']:.1f}", f"{r['values']['KL_r']:.1f}", f"{r['uc']:.3f}", "S1"] for r in br]
    y, rects = table(pg, 40, y, [("Label", 90, "l"), ("Shape", 64, "l"), ("L (ft)", 40, "r"), ("Pu (k)", 44, "r"),
                                 ("phi*Pnc (k)", 54, "r"), ("KL/r", 40, "r"), ("UC Max", 44, "r"), ("LC", 34, "c")], rows, **RISA_TBL)
    for r, rect in zip(br, rects):
        pkg.place(r["id"], rect, f"{r['elements'][0]} {risa_shape(r['values']['size'])}", r["elements"])
    y += 12
    y = risa_title(pg, y, "Columns - gravity + Omega0 x SCBF axial (H1)")
    cm = [r for r in recs if r["kind"] == "column_design"]
    rows = [[r["elements"][0], r["values"]["size"], str(r["values"]["storey"]), f"{r['values']['Pu_k']:.1f}",
             f"{r['values']['phiPn_k']:.1f}", f"{r['values']['Mux_kft']:.1f}", f"{r['values']['Muy_kft']:.1f}",
             f"{r['uc']:.3f}", r["lc"], r["values"]["eq"]] for r in cm]
    y, rects = table(pg, 40, y, [("Label", 52, "l"), ("Shape", 50, "l"), ("Story", 32, "r"), ("Pu (k)", 40, "r"),
                                 ("phi*Pnc (k)", 54, "r"), ("Mux (k-ft)", 46, "r"), ("Muy (k-ft)", 46, "r"),
                                 ("UC Max", 40, "r"), ("LC", 30, "c"), ("Eqn", 40, "c")], rows, **RISA_TBL)
    for r, rect in zip(cm, rects):
        pkg.place(r["id"], rect, f"{r['elements'][0]} {r['values']['size']}", r["elements"])
    y += 12
    y = risa_title(pg, y, "Column axial from E (unfactored), by storey")
    rows = [[c, str(st), f"{v:.1f}"] for (c, st), v in sorted(sc.get("col_e", {}).items())]
    table(pg, 40, y, [("Column", 50, "l"), ("Story", 40, "r"), ("P E (k)", 60, "r")], rows, **RISA_TBL)
    deco(pg, 2, 2)
    _ = zs


# ======================================================================= D
def calc_D1(pkg, ctx, rev_rid=None):
    recs = ctx["recs"]["D1"]
    items = []
    for r in recs:
        v = r["values"]
        fid = r["elements"][0]
        el = ctx["el"][fid]
        items.append({"rid": r["id"], "key": f"{fid} {el.get('mark', '')} {v['B_ft']:.1f}x{v['B_ft']:.1f}", "elements": [fid],
                      "cells": [fid, el.get("mark", ""), f"{v['P_service_k']:.1f}", f"{v['P_E_k']:.1f}", f"{v['B_ft']:.1f}",
                                f"{v['h_in']}", f"{v['q_ksf']:.3f}", f"{v['qa_ksf']:.2f}", f"{v['Pu_k']:.1f}",
                                f"{v['vu_punch_k']:.1f}", f"{v['phiVc_punch_k']:.1f}", f"{v['vu_oneway_k']:.1f}",
                                f"{v['phiVc_oneway_k']:.1f}", f"{v['Mu_kft']:.1f}", f"{v['As_in2']:.2f}", v["bars"],
                                GOV.get(v["governs"], v["governs"]), f"{r['uc']:.3f}"],
                      "colors": {17: _uc_col(r["uc"])}, "left": 2,
                      "rev": (f"{fid}: re-checked per plan check comment S-4 (bearing / punching, row re-issued)"
                              if r["id"] == rev_rid else None)})
    excel_sheet(pkg, "D1", f"{JOB}_Foundations.xlsx", "Footings", ["Footings", "Piers", "Grade beams", "Notes"],
                [44, 30, 40, 34, 30, 26, 36, 32, 38, 40, 44, 40, 44, 38, 34, 54, 46, 36],
                [f"{PROJECT.upper()} - SPREAD FOOTING SCHEDULE (D1)",
                 f"qa = {G.QA:.1f} ksf net allowable (ASD service loads), f'c = {G.FC:g} ksi, fy = {G.FY_R:g} ksi, "
                 "cover 3 in (d = h - 4 in).  ACI 318-19: punching 22.6 (beta = 1), one-way 22.5, flexure 22.2.",
                 "P service = max(D+L+Lr, D+0.75L+0.75Lr+0.75(0.7E)).  Pu = max(LRFD gravity, seismic with Omega0 at SCBF).",
                 "Square footings, size in 6 in steps from 4'-0\"; thickness in 2 in steps from 18 in.  Bars: #7 EW, As >= 0.0018 b h."],
                ["Footing", "Mark", "P svc k", "P E k", "B ft", "h in", "q ksf", "qa ksf", "Pu k", "Vu pun k", "phiVc pun",
                 "Vu 1w k", "phiVc 1w", "Mu k-ft", "As in2", "Bars", "Governs", "Ratio"], items, landscape=True,
                note_rows=["Ratio = max(q/qa, Vu/phiVc punching, Vu/phiVc one-way).  Pier and base plate demands: D2 / E5."])


def calc_D2(pkg, ctx):
    items = []
    for r in ctx["recs"]["D2"]:
        v = r["values"]
        pid = r["elements"][0]
        items.append({"rid": r["id"], "key": f"{pid} {v['type']} {v['b_in']:.0f}x{v['b_in']:.0f}", "elements": [pid],
                      "cells": [pid, v["type"], f"{v['b_in']:.0f} x {v['b_in']:.0f}", v["bars"],
                                f"{G.PIERS[v['type']]['as']:.2f}", f"{v['b_in'] ** 2:.0f}", f"{v['Pu_k']:.1f}", f"{v['phiPn_k']:.1f}",
                                f"{r['uc']:.3f}"], "colors": {8: _uc_col(r["uc"])}})
    excel_sheet(pkg, "D2", f"{JOB}_Foundations.xlsx", "Piers", ["Footings", "Piers", "Grade beams", "Notes"],
                [60, 40, 60, 56, 44, 44, 54, 60, 48],
                [f"{PROJECT.upper()} - PIER SCHEDULE (D2)",
                 f"Tied piers, top of pier {G.PIER_TOP:g} ft, top of footing {G.FTG_TOP:g} ft.  "
                 "phi Pn,max = 0.65 x 0.80 x [0.85 f'c (Ag - Ast) + fy Ast]  (ACI 318-19 22.4.2).",
                 f"f'c = {G.FC:g} ksi, fy = {G.FY_R:g} ksi.  Pu from the column above (B5 / C3 to C5)."],
                ["Pier", "Type", "Size in", "Vert bars", "Ast in2", "Ag in2", "Pu k", "phiPn k", "Ratio"], items)


def _hand_font():
    for nm in ("Bradley Hand", "Noteworthy", "Marker Felt"):
        for f in fm.fontManager.ttflist:
            if f.name == nm:
                return fm.FontProperties(fname=f.fname)
    return fm.FontProperties(family="DejaVu Sans", style="italic")


def calc_D3(pkg, ctx):
    d = ctx["d"]
    recs = ctx["recs"]["D3"]
    npg = max(1, math.ceil(len(recs) / 5))
    sizes = [len(recs) // npg + (1 if k < len(recs) % npg else 0) for k in range(npg)]
    chunks, i0 = [], 0
    for sz in sizes:
        chunks.append(recs[i0:i0 + sz])
        i0 += sz
    for ci, chunk in enumerate(chunks):
        text_layer = ci != 1     # second scan page: raster only, no OCR layer
        pg, sheet = pkg.new_page("D3", "hand_scan", text_layer=text_layer, header=False)
        pno = pkg.pno
        seed = 2611 + ci
        blocks = []
        y = 112.0
        for r in chunk:
            v = r["values"]
            gid = r["elements"][0]
            g = d["topo"].grade_beams[gid]
            h = v["h_in"]
            wall = G.WALL_PSF * 7.0 / 1000 if g["wall"] else 0.0
            swt = G.CONC * 1.5 * h / 12
            wu = 1.2 * (wall + swt)
            L = v["span_ft"]
            m0 = wu * L ** 2 / 8
            lines = [f"{gid}    {v['b_in']}\" x {h}\"    L = {L:.1f}'   (line {g['line']}, {g['a']} - {g['b']})"]
            wtxt = ("15 psf (7') + " if g["wall"] else "") + f"150 pcf (1.5')({h / 12:.2f}')"
            lines.append(f"  wD = {wtxt} = {wall + swt:.3f} klf")
            lines.append(f"  wu = 1.2 wD = {wu:.3f} klf")
            me = v["M_end_kft"]
            if me:
                lines.append(f"  Mend = {me:.1f} k-ft  (1/2 SMF base mom., C3/C4)")
                lines.append(f"  Mu = wuL²/8 + Mend = {m0:.1f} + {me:.1f} = {v['Mu_kft']:.1f} k-ft")
            else:
                lines.append(f"  Mu = wuL²/8 = {v['Mu_kft']:.1f} k-ft")
            ok_m = v["Mu_kft"] <= v["phiMn_kft"]
            lines.append(f"  ØMn = {v['phiMn_kft']:.1f} k-ft {'>' if ok_m else '<'} Mu   {'OK' if ok_m else 'NG!'}   ({v['Mu_kft'] / v['phiMn_kft']:.2f})")
            ok_v = v["Vu_k"] <= v["phiVn_k"]
            lines.append(f"  Vu = {v['Vu_k']:.1f} k {'<' if ok_v else '>'} ØVn = {v['phiVn_k']:.1f} k  {'OK' if ok_v else 'NG!'}  (#4 @ 6\")")
            if v["tie_k"]:
                lines.append(f"  tie T = {v['tie_k']:.1f} k -> {v['tie_bars']}  (rho V/4, C5)")
            hh = 13.0 * len(lines) + 8
            blocks.append((r, gid, lines, y, hh, v))
            y += hh + 10
        angle = float(np.random.default_rng(seed).normal(0, 0.45))

        def render(total, pno=pno, sheet=sheet, blocks=blocks, seed=seed, angle=angle, text_layer=text_layer):
            pg = pkg.doc[pno - 1]
            png = _hand_png(sheet, blocks, seed, angle, pno, total)
            pg.insert_image(R(0, 0, PW, PH), stream=png)
            if text_layer:
                for r, gid, lines, y0, hh, v in blocks:
                    for k, ln in enumerate(lines):
                        x, yy = _rot(52, y0 + 12 + k * 13, angle)
                        pg.insert_text((x, yy), ln.replace("Ø", "phi").replace("²", "^2"), fontname="helv", fontsize=8.5,
                                       render_mode=3)
                for s, (x, yy) in (("CORLISS VANE STRUCTURAL ENGINEERS", (44, 30)), (f"SHEET {sheet}", (470, 50)),
                                   (f"{PROJECT}  JOB {JOB}  BY {BY}  CHK {CHK}  {DATE}", (120, 50))):
                    x, yy = _rot(x, yy, angle)
                    pg.insert_text((x, yy), s, fontname="helv", fontsize=7, render_mode=3)
        pkg.deferred.append(render)
        for r, gid, lines, y0, hh, v in blocks:
            cs = [_rot(x, yy, angle) for x, yy in ((44, y0), (568, y0), (44, y0 + hh), (568, y0 + hh))]
            rect = R(min(c[0] for c in cs) - 2, min(c[1] for c in cs) - 2, max(c[0] for c in cs) + 2, max(c[1] for c in cs) + 2)
            pkg.place(r["id"], rect, f"{gid} {v['b_in']}x{v['h_in']}", [gid], page=pno)


def _rot(x, y, angle):
    """Point on the unrotated page -> point after PIL rotate(angle) about the page centre."""
    t = math.radians(angle)
    dx, dy = x - PW / 2, y - PH / 2
    return PW / 2 + dx * math.cos(t) + dy * math.sin(t), PH / 2 - dx * math.sin(t) + dy * math.cos(t)


def _hand_png(sheet, blocks, seed, angle, pno, total) -> bytes:
    rng = np.random.default_rng(seed)
    hp = _hand_font()
    dpi = 150
    fig = plt.figure(figsize=(8.5, 11), dpi=dpi)
    fig.patch.set_facecolor("#eaf3df")
    ax = fig.add_axes((0, 0, 1, 1))
    ax.set_xlim(0, PW)
    ax.set_ylim(PH, 0)
    ax.axis("off")
    grn = "#9cc48a"
    for k in range(0, int(PW / 14.4) + 1):
        ax.plot([k * 14.4, k * 14.4], [70, PH - 30], color=grn, lw=0.35 if k % 5 else 0.6, alpha=0.55)
    for k in range(0, int((PH - 100) / 14.4) + 1):
        ax.plot([0, PW], [70 + k * 14.4, 70 + k * 14.4], color=grn, lw=0.35 if k % 5 else 0.6, alpha=0.55)
    ax.add_patch(mpatches.Rectangle((30, 14), PW - 60, 48, facecolor="#eef6e6", edgecolor="#2f7d3a", lw=0.9))
    ax.text(38, 30, "CORLISS VANE", color="#2f7d3a", fontsize=11, weight="bold", family="Arial")
    ax.text(38, 40, "STRUCTURAL ENGINEERS", color="#2f7d3a", fontsize=5.5, family="Arial")
    for x, lab in ((170, "PROJECT"), (380, "JOB NO."), (470, "SHEET NO.")):
        ax.text(x, 22, lab, color="#2f7d3a", fontsize=5, family="Arial")
        ax.plot([x - 4, x - 4], [14, 62], color="#2f7d3a", lw=0.6)
    for x, lab in ((170, "CALCULATED BY"), (270, "DATE"), (380, "CHECKED BY")):
        ax.text(x, 46, lab, color="#2f7d3a", fontsize=5, family="Arial")
    ax.plot([166, PW - 30], [38, 38], color="#2f7d3a", lw=0.6)
    ink = "#34343d"
    hand = lambda x, y, s, sz=11.5, rot=0.0: ax.text(x, y, s, fontproperties=hp, fontsize=sz, color=ink, rotation=rot,  # noqa: E731
                                                       va="baseline")
    hand(175, 34, PROJECT, 11)
    hand(385, 34, JOB, 11)
    hand(480, 52, sheet, 15)
    hand(175, 58, BY, 10)
    hand(275, 58, "11/14/26", 10)
    hand(385, 58, CHK, 10)
    hand(52, 96, "GRADE BEAMS  -  18\" wide, f'c 4 ksi, fy 60, d = h - 3.5\"", 12.5)
    ax.plot([50, 400], [100, 100.5], color=ink, lw=0.8)
    for r, gid, lines, y0, hh, v in blocks:
        for k, ln in enumerate(lines):
            jx = rng.normal(0, 0.8)
            hand(52 + jx + (0 if k == 0 else 4), y0 + 12 + k * 13, ln, 11.5 if k else 12.5, rng.normal(0, 0.35))
        # little sketch at right
        sx, sy = 470, y0 + 30
        ax.plot([sx, sx + 80], [sy, sy + rng.normal(0, 0.4)], color=ink, lw=1.4)
        for xx in np.linspace(sx + 5, sx + 75, 7):
            ax.annotate("", xy=(xx, sy - 1), xytext=(xx, sy - 12), arrowprops={"arrowstyle": "->", "color": ink, "lw": 0.6})
        for xx in (sx, sx + 80):
            ax.plot([xx - 4, xx, xx + 4, xx - 4], [sy + 7, sy, sy + 7, sy + 7], color=ink, lw=0.7)
        if v["M_end_kft"]:
            ax.add_patch(mpatches.Arc((sx, sy), 14, 14, theta1=100, theta2=260, color=ink, lw=0.8))
            ax.add_patch(mpatches.Arc((sx + 80, sy), 14, 14, theta1=-80, theta2=80, color=ink, lw=0.8))
        hand(sx + 30, sy + 16, f"{v['span_ft']:.0f}'", 9.5)
        ax.plot([44, 568], [y0 + hh + 3, y0 + hh + 3], color=ink, lw=0.3, alpha=0.4)
    ax.text(PW - 36, PH - 14, f"Page {pno} of {total}", fontsize=6.5, family="Arial", color="#555555", ha="right")
    ax.text(36, PH - 14, f"{JOB}  {PROJECT} - Structural Calculations", fontsize=6.5, family="Arial", color="#555555")
    buf = io.BytesIO()
    fig.savefig(buf, format="png", metadata={"Software": None}, facecolor=fig.get_facecolor())
    plt.close(fig)
    img = Image.open(io.BytesIO(buf.getvalue())).convert("RGB")
    img = img.rotate(angle, resample=Image.BICUBIC, fillcolor=(232, 240, 222))
    arr = np.asarray(img).astype(np.float32)
    arr += rng.normal(0, 6.0, arr.shape[:2])[..., None]
    yy = np.linspace(-1, 1, arr.shape[0])[:, None]
    xx = np.linspace(-1, 1, arr.shape[1])[None, :]
    arr *= (1 - 0.05 * (xx ** 2 + yy ** 2))[..., None]
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.55))
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=72, optimize=False, progressive=False, subsampling=2)
    return out.getvalue()


# ======================================================================= E
def calc_E1(pkg, ctx):
    recs = ctx["recs"]["E1"]
    mc = MC(pkg, "E1", f"{JOB}_E1_ShearTabs.mcdx")
    mc.heading("TYPICAL SINGLE-PLATE SHEAR CONNECTIONS (AISC MANUAL PART 10, CONVENTIONAL)")
    mc.text(40, mc.y, "3/8\" A36 plate, (n) 3/4\" A325-N bolts in STD holes, 3\" pitch, 1-1/2\" edge, e = 3\" from the weld line; "
                      "elastic method for the eccentric bolt group.", size=8.4)
    mc.y += 18
    mc.cols2([(r"\phi r_{n.bolt} \coloneq 0.75 \cdot 54\ \mathrm{ksi} \cdot 0.4418\ \mathrm{in}^2 = %.2f\ \mathrm{kip}\quad (J3\text{-}1)" % G.BOLT_PHI_RN,
               f"phi rn.bolt := 0.75*54 ksi*0.4418 in2 = {G.BOLT_PHI_RN:.2f} kip (J3-1)", "eval"),
              (r"t_p \coloneq %g\ \mathrm{in}\quad F_y \coloneq %g\ \mathrm{ksi}\quad F_u \coloneq %g\ \mathrm{ksi}" % (G.PLATE_T, G.PLATE_FY, G.PLATE_FU),
               f"tp := {G.PLATE_T} in  Fy := {G.PLATE_FY:g} ksi  Fu := {G.PLATE_FU:g} ksi", "in")],
             [(r"e \coloneq 3.0\ \mathrm{in}\quad s \coloneq 3.0\ \mathrm{in}", "e := 3.0 in  s := 3.0 in", "in")])
    n = 3
    e, s = 3.0, 3.0
    ys = [s * (k - (n - 1) / 2) for k in range(n)]
    ip = sum(y * y for y in ys)
    per = math.hypot(1.0 / n, e * max(abs(y) for y in ys) / ip)
    lp = 3.0 * n
    yld = 0.6 * G.PLATE_FY * lp * G.PLATE_T
    anv = (lp - n * (13 / 16 + 1 / 16)) * G.PLATE_T
    rup = 0.75 * 0.6 * G.PLATE_FU * anv
    brg = n * 0.75 * 2.4 * 0.75 * G.PLATE_T * G.PLATE_FU / per * (1.0 / n) * n
    t3 = ctx["rec"].get(f"E-TYP:ST-{n}")
    top = mc.y - 6
    mc.area(f"Worked example: ST-{n}", collapsed=False)
    u = mc.rows([(r"n \coloneq %d\qquad I_p \coloneq \Sigma y^2 = %.1f\ \mathrm{in}^2" % (n, ip), f"n := {n}  Ip := {ip:.1f} in2", "eval"),
                 (r"r_{per} \coloneq \sqrt{\left(\dfrac{1}{n}\right)^2 + \left(\dfrac{e \cdot y_{max}}{I_p}\right)^2} = %.4f\ \mathrm{per\ kip}" % per,
                  f"r_per := {per:.4f}", "eval"),
                 (r"\phi R_{n.bolt} \coloneq \dfrac{\phi r_{n.bolt}}{r_{per}} = %.1f\ \mathrm{kip}" % (G.BOLT_PHI_RN / per),
                  f"phiRn.bolt := {G.BOLT_PHI_RN / per:.1f} kip", "eval"),
                 (r"\phi R_{n.y} \coloneq 1.0 \cdot 0.6 \cdot F_y \cdot L_p \cdot t_p = %.1f\ \mathrm{kip}\quad (J4\text{-}3)" % yld,
                  f"phiRn.y := {yld:.1f} kip (J4-3)", "eval"),
                 (r"\phi R_{n.r} \coloneq 0.75 \cdot 0.6 \cdot F_u \cdot A_{nv} = %.1f\ \mathrm{kip}\quad (J4\text{-}4)" % rup,
                  f"phiRn.r := {rup:.1f} kip (J4-4)", "eval"),
                 (r"\phi R_{n.br} = %.1f\ \mathrm{kip}\quad (J3\text{-}6a)\qquad \phi R_n \coloneq \min(\ldots) = %.1f\ \mathrm{kip}" % (brg, min(G.BOLT_PHI_RN / per, yld, rup, brg)),
                  f"phiRn.br := {brg:.1f} kip  phiRn := {min(G.BOLT_PHI_RN / per, yld, rup, brg):.1f} kip", "eval")])
    mc.y += 8
    mc.text(40, mc.y, "Summary - typical shear tab capacities (assigned in E2 by end reaction; max bolts by beam T-dimension)",
            size=9, bold=True)
    mc.y += 6
    mc.finish()
    if t3:
        pkg.place(t3["id"], R(38, top, 574, u.y1 + 3), f"ST-{n} worked phiRn {t3['capacity']:.1f}", t3["elements"],
                  how="calc_block", page=mc.pno)
    rows = []
    for r in recs:
        v = r["values"]
        t = G.SHEAR_TABS[v["bolts"]]
        nn = v["bolts"]
        ys = [s * (k - (nn - 1) / 2) for k in range(nn)]
        ip_ = sum(y * y for y in ys) or 1.0
        per_ = math.hypot(1.0 / nn, e * max(abs(y) for y in ys) / ip_) if nn > 1 else 1.0
        lp_ = 3.0 * nn
        rows.append([t["type"], v["plate"], str(nn), f"{G.BOLT_PHI_RN / per_:.1f}", f"{0.6 * G.PLATE_FY * lp_ * G.PLATE_T:.1f}",
                     f"{0.75 * 0.6 * G.PLATE_FU * (lp_ - nn * (13 / 16 + 1 / 16)) * G.PLATE_T:.1f}",
                     f"{v['phiRn_k']:.1f}", v["governs"]])
    y, rects = table(mc.pg, 46, mc.y, [("Type", 40, "l"), ("Plate", 56, "l"), ("Bolts", 34, "r"), ("Bolt grp (k)", 58, "r"),
                                       ("Yield (k)", 50, "r"), ("Rupture (k)", 56, "r"), ("phiRn (k)", 50, "r"),
                                       ("Governs", 130, "l")], rows, **MC_TABLE)
    for r, rect in zip(recs, rects):
        pkg.place(r["id"], rect, f"ST-{r['values']['bolts']} {r['values']['plate']} phiRn {r['values']['phiRn_k']:.1f}", r["elements"])


def calc_E2(pkg, ctx):
    items = []
    for r in ctx["recs"]["E2"]:
        v = r["values"]
        cid = r["elements"][0]
        items.append({"rid": r["id"], "key": f"{cid} {v['type']}", "elements": [cid],
                      "cells": [cid, v["member"], v["end"], v["to"], v["type"], f1(v["Ru_k"]), f1(v["phiRn_k"]),
                                f"{r['uc']:.3f}" if r["uc"] is not None else "-", "SPECIAL" if v["type"].endswith("*") else ""],
                      "colors": {7: _uc_col(r["uc"]), 8: RED}, "left": 5})
    excel_sheet(pkg, "E2", f"{JOB}_Connections.xlsx", "Beam ends", ["Beam ends", "Shear tabs", "Lookup"],
                [100, 76, 24, 70, 40, 40, 44, 40, 60],
                [f"{PROJECT.upper()} - BEAM END CONNECTION SCHEDULE (E2)",
                 "Ru = max factored end reaction (RAM, B1 to B4).  Type = lightest typical shear tab ST-n (E1) with n <= max bolts for the beam.",
                 "'*' = exceeds largest typical for the beam depth: special connection by detailer, see note."],
                ["Connection", "Member", "End", "Supported by", "Type", "Ru k", "phiRn k", "Ratio", "Note"], items, rh=10.2)


def calc_E3(pkg, ctx):
    d = ctx["d"]
    recs = ctx["recs"]["E3"]
    typ = [r for r in recs if r["kind"] == "typical_detail"]
    con = [r for r in recs if r["kind"] == "connection"]
    mc = MC(pkg, "E3", f"{JOB}_E3_RBS.mcdx")
    mc.heading("SMF MOMENT CONNECTION MC-1 - REDUCED BEAM SECTION (AISC 358-16 CH. 5)")
    if typ:
        mc.text(40, mc.y, f"MC-1: {typ[0]['values']['type']}.  Prequalification limits: {typ[0]['values']['limits']}.", size=8.4)
    mc.y += 18
    top = mc.y - 30
    for yl, s in d["smf"].items():
        b, c = aisc.get(s["beam"]), aisc.get(s["col"])
        lim = 0.32 * math.sqrt(aisc.E / (LAT.RY * aisc.FY_W))
        zr = b["Zx"] - 2 * 0.25 * b["bf"] * b["tf"] * (b["d"] - b["tf"])
        mpb = 1.1 * LAT.RY * aisc.FY_W * zr * 1.15
        mc.area(f"Line {yl}: beam {s['beam']}, column {s['col']}", collapsed=False)
        mc.cols2([(r"d \coloneq %.2f\ \mathrm{in}\quad b_f \coloneq %.2f\ \mathrm{in}" % (b["d"], b["bf"]), f"d := {b['d']:.2f} in  bf := {b['bf']:.2f} in", "in"),
                  (r"t_f \coloneq %.3f\ \mathrm{in}\quad Z_x \coloneq %.0f\ \mathrm{in}^3" % (b["tf"], b["Zx"]), f"tf := {b['tf']:.3f} in  Zx := {b['Zx']:.0f} in3", "in"),
                  (r"w \coloneq %.0f\ \mathrm{plf}\ \leq\ 302\ \mathrm{plf}" % b["W"], f"w := {b['W']:.0f} plf <= 302", ("chk", b["W"] <= 302)),
                  (r"t_f = %.3f\ \mathrm{in}\ \leq\ 1.75\ \mathrm{in}" % b["tf"], f"tf <= 1.75 in", ("chk", b["tf"] <= 1.75))],
                 [(r"\dfrac{b_f}{2 t_f} = %.2f\ \leq\ 0.32\sqrt{\dfrac{E}{R_y F_y}} = %.2f" % (b["bf"] / (2 * b["tf"]), lim),
                   f"bf/2tf = {b['bf'] / (2 * b['tf']):.2f} <= {lim:.2f}", ("chk", b["bf"] / (2 * b["tf"]) <= lim)),
                  (r"Z_{RBS} \coloneq Z_x - 2 c\, t_f (d - t_f) = %.1f\ \mathrm{in}^3\quad (c = 0.25 b_f)" % zr, f"Z_RBS := {zr:.1f} in3", "eval"),
                  (r"M^*_{pb} \coloneq 1.1 R_y F_y Z_{RBS} \cdot 1.15 = %s\ \mathrm{kip \cdot in}" % f"{mpb:,.0f}".replace(",", "{,}"), f"M*pb := {mpb:,.0f} kip-in", "eval"),
                  (r"\dfrac{\Sigma M^*_{pc}}{\Sigma M^*_{pb}} = %.3f\ \geq\ 1.0\quad (341\ E3.4a)" % s["scwb_ratio"],
                   f"SCWB = {s['scwb_ratio']:.3f} >= 1.0", ("chk", s["scwb_ratio"] >= 1.0))])
        mc.y += 4
    mc.text(40, mc.y, "Clear span to depth: Lc / d >= 7 (AISC 358 5.3.1(5)); ratio shown as 7 d / Lc (<= 1.0 OK).", size=8.2)
    mc.y += 12
    mc.text(40, mc.y, "Beam web: bolted single plate, CJP flange welds, demand-critical E70 (AISC 341 A3.4).", size=8.2)
    mc.y += 8
    mc.finish()
    if typ:
        pkg.place(typ[0]["id"], R(38, top, 574, mc.y), "MC-1 RBS prequalification limits", typ[0]["elements"], page=mc.pno)
    mc2 = MC(pkg, "E3", f"{JOB}_E3_RBS.mcdx")
    mc2.heading("MC-1 CONNECTION SCHEDULE - CLEAR SPAN / DEPTH BY CONNECTION")
    mc2.finish()
    rows = []
    for r in con:
        v = r["values"]
        mem = ctx["el"][v["member"]]
        col = ctx["el"].get(f"COL-{v['to']}")
        bd = aisc.get(mem["size"])["d"]
        cd = aisc.get(col["size"])["d"] if col else 0.0
        clear = mem["span_ft"] - cd / 12
        rows.append([r["elements"][0], mem["size"], col["size"] if col else "-", f"{mem['span_ft']:.2f}", f"{clear:.2f}",
                     f"{bd:.1f}", f"{clear * 12 / bd:.1f}", f"{r['uc']:.3f}", f1(v["Ru_k"]), "OK" if r["uc"] <= 1 else "NG"])
    y, rects = table(mc2.pg, 38, mc2.y, [("Connection", 104, "l"), ("Beam", 52, "l"), ("Column", 52, "l"), ("Span ft", 40, "r"),
                                         ("Lc ft", 38, "r"), ("d in", 34, "r"), ("Lc/d", 34, "r"), ("7d/Lc", 40, "r"),
                                         ("Vu k", 40, "r"), ("", 30, "c")], rows, **MC_TABLE)
    for r, rect in zip(con, rects):
        pkg.place(r["id"], rect, f"{r['elements'][0]} MC-1", r["elements"])


def calc_E4(pkg, ctx):
    from .design import BRACE_GUSSETS, DRAG_TYPES
    recs = ctx["recs"]["E4"]
    typ = {r["elements"][0].split(":")[1]: r for r in recs if r["kind"] == "typical_detail"}
    con = [r for r in recs if r["kind"] == "connection"]
    sc = ctx["d"]["scbf"]
    mc = MC(pkg, "E4", f"{JOB}_E4_DragGusset.mcdx")
    mc.heading("DRAG CONNECTIONS AND BRACE GUSSETS - TYPICAL CAPACITIES")
    mc.text(40, mc.y, "Typical details 7/S5.1 (drag) and 4/S5.2 (gusset); capacities from the typical detail calcs (archived), "
                      "used here as design values.", size=8.4)
    mc.y += 18
    left, right = [], []
    for t, cap in DRAG_TYPES.items():
        left.append((r"\phi R_{n.%s} \coloneq %.0f\ \mathrm{kip}" % (t.replace("-", ""), cap), f"phiRn.{t} := {cap:.0f} kip", "in"))
    for t, cap in BRACE_GUSSETS.items():
        right.append((r"\phi R_{n.%s} \coloneq %.0f\ \mathrm{kip}" % (t.replace("-", ""), cap), f"phiRn.{t} := {cap:.0f} kip", "in"))
    y0 = mc.y
    regs = {}
    for i, (it, t) in enumerate(zip(left, DRAG_TYPES)):
        mc.y = y0 + i * 21
        regs[t] = mc.rows([it])
    for i, (it, t) in enumerate(zip(right, BRACE_GUSSETS)):
        mc.y = y0 + i * 21
        regs[t] = mc.rows([it], x=320)
    mc.y = y0 + 3 * 21 + 4
    if sc.get("brace"):
        b = aisc.get(sc["brace"])
        mc.rows([(r"T_{exp} \coloneq R_y F_y A_g = %.1f \cdot %.0f\ \mathrm{ksi} \cdot %.2f\ \mathrm{in}^2 = %.1f\ \mathrm{kip}\quad (341\ F2.6c)"
                  % (LAT.RY_HSS, aisc.FY_HSS, b["A"], sc["expected_t"]), f"T_exp := Ry Fy Ag = {sc['expected_t']:.1f} kip", "eval")])
    mc.text(40, mc.y, "Assignment: lightest typical with phiRn >= demand; '*' = exceeds the largest typical (special design).", size=8.2)
    mc.y += 8
    mc.finish()
    for t, rr in regs.items():
        if t in typ:
            pkg.place(typ[t]["id"], R(rr.x0 - 3, rr.y0 - 2, rr.x1 + 3, rr.y1 + 2), f"{t} phiRn {typ[t]['capacity']:.0f} kip",
                      typ[t]["elements"], page=mc.pno)
    cols = [("Connection", 118, "l"), ("Member", 92, "l"), ("End", 24, "c"), ("To", 70, "l"), ("Type", 36, "l"),
            ("Ru (k)", 44, "r"), ("phiRn (k)", 46, "r"), ("Ratio", 40, "r"), ("", 30, "c")]

    def rowfor(r):
        v = r["values"]
        return [r["elements"][0], v["member"], v["end"], v["to"], v["type"], f1(v["Ru_k"]), f1(v["phiRn_k"]),
                f"{r['uc']:.3f}", "OK" if r["uc"] <= 1 else "NG"]
    y = mc.y + 4
    pg = mc.pg
    i = 0
    while i < len(con):
        cap = int((BOTTOM - y - 11) // 10.0)
        chunk = con[i:i + cap]
        y2, rects = table(pg, 38, y, cols, [rowfor(r) for r in chunk], **MC_TABLE)
        for r, rect in zip(chunk, rects):
            pkg.place(r["id"], rect, f"{r['elements'][0]} {r['values']['type']}", r["elements"])
        i += len(chunk)
        if i < len(con):
            mcn = MC(pkg, "E4", f"{JOB}_E4_DragGusset.mcdx")
            mcn.heading("DRAG / GUSSET CONNECTION SCHEDULE (CONT.)")
            mcn.finish()
            pg, y = mcn.pg, mcn.y


def calc_E5(pkg, ctx):
    recs = ctx["recs"]["E5"]
    typ = {r["elements"][0].split(":")[1]: r for r in recs if r["kind"] == "typical_detail"}
    bps = [r for r in recs if r["kind"] == "base_plate"]
    mc = MC(pkg, "E5", f"{JOB}_E5_BasePlates.mcdx")
    mc.heading("BASE PLATES - CONCRETE BEARING (AISC 360-16 J8, DESIGN GUIDE 1)")
    mc.rows([(r"\phi_c \coloneq 0.65\qquad f^{\prime}_c \coloneq %g\ \mathrm{ksi}" % G.FC, f"phi_c := 0.65  f'c := {G.FC:g} ksi", "in"),
             (r"\phi P_p \coloneq \phi_c \cdot 0.85 f^{\prime}_c A_1 \cdot \min\left(2,\ \sqrt{\dfrac{A_2}{A_1}}\right)\qquad (J8\text{-}2)",
              "phiPp := phi_c 0.85 f'c A1 min(2, sqrt(A2/A1)) (J8-2)", "eval")])
    mc.y += 4
    regs = {}
    pier_for = {"BP-1": "P-1", "BP-2": "P-1", "BP-3": "P-2", "BP-4": "P-2"}
    for bp, v in G.BASE_PLATES.items():
        pier = pier_for[bp]
        a1 = v["B"] * v["N"]
        a2 = G.PIERS[pier]["b"] ** 2
        cap = G.base_plate_capacity(bp, pier)
        mc.area(f"{bp}: PL {v['t']:g} x {v['B']:.0f} x {v['N']:.0f}, {v['rods']} ({v['use']}) on pier {pier}", collapsed=False)
        regs[bp] = mc.rows([(r"A_1 \coloneq %.0f \cdot %.0f\ \mathrm{in}^2 = %.0f\ \mathrm{in}^2\quad A_2 \coloneq %.0f^2 = %.0f\ \mathrm{in}^2\quad \phi P_p = %.1f\ \mathrm{kip}"
                              % (v["B"], v["N"], a1, G.PIERS[pier]["b"], a2, cap),
                              f"{bp}: A1 := {a1:.0f} in2  A2 := {a2:.0f} in2  phiPp = {cap:.1f} kip", "eval")])
    mc.y += 4
    mc.text(40, mc.y, "Plate thickness and anchor rods per typical details (SMF fixed base BP-3 and SCBF BP-4 by separate detail calcs).",
            size=8.2)
    mc.y += 18
    mc.text(40, mc.y, "Base plate schedule - by column", size=9, bold=True)
    mc.y += 6
    mc.finish()
    for bp, rr in regs.items():
        if bp in typ:
            pkg.place(typ[bp]["id"], R(38, rr.y0 - 16, 574, rr.y1 + 3), f"{bp} typical base plate", typ[bp]["elements"], page=mc.pno)
    mc2 = mc
    rows = []
    for r in bps:
        v = r["values"]
        bpid = r["elements"][0]
        rows.append([bpid, v["type"], v["plate"], v["rods"], f"{v['Pu_k']:.1f}", f"{v['phiPp_k']:.1f}", f"{r['uc']:.3f}",
                     "OK" if r["uc"] <= 1 else "NG"])
    y, rects = table(mc2.pg, 38, mc2.y, [("Base plate", 56, "l"), ("Type", 36, "l"), ("Plate", 76, "l"), ("Anchor rods", 140, "l"),
                                         ("Pu (k)", 46, "r"), ("phiPp (k)", 50, "r"), ("Ratio", 44, "r"), ("", 30, "c")], rows, **MC_TABLE)
    for r, rect in zip(bps, rects):
        pkg.place(r["id"], rect, f"{r['elements'][0]} {r['values']['type']} {r['values']['plate']}", r["elements"])


# ======================================================================= cover / TOC
def _stamp_png() -> bytes:
    fig = plt.figure(figsize=(1.9, 1.9), dpi=220)
    ax = fig.add_axes((0, 0, 1, 1))
    ax.set_xlim(-1.05, 1.05)
    ax.set_ylim(-1.05, 1.05)
    ax.axis("off")
    col = "#1d3d7a"
    for rad, lw in ((1.0, 2.0), (0.93, 0.8), (0.64, 0.8)):
        ax.add_patch(mpatches.Circle((0, 0), rad, fill=False, color=col, lw=lw))
    top = "REGISTERED STRUCTURAL ENGINEER"
    for i, ch in enumerate(top):
        a = math.radians(160 - i * (140 / (len(top) - 1)))
        ax.text(0.79 * math.cos(a), 0.79 * math.sin(a), ch, rotation=math.degrees(a) - 90, ha="center", va="center",
                fontsize=6.2, color=col, family="Arial", weight="bold")
    bot = "SAMPLE SEAL - NO LICENSE"
    for i, ch in enumerate(bot):
        a = math.radians(-155 + i * (130 / (len(bot) - 1)))
        ax.text(0.79 * math.cos(a), 0.79 * math.sin(a), ch, rotation=math.degrees(a) + 90, ha="center", va="center",
                fontsize=6.2, color=col, family="Arial", weight="bold")
    ax.text(0, 0.22, "M. O. LINDQVIST", ha="center", fontsize=6.6, color=col, family="Arial", weight="bold")
    ax.text(0, 0.02, "S.E.", ha="center", fontsize=7, color=col, family="Arial")
    ax.text(0, -0.2, "No. SAMPLE", ha="center", fontsize=6, color=col, family="Arial")
    ax.text(0, -0.03, "SAMPLE - NOT FOR CONSTRUCTION", ha="center", va="center", rotation=28, fontsize=7.5, color="#b01818",
            family="Arial", weight="bold", alpha=0.85)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", metadata={"Software": None}, transparent=True)
    plt.close(fig)
    return buf.getvalue()


def cover(pkg, ctx):
    pg, sheet = pkg.new_page("COVER", "cover")
    exp = ctx["exp"]
    y = 170
    for s, f, size in (("STRUCTURAL CALCULATIONS", "hebo", 22), ("for", "helv", 11), (PROJECT.upper(), "hebo", 26),
                       ("1200 Harbor View Drive, " + CITY, "helv", 11),
                       ("Three-storey steel office building - permit submittal", "helv", 10)):
        pg.insert_text((306 - tl(s, f, size) / 2, y), s, fontname=f, fontsize=size)
        y += size + 14
    y += 6
    pg.draw_line((120, y), (492, y), color=TEAL, width=1.2)
    y += 22
    info = [("Job No.", JOB), ("Date", DATE), ("Owner", CLIENT + " LLC"), ("Architect", "Sable & Finch Architects"),
            ("Structural engineer", FIRM_FULL), ("Engineer of record", ENGINEER), ("Prepared by / checked by", f"{BY} / {CHK}")]
    for a, b in info:
        pg.insert_text((150, y), a, fontname="helv", fontsize=9, color=GREY)
        pg.insert_text((290, y), b, fontname="helv", fontsize=9)
        y += 14
    y += 10
    e = ctx["rec"]
    sx, sy = e.get("C-ELF:X"), e.get("C-ELF:Y")
    lines = [f"Building: {len(ctx['levels'])} storeys, roof at {ctx['levels'][-1]['elev_ft']:.0f} ft; grid "
             f"{len(ctx['grids']['x'])} x {len(ctx['grids']['y'])} lines; composite deck floors, steel roof deck.",
             f"Lateral: X - {sx['values']['system'] if sx else '-'}; Y - {sy['values']['system'] if sy else '-'}.",
             f"Foundations: spread footings on piers, grade beams on the perimeter and line 3.  Records in this package: {len(exp['records'])}."]
    for s in lines:
        pg.insert_text((90, y), s, fontname="helv", fontsize=7.6)
        y += 11
    pg.insert_image(R(400, 560, 540, 700), stream=_stamp_png())
    pg.draw_line((400, 712), (540, 712), color=(0, 0, 0), width=0.5)
    pg.insert_text((400, 721), f"{ENGINEER}   (SAMPLE - NOT FOR CONSTRUCTION)", fontname="helv", fontsize=5.6)
    y = 580
    pg.insert_text((60, y), "REVISIONS", fontname="hebo", fontsize=8)
    _, rr = table(pg, 60, y + 4, [("Rev", 26, "c"), ("Date", 56, "l"), ("Description", 220, "l")],
                  [list(r) for r in REVS], size=7, rh=12, head_fill=(0.9, 0.9, 0.9))
    delta(pg, 44, rr[-1].y0 + 1, "1", s=9)
    pg.insert_text((60, y + 60), "This package is a synthetic sample for software testing.  Firm, engineer, owner, architect, "
                                 "site and seal are fictional.", fontname="heit", fontsize=6.2, color=GREY)


def toc(pkg, ctx, sections):
    pkg.new_page("TOC", "toc")
    tno = pkg.pno

    def fill(total):
        pg = pkg.doc[tno - 1]
        y = 100
        pg.insert_text((306 - tl("TABLE OF CONTENTS", "hebo", 13) / 2, y), "TABLE OF CONTENTS", fontname="hebo", fontsize=13)
        y += 26
        pg.insert_text((50, y), "Item", fontname="hebi", fontsize=9)
        pg.insert_text((396, y), "Sheets", fontname="hebi", fontsize=9)
        pg.insert_text((520, y), "Pages", fontname="hebi", fontsize=9)
        y += 16
        by_calc = {}
        for m in pkg.meta:
            by_calc.setdefault(m["calc"], []).append(m)
        for sec, title in sections.items():
            ms = [m for c in ctx["calcs"] if c["section"] == sec for m in by_calc.get(c["id"], [])]
            if not ms:
                continue
            s = f"{sec}. {title}"
            pg.insert_text((50, y), s, fontname="hebo", fontsize=9)
            rng_s = f"{ms[0]['sheet']} - {ms[-1]['sheet']}"
            pg.insert_text((396, y), rng_s, fontname="hebo", fontsize=8.5)
            pg.insert_text((520, y), f"{ms[0]['page']} - {ms[-1]['page']}", fontname="hebo", fontsize=8.5)
            y += 13
            for c in ctx["calcs"]:
                if c["section"] != sec or c["id"] not in by_calc:
                    continue
                cm = by_calc[c["id"]]
                t = f"{c['id']}   {c['title']}"
                lead = "." * int((330 - tl(t, size=7.6) - tl(c["software"], size=6.8)) / tl(".", size=7.6))
                pg.insert_text((64, y), t, fontname="helv", fontsize=7.6)
                pg.insert_text((64 + tl(t, size=7.6) + 2, y), lead, fontname="helv", fontsize=7.6, color=GREY)
                pg.insert_text((394 - tl(c["software"], size=6.8), y), c["software"], fontname="heit", fontsize=6.8, color=GREY)
                pg.insert_text((398, y), f"{cm[0]['sheet']} - {cm[-1]['sheet']}", fontname="helv", fontsize=7.6)
                pg.insert_text((522, y), f"{cm[0]['page']} - {cm[-1]['page']}", fontname="helv", fontsize=7.6)
                y += 11
            y += 8
        pg.insert_text((50, y + 10), f"Total: {total} pages.  Sheet numbers are calc id - page within calc "
                                     "(e.g. B1-2); software output carries its own page numbers as well.",
                       fontname="helv", fontsize=7, color=GREY)
        pg.insert_text((50, y + 22), "Revision 1 (11/14/2026): footing schedule D1 re-issued, changed row clouded.",
                       fontname="helv", fontsize=7, color=RED)
    pkg.deferred.insert(0, fill)


# ======================================================================= drivers
RENDER = {"A1": calc_A1, "A2": calc_A2, "B1": lambda p, c: calc_B_ram(p, c, "B1"), "B2": lambda p, c: calc_B_ram(p, c, "B2"),
          "B3": lambda p, c: calc_B_ram(p, c, "B3"), "B4": calc_B4, "B5": calc_B5, "C1": calc_C1, "C2": calc_C2,
          "C3": lambda p, c: calc_C_smf(p, c, "C3"), "C4": lambda p, c: calc_C_smf(p, c, "C4"), "C5": calc_C5,
          "C6": calc_C6, "D1": calc_D1, "D2": calc_D2, "D3": calc_D3, "E1": calc_E1, "E2": calc_E2, "E3": calc_E3,
          "E4": calc_E4, "E5": calc_E5}


def _ctx(exp, d):
    recs = {}
    for r in exp["records"]:
        recs.setdefault(r["calc"], []).append(r)
    b = exp.get("building", {})
    return {"exp": exp, "d": d, "recs": recs, "rec": {r["id"]: r for r in exp["records"]},
            "el": {e["id"]: e for e in exp["elements"]}, "calcs": exp["calcs"],
            "calc_title": {c["id"]: c["title"] for c in exp["calcs"]} | {"COVER": "Calculation package cover", "TOC": "Table of contents"},
            "levels": b["levels"],
            "grids": b.get("grids") or {}, "areas": b.get("areas") or []}


def _render_calc(pkg, ctx, cid, d1_rev=None):
    if cid == "D1":
        calc_D1(pkg, ctx, d1_rev)
    else:
        RENDER[cid](pkg, ctx)


def write(exp: dict, d: dict, path: str) -> dict:
    with matplotlib.rc_context(RC):
        ctx = _ctx(exp, d)
        pkg = Pkg(ctx)
        cover(pkg, ctx)
        toc(pkg, ctx, exp["sections"])
        ft = ctx["recs"].get("D1", [])
        d1_rev = max(ft, key=lambda r: (r["uc"] or 0, r["id"]))["id"] if ft else None
        for c in exp["calcs"]:
            if c["id"] in ctx["recs"]:
                _render_calc(pkg, ctx, c["id"], d1_rev)
        # revised sheet: rev field in the pad header
        for p, items in pkg.revs.items():
            m = pkg.meta[p - 1]
            pkg.doc[p - 1].insert_text((m["w"] - 30 - 61, 56), "rev 1", fontname="helv", fontsize=5.5, color=RED)
        pkg.finalize(f"Structural calculations - {PROJECT} (synthetic)")
        pkg.save(path)
    # record evidence into exp
    first = {}
    for pl in pkg.places:
        if pl["how"] == "calc_row" and pl["ref"] not in first:
            first[pl["ref"]] = pl
    for pl in pkg.places:
        first.setdefault(pl["ref"], pl)
    for r in exp["records"]:
        pl = first.get(r["id"])
        if pl:
            r["page"], r["bbox"], r["sheet"] = pl["page"], pl["bbox"], pl["sheet"]
    occ = exp.setdefault("occurrences", [])
    for pl in pkg.places:
        base = {"doc": "calcs", "page": pl["page"], "sheet": pl["sheet"], "bbox": pl["bbox"], "how": pl["how"],
                "text": pl["text"], "text_layer": pl["text_layer"]}
        occ.append({"ref": pl["ref"], **base})
        for e in pl["elements"]:
            if e in ctx["el"]:
                occ.append({"ref": e, **base})
    exp["calc_pages"] = [{"page": m["page"], "sheet": m["sheet"], "calc": m["calc"], "style": m["style"],
                          "text_layer": m["text_layer"]} for m in pkg.meta]
    return {"pages": len(pkg.meta), "placed": len(first), "records": len(exp["records"])}


def _summary(rec) -> str:
    v = rec.get("values", {})
    keys = [k for k in ("size", "type", "B_ft", "h_in", "bars", "plate") if k in v]
    s = ", ".join(f"{k} {v[k]}" for k in keys)
    if rec.get("demand") is not None and rec.get("capacity") is not None:
        s += f"{', ' if s else ''}D/C {rec['demand']:.1f}/{rec['capacity']:.1f} {rec.get('unit', '')}"
    if rec.get("uc") is not None:
        s += f", UC {rec['uc']:.3f}"
    return s


def write_revision(exp: dict, d: dict, record_ids, path: str, rev_label: str = "Rev 1", prev_exp: dict | None = None) -> dict:
    """Revised-sheets PDF: only the calcs holding `record_ids`, rendered by the same per-calc
    renderers, each changed record clouded with a delta tag and a revision note (old -> new
    when prev_exp is given). Returns {record id: {page, bbox, sheet}}; exp is not modified."""
    ids = [i for i in record_ids]
    want = set(ids)
    prev = {r["id"]: r for r in (prev_exp or {}).get("records", [])}
    lab = rev_label.replace("Rev ", "").replace("rev ", "").strip() or "1"
    with matplotlib.rc_context(RC):
        ctx = _ctx(exp, d)
        calcs = {ctx["rec"][i]["calc"] for i in ids if i in ctx["rec"]}
        pkg = Pkg(ctx, rev_label=lab)
        for c in exp["calcs"]:
            if c["id"] in calcs:
                _render_calc(pkg, ctx, c["id"], None)
        seen = set()
        for pl in pkg.places:
            rid = pl["ref"]
            if rid not in want or rid in seen or pl["how"] != "calc_row":
                continue
            seen.add(rid)
            rec = ctx["rec"][rid]
            key = pl["text"].split(" ")[0]
            note = (f"{key}: was {_summary(prev[rid])}  ->  now {_summary(rec)}" if rid in prev
                    else f"{key}: revised, now {_summary(rec)}")
            pkg.revise(pl["page"], pymupdf.Rect(pl["bbox"]), note)
        for p in pkg.revs:
            m = pkg.meta[p - 1]
            pkg.doc[p - 1].insert_text((m["w"] - 30 - 61, 56), f"rev {lab}", fontname="helv", fontsize=5.5, color=RED)
        pkg.finalize(f"Structural calculations - {PROJECT} - revised sheets ({rev_label})")
        pkg.save(path)
    out = {}
    for pl in pkg.places:
        if pl["ref"] in want and pl["ref"] not in out and pl["how"] == "calc_row":
            out[pl["ref"]] = {"page": pl["page"], "bbox": pl["bbox"], "sheet": pl["sheet"]}
    for pl in pkg.places:
        if pl["ref"] in want and pl["ref"] not in out:
            out[pl["ref"]] = {"page": pl["page"], "bbox": pl["bbox"], "sheet": pl["sheet"]}
    return out
