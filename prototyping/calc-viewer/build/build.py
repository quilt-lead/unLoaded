"""Build the calc-viewer data from the drawing set and calc packages.

Reads the three source PDFs at the repo root and writes:
  docs/plans-S.pdf        the structural sheets (S-series) pulled out of the plan set
  data/documents.json     the PDFs and their page labels
  data/elements.json      drawn elements (members, footings, callouts, detail views) with every place they appear
  data/groups.json        typical groups (same size + level), formed from how the calcs refer to members
  data/calcs.json         calcs as ordered spans of page regions (one span = one stepper stop)
  data/links.json         element/group <-> calc links with evidence, confidence and rationale

Rationale summaries come from data/summaries.json (written by a reviewer or, later, by the
Claude API from the same evidence). Links without one get a template summary.

Run from anywhere:  python prototyping/calc-viewer/build/build.py
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path

import pymupdf

HERE = Path(__file__).resolve().parent
VIEWER = HERE.parent
REPO = VIEWER.parent.parent
DATA = VIEWER / "data"
DOCS = VIEWER / "docs"

PLANS_PDF = REPO / "OC-DPH_PKG21-0516_Bldg12_ApprovedPlans.pdf"
CALCS_PDF = REPO / "OC-DPH_PKG21-0516_Bldg12_Calcs.pdf"
STAIR_PDF = REPO / "OC-DPH_PKG21-0516_Bldg12_StairCalcs.pdf"

MATCHER_VERSION = "0.2.0"
TODAY = dt.date.today().isoformat()

# Sheets whose drawn members are extracted, with the level used when a view title doesn't name one.
# Callouts and detail views are extracted from every S-sheet.
MEMBER_SHEETS = {"S2.0.1": "Foundation", "S2.0.2": "Level 2", "S2.0.3": "Roof", "S3.0.1": "Elevation",
                 "S4.0.1": "Elevation", "S4.0.2": "Elevation", "S5.0.1": "Level 2", "S5.0.2": "Level 2", "S5.0.3": "Roof"}
PLAN_SHEETS = {"S2.0.1", "S2.0.2", "S2.0.3", "S5.0.1", "S5.0.2", "S5.0.3"}
LEVEL_ORDER = ["Foundation", "Level 2", "Roof", "Elevation", "Details"]

# member labels: steel shapes anywhere in a short label line, wood sizes only at the start of a label
STEEL_RE = r"W\d{1,2}x\d{2,3}|MC\d{1,2}x[\d.]+|C\d{1,2}x\d{1,2}(?:\.\d)?|HSS\d+(?:\.\d+)?x\d+(?:\.\d+)?x\d+(?:/\d+)?|\d{3}S\d{3}-\d{2,3}"
MEMBER_RE = re.compile(rf"(?<![\w./-])({STEEL_RE}|\d{{1,2}}x\d{{1,2}})(?![\w/])", re.I)
WOOD_RE = re.compile(r"^\d{1,2}x\d{1,2}$", re.I)
FOUND_RE = re.compile(r"^(F\d{1,2}(?:\.\d)?|GB\d|P\d(?:\.\d)?)$")
SHEET_REF_RE = re.compile(r"^S\d\.\d\.\d{1,2}$")
DETAIL_NO_RE = re.compile(r"^\d{1,2}[A-Z]?$")
GRID_RE = re.compile(r"^([A-F](\.\d)?|\d(\.\d)?)$")
STAMP_NOISE = ("Building&Safety", "Permits:", "OCPWAzarvandB", "BNR21", "PLB21", "ELE21", "MEC21")
SMF_MARK = "٭"  # the "٭" glyph the SMF elevations put in front of member sizes


# ---------------------------------------------------------------- helpers
def norm_rect(r, page) -> list[float]:
    w, h = page.rect.width, page.rect.height
    x0, y0, x1, y1 = r
    return [round(max(0, x0) / w, 4), round(max(0, y0) / h, 4), round(min(w, x1) / w, 4), round(min(h, y1) / h, 4)]


def pad(r, p):
    return (r[0] - p, r[1] - p, r[2] + p, r[3] + p)


def union(rs):
    return (min(r[0] for r in rs), min(r[1] for r in rs), max(r[2] for r in rs), max(r[3] for r in rs))


def sha(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:16]


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9.]+", "-", s.lower()).strip("-")


def lines_of(page):
    """Text lines with bbox, direction and max font size."""
    out = []
    for b in page.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            text = "".join(s["text"] for s in l["spans"]).strip()
            if not text:
                continue
            out.append({"text": text, "bbox": tuple(l["bbox"]), "dir": tuple(round(v) for v in l["dir"]),
                        "size": max(s["size"] for s in l["spans"])})
    return out


def char_lines(page):
    """Lines with their characters (for splitting one text line into several labels)."""
    out = []
    for b in page.get_text("rawdict")["blocks"]:
        for l in b.get("lines", []):
            chars = [c for s in l["spans"] for c in s["chars"]]
            if not chars:
                continue
            out.append({"text": "".join(c["c"] for c in chars), "chars": chars, "bbox": tuple(l["bbox"]),
                        "dir": tuple(round(v) for v in l["dir"]), "size": max(s["size"] for s in l["spans"])})
    return out


def content_bottom(page) -> float:
    ys = [l["bbox"][3] for l in lines_of(page) if not any(n in l["text"] for n in STAMP_NOISE)]
    return min(page.rect.height - 18, (max(ys) if ys else page.rect.height - 36) + 4)


def page_text(page) -> str:
    t = page.get_text()
    for n in ("Building&Safety: OCPWAzarvandB 12/22/2025", "Permits: BNR21-0246, ELE21-0853, MEC21-0514, PLB21-0900",
              "Permits: BNR21-0246"):
        t = t.replace(n, "")
    return t


# ---------------------------------------------------------------- documents
def sheet_no_of_plan_page(page) -> str | None:
    w, h = page.rect.width, page.rect.height
    best = None
    for l in lines_of(page):
        x0, y0, x1, y1 = l["bbox"]
        if x0 > w * 0.85 and y0 > h * 0.85 and l["size"] > 40 and re.fullmatch(r"[A-Z]{1,2}\d{1,2}(\.\d{1,2}){1,2}", l["text"]):
            best = l["text"]
    return best


def sheet_title_of_plan_page(page) -> str:
    w, h = page.rect.width, page.rect.height
    parts = [l["text"] for l in lines_of(page)
             if l["bbox"][0] > w * 0.85 and h * 0.86 < l["bbox"][1] < h * 0.92 and 17 < l["size"] < 30]
    return " ".join(parts).strip()


def sheet_no_of_calc_page(page) -> str | None:
    h = page.rect.height
    for w in page.get_text("words"):
        if w[1] < h * 0.12 and re.fullmatch(r"[A-Z]{1,2}\d{1,3}(_\d{1,2})?", w[4]):
            return w[4]
    return None


def build_documents():
    plans = pymupdf.open(PLANS_PDF)
    s_pages, labels, titles = [], [], []
    for i in range(plans.page_count):
        sn = sheet_no_of_plan_page(plans[i])
        if sn and sn.startswith("S"):
            s_pages.append(i)
            labels.append(sn)
            titles.append(sheet_title_of_plan_page(plans[i]))
    DOCS.mkdir(parents=True, exist_ok=True)
    out_pdf = DOCS / "plans-S.pdf"
    if "--force" in sys.argv or not out_pdf.exists() or out_pdf.stat().st_mtime < PLANS_PDF.stat().st_mtime:
        sub = pymupdf.open()
        for i in s_pages:
            sub.insert_pdf(plans, from_page=i, to_page=i)
        sub.save(out_pdf, garbage=3, deflate=True)
        sub.close()

    calcs = pymupdf.open(CALCS_PDF)
    stair = pymupdf.open(STAIR_PDF)
    docs = [
        {"id": "plans", "kind": "drawings", "title": "Approved plans – structural sheets (S-series)",
         "file": "docs/plans-S.pdf", "source": PLANS_PDF.name,
         "pages": [{"page": n + 1, "label": labels[n], "title": titles[n], "sourcePage": s_pages[n] + 1}
                   for n in range(len(s_pages))]},
        {"id": "calcs", "kind": "calcs", "title": "Structural calculations (KPFF, 2021)",
         "file": "../../" + CALCS_PDF.name, "source": CALCS_PDF.name,
         "pages": [{"page": i + 1, "label": sheet_no_of_calc_page(calcs[i])} for i in range(calcs.page_count)]},
        {"id": "stair", "kind": "calcs", "title": "Stair & parapet calculations (KPFF, 2023)",
         "file": "../../" + STAIR_PDF.name, "source": STAIR_PDF.name,
         "pages": [{"page": i + 1, "label": None} for i in range(stair.page_count)]},
    ]
    return docs, plans, s_pages, calcs, stair


# ---------------------------------------------------------------- views (detail views and plan / elevation viewports)
def find_views(page, sheet):
    """Every titled view on a sheet: a title line (font ~19) with the view number (font ~25) to its right, at the
    bottom of the viewport. The view's region is the area above its title bar, bounded by the neighbouring views."""
    w, h = page.rect.width, page.rect.height
    spans = [{"text": s["text"].strip(), "bbox": tuple(s["bbox"]), "size": s["size"]}
             for b in page.get_text("dict")["blocks"] for l in b.get("lines", []) for s in l["spans"] if s["text"].strip()]
    lines = lines_of(page)
    nums = [s for s in spans if 23 < s["size"] < 27 and DETAIL_NO_RE.match(s["text"]) and s["bbox"][0] < w * 0.9]
    views = []
    for n in nums:
        cands = [l for l in lines if 17 < l["size"] < 21 and l["dir"] == (1, 0) and abs(l["bbox"][3] - n["bbox"][3]) < 9
                 and l["bbox"][2] <= n["bbox"][0] + 2 and n["bbox"][0] - l["bbox"][2] < 160 and len(l["text"]) > 2
                 and re.search(r"[A-Z]{3}", l["text"])]
        if not cands:
            continue
        t = max(cands, key=lambda l: l["bbox"][2])
        title_lines = [t]
        # two-line titles: a line directly above, right-aligned with it
        for l in lines:
            if l is not t and 17 < l["size"] < 21 and abs(l["bbox"][2] - t["bbox"][2]) < 14 and 0 <= t["bbox"][1] - l["bbox"][3] < 9:
                title_lines.insert(0, l)
        title = " ".join(x["text"] for x in title_lines)
        bar = union([x["bbox"] for x in title_lines] + [n["bbox"]])
        views.append({"num": n["text"], "title": re.sub(r"\s+", " ", title).strip(), "bar": bar,
                      "right": n["bbox"][2] + 14, "bottom": bar[3] + 8, "tleft": bar[0], "ttop": bar[1]})
    # regions: left bound = the right edge of the nearest view in the same row; top = the bottom of the view above
    for v in views:
        lefts = [o["right"] for o in views if o is not v and o["right"] <= v["tleft"] + 5 and abs(o["bottom"] - v["bottom"]) < 60]
        v["left"] = max(lefts) if lefts else 40
    for v in views:
        span = v["right"] - v["left"]
        tops = [o["bottom"] for o in views if o is not v and o["bottom"] < v["ttop"] - 10
                and min(o["right"], v["right"]) - max(o["left"], v["left"]) > 0.3 * span]
        v["top"] = max(tops) if tops else 40
        v["rect"] = (v["left"], v["top"], v["right"], v["bottom"])
        v["ref"] = f'{v["num"]}/{sheet}'
    # one view per number (a sheet occasionally repeats a number for a continued view: keep the larger region)
    best = {}
    for v in views:
        a = (v["rect"][2] - v["rect"][0]) * (v["rect"][3] - v["rect"][1])
        if v["num"] not in best or a > best[v["num"]][0]:
            best[v["num"]] = (a, v)
    return [v for _, v in best.values()]


def view_at(pt, views):
    x, y = pt
    inside = [v for v in views if v["rect"][0] <= x <= v["rect"][2] and v["rect"][1] <= y <= v["rect"][3]]
    return min(inside, key=lambda v: (v["rect"][2] - v["rect"][0]) * (v["rect"][3] - v["rect"][1])) if inside else None


def level_of_view(title: str, sheet: str) -> str:
    t = title.upper()
    if "FOUNDATION" in t:
        return "Foundation"
    if "ROOF" in t:
        return "Roof"
    if "LEVEL 2" in t:
        return "Level 2"
    if "ELEVATION" in t and sheet.startswith(("S3", "S4")):
        return "Elevation"
    return MEMBER_SHEETS.get(sheet, "Details")


def is_elevation(view) -> bool:
    return bool(view and re.search(r"ELEVATION", view["title"]))


def grid_lines(page, views):
    """Grid bubbles -> per view ref: plans {'x': {label: x}, 'y': {label: y}}; elevations put every bubble on x."""
    per_view = defaultdict(lambda: {"x": defaultdict(list), "y": defaultdict(list)})
    for l in lines_of(page):
        if 17 < l["size"] < 21 and GRID_RE.match(l["text"]) and l["dir"] == (1, 0):
            cx, cy = (l["bbox"][0] + l["bbox"][2]) / 2, (l["bbox"][1] + l["bbox"][3]) / 2
            v = view_at((cx, cy), views)
            if not v:
                continue
            axis = "x" if is_elevation(v) or l["text"][0].isdigit() else "y"
            per_view[v["ref"]][axis][l["text"]].append(cx if axis == "x" else cy)
    return {v: {a: {k: sum(vals) / len(vals) for k, vals in d[a].items()} for a in d} for v, d in per_view.items()}


def grid_pos(val, lines: dict, tol=20.0) -> str:
    if not lines:
        return "?"
    items = sorted(lines.items(), key=lambda kv: kv[1])
    for k, v in items:
        if abs(val - v) <= tol:
            return k
    for (k0, v0), (k1, v1) in zip(items, items[1:]):
        if v0 < val < v1:
            return f"{k0}–{k1}"
    near = min(items, key=lambda kv: abs(kv[1] - val))[0]
    return f"{near}(ext)"


def grid_label(pt, grids, view=None):
    if not grids:
        return "?"
    if is_elevation(view):
        pos = grid_pos(pt[0], grids.get("x", {}))
        m = re.search(r"ALONG GRID ([A-Z0-9.]+)", view["title"])
        if m:
            along = m.group(1)
            return f"{along}/{pos}" if along[0].isalpha() else f"{pos}/{along}"
        face = re.search(r"(NORTH|EAST|SOUTH|WEST)", view["title"])
        return f"{face.group(1)[0] if face else 'E'}:{pos}"
    gx = grid_pos(pt[0], grids.get("x", {}))
    gy = grid_pos(pt[1], grids.get("y", {}))
    return f"{gy}/{gx}"


def find_callouts(page, region_max_x, words=None):
    """Detail callouts: a detail number sitting directly above a sheet reference (e.g. 12 over S8.2.5)."""
    words = words if words is not None else page.get_text("words")
    nums = [w for w in words if DETAIL_NO_RE.match(w[4])]
    out = []
    for w in words:
        if not SHEET_REF_RE.match(w[4]) or w[0] > region_max_x:
            continue
        cx = (w[0] + w[2]) / 2
        above = [n for n in nums if abs((n[0] + n[2]) / 2 - cx) < 8 and 0 <= w[1] - n[3] < 12]
        if above:
            n = min(above, key=lambda n: w[1] - n[3])
            out.append({"detail": n[4], "sheet": w[4], "rect": union([n[:4], w[:4]])})
    return out


def member_type(size: str, follow: str, sheet: str, orient: str) -> str:
    s, f = size.upper(), follow.upper()
    if re.match(r"\d{3}S\d{3}", s):
        return "stud"
    if "STRINGER" in f:
        return "stringer"
    if s.startswith("HSS"):
        if "POST" in f:
            return "post"
        return "column" if sheet in PLAN_SHEETS else "hss-member"
    if s.startswith(("W", "MC", "C")):
        return "column" if sheet == "S3.0.1" and orient == "v" else "beam"
    return "wood-member"


# IFC4 alignment: our working type -> (entity, PredefinedType, material category). Our own `type` stays the
# id/grouping key; `ifc` says what the element would be in an IFC model. Wood members are all drawn in plan on the
# framing plans, so they're beams. A post marked "POST ABOVE" carries the level above (a column); a parapet post
# is a secondary member. P-marks on the foundation plan are drilled piles per the pile schedule on S2.0.1.
IFC_MAP = {
    "beam": ("IfcBeam", "BEAM", "steel"),
    "column": ("IfcColumn", "COLUMN", "steel"),
    "wood-member": ("IfcBeam", "BEAM", "wood"),
    "stringer": ("IfcMember", "STRINGER", "steel"),
    "hss-member": ("IfcMember", "MEMBER", "steel"),
    "post": ("IfcMember", "POST", "steel"),
    "stud": ("IfcMember", "STUD", "steel"),
    "footing": ("IfcFooting", "PAD_FOOTING", "concrete"),
    "grade-beam": ("IfcFooting", "FOOTING_BEAM", "concrete"),
    "pile": ("IfcPile", "NOTDEFINED", "concrete"),
    "callout": ("IfcAnnotation", None, None),
    "detail": ("IfcAnnotation", None, None),
}
MEMBER_TYPES = ("beam", "column", "wood-member", "post", "hss-member", "stringer", "stud", "footing", "grade-beam", "pile")


def ifc_of(e: dict) -> dict:
    cls, ptype, material = IFC_MAP[e["type"]]
    if e["type"] == "post" and "ABOVE" in e["fields"].get("note", "").upper():
        cls, ptype = "IfcColumn", "COLUMN"
    annot = cls == "IfcAnnotation"
    return {"class": cls, "predefinedType": ptype, "material": material,
            "objectType": e["fields"].get("size"),  # IfcObject.ObjectType: the section / mark as drawn
            "storey": None if annot or e["level"] in ("Elevation", "Details") else e["level"],  # IfcBuildingStorey.Name
            "typeClass": None if annot else f"{cls}Type"}


def system_of(e: dict) -> str:
    t, s = e["type"], e["sheet"]
    if t == "callout":
        return "Callouts"
    if t == "detail":
        for pre, name in (("S0", "General notes"), ("S2", "Plans"), ("S3", "Moment frame elevations"),
                          ("S4.0.1", "Exterior wall elevations"), ("S4.0.2", "Exterior wall elevations"), ("S4", "Wall sections"),
                          ("S5", "Enlarged plans & details"), ("S8.0", "Concrete & foundation details"), ("S8.2", "Steel details"),
                          ("S8.4", "Metal stud details"), ("S8.6", "Wood details"), ("S8.8", "Stair details")):
            if s.startswith(pre):
                return name
        return "Details"
    if s == "S3.0.1":
        return "Moment frames (SMF)"
    if s in ("S4.0.1", "S4.0.2"):
        return "Exterior walls"
    if s == "S5.0.1":
        return "Stair framing"
    if s == "S5.0.2" and t not in ("footing", "grade-beam", "pile"):
        return "Elevator framing"
    if t in ("footing", "grade-beam", "pile"):
        return "Foundations"
    if s == "S5.0.3" or (t == "wood-member" and e["level"] == "Roof"):
        return "Wood trellis"
    if t == "wood-member":
        return "Wood framing"
    if t in ("column", "post"):
        return "Columns & posts"
    return "Steel framing"


def zone_of(e: dict) -> str:
    """Top of the index hierarchy: the storey for plan members, the system for elevations, 'Details' for annotations."""
    if e["type"] in ("callout", "detail"):
        return "Details & callouts"
    if e["level"] == "Elevation":
        return "Moment frames" if e["sheet"] == "S3.0.1" else "Exterior walls"
    return e["level"]


def foundation_schedule(page, view_right):
    """S2.0.1 schedules (pad / pile / grade beam): mark -> the values on its row, in column order."""
    lines = lines_of(page)
    out = {}
    for l in lines:
        if l["bbox"][0] > view_right and FOUND_RE.match(l["text"]):
            y = (l["bbox"][1] + l["bbox"][3]) / 2
            vals = [m["text"] for m in sorted(lines, key=lambda m: m["bbox"][0])
                    if m is not l and l["bbox"][2] < m["bbox"][0] < l["bbox"][0] + 340 and abs((m["bbox"][1] + m["bbox"][3]) / 2 - y) < 4]
            out[l["text"]] = vals
    return out


def ft(s: str) -> float | None:
    m = re.match(r"(\d+)\s*'\s*-\s*(\d+)", s or "")
    return int(m.group(1)) + int(m.group(2)) / 12 if m else None


def build_elements(docs, plans, s_pages):
    plan_doc = docs[0]
    label_to_page = {p["label"]: p["page"] for p in plan_doc["pages"]}
    elements, raw_callouts, views_by_sheet = [], defaultdict(list), {}
    schedule = {}
    for p in plan_doc["pages"]:
        sheet, sub_page = p["label"], p["page"]
        page = plans[s_pages[sub_page - 1]]
        views = find_views(page, sheet)
        views_by_sheet[sheet] = (sub_page, page, views)
        if sheet == "S2.0.1":
            fv = [v for v in views if "FOUNDATION PLAN" in v["title"]]
            schedule = foundation_schedule(page, fv[0]["right"] if fv else page.rect.width * 0.75)

    for sheet, (sub_page, page, views) in views_by_sheet.items():
        max_x = page.rect.width * 0.9
        words = page.get_text("words")
        for c in find_callouts(page, max_x, words):
            v = view_at(((c["rect"][0] + c["rect"][2]) / 2, (c["rect"][1] + c["rect"][3]) / 2), views)
            raw_callouts[(c["detail"], c["sheet"])].append(
                {"doc": "plans", "page": sub_page, "sheet": sheet, "view": (v["title"] if v else "").title(),
                 "level": level_of_view(v["title"], sheet) if v and sheet in MEMBER_SHEETS else "Details",
                 "rect": norm_rect(pad(c["rect"], 6), page), "text": f'{c["detail"]}/{c["sheet"]}'})
        if sheet not in MEMBER_SHEETS:
            continue
        grids = grid_lines(page, views)
        lines = lines_of(page)
        clines = char_lines(page)
        found = []
        for l in clines:
            text = l["text"]
            if len(text) > 44:  # notes, not labels
                continue
            ms = list(MEMBER_RE.finditer(text))
            for i, m in enumerate(ms):
                size = m.group(1)
                lead = text[:m.start()].replace(SMF_MARK, " ").strip()
                if WOOD_RE.match(size) and lead not in ("", "(2)", "(3)"):
                    continue
                if not WOOD_RE.match(size) and lead and not re.fullmatch(r"\(\d\)", lead) and i == 0 and not text.startswith(SMF_MARK):
                    continue  # a shape mentioned in a sentence, not a label
                end = ms[i + 1].start() if i + 1 < len(ms) else len(text)
                follow = text[m.end():end].replace(SMF_MARK, " ").strip()
                bbox = union([c["bbox"] for c in l["chars"][m.start():m.end()]])
                found.append({"size": size, "qty": lead if re.fullmatch(r"\(\d\)", lead) else "", "follow": follow,
                              "bbox": bbox, "dir": l["dir"], "line": l, "solo": len(ms) == 1})
        for f in found:
            x0, y0, x1, y1 = f["bbox"]
            follow = f["follow"]
            if not follow and f["solo"]:  # label may be split onto a neighbouring line (e.g. "C12x20.7" + "STRINGER (BENT)")
                lb = f["line"]["bbox"]
                for m in lines:
                    if m["dir"] != f["dir"] or m["bbox"] == lb:
                        continue
                    if f["dir"] == (0, -1) and abs(m["bbox"][0] - lb[2]) < 14 and m["bbox"][1] < lb[3] and m["bbox"][3] > lb[1]:
                        follow = m["text"]
                    elif f["dir"] == (1, 0) and abs(m["bbox"][1] - lb[3]) < 14 and m["bbox"][0] < lb[2] and m["bbox"][2] > lb[0]:
                        follow = m["text"]
                if MEMBER_RE.search(follow or ""):
                    follow = ""
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            view = view_at((cx, cy), views)
            if view is None or re.search(r"DETAIL", view["title"]):
                continue
            orient = "v" if f["dir"][1] != 0 else "h"
            size = f["size"]
            mtype = member_type(size, follow, sheet, orient)
            level = level_of_view(view["title"], sheet)
            grid = grid_label((cx, cy), grids.get(view["ref"]), view)
            near = " ".join(m["text"] for m in lines if abs((m["bbox"][0] + m["bbox"][2]) / 2 - cx) < 60
                            and abs((m["bbox"][1] + m["bbox"][3]) / 2 - cy) < 30 and m["bbox"] != f["line"]["bbox"])[:160]
            tag = size
            if mtype in ("stringer", "post"):
                tag = (size + " " + follow).strip()
            elif mtype == "stud":
                tag = " ".join(x for x in (f["qty"], size, follow) if x)
            elements.append({
                "sheet": sheet, "level": level, "view": view["title"].title(), "viewRef": view["ref"], "type": mtype, "tag": tag,
                "fields": {"size": size, "orientation": orient, "grid": grid, "note": follow, "nearbyText": near,
                           **({"qty": f["qty"]} if f["qty"] else {})},
                "_pt": (cx, cy), "_y": cy,
                "occurrences": [{"doc": "plans", "page": sub_page, "sheet": sheet, "view": view["title"].title(), "level": level,
                                 "rect": norm_rect(pad(f["bbox"], 3), page), "text": f["line"]["text"].replace(SMF_MARK, " ").strip()}],
            })
        # footings, grade beams, piles (marks inside a foundation plan view)
        for l in lines:
            if not FOUND_RE.match(l["text"]):
                continue
            cx, cy = (l["bbox"][0] + l["bbox"][2]) / 2, (l["bbox"][1] + l["bbox"][3]) / 2
            view = view_at((cx, cy), views)
            if view is None or "FOUNDATION" not in view["title"]:
                continue
            mark = l["text"]
            mtype = "footing" if mark.startswith("F") else "grade-beam" if mark.startswith("GB") else "pile"
            sch = schedule.get(mark, [])
            fields = {"size": mark, "orientation": "v" if l["dir"][1] != 0 else "h",
                      "grid": grid_label((cx, cy), grids.get(view["ref"]), view), "note": "", "nearbyText": "", "schedule": sch}
            if mtype == "footing" and len(sch) >= 3:
                fields.update({"length": sch[0], "width": sch[1], "thickness": sch[2], "reinforcing": " ".join(sch[3:])})
            elif mtype == "pile" and len(sch) >= 2:
                fields.update({"diameter": sch[0], "depth": sch[1], "reinforcing": " ".join(sch[2:])})
            elif mtype == "grade-beam" and len(sch) >= 2:
                fields.update({"width": sch[0], "thickness": sch[1], "reinforcing": " ".join(sch[2:])})
            elements.append({
                "sheet": sheet, "level": "Foundation", "view": view["title"].title(), "viewRef": view["ref"], "type": mtype, "tag": mark,
                "fields": fields, "_pt": (cx, cy), "_y": cy,
                "occurrences": [{"doc": "plans", "page": sub_page, "sheet": sheet, "view": view["title"].title(), "level": "Foundation",
                                 "rect": norm_rect(pad(l["bbox"], 3), page), "text": mark}],
            })

        # exterior wall elevations: studs are drawn as schedule marks (J1 jamb, H1 header) keyed to the stud / jamb /
        # header schedules beside the views; the typical stud (ST-1) is only in the schedule
        if sheet in ("S4.0.1", "S4.0.2"):
            vright = max(v["right"] for v in views)
            sched = {}
            for l in lines:
                if l["bbox"][0] > vright and re.fullmatch(r"ST-\d|J\d|H\d", l["text"]):
                    y = (l["bbox"][1] + l["bbox"][3]) / 2
                    row = sorted([m for m in lines if m is not l and l["bbox"][2] < m["bbox"][0] < l["bbox"][0] + 260
                                  and abs((m["bbox"][1] + m["bbox"][3]) / 2 - y) < 4], key=lambda m: m["bbox"][0])
                    stud = next((m for m in row if re.search(r"\d{3}S\d{3}-\d+", m["text"])), None)
                    track = next((m for m in row if re.search(r"\d{3}T\d{3}-\d+", m["text"])), None)
                    if stud:
                        mm = re.search(r"(\(\d\))?\s*(\d{3}S\d{3}-\d+)\s*(.*)", stud["text"])
                        sched[l["text"]] = {"qty": mm.group(1) or "", "size": mm.group(2), "spacing": mm.group(3).strip(),
                                            "track": track["text"] if track else "", "text": stud["text"],
                                            "bbox": union([l["bbox"], stud["bbox"]] + ([track["bbox"]] if track else []))}
            kind = {"ST": "typical stud", "J": "jamb studs", "H": "header"}
            for mark, s in sched.items():
                if not mark.startswith("ST"):
                    continue
                elements.append({
                    "sheet": sheet, "level": "Elevation", "view": "Exterior Wall Stud Schedule", "viewRef": None, "type": "stud",
                    "tag": f"{mark} – {s['text']}", "fields": {"size": s["size"], "mark": mark, "role": kind["ST"], "spacing": s["spacing"],
                                                               "orientation": "h", "grid": "schedule", "note": "schedule", "nearbyText": ""},
                    "_pt": ((s["bbox"][0] + s["bbox"][2]) / 2, (s["bbox"][1] + s["bbox"][3]) / 2), "_y": s["bbox"][1],
                    "occurrences": [{"doc": "plans", "page": sub_page, "sheet": sheet, "view": "Exterior Wall Stud Schedule", "level": "Elevation",
                                     "rect": norm_rect(pad(s["bbox"], 3), page), "text": f"{mark} {s['text']}"}]})
            for l in lines:
                m = re.fullmatch(r"(J\d|H\d)( BEYOND)?", l["text"])
                if not m or m.group(1) not in sched:
                    continue
                cx, cy = (l["bbox"][0] + l["bbox"][2]) / 2, (l["bbox"][1] + l["bbox"][3]) / 2
                view = view_at((cx, cy), views)
                if view is None:
                    continue
                s, mark = sched[m.group(1)], m.group(1)
                elements.append({
                    "sheet": sheet, "level": "Elevation", "view": view["title"].title(), "viewRef": view["ref"], "type": "stud",
                    "tag": f"{mark} – {s['text']}",
                    "fields": {"size": s["size"], "mark": mark, "role": kind[mark[0]], "qty": s["qty"], "track": s["track"],
                               "orientation": "v" if l["dir"][1] != 0 else "h", "grid": grid_label((cx, cy), grids.get(view["ref"]), view),
                               "note": (m.group(2) or "").strip(), "nearbyText": ""},
                    "_pt": (cx, cy), "_y": cy,
                    "occurrences": [{"doc": "plans", "page": sub_page, "sheet": sheet, "view": view["title"].title(), "level": "Elevation",
                                     "rect": norm_rect(pad(l["bbox"], 3), page), "text": l["text"]}]})

    # SMF elevations: the upper beam line in each frame is the roof, the lower one Level 2
    by_view = defaultdict(list)
    for e in elements:
        if e["sheet"] == "S3.0.1" and e["type"] == "beam":
            by_view[e["viewRef"]].append(e)
    for es in by_view.values():
        ys = sorted({round(e["_y"]) for e in es})
        mid = (ys[0] + ys[-1]) / 2 if ys else 0
        for e in es:
            e["fields"]["floor"] = "Roof" if len(ys) > 1 and e["_y"] < mid else "Level 2" if len(ys) > 1 else ""

    # stable, content-based ids: level / type / grid / orientation (+ ordinal for same bay). The same member drawn on
    # two sheets (e.g. the roof plan and the enlarged elevator roof plan) is one element with two occurrences.
    seen, merged, out = defaultdict(int), {}, []
    elements.sort(key=lambda e: (e["sheet"], e["view"], e["_pt"][1], e["_pt"][0]))
    for e in elements:
        grid = e["fields"]["grid"]
        base = f'{slug(e["level"])}/{e["type"]}/{grid.replace("/", "@")}/{e["fields"]["orientation"]}'
        if e["fields"].get("floor"):
            base += "/" + slug(e["fields"]["floor"])
        key = (base, e["fields"]["size"].upper())
        if key in merged and merged[key]["sheet"] != e["sheet"] and not any(o["sheet"] == e["sheet"] for o in merged[key]["occurrences"]):
            merged[key]["occurrences"] += e["occurrences"]
            continue
        seen[base] += 1
        e["id"] = base if seen[base] == 1 else f"{base}#{seen[base]}"
        e["grid"] = grid
        e["fingerprint"] = sha(json.dumps([e["type"], e["fields"]["size"], e["grid"], e["view"]]))
        merged.setdefault(key, e)
        out.append(e)
    elements = out
    for e in elements:
        e.pop("_pt")
        e.pop("_y")

    # detail views: one element per titled view, clickable on its title bar, covering the area above it
    detail_ids = {}
    for sheet, (sub_page, page, views) in views_by_sheet.items():
        for v in sorted(views, key=lambda v: (v["rect"][1], v["rect"][0])):
            did = f'detail/{v["num"]}-{sheet}'
            detail_ids[(v["num"], sheet)] = (did, norm_rect(v["rect"], page), v["title"])
            elements.append({
                "id": did, "sheet": sheet, "level": "Details", "view": v["title"].title(), "viewRef": v["ref"], "type": "detail",
                "tag": f'Detail {v["num"]}/{sheet}', "grid": None,
                "fields": {"detail": v["num"], "sheet": sheet, "title": v["title"]},
                "fingerprint": sha(f'{v["ref"]}|{v["title"]}'),
                "occurrences": [{"doc": "plans", "page": sub_page, "sheet": sheet, "view": v["title"].title(), "level": "Details",
                                 "rect": norm_rect(v["rect"], page), "hot": norm_rect(pad(v["bar"], 4), page), "text": v["title"]}],
            })

    for (detail, sheet), occs in sorted(raw_callouts.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        target = label_to_page.get(sheet)
        tgt = detail_ids.get((detail, sheet))
        if tgt:
            refs = [{"doc": "plans", "page": target, "sheet": sheet, "title": tgt[2], "detail": tgt[0], "rect": tgt[1]}]
        elif target:
            refs = [{"doc": "plans", "page": target, "sheet": sheet, "title": docs[0]["pages"][target - 1]["title"]}]
        else:
            refs = []
        occs = sorted(occs, key=lambda o: (o["page"], o["rect"][1], o["rect"][0]))
        elements.append({
            "id": f"callout/{detail}-{sheet}", "sheet": occs[0]["sheet"], "level": "Details",
            "view": occs[0]["view"], "type": "callout", "tag": f"Detail {detail}/{sheet}", "grid": None,
            "fields": {"detail": detail, "targetSheet": sheet, "count": len(occs), "targetTitle": tgt[2] if tgt else None,
                       "fromSheets": sorted({o["sheet"] for o in occs})},
            "fingerprint": sha(f"{detail}/{sheet}"),
            "occurrences": occs, "refs": refs,
        })
    for e in elements:
        e["ifc"] = ifc_of(e)
        e["system"] = system_of(e)
        e["zone"] = zone_of(e)
    return elements


def build_groups(elements):
    """Typical groups: members of one size on one level. Linked as a group when the calc only names the size."""
    by = defaultdict(list)
    for e in elements:
        if e["type"] in MEMBER_TYPES:
            by[(e["level"], e["type"], e["fields"]["size"].upper())].append(e)
    groups = []
    for (level, t, size), members in sorted(by.items()):
        gid = f"group/{slug(level)}/{t}/{size}"
        for m in members:
            m["group"] = gid
        i = members[0]["ifc"]
        noun = {"wood-member": "wood member", "hss-member": "HSS member", "grade-beam": "grade beam"}.get(t, t)
        groups.append({"id": gid, "level": level, "type": t, "size": size, "system": members[0]["system"],
                       "sheets": sorted({o["sheet"] for m in members for o in m["occurrences"]}),
                       # a typical group is one IFC type object (e.g. IfcBeamType "W12X14") its members are typed by
                       "ifc": {"typeClass": i["typeClass"], "predefinedType": i["predefinedType"], "name": size,
                               "material": i["material"], "storey": i["storey"]},
                       "title": f"{level} {noun}s {size} (typ.)" if len(members) > 1 else f"{level} {noun} {size}",
                       "members": [m["id"] for m in members]})
    return groups


# ---------------------------------------------------------------- calcs
def merge_regions(regions, pages):
    """Split a page-ordered list of regions into spans: regions run on when they hit the page bottom and the
    next starts at the top of the following page. A region marked _break always starts a new span."""
    spans, cur = [], []
    for r in regions:
        if cur:
            prev = cur[-1]
            ph = pages[prev["page"] - 1].rect.height
            touching = (r["page"] == prev["page"] + 1 and prev["_y1"] > ph * 0.85 and r["_y0"] < pages[r["page"] - 1].rect.height * 0.2)
            if not touching or r.get("_break"):
                spans.append(cur)
                cur = []
        cur.append(r)
    if cur:
        spans.append(cur)
    out = []
    for s in spans:
        out.append({"title": s[0].get("_title"), "regions": [{k: v for k, v in r.items() if not k.startswith("_")} for r in s],
                    "textHash": sha("".join(r["_text"] for r in s))})
    return out


def region(doc_id, pages, pno, y0, y1, title=None, full=False, brk=False):
    page = pages[pno - 1]
    clip = pymupdf.Rect(0, y0, page.rect.width, y1)
    return {"doc": doc_id, "page": pno, "rect": norm_rect((24, y0, page.rect.width - 24, y1), page),
            **({"fullPage": True} if full else {}), "_y0": y0, "_y1": y1, "_title": title, "_break": brk,
            "_text": page.get_text(clip=clip)}


def full_page_region(doc_id, pages, pno, title=None, brk=False):
    page = pages[pno - 1]
    return region(doc_id, pages, pno, 20, page.rect.height - 20, title, full=True, brk=brk)


def full_pages(doc_id, pages, a, b, title=None, brk=True):
    """Full-page regions for pages a..b; the first one starts a new span (brk) and carries the title."""
    return [full_page_region(doc_id, pages, p, title if p == a else None, brk=brk and p == a) for p in range(a, b + 1)]


def header_y(page, pattern):
    for l in lines_of(page):
        if re.search(pattern, l["text"]):
            return l["bbox"][1]
    return None


def risa_level_regions(calcs, level="Roof", first=37, last=78):
    """RISAFloor sketch pages and table sections for one level."""
    regs = []
    for pno in range(first, last + 1):
        page = calcs[pno - 1]
        lines = lines_of(page)
        txt = page_text(page)
        if "Company" not in txt[:200]:  # sketch page
            if re.search(rf"\b{re.escape(level)}\s+SK\b", txt):
                t = next((l["text"] for l in lines if l["text"].startswith(level + "_")), f"{level} sketch")
                regs.append(full_page_region("calcs", calcs, pno, t.replace("_", " – ")))
            continue
        heads = [l for l in lines if re.search(r" : (Roof|Level 2)( \(Continued\))?$", l["text"])]
        bottom = content_bottom(page)
        for i, h in enumerate(heads):
            if f": {level}" not in h["text"]:
                continue
            y0 = h["bbox"][1] - 3
            y1 = heads[i + 1]["bbox"][1] - 4 if i + 1 < len(heads) else bottom
            regs.append(region("calcs", calcs, pno, y0, y1, h["text"].replace(" (Continued)", "")))
    return regs


def enercalc_calcs(doc_id, pdf, first, last):
    """Group consecutive ENERCALC printouts by DESCRIPTION (axis variants of one member merge)."""
    items = []
    for pno in range(first, last + 1):
        t = " ".join(pdf[pno - 1].get_text().split())
        m = re.search(r"DESCRIPTION:\s*(.+?)\s+(Software|Project File|Lic)", t)
        if not m:
            continue
        desc = m.group(1)
        base = re.sub(r"\s*\((strong|weak) ax\w*\)|\s*\(cont\)", "", desc, flags=re.I).strip()
        if items and items[-1]["base"] == base and items[-1]["pages"][-1] == pno - 1:
            items[-1]["pages"].append(pno)
        else:
            items.append({"base": base, "pages": [pno]})
    return items


SIZE_TEXT_RE = re.compile(r"\b(W\d{1,2}X\d{2,3}|MC\d{1,2}X[\d.]+|C\d{1,2}X\d{1,2}(?:\.\d)?|HSS[\dX/.]+|\d{3}S\d{3}-\d{2,3})\b", re.I)


def calc_record(cid, title, doc_id, pdf, regions, category, role_hint, extra=None):
    spans = merge_regions(regions, pdf)
    labels = [p for p in DOC_LABELS[doc_id]]
    pages = [r["page"] for s in spans for r in s["regions"]]
    sheets = [labels[p - 1] for p in pages if labels[p - 1]]
    text = "".join(r["_text"] for r in regions)
    sizes = sorted(set(m.upper() for m in SIZE_TEXT_RE.findall(text)))
    refs = sorted(set(re.findall(r"\b(\d{1,2}[A-Z]?/S\d\.\d\.\d{1,2})\b", text)))
    rec = {"id": cid, "title": title, "doc": doc_id, "category": category, "roleHint": role_hint,
           "sheetRange": (f"{sheets[0]}–{sheets[-1]}" if len(set(sheets)) > 1 else (sheets[0] if sheets else None)),
           "pageRange": [min(pages), max(pages)], "spans": spans,
           "fields": {"sizes": sizes, "detailRefs": refs, **(extra or {})},
           "fingerprint": sha("".join(s["textHash"] for s in spans))}
    return rec


DOC_LABELS: dict[str, list] = {}
CALC_GRIDS = "1, 1.3, 1.8, 2, 2.5, 3, 4, 5 / A, A.5, B, B.2, B.5, C, C.8, D, E"


def build_calcs(docs, calcs, stair):
    for d in docs:
        DOC_LABELS[d["id"]] = [p["label"] for p in d["pages"]]
    out = []
    C = lambda *a, **k: out.append(calc_record(*a, **k))

    C("general/cover-toc", "Cover & table of contents", "calcs", calcs, full_pages("calcs", calcs, 1, 2, "Cover & contents"),
      "General", "reference", {"software": "–"})

    # ---- A. Loading criteria
    p3 = calcs[2]
    lines = lines_of(p3)
    start = next(l for l in lines if l["text"].startswith("Flat Roof"))
    nxt = [l for l in lines if l["bbox"][1] > start["bbox"][3] + 4 and l["bbox"][0] < 120 and l["size"] >= start["size"] - 0.5]
    y1 = nxt[0]["bbox"][1] - 4 if nxt else content_bottom(p3)
    C("loads/roof-dead-live", "Roof dead & live loads (flat roof)", "calcs", calcs,
      [region("calcs", calcs, 3, start["bbox"][1] - 4, y1, "Flat Roof loads")], "Loading criteria", "loads",
      {"software": "hand/Excel", "level": "Roof"})
    C("loads/floor-dead-live", "Floor dead & live loads (Level 2)", "calcs", calcs,
      [region("calcs", calcs, 4, 20, content_bottom(calcs[3]), "Floor in building")], "Loading criteria", "loads",
      {"software": "hand/Excel", "level": "Level 2", "sheetHeader": "Dana Point Harbor (Bldg 10)"})
    C("loads/balcony-dead-live", "Exterior balcony dead & live loads", "calcs", calcs,
      [region("calcs", calcs, 5, 20, content_bottom(calcs[4]), "Exterior balcony")], "Loading criteria", "loads",
      {"software": "hand/Excel", "level": "Level 2", "sheetHeader": "Dana Point Harbor (Bldg 10)"})
    C("loads/wall-types", "Exterior wall type weights", "calcs", calcs,
      [region("calcs", calcs, 6, 20, content_bottom(calcs[5]), "Wall type breakdown")], "Loading criteria", "loads",
      {"software": "hand/Excel"})
    C("loads/tsunami", "Tsunami basis of design & loads", "calcs", calcs, full_pages("calcs", calcs, 7, 22, "Tsunami"),
      "Loading criteria", "loads", {"software": "hand", "code": "ASCE 7-16 Ch. 6"})

    # ---- B. Gravity framing (RISAFloor)
    C("gravity/roof-risafloor", "Roof gravity framing – RISAFloor model", "calcs", calcs,
      risa_level_regions(calcs, "Roof", 23, 78), "Gravity framing design", "design",
      {"software": "RISAFloor", "level": "Roof", "model": "2021-03-22_Bldg 12.rfl", "gridSystem": CALC_GRIDS})
    C("gravity/level2-risafloor", "Level 2 gravity framing – RISAFloor model", "calcs", calcs,
      risa_level_regions(calcs, "Level 2", 23, 78), "Gravity framing design", "design",
      {"software": "RISAFloor", "level": "Level 2", "model": "2021-03-22_Bldg 12.rfl", "gridSystem": CALC_GRIDS})
    p96 = calcs[95]
    hy = header_y(p96, r"^Hot Rolled Steel Column Code Checks")
    C("gravity/columns", "Gravity columns – RISAFloor forces & code checks", "calcs", calcs,
      full_pages("calcs", calcs, 79, 95, "Column forces / moments") +
      [region("calcs", calcs, 96, 20, hy - 4), region("calcs", calcs, 96, hy - 3, content_bottom(p96), "Hot-rolled steel column code checks", brk=True),
       full_page_region("calcs", calcs, 97)],
      "Gravity framing design", "design", {"software": "RISAFloor", "model": "2021-03-22_Bldg 12.rfl", "gridSystem": CALC_GRIDS})

    # ---- C. Lateral (RISA-3D, steel special moment frames)
    C("lateral/model-sketches", "Lateral model sketches – nodes, members, member sizes", "calcs", calcs,
      full_pages("calcs", calcs, 98, 99, "Node & member labels") + full_pages("calcs", calcs, 105, 105, "Member sizes (SK-5)")
      + full_pages("calcs", calcs, 107, 107, "SK-6"), "Lateral design", "reference",
      {"software": "RISA-3D", "model": "2021-03-22_Bldg 12.rfl"})
    C("lateral/seismic-loads", "Seismic loads – ELF base shear & distribution (SMF, R = 8)", "calcs", calcs,
      full_pages("calcs", calcs, 100, 104, "Seismic generation & base shear"), "Lateral design", "loads",
      {"software": "RISA-3D + Excel", "system": "Steel special moment frame"})
    C("lateral/drift-check", "SMF story drift check", "calcs", calcs, full_pages("calcs", calcs, 106, 106, "Drift check (C9)"),
      "Lateral design", "design", {"software": "Excel", "frames": ["1.3", "2.5", "4", "A", "B", "D"], "gridSystem": CALC_GRIDS})
    C("lateral/risa3d-input", "RISA-3D lateral model – input", "calcs", calcs, full_pages("calcs", calcs, 108, 121, "Model input"),
      "Lateral design", "reference", {"software": "RISA-3D", "model": "2021-03-22_Bldg 12.rfl"})
    p185 = calcs[184]
    ay = header_y(p185, r"^Envelope AISC 15TH")
    C("lateral/risa3d-results", "RISA-3D lateral model – reactions & displacements", "calcs", calcs,
      full_pages("calcs", calcs, 122, 184, "Reactions & displacements") + [region("calcs", calcs, 185, 20, ay - 4)],
      "Lateral design", "reference", {"software": "RISA-3D"})
    C("lateral/smf-code-checks", "SMF member code checks – AISC 360-16 (RISA-3D)", "calcs", calcs,
      [region("calcs", calcs, 185, ay - 3, content_bottom(p185), "AISC member steel code checks", brk=True),
       full_page_region("calcs", calcs, 186)], "Lateral design", "design",
      {"software": "RISA-3D", "system": "Steel special moment frame"})

    # ---- D. Foundation (RISAFoundation)
    fc_page = next(p for p in range(188, 206) if header_y(calcs[p - 1], r"^Footing Code Check$") is not None)
    fy = header_y(calcs[fc_page - 1], r"^Footing Code Check$")
    C("foundation/risafoundation-model", "Foundation – RISAFoundation sketch & input", "calcs", calcs,
      full_pages("calcs", calcs, 187, 187, "Footing sketch (joint labels)") + full_pages("calcs", calcs, 188, fc_page - 1, "Model input")
      + [region("calcs", calcs, fc_page, 20, fy - 4)], "Foundation design", "reference",
      {"software": "RISAFoundation", "gridSystem": CALC_GRIDS})
    C("foundation/footing-results", "Foundation – footing code checks, geometry & soil pressures", "calcs", calcs,
      [region("calcs", calcs, fc_page, fy - 3, content_bottom(calcs[fc_page - 1]), "Footing results", brk=True)]
      + [full_page_region("calcs", calcs, p) for p in range(fc_page + 1, 205)], "Foundation design", "design",
      {"software": "RISAFoundation", "footingTypes": ["Lateral Ext. Ftn'g.", "Gravity Ftn'g."]})
    C("foundation/beam-results", "Foundation – beam & strip results (no data)", "calcs", calcs,
      full_pages("calcs", calcs, 205, 205, "Beams / strips"), "Foundation design", "reference", {"software": "RISAFoundation"})

    # ---- E. Exterior metal studs
    C("studs/wind-cc", "Wind components & cladding pressures (studs)", "calcs", calcs,
      full_pages("calcs", calcs, 206, 207, "Wind coefficients") + full_pages("calcs", calcs, 212, 214, "Wind modules (Simpson)"),
      "Exterior metal studs", "loads", {"software": "Excel + Simpson CFS Designer", "code": "ASCE 7-16 Ch. 30"})
    C("studs/opening-a-1-s4.0.1", "CFS opening A – 1/S4.0.1 (studs, header, jambs)", "calcs", calcs,
      full_pages("calcs", calcs, 208, 209, "Opening A – 1/S4.0.1"), "Exterior metal studs", "design", {"software": "Simpson CFS Designer"})
    C("studs/opening-b-2-s4.0.2", "CFS opening B – 2/S4.0.2 (studs, header, jambs)", "calcs", calcs,
      full_pages("calcs", calcs, 210, 211, "Opening B – 2/S4.0.2"), "Exterior metal studs", "design", {"software": "Simpson CFS Designer"})
    C("studs/typical-studs", "Typical exterior studs 600S162-54 @ 16\" o.c.", "calcs", calcs,
      full_pages("calcs", calcs, 215, 216, "Typ stud – windward") + full_pages("calcs", calcs, 217, 218, "Typ stud – leeward")
      + full_pages("calcs", calcs, 219, 220, "Typ stud – uniform") + full_pages("calcs", calcs, 221, 221, "Typ stud – simple"),
      "Exterior metal studs", "design", {"software": "Simpson CFS Designer"})
    C("studs/high-parapet-mep-well", "High parapet studs (MEP well)", "calcs", calcs,
      full_pages("calcs", calcs, 222, 223, "High parapet (MEP well)"), "Exterior metal studs", "design", {"software": "Simpson CFS Designer"})
    for it in enercalc_calcs("calcs", calcs, 224, 238):
        regs = [full_page_region("calcs", calcs, p, it["base"]) for p in it["pages"]]
        C(f"studs/{slug(it['base'])}", it["base"].replace(" - ", " – "), "calcs", calcs, regs,
          "Exterior metal studs", "design", {"software": "ENERCALC"})

    # ---- Stair & parapet package (2023)
    C("stair/cover", "Stair & parapet package – cover", "stair", stair, [full_page_region("stair", stair, 1, "Cover")],
      "General", "reference", {"software": "–"})
    C("stair/grid-6-e-f", "Stair at grid 6 / E–F (MV-NS) – stair design", "stair", stair,
      [full_page_region("stair", stair, p) for p in range(2, 9)], "Stair design", "design",
      {"software": "hand + ENERCALC", "grids": ["6", "E", "F", "MV-NS"]})
    C("stair/grid-5-a", "Stair at grid 5 / A – stair design", "stair", stair,
      [full_page_region("stair", stair, p) for p in range(9, 15)], "Stair design", "design",
      {"software": "hand + ENERCALC", "grids": ["5", "4", "A"]})
    C("parapet/hss-posts", "Parapet design – HSS posts (grid B & 4)", "stair", stair,
      [full_page_region("stair", stair, p) for p in range(15, 21)], "Parapet design", "design",
      {"software": "hand + ENERCALC", "grids": ["B", "4"]})
    return out


# ---------------------------------------------------------------- matching
def band(c):
    return "high" if c >= 0.75 else "medium" if c >= 0.5 else "low"


def hits_in(pdf, doc_id, calc, needle, limit=80):
    found = []
    for s_i, s in enumerate(calc["spans"]):
        for r in s["regions"]:
            page = pdf[r["page"] - 1]
            W, H = page.rect.width, page.rect.height
            ry0, ry1 = r["rect"][1] * H, r["rect"][3] * H
            for q in page.search_for(needle):
                if ry0 - 2 <= q.y0 and q.y1 <= ry1 + 2:
                    found.append({"doc": doc_id, "page": r["page"], "span": s_i, "rect": norm_rect(pad(q, 1.5), page),
                                  "text": needle})
                    if len(found) >= limit:
                        return found
    return found


_CALC_CALLOUTS: dict = {}


def find_calc_callouts(pdf, doc_id, calc):
    """Callouts drawn inside calc sketches (same 'number over sheet' pattern as the drawings)."""
    if calc["id"] in _CALC_CALLOUTS:
        return _CALC_CALLOUTS[calc["id"]]
    out = []
    for s_i, s in enumerate(calc["spans"]):
        for r in s["regions"]:
            page = pdf[r["page"] - 1]
            for c in find_callouts(page, page.rect.width):
                out.append({"doc": doc_id, "page": r["page"], "span": s_i, "rect": norm_rect(pad(c["rect"], 3), page),
                            "text": f'{c["detail"]}/{c["sheet"]}'})
    _CALC_CALLOUTS[calc["id"]] = out
    return out


def evidence(n, kind, weight, origin=None, dest=None, note=None):
    e = {"n": n, "kind": kind, "weight": weight}
    if origin:
        e["origin"] = origin
    if dest:
        e["dest"] = dest
    if note:
        e["note"] = note
    return e


def first_occ(el):
    o = el["occurrences"][0]
    return {k: o[k] for k in ("doc", "page", "rect", "text")}


def at(h):
    return {k: h[k] for k in ("doc", "page", "rect", "text")} if h else None


def make_link(src_kind, src_id, calc, role, evid, hits, caveats, method):
    conf = round(max(0.05, min(0.97, sum(e["weight"] for e in evid))), 2)
    return {"id": f"{src_id}→{calc['id']}", "source": {"kind": src_kind, "id": src_id}, "calc": calc["id"],
            "role": role, "confidence": conf, "band": band(conf),
            "rationale": {"summary": None, "evidence": evid, "caveats": caveats},
            "hits": hits, "provenance": {"method": method, "matcher": MATCHER_VERSION, "at": TODAY,
                                         "summaryBy": None, "reviewed": None}}


def renumber(ev):
    for i, e in enumerate(ev):
        e["n"] = i + 1
    return ev


def risa_footings(pdf, calc):
    """RISAFoundation footing geometry rows: joint, type, length, width, thickness."""
    text = " ".join(pdf[p - 1].get_text() for p in range(calc["pageRange"][0], calc["pageRange"][1] + 1)).replace("\n", " ")
    i = text.find("Footing Geometry Results")
    rows = re.findall(r"(R3D_N\d+|FLR_1_N[\d._]+)\s+(Lateral Ext\.+|Gravity Ftn'g\.)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)", text[i:i + 6000])
    seen, out = set(), []
    for j, t, L, W, T in rows:
        if j in seen:
            continue
        seen.add(j)
        out.append({"joint": j, "type": "lateral" if t.startswith("Lateral") else "gravity", "L": float(L), "W": float(W), "T": float(T)})
    return out


def build_links(elements, groups, calcs_list, pdfs):
    by_id = {c["id"]: c for c in calcs_list}
    els = {e["id"]: e for e in elements}
    links = []
    P = pdfs["calcs"]

    # 1. Beam groups on the framing plans -> the RISAFloor model of their level (size + level; grids differ -> low)
    models = {"Roof": by_id["gravity/roof-risafloor"], "Level 2": by_id["gravity/level2-risafloor"]}
    for g in groups:
        if g["type"] != "beam" or g["level"] not in models:
            continue
        own, other_level = models[g["level"]], "Level 2" if g["level"] == "Roof" else "Roof"
        rep = els[g["members"][0]]
        needle = g["size"].upper()
        hits = hits_in(P, "calcs", own, needle)
        if hits:
            ev = [evidence(1, "size-match", 0.35, first_occ(rep), at(hits[0]),
                           f"{needle} appears {len(hits)}× in the {g['level']} model's member tables and sketches"),
                  evidence(2, "level-match", 0.15, None, None, f"Calc model level is '{g['level']}'; element is on the {g['level']} framing"),
                  evidence(3, "grid-conflict", -0.1, None, None,
                           "Calc grid system (1–5 / A–E incl. 1.3, 1.8, 2.5, B.2, B.5, C.8) does not match the plan's grids (1–6 / A–F)")]
            cav = [f"The 2021 RISAFloor {g['level']} model's layout and grid lines differ from the approved framing plan; "
                   "the link is by member size and level only.",
                   f"{len(g['members'])} {g['level']} members of this size share this calc (typical group)."]
            links.append(make_link("group", g["id"], own, "design", ev, hits, cav, "rules"))
        else:
            ohits = hits_in(P, "calcs", models[other_level], needle, limit=20)
            if ohits:
                ev = [evidence(1, "size-match", 0.25, first_occ(rep), at(ohits[0]),
                               f"{needle} not in the {g['level']} model; appears {len(ohits)}× in the {other_level} model"),
                      evidence(2, "level-conflict", -0.1, None, None, f"Calc level is {other_level}; element is on {g['level']}")]
                cav = [f"No {g['level']} calc designs {needle}. The nearest match is the {other_level} model, which is a different floor.",
                       "Likely missing or superseded calc – needs review."]
                links.append(make_link("group", g["id"], models[other_level], "design", ev, ohits, cav, "rules"))

    # 2. Loads by level: roof beams -> flat-roof loads; Level 2 beams -> floor loads (sheet headed "Bldg 10")
    for g in groups:
        if g["type"] != "beam" or g["level"] not in ("Roof", "Level 2"):
            continue
        rep = els[g["members"][0]]
        if g["level"] == "Roof":
            c = by_id["loads/roof-dead-live"]
            lh = hits_in(P, "calcs", c, "Flat Roof", limit=2)
            ev = [evidence(1, "load-source", 0.45, first_occ(rep), at(lh[0] if lh else None),
                           "Roof dead load table gives the superimposed loads carried by all roof framing"),
                  evidence(2, "level-match", 0.15, None, None, "Element is roof framing")]
            links.append(make_link("group", g["id"], c, "loads", ev, lh, [], "rules"))
        else:
            c = by_id["loads/floor-dead-live"]
            lh = hits_in(P, "calcs", c, "Floor In Bldg", limit=2) or hits_in(P, "calcs", c, "Floor", limit=2)
            bh = hits_in(P, "calcs", c, "Bldg 10", limit=2)
            ev = [evidence(1, "load-source", 0.45, first_occ(rep), at(lh[0] if lh else None),
                           "Floor dead load table gives the superimposed loads for deck, beams, girders and columns"),
                  evidence(2, "level-match", 0.15, None, None, "Element is Level 2 floor framing"),
                  evidence(3, "header-conflict", -0.15, None, at(bh[0] if bh else None),
                           "The load sheet is headed 'Dana Point Harbor (Bldg 10)', not Building 12")]
            cav = ["The floor and balcony load sheets (A2–A3) are headed 'Bldg 10' – probably carried over from another building's "
                   "package. Confirm the loads apply to Building 12."]
            links.append(make_link("group", g["id"], c, "loads", ev, lh + bh, cav, "rules"))

    # 3. Column groups (HSS columns on the plans) -> RISAFloor gravity column checks. RISA prints HSS names truncated
    #    (e.g. "HSS6X6X2"), so an HSS column matches on its nominal size (HSS6X6), not its wall thickness.
    colc = by_id["gravity/columns"]
    for g in groups:
        if g["type"] != "column" or g["level"] == "Elevation":
            continue
        rep = els[g["members"][0]]
        size = g["size"].upper()
        if size.startswith("HSS"):
            nominal = "X".join(size.split("X")[:2])
            hits = [h for h in hits_in(P, "calcs", colc, nominal + "X", limit=40) if h["span"] > 0] or hits_in(P, "calcs", colc, nominal + "X", limit=40)
            if not hits:
                continue
            ev = [evidence(1, "size-family", 0.2, first_occ(rep), at(hits[0]), f"{nominal} columns appear in the column code checks (wall thickness truncated in the table)"),
                  evidence(2, "member-family", 0.15, None, None, "Calc designs gravity columns; element is an HSS column on the plans"),
                  evidence(3, "grid-conflict", -0.1, None, None, "Calc column stacks are named by the calc grid system (e.g. A-1, B.2-1.3), not the plan grids")]
            cav = [f"RISAFloor truncates HSS names in the code-check table (e.g. '{nominal}X2'), so the wall thickness of {size} can't be confirmed from the calc.",
                   "Column stack labels use the 2021 model's grid system; the specific column can't be identified."]
        else:
            hits = hits_in(P, "calcs", colc, size, limit=40)
            if not hits:
                continue
            ev = [evidence(1, "size-match", 0.35, first_occ(rep), at(hits[0]), f"{size} appears {len(hits)}× in the column forces / code checks"),
                  evidence(2, "member-family", 0.15, None, None, "Calc designs gravity columns"),
                  evidence(3, "grid-conflict", -0.1, None, None, "Calc column stacks use the calc grid system")]
            cav = ["Column stack labels use the 2021 model's grid system; the specific column can't be identified."]
        links.append(make_link("group", g["id"], colc, "design", ev, hits, cav, "rules"))

    # 4. Special moment frames (S3.0.1) -> SMF code checks, drift check, seismic loads. Sizes differ from the calc.
    smfc, drift, seis = by_id["lateral/smf-code-checks"], by_id["lateral/drift-check"], by_id["lateral/seismic-loads"]
    calc_beams = sorted({s for s in smfc["fields"]["sizes"] if s.startswith("W")})
    drift_note = "W18x283 columns, W24x94 @ roof & W27x114 @ floor; W18x211 columns (W18x311 int. col. @ D/1.8), W21x83"
    for g in groups:
        if g["level"] != "Elevation" or "S3.0.1" not in g["sheets"]:
            continue
        rep = els[g["members"][0]]
        size = g["size"].upper()
        floors = sorted({els[m]["fields"].get("floor") for m in g["members"] if els[m]["fields"].get("floor")})
        fl = f" ({' & '.join(floors)})" if floors else ""
        if g["type"] == "beam":
            sh = hits_in(P, "calcs", smfc, size, limit=20)
            ev = [evidence(1, "system-match", 0.3, first_occ(rep), None,
                           "Element is drawn on the SMF elevations (S3.0.1); calc is the RISA-3D SMF member code check")]
            cav = []
            if sh:
                ev.append(evidence(2, "size-match", 0.35, None, at(sh[0]), f"{size} is checked in the SMF member table ({len(sh)}×)"))
            else:
                ev.append(evidence(2, "size-conflict", -0.1, None, None, f"Plan shows {size}{fl}; calc checks {', '.join(calc_beams)}"))
                cav.append(f"Size mismatch: S3.0.1 shows {size}{fl}, the SMF code checks size the beams {', '.join(calc_beams)}. "
                           "The calc (May 2021) and the approved elevations disagree – check which governs.")
            sh2 = sh or hits_in(P, "calcs", smfc, "AISC 15TH", limit=1)
            links.append(make_link("group", g["id"], smfc, "design", ev, sh2, cav, "rules"))
        dh = hits_in(P, "calcs", drift, size, limit=6)
        fh = hits_in(P, "calcs", drift, "DRIFT CHECK", limit=1)
        ev = [evidence(1, "system-match", 0.25, first_occ(rep), at(fh[0] if fh else None), "Drift check covers every SMF frame line")]
        cav = ["The drift check names its frames by the calc grid system (1.3, 2.5, 4, A, B, D); S3.0.1 draws the frames on plan grids 2, 5, E and B."]
        if dh:
            ev.append(evidence(2, "size-match", 0.35, None, at(dh[0]), f"Drift sheet note names {size}"))
        else:
            ev.append(evidence(2, "size-conflict", -0.1, None, None, f"Plan shows {size}{fl}; drift sheet note lists {drift_note}"))
            cav.append(f"Size mismatch: S3.0.1 {size}{fl} is not among the sizes the drift sheet lists ({drift_note}).")
        links.append(make_link("group", g["id"], drift, "design", ev, dh + fh, cav, "rules"))
        sh3 = hits_in(P, "calcs", seis, "Special Moment Frame", limit=2)
        ev = [evidence(1, "load-source", 0.45, first_occ(rep), at(sh3[0] if sh3 else None),
                       "Seismic base shear for a steel special moment frame (R = 8, Ie = 1.25) – the lateral load the SMF resists"),
              evidence(2, "system-match", 0.15, None, None, "Element is part of the SMF on S3.0.1")]
        links.append(make_link("group", g["id"], seis, "loads", ev, sh3, [], "rules"))

    # 5. Detail references: callouts and detail views -> calcs named for that detail (exact) or drawing it in a sketch
    for e in elements:
        if e["type"] not in ("callout", "detail"):
            continue
        ref = (f'{e["fields"]["detail"]}/{e["fields"]["targetSheet"]}' if e["type"] == "callout"
               else f'{e["fields"]["detail"]}/{e["fields"]["sheet"]}')
        for c in calcs_list:
            pdf = pdfs[c["doc"]]
            if ref in c["title"] or ref in c["fields"]["detailRefs"]:
                hits = hits_in(pdf, c["doc"], c, ref, limit=20)
                ev = [evidence(1, "detail-ref", 0.9, first_occ(e), at(hits[0] if hits else None), f"Calc is titled / labelled with detail {ref}")]
                cav = []
                if e["type"] == "detail" and c["id"].startswith("studs/hss-"):
                    drawn = sorted({x["fields"]["size"].upper() for x in elements if x.get("viewRef") == ref and x["type"] == "hss-member"})
                    designed = [s for s in c["fields"]["sizes"] if s.startswith("HSS")]
                    miss = [s for s in drawn if s not in designed]
                    if drawn and miss:
                        cav.append(f"HSS sizes drawn in this view ({', '.join(drawn)}) are not the size this calc checks "
                                   f"({', '.join(designed) or '–'}) – the header/jamb may not be labelled in the view, or the sizes changed.")
                links.append(make_link("element", e["id"], c, "design", ev, hits, cav, "rules"))
                continue
            drawn = [h for h in find_calc_callouts(pdf, c["doc"], c) if h["text"] == ref]
            if drawn:
                sheet = ref.split("/")[1]
                ev = [evidence(1, "callout-in-sketch", 0.6, first_occ(e), at(drawn[0]), f"Calc sketch shows callout {ref} at the same location"),
                      evidence(2, "sheet-ref", 0.15, None, None, f"Calc references sheet {sheet}")]
                links.append(make_link("element", e["id"], c, "design", ev, drawn, [], "rules"))

    # 6. Exterior wall elevations (S4.0.1/2): studs -> typical stud calc + their view's CFS opening calc; HSS members ->
    #    the ENERCALC calcs named for their view, when the size matches
    typ, wind, walls = by_id["studs/typical-studs"], by_id["studs/wind-cc"], by_id["loads/wall-types"]
    for g in groups:
        if g["type"] != "stud":
            continue
        rep = els[g["members"][0]]
        size = g["size"].upper()
        marks = sorted({els[m]["fields"].get("mark", "") for m in g["members"]})
        if any(m.startswith("ST") for m in marks):
            sh = hits_in(P, "calcs", typ, size, limit=10)
            ev = [evidence(1, "system-match", 0.25, first_occ(rep), None, f"Calc designs the typical exterior wall stud; element is the stud schedule's {', '.join(marks)}")]
            cav = []
            if sh:
                ev.append(evidence(2, "size-match", 0.35, None, at(sh[0]), f"{size} is the stud section designed (windward, leeward, uniform, simple spans)"))
            else:
                ev.append(evidence(2, "size-conflict", -0.1, None, None, f"Plan schedule shows {size}; calc designs other sections"))
                cav.append(f"{size} is not a section this calc designs.")
            links.append(make_link("group", g["id"], typ, "design", ev, sh, cav, "rules"))
            th = hits_in(P, "calcs", walls, "Studs", limit=2)
            links.append(make_link("group", g["id"], walls, "loads",
                                   [evidence(1, "load-source", 0.4, first_occ(rep), at(th[0] if th else None), "Wall type weights include the studs (2 psf) and the finishes the wall carries"),
                                    evidence(2, "system-match", 0.1, None, None, "Element is the exterior wall stud")], th, [], "rules"))
        wh = hits_in(P, "calcs", wind, "Wind", limit=2)
        links.append(make_link("group", g["id"], wind, "loads",
                               [evidence(1, "load-source", 0.45, first_occ(rep), at(wh[0] if wh else None), "Wind components & cladding pressures on the exterior walls"),
                                evidence(2, "system-match", 0.1, None, None, f"Element is exterior wall framing ({', '.join(marks)})")], wh, [], "rules"))
    for e in elements:
        if e["sheet"] not in ("S4.0.1", "S4.0.2") or e["type"] not in ("stud", "hss-member") or not e.get("viewRef"):
            continue
        for c in calcs_list:
            if e["viewRef"] not in c["title"]:
                continue
            is_cfs = c["id"].startswith("studs/opening")
            if (e["type"] == "stud") != is_cfs:
                continue
            size = e["fields"]["size"]
            sh = hits_in(P, "calcs", c, size, limit=6)
            ev = [evidence(1, "in-referenced-view", 0.3, first_occ(e), None, f"Element is drawn in view {e['viewRef']}, the view the calc is named for")]
            cav = []
            if sh:
                ev.append(evidence(2, "size-match", 0.35, None, at(sh[0]), f"{size} appears in the calc"))
            elif e["type"] == "stud":
                role = e["fields"].get("role", "stud")
                word = "Jamb" if role.startswith("jamb") else "Header"
                rh = hits_in(P, "calcs", c, word, limit=2)
                calc_studs = [s for s in c["fields"]["sizes"] if re.match(r"\d{3}S", s)]
                ev.append(evidence(2, "size-conflict", -0.1, None, at(rh[0] if rh else None),
                                   f"Plan {e['fields']['mark']} is {e['fields'].get('qty', '')} {size}; the calc's studs are {', '.join(calc_studs) or '–'}".replace("  ", " ")))
                cav.append(f"Size mismatch: the {role} {e['fields']['mark']} ({e['fields'].get('qty', '')} {size}) is not a section in this opening calc "
                           f"({', '.join(calc_studs) or '–'}) – check which governs.".replace("( ", "("))
                sh = rh
            else:
                continue  # elevation HSS: only link when the size matches (the view's detail link carries the mismatch)
            links.append(make_link("element", e["id"], c, "design", ev, sh, cav, "rules"))

    # 7. Foundations: footing groups -> RISAFoundation footing results by type and plan size; grade beams -> the
    #    (empty) beam results
    fres = by_id["foundation/footing-results"]
    rf = risa_footings(P, fres)
    for g in groups:
        if g["type"] != "footing":
            continue
        rep = els[g["members"][0]]
        f = rep["fields"]
        L, W, T = ft(f.get("length")), ft(f.get("width")), ft(f.get("thickness"))
        same = [r for r in rf if L and W and abs(r["L"] - L) < 0.01 and abs(r["W"] - W) < 0.01]
        th = hits_in(P, "calcs", fres, "Footing Code Check", limit=1)
        ev = [evidence(1, "type-match", 0.25, first_occ(rep), at(th[0] if th else None),
                       "Calc checks spread footings (RISAFoundation code check, geometry, soil pressure)")]
        cav = ["RISAFoundation names footings by model joint (R3D_N…, FLR_1_N…) in the calc grid system; there are no F-marks, "
               "so the specific footing can't be identified."]
        hits = list(th)
        if same:
            kinds = sorted({r["type"] for r in same})
            joints = [r["joint"] for r in same]
            for j in joints[:6]:
                hits += hits_in(P, "calcs", fres, j, limit=3)
            ev.append(evidence(2, "size-match", 0.25, None, at(hits[1] if len(hits) > 1 else None),
                               f"{g['size']} is {f['length']} × {f['width']} on the plan schedule; the calc has {len(same)} {' / '.join(kinds)} "
                               f"footing(s) of {same[0]['L']:g} × {same[0]['W']:g} ft ({', '.join(joints[:4])}{'…' if len(joints) > 4 else ''})"))
            tks = sorted({r["T"] for r in same})
            if T and all(abs(t / 12 - T) > 0.01 for t in tks):
                cav.append(f"Thickness differs: schedule {f['thickness']} vs calc {', '.join(f'{t:g} in' for t in tks)}.")
        else:
            sizes = sorted({f"{r['L']:g}×{r['W']:g} ({r['type']})" for r in rf})
            ev.append(evidence(2, "size-conflict", -0.1, None, None,
                               f"No calc footing is {f.get('length')} × {f.get('width')}; calc footings are {', '.join(sizes)}"))
            cav.append(f"Size mismatch: the schedule's {g['size']} ({f.get('length')} × {f.get('width')}) has no counterpart in the "
                       "RISAFoundation geometry – check which governs.")
        links.append(make_link("group", g["id"], fres, "design", ev, hits, cav, "rules"))
    bres = by_id["foundation/beam-results"]
    for g in groups:
        if g["type"] != "grade-beam":
            continue
        rep = els[g["members"][0]]
        nh = hits_in(P, "calcs", bres, "Beam Design Results", limit=2)
        ev = [evidence(1, "type-match", 0.25, first_occ(rep), at(nh[0] if nh else None), "RISAFoundation beam design tables are where a grade beam would be checked"),
              evidence(2, "no-data", -0.15, None, None, "Every beam / strip table prints 'No Data to Print'")]
        cav = [f"{g['size']} is not designed in this RISAFoundation model – no beam results exist. Its design may be in a calc not "
               "included in these packages, or by inspection."]
        links.append(make_link("group", g["id"], bres, "reference", ev, nh, cav, "rules"))

    # 8. Stair members (S5.0.1) -> stair calcs by location; sizes checked
    stair_calcs = [by_id["stair/grid-6-e-f"], by_id["stair/grid-5-a"]]
    for e in elements:
        if e["sheet"] != "S5.0.1" or e["type"] not in ("beam", "stringer", "column", "post", "hss-member"):
            continue
        grid = e["grid"] or ""
        for c in stair_calcs:
            gl = c["fields"]["grids"]
            shared = [g for g in gl if re.search(rf"(^|[/–]){re.escape(g)}($|[/–(])", grid)]
            if not (any(g[0].isalpha() for g in shared) and any(g[0].isdigit() for g in shared)):
                continue  # need both a letter and a number grid to agree
            gh = []
            for g in gl:
                gh += [h for h in hits_in(pdfs["stair"], "stair", c, g, limit=200) if h["page"] in (c["pageRange"][0], c["pageRange"][0] + 7)]
            ev = [evidence(1, "grid-location", 0.3 + 0.1 * (len(shared) - 1), first_occ(e), None,
                           f"Element at grid {grid}; calc sketch is drawn at grids {', '.join(gl)}")]
            cav = []
            if e["type"] == "stringer":
                kh = hits_in(pdfs["stair"], "stair", c, "STRINGER", limit=6)
                if kh:
                    ev.append(evidence(2, "keyword", 0.2, None, at(kh[0]), "Calc designs stringers"))
            size = e["fields"]["size"].upper()
            sh = hits_in(pdfs["stair"], "stair", c, e["fields"]["size"], limit=10)
            if sh:
                ev.append(evidence(len(ev) + 1, "size-match", 0.3, None, at(sh[0]), f"{size} appears in the calc"))
            else:
                calc_sizes = [s for s in c["fields"]["sizes"] if s.startswith(("C", "MC"))]
                ev.append(evidence(len(ev) + 1, "size-conflict", -0.1, None, None,
                                   f"Plan shows {size}; calc uses {', '.join(calc_sizes) or 'other sizes'}"))
                cav.append(f"Size mismatch: plan {size} vs calc {', '.join(calc_sizes) or '–'}. "
                           "The calc is dated 4/24/2023; the plan sheet carries a 7/24/2023 resubmittal – check which governs.")
            hits = (sh or []) + [h for h in gh if h["text"] in ("MV-NS",)][:4]
            links.append(make_link("element", e["id"], c, "design", ev, hits, cav, "rules"))

    # 9. HSS posts at parapet -> parapet calc
    par = by_id["parapet/hss-posts"]
    for e in elements:
        if e["type"] == "post" and "PARAPET" in (e["fields"]["note"] + " " + e["fields"]["nearbyText"]).upper():
            kh = hits_in(pdfs["stair"], "stair", par, "PARAPET", limit=10)
            hh = hits_in(pdfs["stair"], "stair", par, "HSS", limit=10)
            ev = [evidence(1, "keyword", 0.3, first_occ(e), at(kh[0] if kh else None), "Plan note 'POST AT PARAPET'; calc is the parapet design"),
                  evidence(2, "member-family", 0.2, None, at(hh[0] if hh else None), "Calc designs HSS parapet posts")]
            cav = []
            if not re.search(r"(^|[/–])(B|4)($|[/–(])", e["grid"] or ""):
                cav.append(f"Calc section is cut at grid B & 4; this post is at {e['grid']} – check it is covered by the typical design.")
            else:
                ev.append(evidence(3, "grid-location", 0.25, None, None, "Calc section cut at grid B & 4"))
            links.append(make_link("element", e["id"], par, "design", ev, kh + hh, cav, "rules"))
    for l in links:
        renumber(l["rationale"]["evidence"])
    return links


def apply_summaries(links, calcs_list, elements, groups):
    path = DATA / "summaries.json"
    authored = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    by_calc = {c["id"]: c for c in calcs_list}
    names = {e["id"]: e["tag"] for e in elements} | {g["id"]: g["title"] for g in groups}
    for l in links:
        a = authored.get("links", {}).get(l["id"])
        if a:
            l["rationale"]["summary"] = a["summary"]
            l["rationale"]["caveats"] = a.get("caveats", l["rationale"]["caveats"])
            l["provenance"]["summaryBy"] = authored.get("summaryBy", "reviewer")
        else:
            ev = "; ".join(e.get("note", e["kind"]) for e in l["rationale"]["evidence"] if e["weight"] > 0)
            l["rationale"]["summary"] = f"{names.get(l['source']['id'], l['source']['id'])} → {by_calc[l['calc']]['title']}: {ev}."
            l["provenance"]["summaryBy"] = "template"
    for c in calcs_list:
        d = authored.get("calcs", {}).get(c["id"])
        c["description"] = d if d else None
    for g in groups:
        d = authored.get("groups", {}).get(g["id"])
        g["description"] = d if d else None


def main():
    DATA.mkdir(parents=True, exist_ok=True)
    docs, plans, s_pages, calcs, stair = build_documents()
    elements = build_elements(docs, plans, s_pages)
    groups = build_groups(elements)
    calcs_list = build_calcs(docs, calcs, stair)
    links = build_links(elements, groups, calcs_list, {"calcs": calcs, "stair": stair})
    apply_summaries(links, calcs_list, elements, groups)
    meta = {"builtAt": dt.datetime.now().isoformat(timespec="seconds"), "matcher": MATCHER_VERSION,
            "scope": [p["label"] for p in docs[0]["pages"]], "memberSheets": list(MEMBER_SHEETS), "levels": LEVEL_ORDER}
    for name, obj in (("documents", docs), ("elements", elements), ("groups", groups), ("calcs", calcs_list), ("links", links)):
        (DATA / f"{name}.json").write_text(json.dumps({"meta": meta, name: obj}, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"docs {len(docs)}  elements {len(elements)}  groups {len(groups)}  calcs {len(calcs_list)}  links {len(links)}")
    if "--no-viewers" in sys.argv:
        return
    # refresh the double-click build (viewers/) from the same data and code
    sys.path.insert(0, str(HERE))
    import make_viewers
    make_viewers.main()


if __name__ == "__main__":
    main()
