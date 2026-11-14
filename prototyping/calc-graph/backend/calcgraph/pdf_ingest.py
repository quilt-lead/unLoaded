"""Calc package PDF -> pages of text with word boxes (PyMuPDF).

Text is rebuilt line by line from word boxes grouped by baseline (same approach as
the mockup's pdf.js reader). Every word keeps its character span in the page text
and its box in PDF points, so any match the mapper makes can be turned back into
highlight rectangles on the page.
"""
from __future__ import annotations

import pymupdf


def read_pdf(path: str) -> dict:
    doc = pymupdf.open(path)
    pages = []
    for i, page in enumerate(doc):
        words = page.get_text("words")  # x0, y0, x1, y1, word, block, line, wno
        rows: list[dict] = []
        for w in sorted(words, key=lambda w: (round(w[3], 1), w[0])):
            y = w[3]
            row = next((r for r in rows if abs(r["y"] - y) < 3), None)
            if row is None:
                row = {"y": y, "items": []}
                rows.append(row)
            row["items"].append(w)
        rows.sort(key=lambda r: r["y"])
        text_parts: list[str] = []
        boxes: list[list[float]] = []
        pos = 0
        for r in rows:
            items = sorted(r["items"], key=lambda w: w[0])
            line_start = pos
            for k, w in enumerate(items):
                if k:
                    text_parts.append(" ")
                    pos += 1
                s = w[4]
                boxes.append([round(w[0], 2), round(w[1], 2), round(w[2], 2), round(w[3], 2), pos, pos + len(s)])
                text_parts.append(s)
                pos += len(s)
            if pos > line_start:
                text_parts.append("\n")
                pos += 1
        text = "".join(text_parts).rstrip("\n")
        pages.append({"n": i + 1, "text": text, "words": boxes, "width": page.rect.width, "height": page.rect.height,
                      "images": len(page.get_images())})
    return {"pages": pages, "meta": {"page_count": len(doc), "title": doc.metadata.get("title", "")}}


def rects_for_span(page: dict, start: int, end: int) -> list[list[float]]:
    """Boxes of the words overlapping [start, end) of the page text, merged per line."""
    out: list[list[float]] = []
    for x0, y0, x1, y1, s, e in page["words"]:
        if s < end and e > start:
            if out and abs(out[-1][3] - y1) < 2 and x0 - out[-1][2] < 12:
                out[-1][2] = max(out[-1][2], x1)
                out[-1][1] = min(out[-1][1], y0)
            else:
                out.append([x0, y0, x1, y1])
    return out
