"""Split a calc package into calcs. Port of the mockup's segment() / titleOf().

Rules (deterministic):
- a page with < 25 characters of text has no text layer (scanned / handwritten):
  consecutive such pages form one "scanned" calc that is never mapped
- a page with >= 3 dot-leader entries ("Title ...... 12") is front matter / contents
  and is never mapped
- a page whose first lines carry a calc-like title starts a new calc unless the
  title (ignoring "(cont.)" and punctuation) equals the current calc's title
- software and element type come from keyword tables

Two deliberate changes from the mockup: software named in the title wins over
software the body cites ("Slab reactions from RAM Concept" inside a RAM Structural
System report). And the element type falls back to the line
directly UNDER the title line. The mockup took the second line of the page, which
is the title itself as soon as a page has a running header.
"""
from __future__ import annotations

import re

SOFTWARE = [
    (r"RAM\s*CONCEPT", "RAM Concept"), (r"RAM\s*(STRUCTURAL|STEEL|FRAME|ELEMENTS)", "RAM Structural System"),
    (r"\bETABS\b", "ETABS"), (r"\bSAFE\b", "SAFE"), (r"SAP\s?2000", "SAP2000"), (r"MATHCAD", "MathCAD"),
    (r"TEKLA\s+STRUCTURAL\s+DESIGNER", "Tekla Structural Designer"), (r"RISA", "RISA"), (r"IDEA\s*STATICA", "IDEA StatiCa"),
    (r"PROFIS", "Hilti PROFIS"), (r"\bVBA\b|\.XLSM", "VBA / Excel"), (r"\bEXCEL\b|\.XLSX", "Excel"), (r"HAND\s*CALC", "Hand calc"),
    (r"PROKON", "Prokon"), (r"SPACEGASS|SPACE\s*GASS", "SpaceGass"), (r"ROBOT", "Robot"), (r"SCIA", "SCIA"), (r"MIDAS", "MIDAS"),
    (r"STAAD", "STAAD"), (r"ENERCALC", "Enercalc"),
]
_SOFTWARE = [(re.compile(p, re.I) if p not in (r"\bSAFE\b",) else re.compile(p), n) for p, n in SOFTWARE]

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
_TOC = re.compile(r"\.{4,}\s*\d+")


def cat_of_text(s: str) -> str:
    return next((k for k, rx in CAT_WORDS if rx.search(s)), "")


def title_of(text: str) -> str | None:
    lines = [s.strip() for s in text.split("\n") if s.strip()][:6]
    for line in lines:
        if 4 < len(line) < 90 and _TITLE_KW.search(line) and not re.search(r"\.{4,}", line):
            return re.sub(r"\s*\((cont\.?|continued)\)\s*$", "", line, flags=re.I).strip()
    return None


def _norm(s: str | None) -> str:
    return re.sub(r"[^A-Z0-9]", "", (s or "").upper())


def _slug(s: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s.lower())).strip("-")[:60] or "calc"


def segment(pages: list[dict]) -> list[dict]:
    calcs: list[dict] = []
    cur: dict | None = None

    def push(title: str, scanned: bool = False) -> dict:
        c = {"title": title, "software": "", "cat": "", "pages": [], "scanned": scanned, "front": False, "text": ""}
        calcs.append(c)
        return c

    for pg in pages:
        t = pg["text"].strip()
        if len(t) < 25:
            if not (cur and cur["scanned"]):
                cur = push("Scanned page(s) - no text layer", scanned=True)
            cur["pages"].append(pg["n"])
            continue
        if len(_TOC.findall(t)) >= 3:
            cur = push("Front matter / contents")
            cur["front"] = True
            cur["pages"].append(pg["n"])
            cur["text"] += "\n" + t
            continue
        title = title_of(t)
        if not cur or cur["scanned"] or cur["front"] or (title and _norm(title) != _norm(cur["title"])):
            cur = push(title or ((cur["title"] + " (cont.)") if cur else "Front matter"))
        cur["pages"].append(pg["n"])
        cur["text"] += "\n" + t

    seen: dict[str, int] = {}
    n_scanned = 0
    for c in calcs:
        if c["scanned"]:
            n_scanned += 1
            base = f"scanned-{n_scanned}"
        else:
            base = _slug(c["title"])
        seen[base] = seen.get(base, 0) + 1
        c["key"] = base if seen[base] == 1 else f"{base}-{seen[base]}"
        if c["front"]:
            continue
        # software named in the title wins over software the body merely cites
        sw = next((n for rx, n in _SOFTWARE if rx.search(c["title"])), "") or \
            next((n for rx, n in _SOFTWARE if rx.search(c["text"])), "")
        c["software"] = sw or ("Needs OCR" if c["scanned"] else "")
        lines = [s.strip() for s in c["text"].split("\n") if s.strip()]
        under = ""
        for i, line in enumerate(lines):
            if _norm(title_of(line) or "") == _norm(c["title"]) and _norm(c["title"]):
                under = lines[i + 1] if i + 1 < len(lines) else ""
                break
        c["cat"] = cat_of_text(c["title"]) or cat_of_text(under)
    return calcs
