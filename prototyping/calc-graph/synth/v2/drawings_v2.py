"""Synthetic structural drawing set (ARCH D, 36 x 24 in) for the v2 designed building.

    write(exp, d, path)   # called by synth.v2.generate

Sheets: S-001 general notes, S-101 foundation plan (+ footing / grade beam schedules),
S-201 / S-202 / S-203 framing plans (L2, L3, roof), S-301 frame elevations (SMF A, SMF D,
SCBF 3), S-401 column / pier / grade beam / base plate schedules, S-501 / S-502 typical
connection details, S-601 sections. Every printed appearance of an element, type, detail or
material is recorded in exp["occurrences"] with its exact text and its box in PDF points
(top-left origin), so one element is traceable from its plan tag to its elevation tag, its
schedule row and the detail its callout points at.

Conventions (kept close to backend/calcgraph/drawing_ingest.py and the real set it was
built on, differences noted in the module report):
- every glyph is a real text run (insert_text); tags on vertical members are rotated 90 deg
  and read bottom-up, like a real set
- grid bubbles at both ends of every grid line, label word height 22 pt
- member tags are the size, an SFRS member carries a leading "*" (as on the real S-sheets),
  then "(n)" studs and c=X" camber where nonzero: "W18X40 (30) c=3/4""
- footing marks are F<width in ft> ("F8.5"), pier marks P1 / P2, grade beam marks GB1 / GB2
- the sheet number is the tallest text in the title block

Byte-stable: base-14 fonts only (never embedded), fixed metadata, deterministic order.
"""
from __future__ import annotations

import math

import pymupdf

from .model import GX, GY, LEVELS

W, H = 2592.0, 1728.0
HELV, BOLD = "helv", "hebo"
_FONT = {HELV: pymupdf.Font("helv"), BOLD: pymupdf.Font("hebo")}
ASC, DESC = _FONT[HELV].ascender, _FONT[HELV].descender
BLACK, GREY, LIGHT, RED = (0, 0, 0), (0.42, 0.42, 0.42), (0.62, 0.62, 0.62), (0.75, 0.1, 0.1)

# ---- fictional firm / project (no real firm, person or license)
FIRM = ["QUILLFEATHER", "STRUCTURAL ENGINEERS"]
FIRM_ADDR = ["410 Lantern Row, Suite 3", "Port Calder, CA 90000", "(000) 555-0142"]
ARCHITECT = "MARROW & FINCH ARCHITECTS"
PROJECT = ["HARBOR VIEW", "OFFICE BUILDING"]
PROJECT_ADDR = ["1200 Tidewater Way", "Port Calder, CA 90000"]
CLIENT = "Saltmarsh Holdings LLC"
PROJECT_NO = "2611-SYN"
ISSUE_DATE = "11/14/2026"
ENGINEER = "R. VALCOURT-IMARI, S.E."
REVS = [("", "09/18/2026", "100% DESIGN DEVELOPMENT"), ("", "10/23/2026", "PERMIT SUBMITTAL"),
        ("1", "11/14/2026", "PLAN CHECK RESPONSE 1")]

# ---- sheet layout (points)
BORDER = 36.0
TB_X0, TB_X1 = 2316.0, W - BORDER          # title block strip
NOTES_X0, NOTES_X1 = 2006.0, 2296.0        # plan notes column
DRAW_X1 = 1968.0

# ---- plan transform: 3/16" = 1'-0" (13.5 pt per ft), north up
PS, PX0, PY0 = 13.5, 215.0, 1360.0

# detail number / sheet for each typical detail type
DETAIL_AT = {"MC-1": ("1", "S-501"), **{f"ST-{n}": (str(n), "S-501") for n in range(2, 8)},
             "DC-1": ("8", "S-501"), "DC-2": ("9", "S-501"), "DC-3": ("10", "S-501"),
             "BG-1": ("1", "S-502"), "BG-2": ("2", "S-502"), "BG-3": ("3", "S-502"),
             "BP-1": ("4", "S-502"), "BP-2": ("5", "S-502"), "BP-3": ("6", "S-502"), "BP-4": ("7", "S-502")}
LV_NAME = {"L1": "LEVEL 1", "L2": "LEVEL 2", "L3": "LEVEL 3", "RF": "ROOF"}
LV_Z = {"L1": 0.0, **{k: z for k, _, z in LEVELS}}


def px(x: float) -> float:
    return PX0 + x * PS


def py(y: float) -> float:
    return PY0 - y * PS


def tlen(s: str, size: float, font: str = HELV) -> float:
    return _FONT[font].text_length(s, fontsize=size)


def ftin(ft: float) -> str:
    inch = round(ft * 12)
    return f"{inch // 12}'-{inch % 12}\""


def ftin_sp(ft: float) -> str:
    """Schedule style 8' - 6" (what the ingest's footing-schedule reader expects)."""
    inch = round(ft * 12)
    return f"{inch // 12}' - {inch % 12}\""


def frac_in(v: float) -> str:
    whole = int(v)
    rem = round((v - whole) * 16)
    if rem == 0:
        return f"{whole}"
    g = math.gcd(rem, 16)
    f = f"{rem // g}/{16 // g}"
    return f"{whole}-{f}" if whole else f


def ftg_mark(b_ft: float) -> str:
    return f"F{b_ft:g}"


def pier_mark(t: str) -> str:
    return t.replace("-", "")          # P-1 -> P1


def r2(v: float) -> float:
    return round(v, 2)


def bb(*boxes) -> list[float]:
    return [r2(min(b[0] for b in boxes)), r2(min(b[1] for b in boxes)), r2(max(b[2] for b in boxes)), r2(max(b[3] for b in boxes))]


def wrap(s: str, width: float, size: float, font: str = HELV) -> list[str]:
    out, cur = [], ""
    for w in s.split():
        t = (cur + " " + w).strip()
        if cur and tlen(t, size, font) > width:
            out.append(cur)
            cur = w
        else:
            cur = t
    if cur:
        out.append(cur)
    return out


# =========================================================================== sheet
class Sheet:
    def __init__(self, ds: "DrawingSet", number: str, title: str, kind: str, level: str | None, scale: str):
        self.ds, self.number, self.title, self.kind, self.level, self.scale = ds, number, title, kind, level, scale
        self.page = ds.doc.new_page(width=W, height=H)
        self.pno = len(ds.doc)
        ds.exp["sheets"].append({"sheet": number, "title": title, "page": self.pno, "kind": kind, "level": level})

    # ---- primitives
    def text(self, x, y, s, size=9.0, font=HELV, color=BLACK, rotate=0, anchor="l") -> list[float]:
        """Insert one text run. anchor l / c / r along the reading direction. Returns its box."""
        w = tlen(s, size, font)
        if rotate == 90:
            if anchor == "c":
                y += w / 2
            elif anchor == "r":
                y += w
            self.page.insert_text((x, y), s, fontname=font, fontsize=size, color=color, rotate=90)
            return [r2(x - ASC * size), r2(y - w), r2(x - DESC * size), r2(y)]
        if anchor == "c":
            x -= w / 2
        elif anchor == "r":
            x -= w
        self.page.insert_text((x, y), s, fontname=font, fontsize=size, color=color)
        return [r2(x), r2(y - ASC * size), r2(x + w), r2(y - DESC * size)]

    def para(self, x, y, s, width, size=8.0, font=HELV, lead=None, indent=0.0) -> tuple[float, list[float]]:
        lead = lead or size * 1.32
        boxes = []
        for n, ln in enumerate(wrap(s, width - indent, size, font)):
            boxes.append(self.text(x + (indent if n else 0), y, ln, size, font))
            y += lead
        return y, bb(*boxes)

    def line(self, a, b, width=0.5, color=BLACK, dashes=None):
        self.page.draw_line(a, b, color=color, width=width, dashes=dashes)

    def rect(self, x0, y0, x1, y1, width=0.5, color=BLACK, fill=None, dashes=None):
        self.page.draw_rect(pymupdf.Rect(x0, y0, x1, y1), color=color, fill=fill, width=width, dashes=dashes)

    def circle(self, c, r, width=0.6, color=BLACK, fill=None):
        self.page.draw_circle(c, r, color=color, fill=fill, width=width)

    def poly(self, pts, width=0.6, color=BLACK, fill=None, closed=True, dashes=None):
        self.page.draw_polyline(pts + ([pts[0]] if closed else []), color=color, fill=fill, width=width, dashes=dashes)

    def occ(self, refs, how, text, bbox, **kw):
        refs = [refs] if isinstance(refs, str) else list(refs)
        if text and how in ("plan_tag", "elevation_tag", "schedule_row", "section_cut"):
            # a printed size / pier mark is also an appearance of the type the element is an instance of
            for r in list(refs):
                e = self.ds.el.get(r)
                if not e:
                    continue
                t = (f"TYPE:{e['size']}" if e["type"] in ("beam", "girder", "column", "brace") and e.get("size")
                     else f"TYPE:{e['pier_type']}" if e["type"] == "pier" else None)
                if t and t in self.ds.types and t not in refs:
                    refs.append(t)
        for r in refs:
            self.ds.exp["occurrences"].append({"ref": r, "doc": "drawings", "page": self.pno, "sheet": self.number,
                                               "bbox": list(bbox), "how": how, "text": text, **kw})

    # ---- annotation symbols
    def bubble(self, c, label, refs=None, how="grid_bubble", r=17.0):
        self.circle(c, r, width=1.0)
        box = self.text(c[0], c[1] + 0.36 * 16, label, 16, BOLD, anchor="c")
        if refs:
            self.occ(refs, how, label, box)
        return box

    def callout(self, target, at, num, sheet, refs=(), r=19.0, how="detail_callout"):
        """Detail callout bubble: number over sheet, leader to the target with an arrow."""
        tx, ty = target
        bx, by_ = at
        d = math.dist(target, at) or 1.0
        ux, uy = (tx - bx) / d, (ty - by_) / d
        self.line((bx + ux * r, by_ + uy * r), target, width=0.6)
        hx, hy = tx - ux * 7, ty - uy * 7
        self.poly([(tx, ty), (hx - uy * 2.6, hy + ux * 2.6), (hx + uy * 2.6, hy - ux * 2.6)], width=0.4, fill=BLACK)
        self.circle(at, r, width=0.9)
        self.line((bx - r, by_), (bx + r, by_), width=0.6)
        self.text(bx, by_ - 4, num, 10, BOLD, anchor="c")
        self.text(bx, by_ + 11, sheet, 7, HELV, anchor="c")
        box = [r2(bx - r), r2(by_ - r), r2(bx + r), r2(by_ + r)]
        txt = f"{num}/{sheet}"
        for ref in refs:
            self.occ(ref, how, txt, box)
        return box, txt

    def section_cut(self, a, b, num, sheet, refs=()):
        """Section cut line with a bubble + view arrow at both ends."""
        self.line(a, b, width=1.6, dashes="[18 4 3 4] 0")
        boxes = []
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dy)
        ux, uy = dx / L, dy / L
        nx, ny = uy, -ux            # look direction (right of the cut)
        for p, s in ((a, -1), (b, 1)):
            c = (p[0] + ux * s * 22, p[1] + uy * s * 22)
            self.poly([(c[0] + nx * 30, c[1] + ny * 30), (c[0] - ux * 16 + nx * 0, c[1] - uy * 16),
                       (c[0] + ux * 16, c[1] + uy * 16)], width=0.4, fill=BLACK)
            self.circle(c, 16, width=0.9, fill=(1, 1, 1))
            self.line((c[0] - 16, c[1]), (c[0] + 16, c[1]), width=0.6)
            self.text(c[0], c[1] - 3.5, num, 9, BOLD, anchor="c")
            self.text(c[0], c[1] + 10, sheet, 6.5, HELV, anchor="c")
            boxes.append([c[0] - 16, c[1] - 16, c[0] + 16, c[1] + 16])
        box = bb(*boxes)
        for ref in refs:
            self.occ(ref, "section_cut", f"{num}/{sheet}", box)

    def moment_flag(self, p, toward):
        """Filled triangle at a beam end, pointing at the column (moment connection)."""
        ux, uy = toward
        tip = (p[0] + ux * 5, p[1] + uy * 5)
        base = (p[0] - ux * 5, p[1] - uy * 5)
        self.poly([tip, (base[0] - uy * 5.5, base[1] + ux * 5.5), (base[0] + uy * 5.5, base[1] - ux * 5.5)], width=0.4, fill=BLACK)
        return [r2(p[0] - 6), r2(p[1] - 6), r2(p[0] + 6), r2(p[1] + 6)]

    def drag_diamond(self, p):
        x, y = p
        self.poly([(x, y - 5.5), (x + 5.5, y), (x, y + 5.5), (x - 5.5, y)], width=0.4, fill=BLACK)
        return [r2(x - 6), r2(y - 6), r2(x + 6), r2(y + 6)]

    def column_i(self, c, web_x: bool, hd=8.0, hf=7.0, width=1.8):
        x, y = c
        if web_x:   # web along page x, flanges vertical
            self.line((x - hd, y - hf), (x - hd, y + hf), width=width)
            self.line((x + hd, y - hf), (x + hd, y + hf), width=width)
            self.line((x - hd, y), (x + hd, y), width=width * 0.7)
        else:
            self.line((x - hf, y - hd), (x + hf, y - hd), width=width)
            self.line((x - hf, y + hd), (x + hf, y + hd), width=width)
            self.line((x, y - hd), (x, y + hd), width=width * 0.7)

    def north_arrow(self, x, y):
        self.circle((x, y), 26, width=0.8)
        self.poly([(x, y - 34), (x + 9, y + 12), (x, y + 4)], width=0.5, fill=BLACK)
        self.poly([(x, y - 34), (x - 9, y + 12), (x, y + 4)], width=0.5)
        self.text(x, y - 40, "N", 12, BOLD, anchor="c")
        self.text(x, y + 44, "PLAN NORTH", 6.5, HELV, anchor="c")

    def scale_bar(self, x, y, pt_per_ft, label):
        steps = [0, 4, 8, 16, 32]
        for a, b in zip(steps, steps[1:]):
            fill = BLACK if steps.index(a) % 2 == 0 else None
            self.rect(x + a * pt_per_ft, y, x + b * pt_per_ft, y + 6, width=0.5, fill=fill)
        for s in steps:
            self.text(x + s * pt_per_ft, y + 16, f"{s}'", 6.5, anchor="c")
        self.text(x, y - 6, label, 7, BOLD)

    def drawing_title(self, x, y, num, title, scale, width=520):
        self.circle((x + 18, y), 18, width=1.0)
        self.text(x + 18, y + 0.36 * 14, num, 14, BOLD, anchor="c")
        self.text(x + 46, y + 2, title, 15, BOLD)
        self.line((x + 46, y + 7), (x + 46 + width, y + 7), width=1.6)
        self.text(x + 46, y + 20, f"SCALE: {scale}", 8)

    def delta(self, c, n="1", size=9):
        x, y = c
        self.poly([(x, y - size), (x + size, y + size * 0.7), (x - size, y + size * 0.7)], width=0.8)
        self.text(x, y + size * 0.5, n, 7.5, BOLD, anchor="c")

    def rev_cloud(self, x0, y0, x1, y1, arc=10.0):
        sh = self.page.new_shape()
        pts = []
        for (ax, ay), (bx, by_) in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
            n = max(2, int(math.dist((ax, ay), (bx, by_)) / arc))
            for k in range(n):
                pts.append(((ax + (bx - ax) * k / n, ay + (by_ - ay) * k / n), (ax + (bx - ax) * (k + 1) / n, ay + (by_ - ay) * (k + 1) / n)))
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        for p, q in pts:
            mx, my = (p[0] + q[0]) / 2, (p[1] + q[1]) / 2
            ox, oy = mx - cx, my - cy
            L = math.hypot(ox, oy) or 1
            sh.draw_curve(p, (mx + ox / L * arc * 0.6, my + oy / L * arc * 0.6), q)
        sh.finish(color=RED, width=0.8)
        sh.commit()

    # ---- frame + title block
    def frame(self):
        self.rect(BORDER, BORDER, W - BORDER, H - BORDER, width=2.2)
        self.line((TB_X0, BORDER), (TB_X0, H - BORDER), width=2.0)
        x0, x1 = TB_X0 + 10, TB_X1 - 10
        y = BORDER + 30
        for ln in FIRM:
            self.text(x0, y, ln, 14 if ln == FIRM[0] else 10.5, BOLD)
            y += 17
        y += 4
        for ln in FIRM_ADDR:
            self.text(x0, y, ln, 8)
            y += 11
        y += 8
        self.line((TB_X0, y), (TB_X1, y), width=1.2)
        y += 16
        self.text(x0, y, "ARCHITECT", 5.5, HELV, GREY)
        self.text(x0, y + 13, ARCHITECT, 9, BOLD)
        y += 28
        self.line((TB_X0, y), (TB_X1, y), width=1.2)
        y += 16
        self.text(x0, y, "PROJECT NAME", 5.5, HELV, GREY)
        y += 26
        for ln in PROJECT:
            self.text(x0, y, ln, 21, HELV)
            y += 25
        for ln in PROJECT_ADDR:
            self.text(x0, y, ln, 11)
            y += 14
        self.text(x0, y + 6, "CLIENT", 5.5, HELV, GREY)
        self.text(x0, y + 19, CLIENT, 9, BOLD)
        y += 34
        self.line((TB_X0, y), (TB_X1, y), width=1.2)
        # seal area
        sc = ((TB_X0 + TB_X1) / 2, y + 92)
        self.circle(sc, 72, width=1.0)
        self.circle(sc, 60, width=0.5)
        self.text(sc[0], sc[1] - 14, "SAMPLE", 20, BOLD, (0.55, 0.55, 0.55), anchor="c")
        self.text(sc[0], sc[1] + 4, "NOT FOR CONSTRUCTION", 7, BOLD, GREY, anchor="c")
        self.text(sc[0], sc[1] + 18, ENGINEER, 6.5, HELV, GREY, anchor="c")
        self.text(sc[0], sc[1] + 28, "SYNTHETIC DATASET - NO SEAL", 5.5, HELV, GREY, anchor="c")
        y += 184
        self.line((TB_X0, y), (TB_X1, y), width=1.2)
        # revisions
        cols = [TB_X0, TB_X0 + 26, TB_X0 + 86, TB_X1]
        self.text(cols[0] + 4, y + 11, "No.", 7, BOLD)
        self.text(cols[1] + 4, y + 11, "DATE", 7, BOLD)
        self.text(cols[2] + 4, y + 11, "ISSUE / REVISION", 7, BOLD)
        for k in range(12):
            ry = y + 15 + k * 14
            self.line((TB_X0, ry), (TB_X1, ry), width=0.3)
            if k < len(REVS):
                n, dte, desc = REVS[k]
                if n:
                    self.delta((cols[0] + 13, ry + 7), n, 6)
                self.text(cols[1] + 4, ry + 10.5, dte, 7)
                self.text(cols[2] + 4, ry + 10.5, desc, 7)
        y += 15 + 12 * 14
        for cx in cols[1:3]:
            self.line((cx, y - 12 * 14 - 15), (cx, y), width=0.3)
        self.line((TB_X0, y), (TB_X1, y), width=1.2)
        y += 6
        self.para(x0, y + 7, "DRAWINGS AND WRITTEN MATERIAL HEREIN ARE A SYNTHETIC SAMPLE PREPARED FOR SOFTWARE TESTING. "
                  "NOT FOR CONSTRUCTION, PERMIT OR BIDDING.", x1 - x0, 5.5)
        y += 30
        self.line((TB_X0, y), (TB_X1, y), width=0.6)
        for lab, val in (("PROJECT NO.", PROJECT_NO), ("DATE", ISSUE_DATE), ("SCALE", self.scale),
                         ("DRAWN BY", "TLK"), ("CHECKED BY", "RVI")):
            self.text(x0, y + 9, lab, 5.5, HELV, GREY)
            self.text(x0 + 70, y + 12, val, 8.5)
            y += 18
            self.line((TB_X0, y), (TB_X1, y), width=0.3)
        self.line((TB_X0, y), (TB_X1, y), width=1.2)
        # drawing title + number (ingest: title words sit 5..230 pt above the sheet number)
        ny = H - BORDER - 40
        self.line((TB_X0, ny - 110), (TB_X1, ny - 110), width=1.2)
        self.text(x0, ny - 98, "DRAWING NO.", 5.5, HELV, GREY)
        self.text((TB_X0 + TB_X1) / 2, ny, self.number, 54, BOLD, anchor="c")
        self.text(x0, ny - 300, "DRAWING TITLE", 5.5, HELV, GREY)
        ty = ny - 270
        for ln in wrap(self.title, x1 - x0, 17):
            self.text(x0, ty, ln, 17)
            ty += 22


# =========================================================================== set
class DrawingSet:
    def __init__(self, exp: dict):
        self.exp = exp
        exp.setdefault("occurrences", [])
        exp.setdefault("sheets", [])
        exp.setdefault("details", [])
        self.doc = pymupdf.open()
        self.el = {e["id"]: e for e in exp["elements"]}
        self.types = {t["id"]: t for t in exp["types"]}
        self.by_type: dict[str, list] = {}
        for e in exp["elements"]:
            self.by_type.setdefault(e["type"], []).append(e)
        self.conns = [e for e in self.by_type.get("connection", []) if "member" in e]
        self.conn_by_member: dict[str, list] = {}
        for c in self.conns:
            self.conn_by_member.setdefault(c["member"], []).append(c)
        self.cols = {e["id"][4:]: e for e in self.by_type["column"]}
        self.det_rows: list[dict] = []

    def rel(self, src, dst, kind):
        r = {"src": src, "dst": dst, "kind": kind}
        if r not in self._rels:
            self._rels.append(r)

    def members(self, level: str) -> list[dict]:
        return [e for e in self.exp["elements"] if e["type"] in ("beam", "girder") and e["level"] == level]

    def save(self, path: str):
        self.doc.set_metadata({
            "title": "Structural drawings - Harbor View Office Building (synthetic)", "author": "calc-graph synth",
            "subject": "Synthetic structural drawing set with ground truth", "creator": "calc-graph synth generator",
            "producer": "PyMuPDF", "creationDate": "D:20261114090000-05'00'", "modDate": "D:20261114090000-05'00'",
            "keywords": "",
        })
        self.doc.save(path, garbage=3, deflate=True, no_new_id=True)


def member_tag(e: dict) -> str:
    s = ("*" if e.get("sfrs") else "") + e["size"]
    if e.get("studs"):
        s += f" ({e['studs']})"
    if e.get("camber_in"):
        s += f" c={frac_in(e['camber_in'])}\""
    return s


def dtype(conn: dict) -> str:
    return conn["conn_type"].rstrip("*")


# =========================================================================== plan pieces
def plan_grid(sh: Sheet, dims=True):
    top, bot = py(GY[-1][1]) - 110, py(GY[0][1]) + 110
    left, right = px(GX[0][1]) - 110, px(GX[-1][1]) + 110
    for gl, x in GX:
        X = px(x)
        sh.line((X, top + 17), (X, bot - 17), width=0.9, dashes="[24 5 4 5] 0", color=GREY)
        sh.bubble((X, top), gl, f"GRID:{gl}")
        sh.bubble((X, bot), gl, f"GRID:{gl}")
    for gl, y in GY:
        Y = py(y)
        sh.line((left + 17, Y), (right - 17, Y), width=0.9, dashes="[24 5 4 5] 0", color=GREY)
        sh.bubble((left, Y), gl, f"GRID:{gl}")
        sh.bubble((right, Y), gl, f"GRID:{gl}")
    if not dims:
        return
    # dimension strings: bay dims inner, overall outer
    for yy, pairs in ((py(GY[-1][1]) - 48, list(zip(GX, GX[1:]))), (py(GY[-1][1]) - 74, [(GX[0], GX[-1])])):
        for (la, xa), (lb, xb) in pairs:
            a, b = px(xa), px(xb)
            sh.line((a, yy), (b, yy), width=0.4)
            for t in (a, b):
                sh.line((t - 4, yy + 4), (t + 4, yy - 4), width=0.7)
                sh.line((t, yy - 8), (t, yy + 8), width=0.3)
            sh.text((a + b) / 2, yy - 3, ftin(xb - xa), 9, anchor="c")
    for xx, pairs in ((px(GX[0][1]) - 48, list(zip(GY, GY[1:]))), (px(GX[0][1]) - 74, [(GY[0], GY[-1])])):
        for (la, ya), (lb, yb) in pairs:
            a, b = py(ya), py(yb)
            sh.line((xx, a), (xx, b), width=0.4)
            for t in (a, b):
                sh.line((xx - 4, t + 4), (xx + 4, t - 4), width=0.7)
                sh.line((xx - 8, t), (xx + 8, t), width=0.3)
            sh.text(xx - 3, (a + b) / 2, ftin(yb - ya), 9, rotate=90, anchor="c")


def notes_column(sh: Sheet, heading: str, notes: list[tuple[str, list[str]]], y=80.0) -> float:
    sh.text(NOTES_X0, y, heading, 11, BOLD)
    sh.line((NOTES_X0, y + 4), (NOTES_X0 + tlen(heading, 11, BOLD), y + 4), width=0.8)
    y += 24
    for n, (txt, refs) in enumerate(notes, 1):
        sh.text(NOTES_X0, y, f"{n}.", 8)
        y2, box = sh.para(NOTES_X0 + 16, y, txt, NOTES_X1 - NOTES_X0 - 16)
        if refs:
            sh.occ(refs, "note", txt, box)
        y = y2 + 5
    return y


def legend(sh: Sheet, y: float, items) -> float:
    sh.text(NOTES_X0, y, "FRAMING PLAN SYMBOLS", 11, BOLD)
    sh.line((NOTES_X0, y + 4), (NOTES_X0 + tlen("FRAMING PLAN SYMBOLS", 11, BOLD), y + 4), width=0.8)
    y += 30
    for kind, txt in items:
        cx, cy = NOTES_X0 + 26, y - 3
        if kind == "moment":
            sh.line((cx - 22, cy), (cx + 4, cy), width=2.0)
            sh.moment_flag((cx + 4, cy), (1, 0))
            sh.column_i((cx + 16, cy), True, 6, 5, 1.4)
        elif kind == "drag":
            sh.line((cx - 22, cy), (cx + 10, cy), width=2.0)
            sh.drag_diamond((cx + 4, cy))
        elif kind == "callout":
            sh.circle((cx, cy), 13, width=0.8)
            sh.line((cx - 13, cy), (cx + 13, cy), width=0.5)
            sh.text(cx, cy - 3, "#", 8, BOLD, anchor="c")
            sh.text(cx, cy + 9, "S-XXX", 5.5, anchor="c")
        elif kind == "section":
            sh.circle((cx, cy), 13, width=0.8, fill=(1, 1, 1))
            sh.poly([(cx + 13, cy - 5), (cx + 24, cy), (cx + 13, cy + 5)], width=0.4, fill=BLACK)
            sh.line((cx - 13, cy), (cx + 13, cy), width=0.5)
        elif kind == "column":
            sh.column_i((cx, cy), False, 7, 6, 1.6)
        elif kind == "brace":
            sh.line((cx - 20, cy), (cx + 20, cy), width=2.8)
            sh.text(cx, cy + 12, "*SCBF", 6, anchor="c")
        elif kind == "text":
            sh.text(NOTES_X0, cy + 3, txt[0], 7, BOLD)
            txt = txt[1]
        elif kind == "cloud":
            sh.rev_cloud(cx - 18, cy - 9, cx + 18, cy + 9, 6)
        _, box = sh.para(NOTES_X0 + 62, y, txt, NOTES_X1 - NOTES_X0 - 62, 7.5)
        y = max(y + 30, box[3] + 14)
    return y


# =========================================================================== S-001
def sheet_general_notes(ds: DrawingSet):
    sh = Sheet(ds, "S-001", "GENERAL NOTES, DESIGN CRITERIA AND SPECIAL INSPECTIONS", "notes", None, "NONE")
    sh.frame()
    exp = ds.exp
    rec = {r["id"]: r for r in exp["records"]}
    crit = rec["A1-CRIT"]["values"]
    ex, ey = rec["C-ELF:X"]["values"], rec["C-ELF:Y"]["values"]
    colw, gap = 440.0, 34.0
    xs = [60 + k * (colw + gap) for k in range(5)]
    state = {"k": 0, "y": 80.0}

    def col_break(need=60):
        if state["y"] + need > H - 70:
            state["k"] += 1
            state["y"] = 80.0

    def heading(t, need=80):
        col_break(need)
        x = xs[state["k"]]
        state["y"] += 6
        sh.text(x, state["y"], t, 12.5, BOLD)
        sh.line((x, state["y"] + 4), (x + tlen(t, 12.5, BOLD), state["y"] + 4), width=0.9)
        state["y"] += 22

    def note(n, t, refs=()):
        col_break(40)
        x = xs[state["k"]]
        if n:
            sh.text(x, state["y"], n, 9.5)
        y2, box = sh.para(x + 20, state["y"], t, colw - 20, 9.5, lead=12.5)
        if refs:
            sh.occ(list(refs), "note", t, box)
        state["y"] = y2 + 5

    def table(head, rows, widths, refs_per_row=None, size=8.5):
        col_break(16 * (len(rows) + 1) + 10)
        x = xs[state["k"]]
        y = state["y"]
        cx = [x]
        for w_ in widths:
            cx.append(cx[-1] + w_)
        sh.rect(cx[0], y - 12, cx[-1], y + 5, width=0.5, fill=(0.88, 0.88, 0.88))
        for i, h in enumerate(head):
            sh.text(cx[i] + 3, y, h, 8, BOLD)
        for r_, row in enumerate(rows):
            y += 17
            boxes = [sh.text(cx[i] + 3, y, str(v), size) for i, v in enumerate(row)]
            sh.line((cx[0], y + 4), (cx[-1], y + 4), width=0.3)
            if refs_per_row and refs_per_row[r_]:
                sh.occ(refs_per_row[r_], "note", "  ".join(str(v) for v in row), bb(*boxes))
        for c_ in cx:
            sh.line((c_, state["y"] - 12), (c_, y + 4), width=0.3)
        sh.line((cx[0], y + 4), (cx[-1], y + 4), width=0.5)
        state["y"] = y + 18

    heading("GENERAL")
    gen = [
        "THESE NOTES APPLY TO ALL STRUCTURAL SHEETS UNLESS NOTED OTHERWISE (U.N.O.) ON PLANS OR DETAILS. "
        "WHERE A CONFLICT EXISTS THE MORE STRINGENT REQUIREMENT GOVERNS; NOTIFY THE ENGINEER OF RECORD BEFORE PROCEEDING.",
        "THE STRUCTURE IS DESIGNED FOR ITS COMPLETED CONDITION. THE CONTRACTOR IS RESPONSIBLE FOR TEMPORARY BRACING, "
        "SHORING AND STABILITY OF THE STRUCTURE DURING CONSTRUCTION.",
        "DO NOT SCALE DRAWINGS. VERIFY ALL DIMENSIONS AND ELEVATIONS WITH THE ARCHITECTURAL DRAWINGS.",
        "TYPICAL DETAILS APPLY WHERE NOT SPECIFICALLY CALLED OUT. SEE S-501 AND S-502.",
        "SPECIFICATIONS: SEE PROJECT MANUAL DIVISIONS 03, 05 AND 07 FOR PRODUCTS AND EXECUTION REQUIREMENTS.",
    ]
    for n, t in enumerate(gen, 1):
        note(f"{n}.", t)
    heading("DESIGN CODES")
    codes = [c.strip() for c in crit["codes"].split(",")]
    note("1.", "BUILDING CODE: " + codes[0] + " WITH LOCAL AMENDMENTS.")
    note("2.", "LOADS: " + codes[1] + ". STEEL: " + ", ".join(codes[2:5]) + ". CONCRETE: " + codes[5] + ".")
    heading("DESIGN LOADS (PSF)", 140)
    seen, rows = {}, []
    for a in exp["building"]["areas"]:
        key = (a["kind"], a["d_psf"], a["l_psf"], a["lr_psf"])
        seen.setdefault(key, []).append(a["level"])
    for (kind, d_, l_, lr), lvs in seen.items():
        name = {"office": "OFFICE", "corridor": "CORRIDOR / LOBBY", "mech": "ROOF - MECH (RTU ZONE)", "roof": "ROOF"}[kind]
        lv = ", ".join(sorted(set(LV_NAME[x] for x in lvs)))
        rows.append([name, lv, f"{d_:g}", f"{l_:g}" if l_ else "-", f"{lr:g}" if lr else "-"])
    table(["OCCUPANCY / AREA", "LEVEL", "DEAD", "LIVE", "ROOF LIVE"], rows, [150, 120, 55, 55, 70])
    note("", "FLOOR LIVE LOADS INCLUDE 15 PSF PARTITION ALLOWANCE. DEAD LOAD INCLUDES DECK, CONCRETE, "
             "CEILING, MEP AND FINISHES; STEEL SELF WEIGHT IS ADDITIONAL.", ["DK-L2", "DK-L3"])
    heading("LATERAL DESIGN CRITERIA")
    note("1.", f"SEISMIC: {crit['seismic']}. EQUIVALENT LATERAL FORCE PROCEDURE.")
    note("2.", f"N-S/E-W (X): {ex['system'].upper()}, R = {ex['R']:g}, CD = {ex['Cd']:g}, OMEGA0 = {ex['Omega0']:g}, "
               f"CS = {ex['Cs']:g}, V = {ex['V_k']:g} KIPS.", ["FRAME:SMF-A", "FRAME:SMF-D"])
    note("3.", f"(Y): {ey['system'].upper()}, R = {ey['R']:g}, CD = {ey['Cd']:g}, OMEGA0 = {ey['Omega0']:g}, "
               f"CS = {ey['Cs']:g}, V = {ey['V_k']:g} KIPS.", ["FRAME:SCBF-3"])
    note("4.", f"WIND: {crit['wind'].upper()}, RISK CATEGORY II. MWFRS BASE SHEAR X = {rec['C-WIND:X']['values']['V_k']:g} K, "
               f"Y = {rec['C-WIND:Y']['values']['V_k']:g} K (SEISMIC GOVERNS).")
    note("5.", "SOILS: " + crit["soil"].upper() + " PER GEOTECHNICAL REPORT (BY OTHERS). BOTTOM OF FOOTING 1'-6\" MIN BELOW "
               "TOP OF FOOTING EL. -3'-0\".")
    heading("SEISMIC FORCE-RESISTING SYSTEM", 130)
    frows, frefs = [], []
    for fr in (e for e in ds.by_type["frame"]):
        key = fr["id"].split(":")[1]
        beams = sorted({e["size"] for e in ds.exp["elements"] if e["type"] in ("beam", "girder") and e.get("frame") == key
                        and any(r in e["roles"] for r in ("smf_beam", "scbf_beam"))})
        colsz = sorted({c["size"] for c in ds.cols.values() if key in c["frames"]})
        braces = sorted({e["size"] for e in ds.by_type.get("brace", []) if e["frame"] == key})
        conn = "MC-1 (RBS)" if fr["system"] == "SMF" else "BG GUSSETS"
        frows.append([key, ", ".join(beams), ", ".join(colsz), ", ".join(braces) or "-", conn])
        frefs.append([fr["id"]])
    table(["FRAME", "BEAMS", "COLUMNS", "BRACES", "CONN."], frows, [44, 110, 150, 84, 52], frefs, 7.5)
    heading("SUBMITTALS")
    for n, t in enumerate([
        "SHOP DRAWINGS FOR STRUCTURAL STEEL, STEEL DECK AND REINFORCING SHALL BE REVIEWED BY THE CONTRACTOR BEFORE "
        "SUBMITTAL. ALLOW 10 WORKING DAYS FOR ENGINEER REVIEW.",
        "WELDING PROCEDURE SPECIFICATIONS (WPS) FOR ALL SFRS WELDS AND FILLER METAL CERTIFICATES WITH CVN DATA.",
        "CONCRETE MIX DESIGNS FOR EACH CLASS OF CONCRETE, WITH STRENGTH TEST RECORDS.",
        "DEFERRED SUBMITTAL: STAIRS, GUARDRAILS AND EXTERIOR WALL FRAMING (DELEGATED DESIGN).",
    ], 1):
        note(f"{n}.", t)
    heading("MATERIALS")
    mats = [
        ("STRUCTURAL STEEL W SHAPES: ASTM A992, FY = 50 KSI.", ["MAT:A992"]),
        ("HSS: ASTM A500 GRADE C, FY = 50 KSI (SQUARE AND RECTANGULAR).", ["MAT:A500C"]),
        ("PLATES, ANGLES AND CHANNELS: ASTM A36 U.N.O.", ["MAT:A36"]),
        ("HIGH-STRENGTH BOLTS: ASTM F3125 GRADE A325, 3/4\" DIA U.N.O. SNUG-TIGHT AT SHEAR TABS; PRETENSIONED AT SFRS "
         "CONNECTIONS, SLIP-CRITICAL WHERE NOTED.", ["MAT:F3125-A325"]),
        ("WELD METAL: E70XX LOW HYDROGEN. DEMAND CRITICAL WELDS PER AWS D1.8 WITH CVN TOUGHNESS.", ["MAT:E70XX"]),
        ("ANCHOR RODS: ASTM F1554 GRADE 36 U.N.O.; GRADE 55 WHERE NOTED.", ["MAT:F1554"]),
        ("HEADED SHEAR STUDS: 3/4\" DIA, ASTM A108, AWS D1.1 TYPE B.", ["MAT:STUD"]),
        ("STEEL DECK: ASTM A653 SS GR 50, G60. FLOOR: 3\" 20 GA COMPOSITE; ROOF: 1-1/2\" 20 GA TYPE B.",
         ["MAT:DECK-3VLI20", "DK-L2", "DK-L3", "DK-RF"]),
        ("CONCRETE: FOOTINGS, PIERS, GRADE BEAMS F'C = 4,000 PSI NORMAL WEIGHT AT 28 DAYS.", ["MAT:CONC-4000"]),
        ("CONCRETE ON METAL DECK: F'C = 3,000 PSI LIGHTWEIGHT (110 PCF).", ["MAT:CONC-LW3000"]),
        ("REINFORCING: ASTM A615 GRADE 60. LAP SPLICES CLASS B U.N.O.", ["MAT:REBAR-A615"]),
        ("FIREPROOFING: SPRAY-APPLIED (SFRM) PER UL ASSEMBLY ON ARCH DRAWINGS. MASK FAYING SURFACES AND "
         "PROTECTED ZONES OF RBS BEFORE APPLICATION.", ["MAT:SFRM"]),
    ]
    for n, (t, refs) in enumerate(mats, 1):
        note(f"{n}.", t, refs)
    heading("STRUCTURAL STEEL")
    for n, t in enumerate([
        "FABRICATE AND ERECT PER AISC 360-16 AND AISC 303. SEISMIC FORCE-RESISTING SYSTEM (SFRS) PER AISC 341-16; "
        "SMF MOMENT CONNECTIONS PER AISC 358-16 CHAPTER 5 (RBS).",
        "MEMBERS MARKED * ON PLANS AND ELEVATIONS ARE PART OF THE SFRS. THE PROTECTED ZONE OF EACH RBS (FROM THE COLUMN "
        "FACE TO THE END OF THE CUT) SHALL HAVE NO ATTACHMENTS, WELDS OR SHOT PINS.",
        "CAMBER SHOWN (c=X\") IS AT MIDSPAN; FABRICATE WITH CAMBER UP. BEAMS WITHOUT CAMBER SHALL BE ERECTED WITH NATURAL "
        "MILL CAMBER UP.",
        "SHEAR STUDS: (n) ON PLAN IS THE TOTAL NUMBER OF STUDS ON THE BEAM, EQUALLY SPACED, ONE PER RIB MIN.",
    ], 1):
        note(f"{n}.", t)
    heading("FOUNDATIONS")
    for n, t in enumerate([
        "FOOTINGS BEAR ON UNDISTURBED NATIVE SOIL OR ENGINEERED FILL APPROVED BY THE GEOTECHNICAL ENGINEER.",
        "GRADE BEAMS ON LINES A, D, 1 AND 5 SUPPORT THE PERIMETER WALL; LINE 3 GRADE BEAMS ARE TIES BETWEEN BRACED "
        "FRAME FOOTINGS. SEE FOUNDATION SCHEDULES ON S-101 AND S-401.",
        "CONCRETE COVER: 3\" CAST AGAINST EARTH, 2\" FORMED AND EXPOSED, 1-1/2\" PIER TIES.",
    ], 1):
        note(f"{n}.", t)
    heading("SPECIAL INSPECTIONS (IBC CH. 17)", 17 * 12 + 60)
    srows, srefs = [], []
    for item, freq, ref, refs in [
        ("SMF DEMAND CRITICAL CJP WELDS", "CONTINUOUS", "AISC 341 J6, AWS D1.8", ["FRAME:SMF-A", "FRAME:SMF-D", "DETAIL:MC-1", "MAT:E70XX"]),
        ("SCBF GUSSET WELDS AND BRACES", "CONTINUOUS", "AISC 341 J6", ["FRAME:SCBF-3", "DETAIL:BG-3"]),
        ("PRETENSIONED / SC BOLTS (SFRS)", "PERIODIC", "AISC 360 N5.6", ["MAT:F3125-A325"]),
        ("STRUCTURAL STEEL FABRICATION", "PERIODIC", "IBC 1704.2.5", ["MAT:A992", "MAT:A500C"]),
        ("ULTRASONIC TEST OF CJP WELDS", "100% SFRS", "AISC 341 J6.2", ["DETAIL:MC-1"]),
        ("REINFORCING STEEL PLACEMENT", "PERIODIC", "ACI 318 26.13", ["MAT:REBAR-A615"]),
        ("CONCRETE SAMPLING AND PLACEMENT", "CONTINUOUS", "ACI 318 26.13", ["MAT:CONC-4000"]),
        ("ANCHOR RODS BEFORE PLACEMENT", "PERIODIC", "IBC 1705.3", ["MAT:F1554"]),
        ("STEEL DECK AND STUD WELDING", "PERIODIC", "SDI QA/QC", ["MAT:DECK-3VLI20", "MAT:STUD"]),
        ("SPRAYED FIRE-RESISTANT MATERIAL", "PERIODIC", "IBC 1705.14", ["MAT:SFRM"]),
    ]:
        srows.append([item, freq, ref])
        srefs.append(refs)
    table(["INSPECTION", "FREQUENCY", "REFERENCE"], srows, [210, 90, 140], srefs)
    note("", "A STATEMENT OF SPECIAL INSPECTIONS SHALL BE SUBMITTED BEFORE PERMIT ISSUE. SEE SPEC SECTION 01 45 33.")
    heading("ABBREVIATIONS")
    abbr = [("ABV", "ABOVE"), ("B.O.", "BOTTOM OF"), ("c=", "CAMBER"), ("CJP", "COMPLETE JOINT PENETRATION"),
            ("CONT", "CONTINUOUS"), ("DC", "DRAG CONNECTION"), ("EL.", "ELEVATION"), ("EW", "EACH WAY"),
            ("FTG", "FOOTING"), ("GB", "GRADE BEAM"), ("LW", "LIGHTWEIGHT"), ("MC", "MOMENT CONNECTION"),
            ("RBS", "REDUCED BEAM SECTION"), ("SCBF", "SPECIAL CONCENTRICALLY BRACED FRAME"),
            ("SFRS", "SEISMIC FORCE-RESISTING SYSTEM"), ("SMF", "SPECIAL MOMENT FRAME"), ("ST", "SHEAR TAB"),
            ("T.O.S.", "TOP OF STEEL"), ("TYP", "TYPICAL"), ("U.N.O.", "UNLESS NOTED OTHERWISE")]
    for a, t in abbr:
        col_break(14)
        x = xs[state["k"]]
        sh.text(x, state["y"], a, 9, BOLD)
        sh.text(x + 64, state["y"], t, 9)
        state["y"] += 12.5
    heading("SHEET INDEX")
    for s in SHEET_LIST:
        col_break(14)
        x = xs[state["k"]]
        sh.text(x, state["y"], s[0], 9, BOLD)
        sh.text(x + 64, state["y"], s[1], 9)
        state["y"] += 12.5


SHEET_LIST = [
    ("S-001", "GENERAL NOTES, DESIGN CRITERIA AND SPECIAL INSPECTIONS"), ("S-101", "FOUNDATION PLAN"),
    ("S-201", "LEVEL 2 FRAMING PLAN"), ("S-202", "LEVEL 3 FRAMING PLAN"), ("S-203", "ROOF FRAMING PLAN"),
    ("S-301", "MOMENT FRAME ELEVATIONS AND BRACED FRAME ELEVATION"), ("S-401", "COLUMN AND FOUNDATION SCHEDULES"),
    ("S-501", "TYPICAL STEEL CONNECTION DETAILS"), ("S-502", "TYPICAL BRACE AND BASE PLATE DETAILS"),
    ("S-601", "SECTIONS"),
]


# =========================================================================== S-101
def gb_mark(g: dict) -> str:
    return "GB2" if g.get("tie_bars") else "GB1"


def sheet_foundation(ds: DrawingSet):
    sh = Sheet(ds, "S-101", "FOUNDATION PLAN", "plan", "L1", "3/16\" = 1'-0\"")
    sh.frame()
    plan_grid(sh)
    foot = {e["id"][2:]: e for e in ds.by_type["footing"]}
    pier = {e["id"][2:]: e for e in ds.by_type["pier"]}
    bps = {e["id"][3:]: e for e in ds.by_type["connection"] if e["id"].startswith("BP-")}
    # grade beams (under) first
    for g in ds.by_type["grade_beam"]:
        (x1, y1, _), (x2, y2, _) = g["p1"], g["p2"]
        a, b = (px(x1), py(y1)), (px(x2), py(y2))
        hw = g["b_in"] / 12 / 2 * PS
        fa, fb = foot[_gb_end(g, "a")], foot[_gb_end(g, "b")]
        if abs(y1 - y2) < 1e-6:     # along x
            sa, sb = a[0] + fa["B_ft"] / 2 * PS, b[0] - fb["B_ft"] / 2 * PS
            for o in (-hw, hw):
                sh.line((sa, a[1] + o), (sb, a[1] + o), width=1.0, dashes="[6 3] 0")
            box = sh.text((sa + sb) / 2, a[1] - hw - 4, gb_mark(g), 9, BOLD, anchor="c")
        else:
            sa, sb = a[1] - fa["B_ft"] / 2 * PS, b[1] + fb["B_ft"] / 2 * PS
            for o in (-hw, hw):
                sh.line((a[0] + o, sa), (a[0] + o, sb), width=1.0, dashes="[6 3] 0")
            box = sh.text(a[0] - hw - 4, (sa + sb) / 2, gb_mark(g), 9, BOLD, rotate=90, anchor="c")
        sh.occ(g["id"], "plan_tag", gb_mark(g), box)
    for c, f in foot.items():
        X, Y = px(f["x"]), py(f["y"])
        hb = f["B_ft"] / 2 * PS
        sh.rect(X - hb, Y - hb, X + hb, Y + hb, width=1.1, dashes="[7 3] 0")
        p = pier[c]
        hp = p["b_in"] / 12 / 2 * PS
        sh.rect(X - hp, Y - hp, X + hp, Y + hp, width=1.3)
        col = ds.cols[c]
        sh.column_i((X, Y), "smf_column" in col["roles"], 6.5, 5.5, 1.5)
        mk = ftg_mark(f["B_ft"])
        box = sh.text(X + hp + 3, Y + hb - 5, mk, 10, BOLD)
        sh.occ(f["id"], "plan_tag", mk, box)
        pm = pier_mark(p["pier_type"])
        box = sh.text(X - hb + 4, Y - hp - 4, pm, 8.5)
        sh.occ(p["id"], "plan_tag", pm, box)
    # base plate callouts: one per base plate type
    done = set()
    for c, bp in bps.items():
        t = bp["conn_type"].rstrip("*")
        if t in done:
            continue
        done.add(t)
        X, Y = px(bp["x"]), py(bp["y"])
        hb = foot[c]["B_ft"] / 2 * PS
        num, s = DETAIL_AT[t]
        up = 1 if bp["y"] < 40 else -1     # bubble toward the inside of the plan
        sh.callout((X + 6, Y - 6 * up), (X + hb + 34, Y - up * (hb + 30)), num, s, [bp["id"]])
        ds.rel(bp["id"], f"DET:{num}/{s}", "detailed-by")
    # sections
    sh.section_cut((px(33), py(-4)), (px(33), py(9)), "1", "S-601",
                   ["COL-2A", "BP-2A", "P-2A", "F-2A", "GB-A-12", "GB-A-23"])
    sh.section_cut((px(57), py(-4)), (px(57), py(12)), "3", "S-601", ["F-3A", "P-3A", "COL-3A", "BP-3A", "GB-3-AB", "BR-L1-3-AB-S"])
    sh.drawing_title(215, 1530, "1", "FOUNDATION PLAN", "3/16\" = 1'-0\"")
    sh.north_arrow(1880, 1560)
    sh.scale_bar(1400, 1540, PS, "GRAPHIC SCALE")
    # notes column + schedules (the ingest reads footing rows right of the plan cutoff)
    y = notes_column(sh, "FOUNDATION PLAN NOTES", [
        ("TOP OF FOOTING EL. -3'-0\" AND TOP OF PIER EL. -0'-6\" U.N.O. FINISH FLOOR (SLAB ON GRADE) EL. 0'-0\".",
         ["LEVEL:L1"]),
        ("SLAB ON GRADE: 5\" NORMAL WEIGHT CONCRETE W/ #4 @ 16\" O.C. EACH WAY OVER 15 MIL VAPOR RETARDER. NOT PART OF "
         "THE STRUCTURAL SYSTEM.", []),
        ("ALL FOUNDATION CONCRETE F'C = 4,000 PSI; REINFORCING ASTM A615 GR 60. SEE SPEC 03 30 00 AND 03 20 00.",
         ["MAT:CONC-4000", "MAT:REBAR-A615"]),
        ("CENTER FOOTINGS AND PIERS ON COLUMN GRID INTERSECTIONS U.N.O.", []),
        ("BASE PLATES AND ANCHOR RODS PER COLUMN SCHEDULE S-401 AND DETAILS 4/S-502 THRU 7/S-502.", ["MAT:F1554"]),
        ("GB1 = PERIMETER WALL GRADE BEAM. GB2 = BRACED FRAME TIE GRADE BEAM. SEE GRADE BEAM SCHEDULE.", []),
    ])
    y += 14
    sh.text(NOTES_X0, y, "FOOTING SCHEDULE", 11, BOLD)
    y += 18
    hdr = ["MARK", "LENGTH", "WIDTH", "THICK", "REINFORCING"]
    xs = [NOTES_X0, NOTES_X0 + 38, NOTES_X0 + 86, NOTES_X0 + 134, NOTES_X0 + 182]
    for x, h in zip(xs, hdr):
        sh.text(x, y, h, 7, BOLD)
    sh.line((NOTES_X0, y + 4), (NOTES_X1, y + 4), width=0.6)
    marks: dict[str, list] = {}
    for f in ds.by_type["footing"]:
        marks.setdefault(ftg_mark(f["B_ft"]), []).append(f)
    for mk in sorted(marks, key=lambda m: float(m[1:])):
        f = marks[mk][0]
        y += 15
        vals = [mk, ftin_sp(f["B_ft"]), ftin_sp(f["B_ft"]), ftin_sp(f["h_in"] / 12), f["bars"] + " B"]
        boxes = [sh.text(x, y, v, 7.5, BOLD if i == 0 else HELV) for i, (x, v) in enumerate(zip(xs, vals))]
        sh.line((NOTES_X0, y + 4), (NOTES_X1, y + 4), width=0.3)
        sh.occ([e["id"] for e in marks[mk]], "schedule_row", " ".join(vals), bb(*boxes))
    y += 34
    sh.text(NOTES_X0, y, "GRADE BEAM SCHEDULE", 11, BOLD)
    y += 18
    xs = [NOTES_X0, NOTES_X0 + 34, NOTES_X0 + 68, NOTES_X0 + 104, NOTES_X0 + 236]
    for x, h in zip(xs, ["MARK", "WIDTH", "DEPTH", "TOP & BOTTOM", "REMARKS"]):
        sh.text(x, y, h, 7, BOLD)
    sh.line((NOTES_X0, y + 4), (NOTES_X1, y + 4), width=0.6)
    gbs: dict[str, list] = {}
    for g in ds.by_type["grade_beam"]:
        gbs.setdefault(gb_mark(g), []).append(g)
    for mk in sorted(gbs):
        g = gbs[mk][0]
        y += 15
        vals = [mk, f"{g['b_in']}\"", f"{g['h_in']}\"", "(3) #6 T&B" + (" + " + g["tie_bars"].replace(" cont.", " CONT") if g["tie_bars"] else ""),
                "TIE" if g["tie_bars"] else "WALL"]
        boxes = [sh.text(x, y, v, 7.5, BOLD if i == 0 else HELV) for i, (x, v) in enumerate(zip(xs, vals))]
        sh.line((NOTES_X0, y + 4), (NOTES_X1, y + 4), width=0.3)
        sh.occ([e["id"] for e in gbs[mk]], "schedule_row", " ".join(vals), bb(*boxes))
    y += 12
    sh.para(NOTES_X0, y + 8, "#4 STIRRUPS @ 6\" O.C. FULL LENGTH, 2 LEGS. HOOK TOP AND BOTTOM BARS INTO FOOTINGS.",
            NOTES_X1 - NOTES_X0, 7.5)


def _gb_end(g: dict, end: str) -> str:
    # GB-A-12 -> columns 1A / 2A ; GB-3-AB -> 3A / 3B
    _, line, seg = g["id"].split("-")
    a, b = seg[0], seg[1]
    if line.isalpha():
        return (a if end == "a" else b) + line
    return line + (a if end == "a" else b)


# =========================================================================== S-20x framing
def sheet_framing(ds: DrawingSet, level: str, number: str):
    title = f"{LV_NAME[level]} FRAMING PLAN"
    sh = Sheet(ds, number, title, "plan", level, "3/16\" = 1'-0\"")
    sh.frame()
    plan_grid(sh)
    colpos = {(round(c["x"], 3), round(c["y"], 3)): cid for cid, c in ds.cols.items()}
    mems = ds.members(level)
    sfrs_x = []
    for m in mems:
        (x1, y1, _), (x2, y2, _) = m["p1"], m["p2"]
        a, b = (px(x1), py(y1)), (px(x2), py(y2))
        horiz = abs(a[1] - b[1]) < 1e-6
        ga = 10.0 if (round(x1, 3), round(y1, 3)) in colpos else 4.0
        gb_ = 10.0 if (round(x2, 3), round(y2, 3)) in colpos else 4.0
        L = math.dist(a, b)
        ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        sa, sb = (a[0] + ux * ga, a[1] + uy * ga), (b[0] - ux * gb_, b[1] - uy * gb_)
        sh.line(sa, sb, width=3.0 if m["sfrs"] else 1.9)
        tag = member_tag(m)
        mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        if horiz:
            box = sh.text(mid[0], mid[1] - 4.5, tag, 9, anchor="c")
        else:
            box = sh.text(mid[0] - 4.5 - (-DESC) * 9, mid[1], tag, 9, rotate=90, anchor="c")
        sh.occ(m["id"], "plan_tag", tag, box)
        if "smf_beam" in m["roles"]:
            fb = sh.text(mid[0], mid[1] + 16, "*SMF", 8, BOLD, anchor="c")
            sh.occ(f"FRAME:{m['frame']}", "plan_tag", "*SMF", fb)
        if "scbf_beam" in m["roles"]:
            fb = sh.text(mid[0] + 26, mid[1], "*SCBF", 8, BOLD, rotate=90, anchor="c")
            sh.occ(f"FRAME:{m['frame']}", "plan_tag", "*SCBF", fb)
            sfrs_x.append(m)
        # end symbols: moment flags / drag diamonds at the connection instance
        for c in ds.conn_by_member.get(m["id"], []):
            t = dtype(c)
            p, s = ((sa, (-ux, -uy)) if c["end"] == "i" else (sb, (ux, uy)))
            q = (p[0] - s[0] * 6, p[1] - s[1] * 6)
            if t == "MC-1":
                box = sh.moment_flag(q, s)
                sh.occ(c["id"], "plan_tag", "", box, symbol="moment_connection")
            elif t.startswith("DC"):
                box = sh.drag_diamond(q)
                sh.occ(c["id"], "plan_tag", "", box, symbol="drag_connection")
    # braced frame below: heavy dashed line offset from line 3 girders in braced bays
    for m in sfrs_x:
        (x1, y1, _), (x2, y2, _) = m["p1"], m["p2"]
        X = px(x1) + 9
        sh.line((X, py(y1) - 14), (X, py(y2) + 14), width=1.2, dashes="[10 4] 0", color=GREY)
    # columns
    for cid, col in ds.cols.items():
        sh.column_i((px(col["x"]), py(col["y"])), "smf_column" in col["roles"])
    # detail callouts: first instance of each connection type at this level
    seen = {}
    for m in mems:
        for c in ds.conn_by_member.get(m["id"], []):
            seen.setdefault(dtype(c), (m, c))
    for t, (m, c) in sorted(seen.items(), key=lambda kv: kv[0]):
        if t not in DETAIL_AT:
            continue
        (x1, y1, _), (x2, y2, _) = m["p1"], m["p2"]
        a, b = (px(x1), py(y1)), (px(x2), py(y2))
        L = math.dist(a, b)
        ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        f = 0.12 if c["end"] == "i" else 0.88
        tgt = (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)
        if abs(uy) < 1e-6:   # horizontal member: bubble above-inside
            at = (tgt[0] + (40 if c["end"] == "i" else -40), tgt[1] - 46)
        else:
            at = (tgt[0] + 46, tgt[1] + (-40 if c["end"] == "i" else 40))
        num, s = DETAIL_AT[t]
        sh.callout(tgt, at, num, s, [c["id"]])
        ds.rel(c["id"], f"DET:{num}/{s}", "detailed-by")
    if level == "L2":
        sh.section_cut((px(20), py(14)), (px(20), py(6)), "2", "S-601", ["B-L2-12-AB1", "DK-L2"])
        # revision 1 cloud around the mech-bay girder tag (plan check response)
        sh.rev_cloud(px(90) - 26, py(22) - 12, px(90) + 4, py(8) + 12)
        sh.delta((px(90) - 34, py(22) - 18), "1")
    if level == "RF":
        x0, y0, x1, y1 = px(60), py(30), px(90), py(0)
        sh.rect(x0 + 6, y0 + 6, x1 - 6, y1 - 6, width=0.7, dashes="[3 3] 0", color=GREY)
        sh.text(x0 + 12, y0 + 22, "MECHANICAL (RTU) ZONE - 90 PSF DEAD", 7, BOLD, GREY)
    sh.drawing_title(215, 1530, "1", title, "3/16\" = 1'-0\"")
    sh.north_arrow(1880, 1560)
    sh.scale_bar(1400, 1540, PS, "GRAPHIC SCALE")
    deck = ds.el[f"DK-{level}"]
    z = LV_Z[level]
    if level == "RF":
        deck_note = ("ROOF DECK: 1-1/2\" 20 GA TYPE B STEEL ROOF DECK, ATTACH PER SPEC 05 31 00. SLOPE TO DRAIN BY "
                     "TAPERED INSULATION (ARCH).", [deck["id"], "MAT:DECK-3VLI20"])
    else:
        deck_note = ("FLOOR DECK: 3\" 20 GA COMPOSITE STEEL DECK WITH 3-1/4\" LIGHTWEIGHT CONCRETE TOPPING "
                     "(F'C = 3,000 PSI), 6-1/4\" TOTAL, W/ 6X6-W2.9XW2.9 WWF. SPAN DECK PERPENDICULAR TO INFILL BEAMS.",
                     [deck["id"], "MAT:DECK-3VLI20", "MAT:CONC-LW3000"])
    y = notes_column(sh, "FRAMING PLAN NOTES", [
        (f"TOP OF STEEL (T.O.S.) EL. {ftin(z)} U.N.O. SEE ARCHITECTURAL DRAWINGS FOR SLAB EDGES AND OPENINGS.",
         [f"LEVEL:{level}"]),
        deck_note,
        ("ALL W SHAPES ASTM A992 U.N.O. BRACES ASTM A500 GR C.", ["MAT:A992"]),
        ("(n) INDICATES TOTAL NUMBER OF 3/4\" DIA HEADED SHEAR STUDS, EQUALLY SPACED. c=X\" INDICATES CAMBER AT MIDSPAN.",
         ["MAT:STUD"]),
        ("BEAM END CONNECTIONS ARE SINGLE-PLATE SHEAR TABS ST-2 THRU ST-7 SELECTED FOR THE END REACTION, SEE 2/S-501 "
         "THRU 7/S-501, U.N.O. ON PLAN.", [f"DETAIL:ST-{n}" for n in range(2, 8)]),
        ("* INDICATES MEMBER OF THE SEISMIC FORCE-RESISTING SYSTEM. SEE S-001 SPECIAL INSPECTIONS.", []),
        ("SMF MOMENT CONNECTIONS MC-1 (RBS) PER 1/S-501; DRAG CONNECTIONS PER 8/S-501 THRU 10/S-501; SEE FRAME "
         "ELEVATIONS ON S-301.", ["DETAIL:MC-1", "DETAIL:DC-1"]),
        ("CENTER BEAMS ON GRID LINES; INFILL BEAMS EQUALLY SPACED BETWEEN GRIDS U.N.O.", []),
    ])
    legend(sh, y + 18, [
        ("moment", "MOMENT CONNECTION (MC-1, RBS). SEE 1/S-501."),
        ("drag", "DRAG / COLLECTOR CONNECTION (DC). SEE 8/S-501."),
        ("column", "STEEL COLUMN BELOW / ABOVE. SEE COLUMN SCHEDULE S-401."),
        ("brace", "SPECIAL CONCENTRICALLY BRACED FRAME BELOW. SEE S-301."),
        ("callout", "DETAIL CALLOUT: DETAIL NUMBER OVER SHEET NUMBER."),
        ("section", "SECTION CUT. SEE S-601."),
        ("text", ("W##X## (n) c=#\"", "MEMBER SIZE, (n) TOTAL SHEAR STUDS, c= MIDSPAN CAMBER. * = SFRS MEMBER.")),
        ("cloud", "REVISION CLOUD WITH DELTA (REVISION 1)."),
    ])


# =========================================================================== S-301 elevations
ES = 9.0   # 1/8" = 1'-0"


def elevation(ds: DrawingSet, sh: Sheet, line: str, axis: str, ox: float, base: float, num: str):
    grids = GX if axis == "x" else GY
    hx = lambda u: ox + u * ES          # noqa: E731
    vz = lambda z: base - z * ES        # noqa: E731
    u0, u1 = grids[0][1], grids[-1][1]
    # grid lines + bubbles (bottom)
    for gl, u in grids:
        X = hx(u)
        sh.line((X, vz(44)), (X, vz(0) + 45), width=0.8, dashes="[22 5 4 5] 0", color=GREY)
        sh.bubble((X, vz(0) + 62), gl, f"GRID:{gl}")
    # level lines
    for lv, z in [("L1", 0.0)] + [(k, zz) for k, _, zz in LEVELS]:
        Y = vz(z)
        sh.line((hx(u0) - 120, Y), (hx(u1) + 30, Y), width=0.5, dashes="[12 3] 0" if lv != "L1" else None)
        sh.poly([(hx(u0) - 120, Y), (hx(u0) - 112, Y - 8), (hx(u0) - 104, Y)], width=0.5, fill=BLACK)
        b1 = sh.text(hx(u0) - 120, Y - 12, LV_NAME[lv], 8.5, BOLD)
        b2 = sh.text(hx(u0) - 120, Y + 11, f"EL. {ftin(z)}", 7.5)
        sh.occ(f"LEVEL:{lv}", "elevation_tag", f"{LV_NAME[lv]} EL. {ftin(z)}", bb(b1, b2))
    # foundations (dashed), grade line
    sh.line((hx(u0) - 40, vz(0) + 3), (hx(u1) + 40, vz(0) + 3), width=1.0)
    for cid, col in ds.cols.items():
        if (axis == "x" and cid[-1] == line) or (axis == "y" and cid[:-1] == line):
            u = col["x"] if axis == "x" else col["y"]
            f = ds.el[f"F-{cid}"]
            hb = f["B_ft"] / 2 * ES
            sh.rect(hx(u) - hb, vz(-3), hx(u) + hb, vz(-4.5), width=0.6, dashes="[4 2] 0", color=GREY)
            sh.rect(hx(u) - 10, vz(-0.5), hx(u) + 10, vz(-3), width=0.6, dashes="[4 2] 0", color=GREY)
    # members on this line
    mems = [e for e in ds.exp["elements"] if e["type"] in ("beam", "girder") and e["line"] == line
            and ((axis == "x" and e["kind"] == "beam") or (axis == "y" and e["kind"] == "girder"))]
    k = 0 if axis == "x" else 1
    colu = {cid: (col["x"] if axis == "x" else col["y"]) for cid, col in ds.cols.items()
            if (axis == "x" and cid[-1] == line) or (axis == "y" and cid[:-1] == line)}
    for m in mems:
        z = LV_Z[m["level"]]
        a, b = hx(m["p1"][k]), hx(m["p2"][k])
        Y = vz(z)
        sh.line((a + 9, Y), (b - 9, Y), width=3.0 if m["sfrs"] else 1.6, color=BLACK if m["sfrs"] else GREY)
        tag = member_tag(m)
        box = sh.text((a + b) / 2, Y - 5, tag, 8.5, anchor="c")
        sh.occ(m["id"], "elevation_tag", tag, box)
        for c in ds.conn_by_member.get(m["id"], []):
            t = dtype(c)
            if c["end"] == "i":
                p, s = (a + 15, Y), (-1, 0)
            else:
                p, s = (b - 15, Y), (1, 0)
            if t == "MC-1":
                bx_ = sh.moment_flag(p, s)
                # RBS dogbone marks
                rx = p[0] - s[0] * 20
                for dy in (-2.2, 2.2):
                    sh.line((rx - 9, Y + dy * 1.6), (rx + 9, Y + dy * 1.6), width=0.4)
                sh.occ(c["id"], "elevation_tag", "", bx_, symbol="moment_connection")
            elif t.startswith("DC"):
                bx_ = sh.drag_diamond(p)
                sh.occ(c["id"], "elevation_tag", "", bx_, symbol="drag_connection")
    # columns
    braced_left = {}   # column -> side for tag (outside the braced bay)
    if axis == "y":
        for e in ds.by_type.get("brace", []):
            bay = e["id"].split("-")[3]
            braced_left[f"{line}{bay[0]}"] = "l"
            braced_left[f"{line}{bay[1]}"] = "r"
    for cid, u in colu.items():
        col = ds.cols[cid]
        X = hx(u)
        sh.line((X, vz(0)), (X, vz(40) - 4), width=3.0 if col["sfrs"] else 1.6, color=BLACK if col["sfrs"] else GREY)
        sh.rect(X - 9, vz(0) - 2, X + 9, vz(0), width=0.5, fill=BLACK)
        tag = ("*" if col["sfrs"] else "") + col["size"]
        side = braced_left.get(cid, "l")
        zs = [0.0] + [zz for _, _, zz in LEVELS]
        for z0, z1 in zip(zs, zs[1:]):
            ym = vz((z0 + z1) / 2)
            xb = X - 5 + DESC * 8.5 if side == "l" else X + 5 + ASC * 8.5
            box = sh.text(xb, ym, tag, 8.5, rotate=90, anchor="c")
            sh.occ(col["id"], "elevation_tag", tag, box)
    # braces
    gusset_done = False
    for e in ds.by_type.get("brace", []):
        if axis != "y" or e["frame"] != f"SCBF-{line}":
            continue
        a, b = (hx(e["p1"][1]), vz(e["p1"][2])), (hx(e["p2"][1]), vz(e["p2"][2]))
        sh.line(a, b, width=2.6)
        tag = "*" + e["size"]
        t_ = 0.62
        mp = (a[0] + (b[0] - a[0]) * t_, a[1] + (b[1] - a[1]) * t_)
        if b[0] > a[0]:
            box = sh.text(mp[0] - 6, mp[1] + 3, tag, 8, anchor="r")
        else:
            box = sh.text(mp[0] + 6, mp[1] + 3, tag, 8)
        sh.occ(e["id"], "elevation_tag", tag, box)
        # gusset plates
        for end, p in (("i", a), ("j", b)):
            sh.poly([(p[0] - 8, p[1]), (p[0] + 8, p[1]), (p[0], p[1] + (-12 if end == "i" else 12))], width=0.6)
        if not gusset_done:
            gusset_done = True
            for end, p in (("i", a), ("j", b)):
                cx = next(c for c in ds.conn_by_member[e["id"]] if c["end"] == end)
                num_, s_ = DETAIL_AT[dtype(cx)]
                at = (p[0] + 72, p[1] - 14) if end == "i" else (p[0] + 72, p[1] - 40)
                sh.callout((p[0] - 2, p[1] - 6 if end == "i" else p[1] + 6), at, num_, s_, [cx["id"]])
                ds.rel(cx["id"], f"DET:{num_}/{s_}", "detailed-by")
    # moment connection + base plate + drag callouts on the frame lines
    if axis == "x":
        smf = [m for m in mems if "smf_beam" in m["roles"] and m["level"] == "L3"]
        if smf:
            m = smf[0]
            c = next(c for c in ds.conn_by_member[m["id"]] if c["end"] == "i")
            p = (hx(m["p1"][0]) + 22, vz(LV_Z["L3"]))
            sh.callout(p, (p[0] + 50, p[1] - 58), *DETAIL_AT["MC-1"], [c["id"]])
            ds.rel(c["id"], "DET:{}/{}".format(*DETAIL_AT["MC-1"]), "detailed-by")
        coll = [m for m in mems if "collector" in m["roles"] and m["level"] == "L2"]
        for m in coll[:1]:
            c = next((c for c in ds.conn_by_member[m["id"]] if dtype(c).startswith("DC")), None)
            if c:
                end_x = hx(m["p2"][0]) - 15 if c["end"] == "j" else hx(m["p1"][0]) + 15
                p = (end_x, vz(LV_Z["L2"]))
                sh.callout(p, (p[0] - 54, p[1] - 56), *DETAIL_AT[dtype(c)], [c["id"]])
                ds.rel(c["id"], "DET:{}/{}".format(*DETAIL_AT[dtype(c)]), "detailed-by")
    frame_cols = [cid for cid in colu if ds.cols[cid]["sfrs"]]
    if frame_cols:
        cid = frame_cols[0]
        bp = ds.el[f"BP-{cid}"]
        t = dtype(bp)
        p = (hx(colu[cid]) + 9, vz(0) - 1)
        at = (p[0] + 48, p[1] - 44) if axis == "x" else (p[0] + 110, p[1] + 28)
        sh.callout(p, at, *DETAIL_AT[t], [bp["id"]])
        ds.rel(bp["id"], "DET:{}/{}".format(*DETAIL_AT[t]), "detailed-by")
    frame_id = f"FRAME:SMF-{line}" if axis == "x" else f"FRAME:SCBF-{line}"
    ttl = (f"SPECIAL MOMENT FRAME - LINE {line}" if axis == "x" else f"SPECIAL CONCENTRICALLY BRACED FRAME - LINE {line}")
    ty = vz(0) + 108
    sh.drawing_title(hx(u0) - 120, ty, num, ttl, "1/8\" = 1'-0\"", width=560)
    sh.occ(frame_id, "elevation_tag", ttl, [r2(hx(u0) - 74), r2(ty + 2 - ASC * 15), r2(hx(u0) - 74 + tlen(ttl, 15, BOLD)), r2(ty + 2 - DESC * 15)])


def sheet_elevations(ds: DrawingSet):
    sh = Sheet(ds, "S-301", "MOMENT FRAME ELEVATIONS AND BRACED FRAME ELEVATION", "elevation", None, "1/8\" = 1'-0\"")
    sh.frame()
    elevation(ds, sh, "A", "x", 250, 442, "1")
    elevation(ds, sh, "D", "x", 250, 948, "2")
    elevation(ds, sh, "3", "y", 250, 1454, "3")
    notes_column(sh, "FRAME ELEVATION NOTES", [
        ("* INDICATES MEMBER OF THE SEISMIC FORCE-RESISTING SYSTEM (SFRS).", ["FRAME:SMF-A", "FRAME:SMF-D", "FRAME:SCBF-3"]),
        ("SMF BEAM-TO-COLUMN CONNECTIONS ARE MC-1 REDUCED BEAM SECTION (RBS) PER AISC 358 CH. 5, SEE 1/S-501. "
         "PROTECTED ZONE AT EACH RBS: NO ATTACHMENTS.", ["DETAIL:MC-1"]),
        ("SCBF BRACE CONNECTIONS: GUSSET PLATES BG-1 THRU BG-3 PER 1/S-502 THRU 3/S-502, DESIGNED FOR EXPECTED BRACE "
         "TENSION RY FY AG.", ["DETAIL:BG-1", "DETAIL:BG-2", "DETAIL:BG-3"]),
        ("COLLECTOR (DRAG) BEAMS IN BAYS 1-2 AND 4-5 OF LINES A AND D AND BAY B-C OF LINE 3: DRAG CONNECTIONS DC-1 THRU "
         "DC-3 PER 8/S-501 THRU 10/S-501.", ["DETAIL:DC-1", "DETAIL:DC-2", "DETAIL:DC-3"]),
        ("SMF COLUMN BASES: FIXED BASE PLATE BP-3 (6/S-502). SCBF COLUMN BASES: BP-4 WITH SHEAR LUG (7/S-502).",
         ["DETAIL:BP-3", "DETAIL:BP-4"]),
        ("HSS BRACES ASTM A500 GR C; W SHAPES ASTM A992.", ["MAT:A500C", "MAT:A992"]),
        ("FOUNDATIONS SHOWN DASHED FOR REFERENCE; SEE S-101.", []),
    ])


# =========================================================================== S-401 schedules
def sheet_schedules(ds: DrawingSet):
    sh = Sheet(ds, "S-401", "COLUMN AND FOUNDATION SCHEDULES", "schedule", None, "NONE")
    sh.frame()
    cols = sorted(ds.cols.values(), key=lambda c: (c["grid"].split("/")[0], c["grid"].split("/")[1]))
    x0, y0 = 70.0, 110.0
    lab_w, cw = 170.0, (DRAW_X1 + 290 - 70 - 170) / 20
    sh.text(x0, y0 - 22, "COLUMN SCHEDULE", 14, BOLD)
    sh.line((x0, y0 - 18), (x0 + tlen("COLUMN SCHEDULE", 14, BOLD), y0 - 18), width=1.0)
    rows = ["COLUMN LINE", "ROOF  EL. 40'-0\"", "L3 - ROOF", "LEVEL 3  EL. 27'-0\"", "L2 - L3", "LEVEL 2  EL. 14'-0\"",
            "L1 - L2", "LEVEL 1  EL. 0'-0\"", "BASE PLATE", "PIER", "FOOTING", "SYSTEM"]
    rh = 30.0
    xr = x0 + lab_w + cw * len(cols)
    for i, r in enumerate(rows):
        ry = y0 + i * rh
        lvl_row = "EL." in r
        sh.text(x0 + 4, ry + 19, r, 8.5 if not lvl_row else 8, BOLD if i == 0 or lvl_row else HELV)
        sh.line((x0, ry), (xr, ry), width=0.8 if lvl_row or i in (0, 1) else 0.3)
    yend = y0 + len(rows) * rh
    sh.line((x0, yend), (xr, yend), width=1.0)
    sh.line((x0, y0), (x0, yend), width=1.0)
    for j, c in enumerate(cols):
        cx = x0 + lab_w + j * cw
        sh.line((cx, y0), (cx, yend), width=0.3)
        mid = cx + cw / 2
        sh.text(mid, y0 + 19, c["grid"], 9, BOLD, anchor="c")
        tag = ("*" if c["sfrs"] else "") + c["size"]
        cid = c["id"][4:]
        for i in (2, 4, 6):
            box = sh.text(mid, y0 + i * rh + 19, tag, 8.5, anchor="c")
            sh.occ(c["id"], "schedule_row", tag, box)
        # tier bars between level rows
        sh.line((mid, y0 + 2 * rh + 24), (mid, y0 + 3 * rh + 6), width=1.4)
        sh.line((mid, y0 + 4 * rh + 24), (mid, y0 + 5 * rh + 6), width=1.4)
        sh.line((mid, y0 + 6 * rh + 24), (mid, y0 + 7 * rh + 6), width=1.4)
        bp = ds.el[f"BP-{cid}"]
        box = sh.text(mid, y0 + 8 * rh + 19, bp["conn_type"], 8.5, anchor="c")
        sh.occ(bp["id"], "schedule_row", bp["conn_type"], box)
        p = ds.el[f"P-{cid}"]
        box = sh.text(mid, y0 + 9 * rh + 19, pier_mark(p["pier_type"]), 8.5, anchor="c")
        sh.occ(p["id"], "schedule_row", pier_mark(p["pier_type"]), box)
        f = ds.el[f"F-{cid}"]
        box = sh.text(mid, y0 + 10 * rh + 19, ftg_mark(f["B_ft"]), 8.5, anchor="c")
        sh.occ(f["id"], "schedule_row", ftg_mark(f["B_ft"]), box)
        sysl = ", ".join(x.replace("SCBF-", "SCBF ").replace("SMF-", "SMF ") for x in c["frames"]) or "GRAVITY"
        box = sh.text(mid, y0 + 11 * rh + 19, sysl, 7.5, anchor="c")
        if c["frames"]:
            sh.occ([f"FRAME:{x}" for x in c["frames"]], "schedule_row", sysl, box)
    sh.line((xr, y0), (xr, yend), width=1.0)
    y = yend + 22
    for t in ["COLUMNS ARE SINGLE-TIER (NO SPLICE) FROM BASE PLATE TO ROOF. * = SFRS MEMBER, SEE S-001.",
              "SMF COLUMNS: CONTINUITY PLATES AND DOUBLER PLATES PER 1/S-501. ALL COLUMNS ASTM A992."]:
        sh.text(x0, y, t, 8)
        y += 13
    sh.occ("MAT:A992", "note", "SMF COLUMNS: CONTINUITY PLATES AND DOUBLER PLATES PER 1/S-501. ALL COLUMNS ASTM A992.",
           [x0, y - 13 - ASC * 8, x0 + tlen("SMF COLUMNS: CONTINUITY PLATES AND DOUBLER PLATES PER 1/S-501. ALL COLUMNS ASTM A992.", 8), y - 13 - DESC * 8])

    def sched(x, y, title, head, widths, rows_, refs_):
        sh.text(x, y, title, 12, BOLD)
        y += 20
        cx = [x]
        for w_ in widths:
            cx.append(cx[-1] + w_)
        sh.rect(cx[0], y - 12, cx[-1], y + 5, width=0.6, fill=(0.88, 0.88, 0.88))
        for i, h_ in enumerate(head):
            sh.text(cx[i] + 4, y, h_, 7.5, BOLD)
        top = y - 12
        for row, refs in zip(rows_, refs_):
            y += 17
            boxes = [sh.text(cx[i] + 4, y, v, 8, BOLD if i == 0 else HELV) for i, v in enumerate(row)]
            sh.line((cx[0], y + 5), (cx[-1], y + 5), width=0.3)
            sh.occ(refs, "schedule_row", " ".join(row), bb(*boxes))
        for c_ in cx:
            sh.line((c_, top), (c_, y + 5), width=0.4)
        sh.line((cx[0], y + 5), (cx[-1], y + 5), width=0.8)
        return y + 30

    ys = yend + 80
    # pier schedule
    piers: dict[str, list] = {}
    for p in ds.by_type["pier"]:
        piers.setdefault(p["pier_type"], []).append(p)
    rows_, refs_ = [], []
    for t in sorted(piers):
        p = piers[t][0]
        rows_.append([pier_mark(t), f"{p['b_in']:.0f}\" x {p['b_in']:.0f}\"", p["bars"].replace("-", " "), "#4 TIES @ 12\" O.C.",
                      "-0'-6\" / -3'-0\"", "SFRS" if t == "P-2" else "GRAVITY"])
        refs_.append([f"TYPE:{t}"] + [x["id"] for x in piers[t]])
    sched(x0, ys, "PIER SCHEDULE", ["MARK", "SIZE", "VERT. BARS", "TIES", "TOP / BOTTOM", "USE"],
          [50, 90, 90, 120, 110, 80], rows_, refs_)
    # grade beam schedule (repeated from S-101 with the segments it covers)
    gbs: dict[str, list] = {}
    for g in ds.by_type["grade_beam"]:
        gbs.setdefault(gb_mark(g), []).append(g)
    rows_, refs_ = [], []
    for mk in sorted(gbs):
        g = gbs[mk][0]
        lines = sorted({x["line"] for x in gbs[mk]})
        rows_.append([mk, f"{g['b_in']}\" x {g['h_in']}\"", "(3) #6 T&B" + (" + (4) #8" if g["tie_bars"] else ""),
                      "#4 @ 6\"", "LINES " + ", ".join(lines)])
        refs_.append([x["id"] for x in gbs[mk]])
    sched(x0 + 620, ys, "GRADE BEAM SCHEDULE", ["MARK", "SIZE", "LONG. BARS", "STIRRUPS", "LOCATION"],
          [50, 80, 130, 70, 120], rows_, refs_)
    # base plate schedule
    rows_, refs_ = [], []
    bps: dict[str, list] = {}
    for b in ds.by_type["connection"]:
        if b["id"].startswith("BP-"):
            bps.setdefault(b["conn_type"].rstrip("*"), []).append(b)
    for t in sorted(k for k in ds.types if k.startswith("DETAIL:BP-")):
        tt = t.split(":")[1]
        inst = bps.get(tt, [])
        from .gravity import BASE_PLATES
        v = BASE_PLATES[tt]
        num, s = DETAIL_AT[tt]
        rows_.append([tt, f"PL{frac_in(v['t'])}x{v['B']:.0f}x{v['N']:.0f}", v["rods"].replace("\"", "\""), v["use"].upper(),
                      f"{num}/{s}", str(len(inst))])
        refs_.append([t] + [x["id"] for x in inst])
    sched(x0 + 1220, ys, "BASE PLATE SCHEDULE", ["TYPE", "PLATE", "ANCHOR RODS", "USE", "DETAIL", "QTY"],
          [44, 92, 190, 120, 50, 36], rows_, refs_)


# =========================================================================== S-501 / S-502 details
def _detail_frame(sh: Sheet, box, num, title, scale):
    x0, y0, x1, y1 = box
    sh.rect(x0, y0, x1, y1, width=0.4, color=LIGHT)
    ty = y1 - 34
    sh.circle((x0 + 26, ty), 18, width=1.0)
    sh.line((x0 + 8, ty), (x0 + 44, ty), width=0.6)
    sh.text(x0 + 26, ty - 4, num, 11, BOLD, anchor="c")
    sh.text(x0 + 26, ty + 11, sh.number, 6.5, anchor="c")
    tb = sh.text(x0 + 52, ty - 2, title, 12, BOLD)
    sh.line((x0 + 52, ty + 3), (x1 - 14, ty + 3), width=1.4)
    sh.text(x0 + 52, ty + 15, f"SCALE: {scale}", 7.5)
    return tb


def _leader_note(sh: Sheet, target, at, txt, size=7.5, refs=(), how="detail"):
    sh.line(target, (at[0] - 3, at[1] - 3), width=0.4)
    sh.circle(target, 1.4, width=0.4, fill=BLACK)
    box = sh.text(at[0], at[1], txt, size)
    if refs:
        sh.occ(list(refs), how, txt, box)
    return box


def _bolts(sh: Sheet, x, y0, n, pitch=27.0, r=3.4):
    for k in range(n):
        cy = y0 + k * pitch
        sh.circle((x, cy), r, width=0.6)
        sh.line((x - r - 2, cy), (x + r + 2, cy), width=0.3)
        sh.line((x, cy - r - 2), (x, cy + r + 2), width=0.3)


def _weld(sh: Sheet, at, txt, target, refs=("MAT:E70XX",)):
    sh.line(target, at, width=0.4)
    sh.line(at, (at[0] + 40, at[1]), width=0.4)
    sh.poly([(at[0] + 12, at[1]), (at[0] + 20, at[1]), (at[0] + 12, at[1] - 7)], width=0.5)
    box = sh.text(at[0] + 44, at[1] + 3, txt, 7)
    sh.occ(list(refs), "detail", txt, box)


def det_shear_tab(ds, sh, box, n, t):
    x0, y0, x1, y1 = box
    k = 9.0                          # 1-1/2" = 1'-0": 9 pt per inch
    cx, top = x0 + 120, y0 + 60
    depth = max(12, 3 * n + 6) * k
    # supporting girder web / column flange (vertical band)
    sh.rect(cx - 10, top - 20, cx, top + depth + 20, width=1.4)
    sh.line((cx - 10, top - 20), (cx - 10, top + depth + 20), width=1.4)
    # beam in elevation
    bx0, bx1 = cx + 6, x1 - 50
    sh.line((bx0, top), (bx1, top), width=1.8)
    sh.line((bx0, top + 6), (bx1, top + 6), width=0.6)
    sh.line((bx0, top + depth), (bx1, top + depth), width=1.8)
    sh.line((bx0, top + depth - 6), (bx1, top + depth - 6), width=0.6)
    sh.line((bx0, top), (bx0, top + depth), width=0.6, dashes="[3 2] 0")
    # plate
    ph = 3 * n * k
    py0 = top + (depth - ph) / 2
    sh.rect(cx, py0, cx + 4.5 * k, py0 + ph, width=1.1)
    _bolts(sh, cx + 3 * k, py0 + 1.5 * k, n, 3 * k)
    plate = t.get("plate", "")
    _leader_note(sh, (cx + 4.2 * k, py0 + 6), (cx + 80, top - 22), f"{plate} (ASTM A36)", refs=["MAT:A36"])
    _leader_note(sh, (cx + 3 * k + 3, py0 + ph - 1.5 * k), (cx + 80, top + depth + 30),
                 f"({n}) 3/4\" DIA A325-N BOLTS, SSL, SNUG TIGHT", refs=["MAT:F3125-A325"])
    _weld(sh, (cx + 30, top + depth + 58), "1/4\" E70XX FILLET BOTH SIDES", (cx + 1, py0 + ph - 8))
    cap = t.get("capacity_k")
    box_c = sh.text(x0 + 20, y1 - 74, f"ØRn = {cap:g} KIPS (LRFD), {n} BOLTS, e = 3\"", 8.5, BOLD)
    sh.occ(t["id"], "detail", f"ØRn = {cap:g} KIPS (LRFD), {n} BOLTS, e = 3\"", box_c)
    sh.text(x0 + 20, y1 - 88, "USE WHERE END REACTION <= ØRn; BEAM DEPTH PERMITTING N BOLTS AT 3\" PITCH.", 7)


def det_rbs(ds, sh, box, t):
    x0, y0, x1, y1 = box
    cx, top, bot = x0 + 90, y0 + 70, y0 + 330
    sh.rect(cx - 16, y0 + 30, cx + 16, y1 - 120, width=1.6)      # column
    sh.line((cx - 16, y0 + 30), (cx - 16, y1 - 120), width=0.6)
    for yy in (top, bot):                                        # continuity plates
        sh.line((cx - 16, yy), (cx + 16, yy), width=1.2)
    bx1 = x1 - 30
    sh.line((cx + 16, top), (bx1, top), width=1.8)
    sh.line((cx + 16, bot), (bx1, bot), width=1.8)
    # RBS cut: arcs in both flanges (shown in elevation as the reduced flange line)
    a, b = cx + 16 + 50, cx + 16 + 50 + 140
    sh.page.draw_curve((a, top), ((a + b) / 2, top + 22), (b, top), color=BLACK, width=0.8)
    sh.page.draw_curve((a, bot), ((a + b) / 2, bot - 22), (b, bot), color=BLACK, width=0.8)
    sh.line((cx + 16, top - 40), (b + 30, top - 40), width=0.3, dashes="[4 2] 0")
    sh.text(cx + 20, top - 46, "PROTECTED ZONE - NO ATTACHMENTS", 7, BOLD)
    sh.rect(cx + 16, top + 60, cx + 46, bot - 60, width=1.0)    # shear plate
    _bolts(sh, cx + 34, top + 75, 5, 24)
    _weld(sh, (cx + 60, top - 80), "CJP, DEMAND CRITICAL, E70XX, AWS D1.8", (cx + 18, top))
    _leader_note(sh, ((a + b) / 2, top + 11), ((a + b) / 2 + 20, top + 50), "RBS: a = 0.5bf, b = 0.75d, c = 0.2bf")
    _leader_note(sh, (cx + 30, top + 100), (cx + 90, bot + 50), "SHEAR PL + (N) 7/8\" A325-SC BOLTS, PRETENSIONED",
                 refs=["MAT:F3125-A325"])
    _leader_note(sh, (cx, bot), (cx + 60, bot + 80), "CONTINUITY PL 3/4\" BOTH SIDES (A572 GR 50)")
    lim = next((r["values"]["limits"] for r in ds.exp["records"] if r["id"] == "E-TYP:MC-1"), "")
    box_c = sh.text(x0 + 20, y1 - 74, "AISC 358 CH. 5 PREQUALIFIED: " + lim.upper(), 7.5, BOLD)
    sh.occ(t["id"], "detail", "AISC 358 CH. 5 PREQUALIFIED: " + lim.upper(), box_c)


def det_drag(ds, sh, box, t, num):
    x0, y0, x1, y1 = box
    cx, top, bot = x0 + 100, y0 + 110, y0 + 270
    sh.rect(cx - 16, y0 + 40, cx + 16, y1 - 120, width=1.6)
    bx1 = x1 - 40
    sh.line((cx + 20, top), (bx1, top), width=1.8)
    sh.line((cx + 20, bot), (bx1, bot), width=1.8)
    tp = {1: "1/2", 2: "3/4", 3: "1"}[num]
    for yy, s in ((top - 6, -1), (bot + 6, 1)):
        sh.rect(cx + 16, min(yy, yy + s * 8), cx + 140, max(yy, yy + s * 8), width=1.0)
    _bolts(sh, cx + 60, top + 40, 4, 24)
    sh.rect(cx + 16, top + 26, cx + 80, bot - 26, width=0.8)
    _leader_note(sh, (cx + 100, top - 10), (cx + 160, top - 46), f"PL{tp}x8 DRAG PLATE TOP & BOTTOM (A36)", refs=["MAT:A36"])
    _weld(sh, (cx + 40, bot + 70), "5/16\" E70XX FILLET, 3 SIDES", (cx + 17, bot + 8))
    _leader_note(sh, (cx + 60, top + 64), (cx + 160, top + 80), "SHEAR TAB PER TYP. ST, BOLTS PRETENSIONED",
                 refs=["MAT:F3125-A325"])
    cap = t["capacity_k"]
    txt = f"DRAG CAPACITY ØRn = {cap:g} KIPS (INCL. OMEGA0)"
    box_c = sh.text(x0 + 20, y1 - 74, txt, 8.5, BOLD)
    sh.occ(t["id"], "detail", txt, box_c)


def det_gusset(ds, sh, box, t, num):
    x0, y0, x1, y1 = box
    by_ = y0 + 90
    sh.line((x0 + 30, by_), (x1 - 30, by_), width=1.8)
    sh.line((x0 + 30, by_ + 26), (x1 - 30, by_ + 26), width=1.8)
    mx = (x0 + x1) / 2
    w = {1: 70, 2: 85, 3: 100}[num]
    sh.poly([(mx - w, by_ + 26), (mx + w, by_ + 26), (mx + w * 0.55, by_ + 26 + w), (mx - w * 0.55, by_ + 26 + w)], width=1.1)
    for s in (-1, 1):
        a = (mx + s * w * 0.3, by_ + 26 + w * 0.6)
        b = (mx + s * 200, by_ + 330)
        sh.line(a, b, width=1.6)
        sh.line((a[0] + 9, a[1]), (b[0] + 9, b[1]), width=1.6)
    _leader_note(sh, (mx, by_ + 26 + w * 0.5), (mx + w + 20, by_ + 50), f"GUSSET PL{['3/4', '1', '1-1/4'][num - 1]} (A572 GR 50)")
    _leader_note(sh, (mx + 120, by_ + 210), (mx + 130, by_ + 250), "HSS BRACE (ASTM A500 GR C), SLOTTED", refs=["MAT:A500C"])
    _weld(sh, (mx - 190, by_ + 160), "E70XX FILLET, DEMAND CRITICAL", (mx - w * 0.6, by_ + 70))
    sh.text(mx - 180, by_ + 300, "2t LINEAR CLEARANCE FOR BRACE BUCKLING", 7)
    cap = t["capacity_k"]
    txt = f"ØRn = {cap:g} KIPS >= EXPECTED BRACE TENSION RY FY AG"
    box_c = sh.text(x0 + 20, y1 - 74, txt, 8.5, BOLD)
    sh.occ(t["id"], "detail", txt, box_c)


def det_base_plate(ds, sh, box, t, name):
    from .gravity import BASE_PLATES
    v = BASE_PLATES[name]
    x0, y0, x1, y1 = box
    k = 7.0
    cx, cy = (x0 + x1) / 2 - 40, y0 + 190
    hb, hn = v["B"] / 2 * k, v["N"] / 2 * k
    sh.rect(cx - hb, cy - hn, cx + hb, cy + hn, width=1.4)
    sh.column_i((cx, cy), True, hn * 0.55, hb * 0.55, 2.0)
    nrod = 8 if "(8)" in v["rods"] else 4
    pts = [(-1, -1), (1, -1), (1, 1), (-1, 1)] + ([(0, -1), (0, 1), (-1, 0), (1, 0)] if nrod == 8 else [])
    for sx, sy in pts:
        sh.circle((cx + sx * (hb - 14), cy + sy * (hn - 14)), 4.5, width=0.8)
    plate = f"PL{frac_in(v['t'])}x{v['B']:.0f}x{v['N']:.0f}"
    _leader_note(sh, (cx + hb - 4, cy - hn + 6), (cx + hb + 20, cy - hn - 14), f"{plate} (ASTM A36)", refs=["MAT:A36"])
    _leader_note(sh, (cx + hb - 14, cy + hn - 14), (cx + hb + 20, cy + hn + 20), v["rods"].upper() + " ANCHOR RODS",
                 refs=["MAT:F1554"])
    sh.text(cx - hb, cy + hn + 50, "1-1/2\" NON-SHRINK GROUT. HEAVY HEX NUTS + PLATE WASHERS.", 7)
    if "lug" in v["rods"]:
        sh.rect(cx - 6, cy + hn + 4, cx + 6, cy + hn + 30, width=1.0, dashes="[3 2] 0")
    txt = f"{name}: {v['use'].upper()}, {plate}"
    box_c = sh.text(x0 + 20, y1 - 74, txt, 8.5, BOLD)
    sh.occ(t["id"], "detail", txt, box_c)


def sheet_details(ds: DrawingSet, number: str, title: str, items: list[str], ncol: int):
    sh = Sheet(ds, number, title, "details", None, "AS NOTED")
    sh.frame()
    nrow = math.ceil(len(items) / ncol)
    gx0, gy0, gx1, gy1 = 60.0, 60.0, DRAW_X1 + 300, H - 70
    cw, rh = (gx1 - gx0) / ncol, (gy1 - gy0) / nrow
    for k, typ in enumerate(items):
        r_, c_ = divmod(k, ncol)
        box = (gx0 + c_ * cw + 8, gy0 + r_ * rh + 8, gx0 + (c_ + 1) * cw - 8, gy0 + (r_ + 1) * rh - 8)
        num, s = DETAIL_AT[typ]
        t = ds.types[f"DETAIL:{typ}"]
        if typ.startswith("ST"):
            ttl, scl = f"SINGLE-PLATE SHEAR TAB {typ}", "1-1/2\" = 1'-0\""
        elif typ == "MC-1":
            ttl, scl = "SMF MOMENT CONNECTION MC-1 (RBS)", "1\" = 1'-0\""
        elif typ.startswith("DC"):
            ttl, scl = f"DRAG CONNECTION {typ}", "1\" = 1'-0\""
        elif typ.startswith("BG"):
            ttl, scl = f"SCBF BRACE GUSSET {typ}", "3/4\" = 1'-0\""
        else:
            ttl, scl = f"COLUMN BASE PLATE {typ}", "1\" = 1'-0\""
        tb = _detail_frame(sh, box, num, ttl, scl)
        sh.occ(t["id"], "detail", ttl, tb)
        did = f"DET:{num}/{s}"
        ds.exp["details"].append({"id": did, "detail_type": t["id"], "sheet": s, "page": sh.pno,
                                  "bbox": [r2(v) for v in box], "title": ttl})
        ds.rel(t["id"], did, "detailed-by")
        if typ.startswith("ST"):
            det_shear_tab(ds, sh, box, int(typ[3:]), t)
        elif typ == "MC-1":
            det_rbs(ds, sh, box, t)
        elif typ.startswith("DC"):
            det_drag(ds, sh, box, t, int(typ[3:]))
        elif typ.startswith("BG"):
            det_gusset(ds, sh, box, t, int(typ[3:]))
        else:
            det_base_plate(ds, sh, box, t, typ)


# =========================================================================== S-601 sections
def sheet_sections(ds: DrawingSet):
    sh = Sheet(ds, "S-601", "SECTIONS", "sections", None, "3/4\" = 1'-0\"")
    sh.frame()
    k = 4.5   # 3/4" = 1'-0": 4.5 pt per inch

    def tag(x, y, txt, refs, target=None):
        if target:
            sh.line(target, (x - 3, y - 3), width=0.4)
            sh.circle(target, 1.4, width=0.4, fill=BLACK)
        box = sh.text(x, y, txt, 8)
        sh.occ(refs, "section_cut", txt, box)

    def footing_stack(cx, gl, cid, gb_id, gb_cut: bool):
        f, p, bp, col = ds.el[f"F-{cid}"], ds.el[f"P-{cid}"], ds.el[f"BP-{cid}"], ds.cols[cid]
        hb = f["B_ft"] * 12 / 2 * k
        tf = gl + 36 * k                       # top of footing 3'-0" below slab
        sh.rect(cx - hb, tf, cx + hb, tf + f["h_in"] * k, width=1.4)
        hp = p["b_in"] / 2 * k
        sh.rect(cx - hp, gl + 6 * k, cx + hp, tf, width=1.2)
        sh.rect(cx - 30, gl + 1, cx + 30, gl + 6 * k, width=0.6, dashes="[2 2] 0")   # slab/grout zone
        sh.rect(cx - 7 * k, gl - 4, cx + 7 * k, gl, width=0.8, fill=BLACK)            # base plate
        sh.line((cx - 7 * k, gl - 4), (cx - 7 * k, gl - 260), width=1.6)
        sh.line((cx + 7 * k, gl - 4), (cx + 7 * k, gl - 260), width=1.6)
        sh.line((cx - 260, gl), (cx + 260, gl), width=1.0)
        for xx in (-hp + 8, hp - 8):
            sh.line((cx + xx, gl), (cx + xx, tf + f["h_in"] * k - 12), width=0.6)
        sh.line((cx - hb + 10, tf + f["h_in"] * k - 12), (cx + hb - 10, tf + f["h_in"] * k - 12), width=0.6)
        tag(cx + 70, gl - 180, ("*" if col["sfrs"] else "") + col["size"] + " COLUMN", [col["id"]], (cx + 7 * k, gl - 170))
        num, s = DETAIL_AT[dtype(bp)]
        tag(cx + 90, gl - 30, f"{bp['conn_type']} PER {num}/{s}", [bp["id"]], (cx + 7 * k - 4, gl - 2))
        tag(cx + hp + 30, gl + 70, f"{pier_mark(p['pier_type'])} PIER, {p['bars'].replace('-', ' ')} VERT.", [p["id"]],
            (cx + hp, gl + 60))
        tag(cx + hb + 16, tf + 20, f"{ftg_mark(f['B_ft'])} FOOTING PER SCHEDULE, {f['bars']} B", [f["id"]], (cx + hb, tf + 30))
        g = ds.el[gb_id]
        if gb_cut:
            gx0 = cx - hb - 120
            sh.rect(gx0, tf - g["h_in"] * k + f["h_in"] * k, gx0 + g["b_in"] * k, tf + f["h_in"] * k, width=1.2)
            tag(gx0 - 10, tf - g["h_in"] * k + f["h_in"] * k - 14, f"{gb_mark(g)} GRADE BEAM {g['b_in']}\"x{g['h_in']}\" (BEYOND)",
                [g["id"]])
        else:
            sh.rect(cx - hb - 200, tf + f["h_in"] * k - g["h_in"] * k, cx - hb, tf + f["h_in"] * k, width=1.2)
            tag(cx - hb - 200, tf + f["h_in"] * k - g["h_in"] * k - 8, f"{gb_mark(g)} GRADE BEAM", [g["id"]])
        sh.text(cx - 255, gl - 6, "T.O. SLAB EL. 0'-0\"", 7)
        sh.text(cx - 255, tf - 4, "T.O. FTG EL. -3'-0\"", 7)
        return tf + f["h_in"] * k

    # 1: SMF base on line A at grid 2 (cut along line 2)
    gl = 520.0
    yb = footing_stack(560, gl, "2A", "GB-A-12", True)
    sh.occ("GB-A-23", "section_cut", "GB1 GRADE BEAM 18\"x24\" (BEYOND)",
           next(o["bbox"] for o in reversed(ds.exp["occurrences"]) if o["ref"] == "GB-A-12" and o["sheet"] == "S-601"))
    sh.drawing_title(300, yb + 60, "1", "SECTION AT SMF COLUMN BASE - LINE A / 2", "3/4\" = 1'-0\"", width=440)
    # 2: composite deck at infill beam B-L2-12-AB1
    m = ds.el["B-L2-12-AB1"]
    cx, top = 1400.0, 360.0
    sh.rect(cx - 330, top - 6.25 * k * 2, cx + 330, top, width=1.0)
    for j in range(-6, 7):                                      # deck flutes
        x = cx + j * 12 * k
        sh.poly([(x - 2.5 * k * 2, top), (x - 1.75 * k * 2, top - 3 * k * 2), (x + 1.75 * k * 2, top - 3 * k * 2),
                 (x + 2.5 * k * 2, top)], width=0.8, closed=False)
    d = 17.9 * k * 2
    sh.line((cx - 6 * k * 2, top), (cx + 6 * k * 2, top), width=2.0)
    sh.line((cx - 6 * k * 2, top + d), (cx + 6 * k * 2, top + d), width=2.0)
    sh.line((cx, top), (cx, top + d), width=1.4)
    for sx in (-14, 14):
        sh.line((cx + sx, top), (cx + sx, top - 4.5 * k * 2), width=1.4)
        sh.circle((cx + sx, top - 4.5 * k * 2), 4, width=1.0)
    tag(cx + 120, top + 80, f"{member_tag(m)} INFILL BEAM", [m["id"]], (cx + 3, top + 60))
    tag(cx + 120, top - 80, "3\" 20 GA COMPOSITE DECK + 3-1/4\" LW CONCRETE (6-1/4\" TOTAL)", ["DK-L2", "MAT:DECK-3VLI20"],
        (cx + 160, top - 20))
    tag(cx - 320, top - 90, "3/4\" DIA HEADED STUDS, 1 PER RIB MIN", ["MAT:STUD"], (cx - 14, top - 20))
    tag(cx - 320, top + 40, "T.O.S. LEVEL 2 EL. 14'-0\"", ["LEVEL:L2"])
    sh.drawing_title(1070, top + d + 120, "2", "SECTION AT COMPOSITE FLOOR BEAM - LEVEL 2", "1-1/2\" = 1'-0\"", width=440)
    # 3: SCBF base on line 3 at A (cut along line 3)
    gl3 = 1250.0
    yb3 = footing_stack(560, gl3, "3A", "GB-3-AB", False)
    br = ds.el["BR-L1-3-AB-S"]
    sh.line((560 + 20, gl3 - 10), (560 + 230, gl3 - 250), width=2.4)
    sh.line((560 + 32, gl3 - 4), (560 + 242, gl3 - 244), width=2.4)
    sh.poly([(560 + 7 * k, gl3 - 4), (560 + 90, gl3 - 4), (560 + 7 * k, gl3 - 100)], width=1.1)
    tag(560 + 250, gl3 - 230, f"*{br['size']} BRACE", [br["id"]], (560 + 200, gl3 - 200))
    cxi = next(c for c in ds.conn_by_member[br["id"]] if c["end"] == "i")
    num, s = DETAIL_AT[dtype(cxi)]
    tag(560 + 250, gl3 - 120, f"GUSSET {dtype(cxi)} PER {num}/{s}", [cxi["id"]], (560 + 60, gl3 - 30))
    ds.rel(cxi["id"], f"DET:{num}/{s}", "detailed-by")
    sh.drawing_title(300, yb3 + 60, "3", "SECTION AT SCBF COLUMN BASE - LINE 3 / A", "3/4\" = 1'-0\"", width=440)
    notes_column(sh, "SECTION NOTES", [
        ("SECTIONS ARE CUT ON S-101 AND S-201. FOOTING, PIER AND GRADE BEAM SIZES PER S-101 AND S-401.", []),
        ("PROVIDE 3\" CLEAR COVER TO REINFORCING CAST AGAINST EARTH.", ["MAT:REBAR-A615"]),
        ("GROUT BASE PLATES AFTER COLUMNS ARE PLUMBED; NON-SHRINK GROUT 5,000 PSI MIN.", []),
    ])


# =========================================================================== entry
def write(exp: dict, d: dict, path: str) -> dict:
    ds = DrawingSet(exp)
    ds._rels = []
    sheet_general_notes(ds)
    sheet_foundation(ds)
    for lv, num in (("L2", "S-201"), ("L3", "S-202"), ("RF", "S-203")):
        sheet_framing(ds, lv, num)
    sheet_elevations(ds)
    sheet_schedules(ds)
    st = [f"ST-{n}" for n in range(2, 8)]
    sheet_details(ds, "S-501", "TYPICAL STEEL CONNECTION DETAILS", ["MC-1"] + st + ["DC-1", "DC-2", "DC-3"], 4)
    sheet_details(ds, "S-502", "TYPICAL BRACE AND BASE PLATE DETAILS", ["BG-1", "BG-2", "BG-3", "BP-1", "BP-2", "BP-3", "BP-4"], 4)
    sheet_sections(ds)
    exp["relations"].extend(ds._rels)
    ds.save(path)
    return {"pages": len(ds.doc), "occurrences": sum(1 for o in exp["occurrences"] if o["doc"] == "drawings")}
