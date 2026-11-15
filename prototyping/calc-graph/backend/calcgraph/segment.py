"""Split a calc package into calcs for the IFC path, from the ONE calc-package reader.

The page heads (sheet id, title, title box, sub-calc group, software, contents flag) come from
calcpkg_ingest.read_package, which reads every set convention from the set's profile
(calcgraph/profiles/*.yaml). This module only groups pages into calcs:

- a page with < 25 characters of text has no text layer (scanned / handwritten):
  consecutive such pages form one "scanned" calc that is never mapped
- a contents page (the profile's dot-leader rule), and any page before the first page that
  carries a profile sheet id (a cover), is front matter and is never mapped; a package with no
  sheet ids at all has only its contents pages as front matter
- otherwise a calc is one calcpkg_ingest sub-calc group (consecutive pages of one section with
  the same title, "(cont.)" ignored)
- software comes from the page head (profile detectors); the element type from the title, then
  the page's table titles, through CAT_WORDS; `cats` = every type the calc designs (its type plus the
  type each of its table titles names), which the matcher uses to tell a design link from a cross-reference
"""
from __future__ import annotations

import re

CAT_WORDS = [
    ("Connection", re.compile(r"\b(connection|shear tab|fin plate|end plate|base plate|bolt group|cleat|moment conn)", re.I)),
    ("Footing", re.compile(r"\b(footing|foundation|pad|raft|pile cap)", re.I)),
    ("Pile", re.compile(r"\bpiles?\b", re.I)),
    ("Brace", re.compile(r"\b(brac(e|ing)|x-brace)", re.I)),
    ("Column", re.compile(r"\bcolumns?\b", re.I)),
    ("Slab", re.compile(r"\b(slab|deck|pt slab|post-tension)", re.I)),
    ("Wall", re.compile(r"\b(wall|core)\b", re.I)),
    ("Beam", re.compile(r"\b(beams?|girders?|joists?|lintels?|transfer)\b", re.I)),
]
_TITLE_KW = re.compile(r"(design|calc|calculation|check|analysis|criteria|framing|report|schedule|connection|footing|bracing)", re.I)

TITLE_BOX_RULE = "segment.title_box"
SEGMENT_RULE = "segment.calcpkg_group"


def cat_of_text(s: str) -> str:
    return next((k for k, rx in CAT_WORDS if rx.search(s)), "")


def _title_line(text: str) -> str | None:
    """A calc-like title in a line of text (title_box's text fallback for stored pages)."""
    for line in [s.strip() for s in text.split("\n") if s.strip()][:6]:
        if 4 < len(line) < 90 and _TITLE_KW.search(line) and not re.search(r"\.{4,}", line):
            return re.sub(r"\s*\((cont\.?|continued)\)\s*$", "", line, flags=re.I).strip()
    return None


def _norm(s: str | None) -> str:
    return re.sub(r"[^A-Z0-9]", "", (s or "").upper())


def _slug(s: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s.lower())).strip("-")[:60] or "calc"


def title_box(page: dict, title: str, scanned: bool = False, front: bool = False, rect: list | None = None) -> dict:
    """Where a calc's title sits on its first page (PDF points). `rect` = the title box the
    calc-package reader found; without it (a store written before this reader) the title line is
    searched in the page's first lines. A scanned page, front matter, or a title not on the page
    is located by the whole first page and says so."""
    from .pdf_ingest import rects_for_span
    whole = {"page": page["n"], "rects": [[0.0, 0.0, round(page["width"], 2), round(page["height"], 2)]],
             "span": None, "rule": TITLE_BOX_RULE}
    if scanned:
        return whole | {"note": "scanned page, no text layer: located by the whole page"}
    if front:
        return whole | {"note": "front matter / contents page: located by the whole page"}
    if rect:
        return {"page": page["n"], "rects": [[round(float(v), 2) for v in rect]], "span": None, "rule": TITLE_BOX_RULE,
                "note": "title box from the calc-package reader (profile title rule)"}
    text, pos, seen = page["text"], 0, 0
    want = _norm(title)
    for line in text.split("\n"):
        start, pos = pos, pos + len(line) + 1
        if not line.strip():
            continue
        seen += 1
        if seen > 6:
            break
        t = _title_line(line)
        if want and t and _norm(t) == want:
            lead = len(line) - len(line.lstrip())
            span = [start + lead, start + len(line.rstrip())]
            rects = rects_for_span(page, *span)
            if rects:
                return {"page": page["n"], "rects": rects, "span": span, "rule": TITLE_BOX_RULE,
                        "note": "title line words"}
    return whole | {"note": "title line not found on the first page (continuation or derived title): whole page"}


def segment(pages: list[dict], heads: list[dict]) -> list[dict]:
    """pages: pdf_ingest pages (text + word boxes, n 1-based); heads: calcpkg_ingest.read_package
    pages for the same PDF (one per page, in order)."""
    head = {h["page"]: h for h in heads}
    with_id = [h["page"] for h in heads if h.get("sheet_rect")]
    first_id = min(with_id) if with_id else None
    calcs: list[dict] = []
    cur: dict | None = None

    def push(title: str, group: str | None, scanned: bool = False, front: bool = False) -> dict:
        c = {"title": title, "software": "", "cat": "", "cats": [], "pages": [], "scanned": scanned, "front": front, "text": "",
             "group": group, "tables": []}
        calcs.append(c)
        return c

    for pg in pages:
        h = head.get(pg["n"], {})
        t = pg["text"].strip()
        if len(t) < 25:
            if not (cur and cur["scanned"]):
                cur = push("Scanned page(s) - no text layer", None, scanned=True)
        elif h.get("toc") or (first_id is not None and pg["n"] < first_id):
            if not (cur and cur["front"]):
                cur = push("Front matter / contents", None, front=True)
        elif not cur or cur["scanned"] or cur["front"] or h.get("group") != cur["group"]:
            cur = push(h.get("title") or f"Page {pg['n']}", h.get("group"))
            cur["software"] = h.get("software") or ""
            cur["title_rect"] = h.get("title_rect")
        cur["pages"].append(pg["n"])
        cur["text"] += "\n" + t
        cur["tables"] += [x["title"] for x in h.get("tables") or []]

    by_n = {pg["n"]: pg for pg in pages}
    seen: dict[str, int] = {}
    n_scanned = 0
    for c in calcs:
        c["title_box"] = title_box(by_n[c["pages"][0]], c["title"], c["scanned"], c["front"], c.pop("title_rect", None))
        if c["scanned"]:
            n_scanned += 1
            base = f"scanned-{n_scanned}"
        else:
            base = _slug(c["title"])
        seen[base] = seen.get(base, 0) + 1
        c["key"] = base if seen[base] == 1 else f"{base}-{seen[base]}"
        c["rule"] = SEGMENT_RULE
        tables = c.pop("tables")
        c.pop("group")
        if c["front"]:
            continue
        if c["scanned"]:
            c["software"] = "Needs OCR"
            continue
        c["cat"] = cat_of_text(c["title"]) or cat_of_text(" ".join(tables))
        # every element type the calc designs: its own type, then the type each of its tables names (a RISA
        # frame page checks the frame's beams AND its columns) - a mark of one of these types is designed here
        c["cats"] = list(dict.fromkeys(x for x in [c["cat"]] + [cat_of_text(t) for t in tables] if x))
    return calcs
