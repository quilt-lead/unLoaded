"""Second element source: structural elements read off the S-sheets of a drawing set
(no BIM model). A sibling of ifc_ingest, not a fork of it.

Every element is a TAG on a sheet - a member size (W16x26, HSS6x6x1/4, C12x20.7,
600S162-54, 8x10 timber), a foundation mark (F9, P2.5, TB-1, GB1) or a moment frame
marker (SMF) - with the words that produced it, so the UI can open the original
sheet zoomed to and highlighting exactly those words.

Deterministic rules, each recorded on the element or edge it produced:
- sheet number = the tallest word in the title block matching S#.#.# style
- sheet title / level from the title block text above the sheet number
- grid: bubble labels that occur twice on a sheet, at the same x (number grids) or
  the same y (letter grids) far apart, define the grid lines of that sheet
- grid ref of a tag = row/column it sits on or between ("C/4-5"), nearest
  intersection kept with its distance in points
- load path (plans only): a beam tag is followed onto the drawn line it labels
  (vector geometry from page.get_drawings()); the line's ends are tested against
  grid intersections that carry a column tag, or against another beam's line.
  Columns stack by grid intersection; columns bear on the footing mark at the same
  intersection of the foundation plan.
"""
from __future__ import annotations

import re
from collections import defaultdict

import pymupdf

from . import sizes

SHEET_NO = re.compile(r"^S\d+(?:\.\d+){1,3}$")
GRID_LABEL = re.compile(r"^(\d{1,2}(?:\.\d)?|[A-H](?:\.\d)?)$")
FOUND_MARK = re.compile(r"^(F\d{1,2}(?:\.\d)?|P\d(?:\.\d)?|TB-\d{1,2}|GB-?\d{1,2})$")
SMF = re.compile(r"^\*?SMF$")
ROLE_WORDS = ["JAMB", "POST", "COL", "COLUMN", "HDR", "HEADER", "STUD", "STRINGER", "BEAM", "BM", "TRELLIS", "KICKER",
              "BRACE", "LEDGER", "FRMG", "ABV", "ABOVE", "BELOW", "FLAT", "LOW", "JOIST", "TRACK"]
SPLIT_SIZES = re.compile(r"(?<=[0-9/])(?=(?:HSS|W|MC|C|L)\d)")


def _sheet_kind(title: str) -> str:
    t = title.upper()
    for key, kind in (("FOUNDATION PLAN", "foundation"), ("FRAMING PLAN", "framing"), ("MOMENT FRAME ELEV", "smf"),
                      ("WALL ELEVATION", "wall"), ("WALL SECTION", "wall"), ("SECTION", "wall"), ("STAIR", "stair"),
                      ("ELEVATOR", "elevator"), ("TRELLIS", "trellis"), ("NOTES", "notes"), ("DETAIL", "details")):
        if key in t:
            return kind
    return "other"


def _level_of(title: str, kind: str) -> str:
    t = title.upper()
    if kind == "foundation":
        return "Level 1 / Foundation"
    m = re.search(r"LEVEL\s*(\d+)", t)
    if m and kind == "framing":
        return f"Level {m.group(1)}"
    if "ROOF" in t and kind == "framing":
        return "Roof"
    return ""


def _rect(w) -> list[float]:
    return [round(w[0], 1), round(w[1], 1), round(w[2], 1), round(w[3], 1)]


def _sheet_header(words: list) -> tuple[str, str, list] | None:
    tb = [w for w in words if w[0] > 2690]
    nos = [w for w in tb if SHEET_NO.match(w[4])]
    if not nos:
        return None
    sn = max(nos, key=lambda w: w[3] - w[1])
    # title: the larger words between the "DRAWING TITLE" label and the sheet number
    cand = [w for w in tb if sn[1] - 230 < w[1] < sn[1] - 5 and (w[3] - w[1]) >= 12 and w is not sn]
    rows: dict[int, list] = defaultdict(list)
    for w in cand:
        rows[round(w[3] / 6)].append(w)
    title = " ".join(" ".join(x[4] for x in sorted(r, key=lambda x: x[0])) for _, r in sorted(rows.items()))
    title = re.sub(r"^DRAWING TITLE\s*", "", title).strip()
    return sn[4], title, _rect(sn)


def _grids(words: list, cutoff: float) -> dict:
    lab = [w for w in words if GRID_LABEL.match(w[4]) and w[2] < cutoff and 15 <= (w[3] - w[1]) <= 26]
    by: dict[str, list] = defaultdict(list)
    for w in lab:
        by[w[4]].append(w)
    cols, rows = {}, {}
    for name, ws in by.items():
        for i in range(len(ws)):
            for j in range(i + 1, len(ws)):
                a, b = ws[i], ws[j]
                ax, ay = (a[0] + a[2]) / 2, (a[1] + a[3]) / 2
                bx, by_ = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
                if abs(ax - bx) < 6 and abs(ay - by_) > 500 and name[0].isdigit():
                    cols[name] = {"label": name, "pos": round((ax + bx) / 2, 1), "rects": [_rect(a), _rect(b)]}
                elif abs(ay - by_) < 6 and abs(ax - bx) > 500 and name[0].isalpha():
                    rows[name] = {"label": name, "pos": round((ay + by_) / 2, 1), "rects": [_rect(a), _rect(b)]}
    return {"cols": sorted(cols.values(), key=lambda g: g["pos"]), "rows": sorted(rows.values(), key=lambda g: g["pos"])}


def _nat(s: str):
    return [float(x) if x.replace(".", "").isdigit() else x for x in re.findall(r"\d+(?:\.\d+)?|[A-Z]+", s)]


def _axis_ref(v: float, lines: list[dict], tol: float = 14) -> str:
    if not lines:
        return ""
    near = min(lines, key=lambda g: abs(g["pos"] - v))
    if abs(near["pos"] - v) <= tol:
        return near["label"]
    lo = [g for g in lines if g["pos"] < v]
    hi = [g for g in lines if g["pos"] > v]
    if lo and hi:
        a, b = sorted([lo[-1]["label"], hi[0]["label"]], key=_nat)
        return f"{a}-{b}"
    return f"beyond {near['label']}"


def grid_ref(cx: float, cy: float, grid: dict) -> dict:
    if not grid["cols"] or not grid["rows"]:
        return {"ref": "", "node": None, "node_dist": None}
    col = _axis_ref(cx, grid["cols"])
    row = _axis_ref(cy, grid["rows"])
    # nearest intersection, kept only if clearly nearer than the runner-up
    pts = sorted(((((c["pos"] - cx) ** 2 + (r["pos"] - cy) ** 2) ** 0.5, f"{r['label']}/{c['label']}")
                  for c in grid["cols"] for r in grid["rows"]))
    d0, n0 = pts[0]
    d1 = pts[1][0] if len(pts) > 1 else 1e9
    node = n0 if d0 <= 70 and d0 <= 0.6 * d1 else None
    return {"ref": f"{row}/{col}", "node": node, "node_dist": round(d0, 1), "nearest": n0}


def _split_word(w) -> list:
    """'HSS6x6x1/4HSS6x6x1/4' arrives as one word: split it, boxes in proportion."""
    t = w[4]
    parts = SPLIT_SIZES.split(t)
    if len(parts) == 1:
        return [w]
    out, pos = [], 0
    horiz = (w[2] - w[0]) >= (w[3] - w[1])
    for p in parts:
        a, b = pos / len(t), (pos + len(p)) / len(t)
        pos += len(p)
        if horiz:
            out.append((w[0] + a * (w[2] - w[0]), w[1], w[0] + b * (w[2] - w[0]), w[3], p, w[5], w[6], w[7]))
        else:  # vertical text reads bottom-up (dir 0,-1)
            out.append((w[0], w[3] - b * (w[3] - w[1]), w[2], w[3] - a * (w[3] - w[1]), p, w[5], w[6], w[7]))
    return out


def _category(kind: str, fam: str, role: str, vertical: bool) -> tuple[str, str]:
    """(cat, type label) for a size tag on a sheet of this kind."""
    r = role.upper()
    if fam == "CFS":
        return ("Wall", "Metal stud / track")
    if fam == "Timber":
        return ("Beam", "Timber trellis member")
    if fam == "L":
        return ("Other", "Angle")
    if fam == "HSS":
        if "JAMB" in r:
            return ("Column", "HSS jamb")
        if "HDR" in r or "HEADER" in r:
            return ("Beam", "HSS header")
        if "POST" in r:
            return ("Column", "HSS post")
        if kind in ("framing", "foundation"):
            return ("Column", "HSS column")
        if kind == "stair":
            return ("Column", "Stair post")
        return ("Column" if vertical else "Beam", "HSS member")
    if fam in ("C", "MC"):
        if kind == "stair":
            return ("Beam", "Stair stringer / channel")
        return ("Beam", "Channel")
    if fam == "W":
        if kind == "smf":
            return ("Column", "Moment frame column") if vertical else ("Beam", "Moment frame beam")
        if "COL" in r or "POST" in r:
            return ("Column", "W column")
        return ("Beam", "W beam")
    return ("Other", fam)


def read_plans(path: str) -> dict:
    doc = pymupdf.open(path)
    sheets, elements, schedule = [], [], {}
    for pno, page in enumerate(doc):
        words = page.get_text("words")
        hdr = _sheet_header(words)
        if not hdr:
            continue
        sheet_no, title, sn_rect = hdr
        kind = _sheet_kind(title)
        level = _level_of(title, kind)
        # drawing area: left of the plan-notes column on plan sheets, else left of the title block
        notes = [w for w in words if w[4] == "NOTES" and w[0] > 1900 and w[0] < 2690]
        cutoff = min(w[0] for w in notes) - 40 if notes and kind in ("framing", "foundation") else 2690
        # widen to the left edge of the notes heading line (the heading is "FRAMING PLAN NOTES")
        if notes and kind in ("framing", "foundation"):
            hn = min(notes, key=lambda w: w[0])
            line = [w for w in words if abs(w[3] - hn[3]) < 2 and abs(w[0] - hn[0]) < 260]
            cutoff = min(w[0] for w in line) - 40
        grid = _grids(words, cutoff)
        sheet = {"sheet": sheet_no, "title": title, "kind": kind, "level": level, "page": pno + 1,
                 "width": page.rect.width, "height": page.rect.height, "sheet_rect": sn_rect,
                 "cutoff": round(cutoff, 1), "grid": grid, "tags": 0}
        sheets.append(sheet)
        if kind == "notes":
            continue
        by_line: dict[tuple, list] = defaultdict(list)
        for w in words:
            by_line[(w[5], w[6])].append(w)
        if kind == "foundation":
            schedule.update(_footing_schedule(words, cutoff, sheet_no, pno + 1))
        timber_ok = kind in ("framing", "trellis")
        n = 0
        for w0 in words:
            if w0[2] > cutoff:
                continue
            for w in _split_word(w0):
                t = w[4]
                info = sizes.norm(t, timber=timber_ok)
                mark = ""
                if info is None:
                    tc = sizes.clean(t)
                    if kind == "foundation" and FOUND_MARK.match(tc):
                        mark = tc
                    elif kind in ("framing", "foundation") and SMF.match(tc):
                        mark = "SMF"
                    else:
                        continue
                # role: other words on the same text line plus the next line of the block
                line = sorted(by_line[(w[5], w[6])], key=lambda x: x[7])
                nxt = sorted(by_line.get((w[5], w[6] + 1), []), key=lambda x: x[7])
                ctx = [x for x in line if x[7] > w[7]][:4] + nxt[:3]
                role = " ".join(x[4] for x in ctx if re.sub(r"[^A-Z]", "", x[4].upper()) in ROLE_WORDS or x[4].startswith("("))
                is_vert = (w[3] - w[1]) > 1.2 * (w[2] - w[0])  # rotated 90 deg text: box taller than wide
                if mark:
                    if mark == "SMF":
                        cat, typ = "Frame", "Moment frame marker"
                    elif mark.startswith("F"):
                        cat, typ = "Footing", "Spread footing"
                    elif mark.startswith("P"):
                        cat, typ = "Pile", "Pier / pile"
                    else:
                        cat, typ = "Beam", "Tie beam" if mark.startswith("TB") else "Grade beam"
                    size = mark
                    snorm = ""
                    fam = "mark"
                else:
                    cat, typ = _category(kind, info["family"], role, is_vert)
                    size, snorm, fam = sizes.clean(t), info["norm"], info["family"]
                cx, cy = (w[0] + w[2]) / 2, (w[1] + w[3]) / 2
                g = grid_ref(cx, cy, grid) if grid["cols"] and grid["rows"] else {"ref": "", "node": None, "node_dist": None}
                rects = [_rect(w)] + [_rect(x) for x in ctx if x[4] in role.split()]
                n += 1
                el = {
                    "id": f"{sheet_no}#{n:03d}", "doc": "plans", "page": pno + 1, "sheet": sheet_no, "sheet_title": title,
                    "sheet_kind": kind, "cat": cat, "type": typ, "mark": mark, "size": size if not mark else "",
                    "size_norm": snorm, "family": fam, "level": level, "grid": g["ref"], "grid_node": g["node"],
                    "grid_node_dist": g["node_dist"], "bbox": _rect(w), "rects": rects,
                    "text": (t + (" " + role if role else "")).strip(), "vertical_text": is_vert,
                    "params": {"role": role} if role else {},
                }
                if mark and mark in schedule:
                    el["params"]["schedule"] = schedule[mark]["text"]
                    el["schedule"] = schedule[mark]
                elements.append(el)
        sheet["tags"] = n
    _dedupe(elements)
    return {"sheets": sheets, "elements": elements, "schedule": schedule,
            "meta": {"page_count": len(doc), "s_sheets": len(sheets)}}


def _footing_schedule(words: list, cutoff: float, sheet: str, page: int) -> dict:
    """FOUNDATION SCHEDULE - PAD rows: 'F9 9' - 0" 9' - 0" 2' - 6" (14) #6 EA WAY T&B'."""
    out = {}
    marks = [w for w in words if w[0] > cutoff and re.fullmatch(r"F\d{1,2}(?:\.\d)?", w[4])]
    for m in marks:
        row = sorted((w for w in words if abs((w[1] + w[3]) / 2 - (m[1] + m[3]) / 2) < 4 and m[0] <= w[0] < m[0] + 420),
                     key=lambda w: w[0])
        text = " ".join(w[4] for w in row)
        dims = re.findall(r"(\d+)'\s*-\s*(\d+)\"", text)
        if len(dims) >= 3:
            ft = [int(a) + int(b) / 12 for a, b in dims[:3]]
            out[m[4]] = {"mark": m[4], "length_ft": ft[0], "width_ft": ft[1], "thick_ft": ft[2], "text": text,
                         "sheet": sheet, "page": page, "rects": [_rect(w) for w in row[:4]]}
    return out


def _dedupe(elements: list[dict]) -> None:
    """Same text at the same box on the same page is one element (PDF overprints)."""
    seen = set()
    keep = []
    for e in elements:
        k = (e["page"], e["size"] or e["mark"], tuple(round(v) for v in e["bbox"]))
        if k in seen:
            continue
        seen.add(k)
        keep.append(e)
    elements[:] = keep
