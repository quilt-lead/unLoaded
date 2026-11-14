"""CSI MasterFormat 3-part specification book -> sections, articles, paragraphs (with boxes).

    read_specs(path) -> {"sections": [...], "paragraphs": [...], "meta": {...}}

Generic structure reader for a project manual in the CSI SectionFormat (no set profile needed):

- running header / footer: a line in the top / bottom tenth of the page whose text (digits
  masked) repeats there on at least half of the pages, or a "05 12 00 - 3" page footer, is
  boilerplate, never body text
- section start: "SECTION 05 12 00 - STRUCTURAL STEEL FRAMING" (6 or 8 digit number, spaced or
  not, dash or en dash before the title); "END OF SECTION" closes it
- part: "PART 2 - PRODUCTS"
- article: "2.1" with its title on the same row ("2.1 HIGH-STRENGTH BOLTS" as one or two lines)
- paragraph: a "A." label at the paragraph indent, text to its right until the next label at the
  same or a shallower indent; subparagraphs ("1.", "a.") are deeper labels and stay inside
  their paragraph. Paragraph id SPEC:<section>/<article>.<letter>; its box is the union of its
  text lines (labels excluded), one box per page it spans
- an article with no lettered paragraph (a single block of text) becomes paragraph "-"

What an article GOVERNS is not decided here (that needs the registry's vocabulary of materials,
types and details): see registry_ingest.governs(), which reads each paragraph's text.
"""
from __future__ import annotations

import re
from collections import Counter

import pymupdf

SECTION_RE = re.compile(r"^SECTION\s+(\d{2}\s?\d{2}\s?\d{2}(?:\.\d{2})?)\s*[-–—]\s*(.+)$", re.I)
END_RE = re.compile(r"^END OF SECTION", re.I)
PART_RE = re.compile(r"^PART\s+(\d)\s*[-–—]\s*(.+)$", re.I)
ART_RE = re.compile(r"^(\d\.\d{1,2})(?:\s+(.+))?$")
PARA_RE = re.compile(r"^([A-Z])\.$")
SUB_RE = re.compile(r"^(\d{1,2}|[a-z])\.$")
BAND = 0.1         # header / footer band: top and bottom tenth of the page
FOOTER_RE = re.compile(r"^(\d{2}\s?\d{2}\s?\d{2}(?:\.\d{2})?)\s*[-–]\s*\d+$")


def _norm_sec(s: str) -> str:
    d = re.sub(r"\D", "", s)
    return " ".join([d[0:2], d[2:4], d[4:6]]) + (("." + d[6:]) if len(d) > 6 else "")


def _rows(page) -> list[dict]:
    """Text lines grouped into rows (same baseline within 2 pt), each part kept with its box; a part
    in the top / bottom BAND of the page is flagged (only those can be running header / footer)."""
    lines = []
    H = page.rect.height
    for b in page.get_text("dict")["blocks"]:
        for ln in b.get("lines", []):
            t = "".join(s["text"] for s in ln["spans"]).strip()
            if t and ln.get("dir", (1, 0))[0] > 0.99:
                lines.append({"text": t, "bbox": list(ln["bbox"]),
                              "band": ln["bbox"][3] < BAND * H or ln["bbox"][1] > (1 - BAND) * H})
    lines.sort(key=lambda l: (round(l["bbox"][3]), l["bbox"][0]))
    rows: list[list[dict]] = []
    for l in lines:
        if rows and abs(rows[-1][0]["bbox"][3] - l["bbox"][3]) < 2.0:
            rows[-1].append(l)
        else:
            rows.append([l])
    out = []
    for r in rows:
        r.sort(key=lambda l: l["bbox"][0])
        out.append({"parts": r, "text": " ".join(p["text"] for p in r), "x0": r[0]["bbox"][0],
                    "y0": min(p["bbox"][1] for p in r), "y1": max(p["bbox"][3] for p in r)})
    return out


def _mask(t: str) -> str:
    return re.sub(r"\d+", "#", t.strip().upper())


def read_specs(path: str) -> dict:
    doc = pymupdf.open(path)
    pages = [_rows(p) for p in doc]
    # running header / footer: masked text in the page band on >= half the pages (and more than 2)
    freq = Counter()
    for rows in pages:
        freq.update({_mask(p["text"]) for r in rows for p in r["parts"] if p["band"]})
    boiler = {t for t, n in freq.items() if n >= max(3, len(pages) // 2)}
    sections, paras = [], []
    sec = art = part = None
    cur = None          # open paragraph
    para_x = None       # indent of the lettered-paragraph labels in this section

    def close():
        nonlocal cur
        if cur and cur["chunks"]:
            paras.append(cur)
        cur = None

    def chunk(pno, bbox, text):
        if cur["chunks"] and cur["chunks"][-1]["page"] == pno:
            c = cur["chunks"][-1]
            c["bbox"] = [min(c["bbox"][0], bbox[0]), min(c["bbox"][1], bbox[1]), max(c["bbox"][2], bbox[2]),
                         max(c["bbox"][3], bbox[3])]
        else:
            cur["chunks"].append({"page": pno, "bbox": list(bbox)})
        cur["text"] = (cur["text"] + " " + text).strip()

    for pno, rows in enumerate(pages, start=1):
        for r in rows:
            if any(p["band"] and FOOTER_RE.match(p["text"]) for p in r["parts"]):
                continue        # the page-footer row ("STEEL DECKING ... 05 31 00 - 2") is all footer
            parts = [p for p in r["parts"] if not (p["band"] and _mask(p["text"]) in boiler)]
            if not parts:
                continue
            text = " ".join(p["text"] for p in parts)
            m = SECTION_RE.match(text)
            if m:
                close()
                sec = {"section": _norm_sec(m.group(1)), "title": m.group(2).strip(), "page": pno, "page_end": pno,
                       "bbox": [round(v, 2) for v in [parts[0]["bbox"][0], r["y0"], parts[-1]["bbox"][2], r["y1"]]]}
                sections.append(sec)
                art = part = None
                para_x = None
                continue
            if sec is None:
                continue
            sec["page_end"] = pno
            if END_RE.match(text):
                close()
                sec = None
                continue
            m = PART_RE.match(text)
            if m:
                close()
                part = {"part": m.group(1), "title": m.group(2).strip()}
                continue
            m = ART_RE.match(parts[0]["text"])
            if m and (m.group(2) or len(parts) > 1) and re.search(r"[A-Z]{3}", (m.group(2) or "") + " ".join(
                    p["text"] for p in parts[1:])):
                close()
                art = {"article": m.group(1), "title": ((m.group(2) or "") + " " + " ".join(p["text"] for p in parts[1:])).strip()}
                continue
            if art is None:
                continue
            lab = PARA_RE.match(parts[0]["text"])
            sub = SUB_RE.match(parts[0]["text"])
            x = parts[0]["bbox"][0]
            if lab and (para_x is None or x <= para_x + 3):
                para_x = x if para_x is None else min(para_x, x)
                close()
                cur = {"section": sec["section"], "section_title": sec["title"], "part": (part or {}).get("part"),
                       "article": art["article"], "title": art["title"], "paragraph": lab.group(1), "text": "", "chunks": []}
                body = parts[1:]
                if body:
                    chunk(pno, [min(p["bbox"][0] for p in body), r["y0"], max(p["bbox"][2] for p in body), r["y1"]],
                          " ".join(p["text"] for p in body))
                continue
            if cur is None or cur["article"] != art["article"]:
                # body text right under an article title with no lettered paragraph
                close()
                cur = {"section": sec["section"], "section_title": sec["title"], "part": (part or {}).get("part"),
                       "article": art["article"], "title": art["title"], "paragraph": "-", "text": "", "chunks": []}
            body = parts if not sub else parts      # subparagraph labels stay in the box (they sit inside it)
            chunk(pno, [min(p["bbox"][0] for p in body), r["y0"], max(p["bbox"][2] for p in body), r["y1"]], text)
    close()
    out = []
    for p in paras:
        pid = f"SPEC:{p['section']}/{p['article']}.{p['paragraph']}" if p["paragraph"] != "-" else \
            f"SPEC:{p['section']}/{p['article']}"
        out.append({"id": pid, **{k: p[k] for k in ("section", "section_title", "part", "article", "title", "paragraph")},
                    "text": p["text"], "chunks": [{"page": c["page"], "bbox": [round(v, 2) for v in c["bbox"]]} for c in p["chunks"]],
                    "rule": "CSI 3-part: lettered paragraph under an article, box = its text lines"})
    return {"sections": sections, "paragraphs": out,
            "meta": {"pages": len(pages), "boilerplate_lines": len(boiler), "sections": len(sections), "paragraphs": len(out)}}
