"""Logical model of the Harborview tower, read from the demo model bundles.

Sources (both committed):
- ``data/harborview/harborview-tower-rev{1-base,2-compare}.bundle.json``: the element graph (ids, marks,
  kinds, profiles, materials, levels, geometry) and the demo calc graph (calc titles, codes, revs, and which
  calc designs which element).
- ``legacy_params.json`` (next to this file): per-element demand (kN), utilisation and rated strength.
  The bundles do not keep them; they come from the legacy demo JSON at commit 410a100.

Marks: the legacy labels with a space ("Cap A1", "Pile P-A1", "Slab L01", "Core N-L01", "Brace A-L01")
become space-free marks (PC-A1, P-A1, SL-L01, SW-N-L01, BR-A-L01), because the calc matcher reads a mark as
one token. The old label is kept as the element name.

Calcs: one calc per bundle calc, except the S-102 pile cap & caisson calcs, which are written as two calcs
in the same PDF (a pile cap calc and a caisson calc). The engine takes a calc's element type from its
title, so one "Pile Cap & Caisson" calc would file the caisson as a reference, not a design.
"""
from __future__ import annotations

import json
import math
import os
import re
from dataclasses import dataclass, field

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
DATA = os.path.join(REPO, "data", "harborview")
BUNDLES = {1: "harborview-tower-rev1-base.bundle.json", 2: "harborview-tower-rev2-compare.bundle.json"}

IFC_CLASS = {"beam": "IfcBeam", "column": "IfcColumn", "brace": "IfcMember", "slab": "IfcSlab", "wall": "IfcWall",
             "footing": "IfcFooting", "pile": "IfcPile", "connection": "IfcPlate"}
TITLE_KW = re.compile(r"(design|calc|calculation|check|analysis|criteria|framing|report|schedule|connection|footing|bracing)", re.I)


def bundle_path(rev: int) -> str:
    for d in (DATA, os.path.join(REPO, "data")):
        p = os.path.join(d, BUNDLES[rev])
        if os.path.exists(p):
            return p
    raise FileNotFoundError(f"{BUNDLES[rev]} not found in {DATA}")


def space_free_mark(mark: str) -> str:
    """'Cap A1' -> 'PC-A1', 'Pile P-A1' -> 'P-A1', 'Slab L01' -> 'SL-L01', 'Core N-L01' -> 'SW-N-L01',
    'Brace A-L01' -> 'BR-A-L01'; marks without a space are unchanged."""
    if " " not in mark:
        return mark
    head, rest = mark.split(" ", 1)
    prefix = {"Cap": "PC-", "Pile": "", "Slab": "SL-", "Core": "SW-", "Brace": "BR-"}[head]
    return prefix + rest.replace(" ", "-")


def norm_size(s: str) -> str:
    """'W14x90' -> 'W14X90' (the section table's key); other profiles unchanged."""
    return s.upper() if re.match(r"^(W|HSS)\d", s or "", re.I) else s


@dataclass
class Element:
    id: str
    kind: str
    mark: str
    label: str          # the legacy label (element name in the IFC)
    desc: str
    profile: str
    material: str
    storey: str
    geom: dict
    kn: float
    uc: float
    fy: float | None
    role: str | None    # legacy beamRole ("InfillBeam") or None

    @property
    def ifc_class(self) -> str:
        return IFC_CLASS[self.kind]

    @property
    def grid(self) -> str:
        """Grid reference from the id: 'girder-A1-B1-L02' -> 'A1-B1', 'col-A1-L02' -> 'A1', 'slab-L02' -> ''."""
        parts = self.id.split("-")[1:]
        return "-".join(p for p in parts if not re.match(r"^L\d\d$", p) and p not in ("bp",))

    def length_ft(self) -> float:
        a = self.geom.get("axis")
        if a:
            return math.dist(a["start"], a["end"]) * 3.28084
        mn, mx = self.geom["bbox"]["min"], self.geom["bbox"]["max"]
        return max(mx[i] - mn[i] for i in range(3)) * 3.28084


@dataclass
class Calc:
    id: str             # truth calc id: the bundle calc key, or "<key>/cap" | "<key>/caisson" for S-102
    doc: str            # the bundle calc key = the calc document (one PDF)
    title: str          # the title written on the calc's pages
    family: str
    cat: str            # element type the engine should read from the title
    code: str
    rev: str
    date: str
    summary: str
    elements: list[str] = field(default_factory=list)  # element ids it designs, in model order


@dataclass
class Document:
    key: str
    title: str          # the bundle calc title (the document's name)
    rev: str
    date: str
    calcs: list[Calc]

    @property
    def sheet(self) -> str:
        return self.title.split(" ", 1)[0]

    @property
    def file_name(self) -> str:
        # no "&" in a served file name: Vite's static server does not decode %26 (and hosts differ)
        return f"{self.title.replace(' & ', ' and ')} - {self.rev}.pdf"


@dataclass
class Model:
    rev: int
    label: str
    project: str
    levels: list[tuple[str, float]]
    elements: list[Element]
    by_id: dict[str, Element]
    edges: list[dict]
    documents: list[Document]

    def calcs(self) -> list[Calc]:
        return [c for d in self.documents for c in d.calcs]

    def design_calc(self) -> dict[str, str]:
        return {e: c.id for c in self.calcs() for e in c.elements}


def family_of(title: str) -> str:
    for fam, rx in (("pilecap", r"Pile Cap & Caisson"), ("baseplate", r"Base Plate"), ("slab", r"Floor Slab"),
                    ("corewall", r"Shear Wall"), ("brace", r"Braced Frame"), ("colstack", r"Column Stack"),
                    ("girder", r"Girder Sizing"), ("connection", r"Bolted Moment"), ("infill", r"Infill Beams")):
        if re.search(rx, title):
            return fam
    raise ValueError(f"no calc family for {title!r}")


def page_title(title: str) -> str:
    """The title as written on the calc pages: every title must read as a calc title to the segmenter
    (segment.ts TITLE_KW). Two bundle titles do not: the base plate 'Package' and the infill beam titles."""
    t = title.replace("Anchor Rod Package", "Anchor Rod Design")
    return t if TITLE_KW.search(t) else f"{t} Design"


def load(rev: int) -> Model:
    b = json.load(open(bundle_path(rev), encoding="utf-8"))
    params = json.load(open(os.path.join(HERE, "legacy_params.json"), encoding="utf-8"))["revs"][str(rev)]
    eg, cg = b["elementGraph"], b["calcGraph"]
    levels = [(lv["name"], float(lv["elevation"])) for lv in eg["levels"]]
    elements = []
    for n in eg["nodes"]:
        p = params[n["id"]]
        elements.append(Element(
            id=n["id"], kind=n["kind"], mark=space_free_mark(n["mark"]), label=n["mark"], desc=n.get("name") or "",
            profile=n.get("profile") or "", material=n.get("material") or "", storey=n["levelId"].split(":", 1)[1],
            geom=n["geometry"], kn=float(p["kn"] or 0), uc=float(p["uc"] or 0), fy=p["fy"], role=p["role"]))
    by_id = {e.id: e for e in elements}
    members: dict[str, list[str]] = {}
    for l in cg["links"]:
        if l["role"] == "design":
            members.setdefault(l["calc"], []).append(l["element"])
    order = {e.id: i for i, e in enumerate(elements)}
    docs = []
    for c in cg["calcs"]:
        ids = sorted(members.get(c["key"], []), key=order.__getitem__)
        fam = family_of(c["title"])
        base = dict(code=c["code"], rev=c["rev"], date=c["date"], summary=c["summary"])
        if fam == "pilecap":
            grid = re.search(r"Grid ([A-E]\d)", c["title"]).group(1)
            sheet = c["title"].split(" ", 1)[0]
            calcs = [
                Calc(id=f"{c['key']}/cap", doc=c["key"], title=f"{sheet} Pile Cap Design - Grid {grid}", family="pilecap",
                     cat="Footing", elements=[i for i in ids if by_id[i].kind == "footing"], **base),
                Calc(id=f"{c['key']}/caisson", doc=c["key"], title=f"{sheet} Caisson (Drilled Pile) Design - Grid {grid}",
                     family="caisson", cat="Pile", elements=[i for i in ids if by_id[i].kind == "pile"], **base),
            ]
        else:
            calcs = [Calc(id=c["key"], doc=c["key"], title=page_title(c["title"]), family=fam, cat=c["cat"],
                          elements=ids, **base)]
        docs.append(Document(key=c["key"], title=c["title"], rev=c["rev"], date=c["date"], calcs=calcs))
    # the loading calcs (S-001..S-004) are not in the bundles: they design no element, other calcs cite them
    from . import loading
    docs = loading.documents(rev) + docs
    meta = b.get("meta", {})
    return Model(rev=rev, label=meta.get("label", f"Rev {rev}"), project=meta.get("project", "Harborview Corporate Center"),
                 levels=levels, elements=elements, by_id=by_id, edges=eg["edges"], documents=docs)
