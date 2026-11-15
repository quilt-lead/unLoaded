"""Harborview calc PDFs: one PDF per calc document, written with PyMuPDF (byte-stable).

Every page carries the running header (job, sheet, rev, page x/y) and the calc title, with "(cont.)" on later
pages, so the engine's segmenter starts exactly one calc per title. The body is a design basis, a schedule
naming every mark the calc designs with its size and demand / capacity, and "from" lines naming the elements
it takes loads from. Those lines are the calc -> calc edges: slab -> infill / girder / core wall / braced frame,
girder -> connection, connection -> column stack, braced frame -> column stack, column stack -> base plate,
base plate -> pile cap -> caisson.

Numbers come from the demo data (demand kN, utilisation) so the calcs agree with the inspector; capacities are
demand / utilisation. Plausible, not a design.

Rules the text keeps (packages/calc-mapper): one designed mark per schedule row, its size on the same row (a
wrong size on a mark row is a size-mismatch finding: only the planted one); no size on a line without a mark,
except the infill "typical" line (a typical-group link); no "to" on a line that names another element type's
mark (it would reverse the calc edge); section headings smaller than the title (no mid-page calc cut).
"""
from __future__ import annotations

import re

import pymupdf

from .. import shapes
from .model import Calc, Document, Element, Model, norm_size

W_PT, H_PT = 612, 792
KIP = 0.224809
SIZE = re.compile(r"\b(?:W\d+x\d+|HSS[\dx/]+)\b", re.I)
COMPOSITE = 1.35   # composite / non-composite flexural strength, typical for these spans
TOP, BOTTOM = 92.0, 748.0
MONO, LEAD = 8.3, 12.0


class Layout:
    """Lays a calc's blocks onto pages (ops only); render() draws them once the page count is known."""

    def __init__(self, title: str):
        self.title = title
        self.pages: list[list[tuple]] = []
        self.y = BOTTOM
        self.first_of_calc = True

    def new_page(self):
        self.pages.append([])
        cont = "" if self.first_of_calc else " (cont.)"
        self.first_of_calc = False
        self.pages[-1].append(("text", 40, 66, self.title + cont, "hebo", 12.5))
        self.y = TOP

    def need(self, h: float):
        if not self.pages or self.y + h > BOTTOM:
            self.new_page()

    def heading(self, s: str):
        self.need(LEAD * 3)
        self.y += 6
        self.pages[-1].append(("text", 40, self.y, s, "hebo", 9.5))
        self.y += LEAD + 2

    def line(self, s: str, indent: float = 0):
        self.need(LEAD)
        self.pages[-1].append(("text", 46 + indent, self.y, s, "cour", MONO))
        self.y += LEAD

    def gap(self, h: float = 5):
        self.y += h

    def table(self, cols: list[float], head: list[str], rows: list[list[str]], rh: float = 14.0):
        i = 0
        while i < len(rows):
            self.need(rh * 3)
            room = int((BOTTOM - self.y) // rh) - 1
            chunk = rows[i:i + max(1, room)]
            self.pages[-1].append(("grid", 46, self.y - 8, cols, [head] + chunk, rh))
            self.y += (len(chunk) + 1) * rh + 8
            i += len(chunk)


def render(doc: pymupdf.Document, layouts: list[Layout], header: str):
    pages = [p for lay in layouts for p in lay.pages]
    n = len(pages)
    for k, ops in enumerate(pages, 1):
        page = doc.new_page(width=W_PT, height=H_PT)
        page.insert_text((40, 34), f"{header}     SHT {k}/{n}", fontname="helv", fontsize=7.2)
        page.draw_line((40, 40), (W_PT - 40, 40), color=(0.6, 0.6, 0.6), width=0.5)
        for op in ops:
            if op[0] == "text":
                _, x, y, s, font, size = op
                page.insert_text((x, y), s, fontname=font, fontsize=size)
            else:
                _, x, y, cols, rows, rh = op
                xs = [x]
                for w in cols:
                    xs.append(xs[-1] + w)
                for r, row in enumerate(rows):
                    top = y + r * rh
                    if r == 0:
                        page.draw_rect(pymupdf.Rect(xs[0], top, xs[-1], top + rh), color=None, fill=(0.88, 0.91, 0.95))
                    for c, val in enumerate(row):
                        page.draw_rect(pymupdf.Rect(xs[c], top, xs[c + 1], top + rh), color=(0.72, 0.72, 0.72), width=0.4)
                        page.insert_text((xs[c] + 3, top + rh - 4.2), val, fontname="hebo" if r == 0 else "helv", fontsize=7.6)
        page.draw_line((40, H_PT - 34), (W_PT - 40, H_PT - 34), color=(0.8, 0.8, 0.8), width=0.4)
        page.insert_text((40, H_PT - 24), "Synthetic calculation set for software testing - not for construction.",
                         fontname="helv", fontsize=6.5, color=(0.45, 0.45, 0.45))


# ---------------------------------------------------------------- content


def f1(x: float) -> str:
    return f"{x:,.1f}"


def f2(x: float) -> str:
    return f"{x:.2f}"


def ok(uc: float) -> str:
    return "OK" if uc <= 1.0 else "NG"


class Writer:
    """Writes one model revision's calc documents; records what each calc mentions (truth)."""

    def __init__(self, m: Model, mismatch: dict[str, str] | None = None):
        self.m = m
        self.mismatch = mismatch or {}        # element id -> size written in its calc (planted finding)
        self.refs: dict[str, list[str]] = {}  # calc id -> element ids it takes loads from
        self.explicit = self._adjacency(explicit_only=True)
        self.adjacent = self._adjacency(explicit_only=False)

    def _adjacency(self, explicit_only: bool) -> dict[str, list[str]]:
        adj: dict[str, list[str]] = {}
        for e in self.m.edges:
            if e["kind"] == "connects" and (not explicit_only or any(ev.get("source") == "explicit" for ev in e.get("evidence", []))):
                adj.setdefault(e["a"], []).append(e["b"])
                adj.setdefault(e["b"], []).append(e["a"])
        return adj

    def el(self, i: str) -> Element:
        return self.m.by_id[i]

    def size_of(self, e: Element) -> str:
        return self.mismatch.get(e.id, e.profile)

    def cite(self, lay: Layout, calc: Calc, lead: str, ids: list[str], per_line: int = 5):
        """'<lead> from A, B, C' lines (the cue word on every line), recording the mentions."""
        ids = [i for i in ids if i in self.m.by_id]
        if not ids:
            return
        self.refs.setdefault(calc.id, []).extend(i for i in ids if i not in self.refs.get(calc.id, []))
        for k in range(0, len(ids), per_line):
            chunk = ", ".join(self.el(i).mark for i in ids[k:k + per_line])
            lay.line(f"{lead} from {chunk}" if k == 0 else f"{' ' * len(lead)} from {chunk}")

    def basis(self, lay: Layout, calc: Calc, extra: list[str]):
        lay.heading("1. Basis")
        lay.line(f"Code: {calc.code}.   Issue: {calc.rev}, {calc.date}.")
        # the demo summaries name sections ("... check for W21x62"): a size on a line with no mark is a
        # typical-group link to the engine, so the scope line names none
        lay.line("Scope: " + SIZE.sub("the scheduled sections", calc.summary))
        for s in extra:
            lay.line(s)
        if self.m.rev == 2 and calc.rev != "Rev A":
            lay.line(f"Revision {calc.rev[-1]}: demands updated for the L06 vertical addition (model Rev 2).")

    # -- families
    def slab(self, lay: Layout, calc: Calc):
        self.basis(lay, calc, ["Deck: 3 in. 20 ga composite deck, 3.25 in. NWC topping (6.25 in. total), f'c = 4 ksi.",
                               "Loads: SDL 15 psf, LL 50 psf office + 15 psf partitions. Combination 1.2D + 1.6L."])
        lay.heading("2. Slab schedule")
        rows = []
        for i in calc.elements:
            e = self.el(i)
            mu = 0.55 + e.kn / 9000.0
            rows.append([e.mark, e.storey, e.profile, "10.0", f2(mu), f2(mu / e.uc), f2(e.uc), ok(e.uc)])
        lay.table([62, 40, 128, 52, 64, 74, 46, 36], ["Mark", "Level", "System", "Span ft", "Mu k-ft/ft", "phiMn k-ft/ft", "D/C", ""], rows)
        lay.heading("3. Diaphragm")
        for i in calc.elements:
            e = self.el(i)
            v = 180 + e.kn / 12.0
            lay.line(f"{e.mark}: collector shear vu = {f1(v)} plf, phi vn = {f1(v / max(e.uc, 0.3))} plf. {ok(e.uc)}")
        lay.line("Chords and collectors at grid lines A and E (braced frames) and at the core walls.")

    def beams(self, lay: Layout, calc: Calc, girder: bool):
        storey = self.el(calc.elements[0]).storey if calc.elements else ""
        slab = [e.id for e in self.m.elements if e.kind == "slab" and e.storey == storey]
        self.basis(lay, calc, ["Steel A992 Gr.50, composite with 3/4 in. headed studs; unshored construction.",
                               "Combinations 1.2D + 1.6L (strength), LL deflection limit span/360."])
        self.cite(lay, calc, "Tributary floor loads", slab)
        if not girder and calc.elements:
            lay.line(f"Typical infill beam at {storey}: W16x31 composite, studs at 12 in.")
        # sizes only where every same-size element on the storey is in this calc (infill beams): the engine
        # links a size on a mark row to every element of that size on the storey (the size tier), so a girder
        # line's rows would also link the other lines' girders
        show = not girder
        lay.heading("2. Flexure and shear")
        rows = []
        for i in calc.elements:
            e = self.el(i)
            span = e.length_ft()
            d, _, tw = shapes.W[norm_size(e.profile)][:3]
            phi_mn = COMPOSITE * shapes.phi_mn_kft(norm_size(e.profile))
            mu = e.uc * phi_mn
            vu = 4 * mu / span                      # uniform load: Vu = wL/2, Mu = wL^2/8
            phi_vn = 0.6 * shapes.FY_KSI * d * tw   # AISC G2.1, Cv = 1, phi = 1.0
            rows.append([e.mark] + ([self.size_of(e)] if show else []) +
                        [f1(span), f1(mu), f1(phi_mn), f1(vu), f1(phi_vn), f2(e.uc), ok(e.uc)])
        cols = [70] + ([50] if show else []) + [44, 50, 58, 42, 52, 38, 28]
        head = ["Mark"] + (["Size"] if show else []) + ["Span ft", "Mu k-ft", "phiMn k-ft", "Vu k", "phiVn k", "D/C", ""]
        lay.table(cols, head, rows)
        lay.heading("3. Live load deflection")
        rows = []
        for i in calc.elements:
            e = self.el(i)
            lim = e.length_ft() * 12 / 360
            rows.append([e.mark] + ([self.size_of(e)] if show else []) + [f2(lim * e.uc * 0.8), f2(lim), ok(e.uc)])
        lay.table([70] + ([50] if show else []) + [70, 70, 28], ["Mark"] + (["Size"] if show else []) + ["dLL in.", "limit in.", ""], rows)

    def connection(self, lay: Layout, calc: Calc):
        self.basis(lay, calc, ["Bolts 7/8 in. A325-N in standard holes; shear tab 3/8 in. A36; E70 fillet welds.",
                               "Checks: bolt shear, bearing, block shear, tab flexure, weld (AISC J3, J4)."])
        lay.heading("2. Connection schedule")
        rows = []
        for i in calc.elements:
            e = self.el(i)
            vu = e.kn * KIP
            rows.append([e.mark, e.grid, e.profile, f1(vu), f1(vu / e.uc), f2(e.uc), ok(e.uc)])
        lay.table([72, 56, 92, 52, 58, 40, 28], ["Mark", "Grid", "Bolts", "Vu k", "phiRn k", "D/C", ""], rows)
        lay.heading("3. Member end reactions")
        for i in calc.elements:
            beams = [j for j in self.explicit.get(i, []) if self.el(j).kind == "beam"]
            self.cite(lay, calc, f"{self.el(i).mark} end reaction", beams)

    def colstack(self, lay: Layout, calc: Calc):
        self.basis(lay, calc, ["Steel A992 Gr.50. K = 1.0, unbraced length = storey height. Splice above L03 floor.",
                               "Checks: axial compression (AISC E3), combined axial + flexure (H1), splice."])
        lay.heading("2. Column schedule")
        rows = []
        for i in calc.elements:
            e = self.el(i)
            pu = e.kn * KIP
            rows.append([e.mark, e.storey, f1(pu), f1(e.length_ft()), f1(pu / e.uc), f2(e.uc), ok(e.uc)])
        # no size column: a size on a mark row links every column of that size on the storey (other stacks)
        lay.table([70, 40, 54, 46, 58, 40, 28], ["Mark", "Level", "Pu k", "KL ft", "phiPn k", "D/C", ""], rows)
        lay.heading("3. Loads")
        cols = set(calc.elements)
        conns = [e.id for e in self.m.elements if e.kind == "connection" and not e.id.startswith("conn-bp")
                 and cols & set(self.explicit.get(e.id, []))]
        self.cite(lay, calc, "Floor reactions", conns, per_line=4)
        braces = []
        for e in self.m.elements:
            if e.kind == "brace":
                bays = [j for j in self.adjacent.get(e.id, []) if self.el(j).kind == "beam"]
                ends = {g for j in bays for g in self.el(j).grid.split("-")}
                if any(self.el(c).grid in ends and self.el(c).storey == e.storey for c in cols):
                    braces.append(e.id)
        self.cite(lay, calc, "Brace axial forces", braces)

    def baseplate(self, lay: Layout, calc: Calc):
        self.basis(lay, calc, ["Plate A572 Gr.50; rods F1554 Gr.55; grout 1.5 in. non-shrink; pier f'c = 5 ksi.",
                               "Checks: concrete bearing (J8), plate yielding, rod tension and shear (ACI 318 Ch.17)."])
        lay.heading("2. Base plate schedule")
        rows = []
        for i in calc.elements:
            e = self.el(i)
            pu = e.kn * KIP
            fp = pu / (26 * 26)
            rows.append([e.mark, e.grid, e.profile, f1(pu), f2(fp), f2(fp / e.uc), f2(e.uc), ok(e.uc)])
        lay.table([56, 40, 104, 54, 50, 58, 40, 28], ["Mark", "Grid", "Plate", "Pu k", "fp ksi", "phi fp ksi", "D/C", ""], rows)
        lay.heading("3. Column loads")
        for i in calc.elements:
            cols = [j for j in self.explicit.get(i, []) if self.el(j).kind == "column"]
            self.cite(lay, calc, f"{self.el(i).mark} axial load", cols)

    def pilecap(self, lay: Layout, calc: Calc):
        self.basis(lay, calc, ["Concrete f'c = 5 ksi, rebar A615 Gr.60. One 42 in. caisson per cap.",
                               "Checks: flexure, one-way shear, punching shear about the pier (ACI 318 Ch.13, 22)."])
        lay.heading("2. Pile cap schedule")
        rows = []
        for i in calc.elements:
            e = self.el(i)
            pu = e.kn * KIP
            mu = pu * 2.25
            rows.append([e.mark, e.profile, f1(pu), f1(mu), f1(mu / e.uc), f2(e.uc), ok(e.uc)])
        lay.table([56, 110, 56, 60, 64, 40, 28], ["Mark", "Size", "Pu k", "Mu k-ft", "phiMn k-ft", "D/C", ""], rows)
        lay.heading("3. Loads")
        for i in calc.elements:
            bps = [j for j in self.explicit.get(i, []) if j.startswith("conn-bp")]
            self.cite(lay, calc, "Column load", bps)
        lay.line("Bottom mat #8 at 8 in. each way; punching vu / phi vc within limits.")

    def caisson(self, lay: Layout, calc: Calc):
        self.basis(lay, calc, ["Drilled caisson, f'c = 5 ksi, 12 #9 vertical, #4 ties at 12 in.",
                               "Geotechnical: allowable end bearing 30 ksf, skin friction 1.2 ksf below 8 ft."])
        lay.heading("2. Caisson schedule")
        rows = []
        for i in calc.elements:
            e = self.el(i)
            pu = e.kn * KIP
            rows.append([e.mark, e.profile, f1(e.length_ft()), f1(pu), f1(pu / e.uc), f2(e.uc), ok(e.uc)])
        lay.table([56, 96, 50, 56, 64, 40, 28], ["Mark", "Size", "Length ft", "Pu k", "phiQn k", "D/C", ""], rows)
        lay.heading("3. Loads")
        for i in calc.elements:
            caps = [j for j in self.explicit.get(i, []) if self.el(j).kind == "footing"]
            self.cite(lay, calc, "Cap reaction", caps)

    def corewall(self, lay: Layout, calc: Calc):
        self.basis(lay, calc, ["Concrete f'c = 6 ksi, rebar A615 Gr.60, 18 in. walls, special boundary elements.",
                               "Checks: in-plane shear (ACI 18.10.4), flexure + axial, boundary element need (18.10.6)."])
        lay.heading("2. Wall schedule")
        rows = []
        for i in calc.elements:
            e = self.el(i)
            vu = e.kn * KIP * 0.35
            rows.append([e.mark, e.storey, e.profile, f1(vu), f1(vu / e.uc), f1(e.kn * KIP), f2(e.uc), ok(e.uc)])
        lay.table([64, 40, 110, 50, 56, 50, 40, 28], ["Mark", "Level", "Wall", "Vu k", "phiVn k", "Pu k", "D/C", ""], rows)
        lay.heading("3. Lateral loads")
        storeys = {self.el(i).storey for i in calc.elements}
        self.cite(lay, calc, "Diaphragm shear", [e.id for e in self.m.elements if e.kind == "slab" and e.storey in storeys])

    def brace(self, lay: Layout, calc: Calc):
        self.basis(lay, calc, ["HSS A500 Gr.C; gussets 3/4 in. A572 Gr.50; OCBF (AISC 341 F1).",
                               "Checks: brace compression and tension, gusset Whitmore section, block shear, welds."])
        lay.heading("2. Brace schedule")
        rows = []
        for i in calc.elements:
            e = self.el(i)
            pu = e.kn * KIP
            mn, mx = e.geom["bbox"]["min"], e.geom["bbox"]["max"]
            ext = sorted((mx[k] - mn[k] for k in range(3)), reverse=True)
            diag = (ext[0] ** 2 + ext[1] ** 2) ** 0.5 * 3.28084   # corner to corner of the braced panel
            rows.append([e.mark, e.storey, self.size_of(e), f1(pu), f1(diag), f1(pu / e.uc), f2(e.uc), ok(e.uc)])
        lay.table([64, 40, 70, 52, 46, 58, 40, 28], ["Mark", "Level", "Size", "Pu k", "L ft", "phiPn k", "D/C", ""], rows)
        lay.heading("3. Lateral loads")
        storeys = {self.el(i).storey for i in calc.elements}
        self.cite(lay, calc, "Diaphragm forces", [e.id for e in self.m.elements if e.kind == "slab" and e.storey in storeys])

    def calc_layout(self, calc: Calc) -> Layout:
        lay = Layout(calc.title)
        lay.new_page()
        fam = calc.family
        if fam == "slab":
            self.slab(lay, calc)
        elif fam in ("girder", "infill"):
            self.beams(lay, calc, girder=fam == "girder")
        elif fam == "connection":
            self.connection(lay, calc)
        elif fam == "colstack":
            self.colstack(lay, calc)
        elif fam == "baseplate":
            self.baseplate(lay, calc)
        elif fam == "pilecap":
            self.pilecap(lay, calc)
        elif fam == "caisson":
            self.caisson(lay, calc)
        elif fam == "corewall":
            self.corewall(lay, calc)
        elif fam == "brace":
            self.brace(lay, calc)
        else:
            raise ValueError(fam)
        return lay

    def document(self, d: Document, path: str):
        doc = pymupdf.open()
        header = (f"HARBORVIEW CORPORATE CENTER     JOB 2614     {d.sheet}     {d.rev}     BY: JMS     "
                  f"CHK: RKL     DATE: {d.date}")
        render(doc, [self.calc_layout(c) for c in d.calcs], header)
        save(doc, path, f"{d.title} ({d.rev})")


def save(doc: pymupdf.Document, path: str, title: str):
    doc.set_metadata({
        "title": f"{title} - Harborview Corporate Center (synthetic)", "author": "calc-graph synth",
        "subject": "Synthetic calc package with ground truth", "creator": "calc-graph synth generator (harborview)",
        "producer": "PyMuPDF", "creationDate": "D:20261115090000-05'00'", "modDate": "D:20261115090000-05'00'", "keywords": "",
    })
    doc.save(path, garbage=3, deflate=True, no_new_id=True)


def combine(paths: list[str], out: str, title: str):
    doc = pymupdf.open()
    for p in paths:
        with pymupdf.open(p) as src:
            doc.insert_pdf(src)
    save(doc, out, title)


def sheet_key(d: Document) -> tuple:
    """Package order: by sheet number, then title (S-102 grids A1..E4, S-201.., S-302 by level and line, ...)."""
    m = re.match(r"S-(\d+)", d.sheet)
    return (int(m.group(1)) if m else 999, d.title)
