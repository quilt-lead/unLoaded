"""Calc graph from a real calc package: one node per calc page, keyed by the engineer's
sheet number (KPFF "sheet no." A1, B10, C23 ...), grouped by section (A-E) and by
sub-calc (consecutive pages carrying the same table / sketch title).

Every token the graph or the mapper uses (entity labels, member sizes, drawing
references, load names) is kept with the PDF-point box of the word(s) it came from,
so any node or edge can be shown on the original page with a highlight.

Page id rule: a word matching ^[A-E]\\d{1,3}(_\\d{1,3})?$ in the top-right corner
(x > 480, y < 45) or, on RISA sketch pages whose content is rotated, in the left
margin (x < 45, 40 < y < 130). Material grades (A36, A992, A500 ...) never qualify.
A package without such ids (the stair calcs) gets ids <PREFIX>-<page>.
"""
from __future__ import annotations

import re
from collections import defaultdict

import pymupdf

from . import sizes

PAGE_ID = re.compile(r"^[A-E]\d{1,3}(?:_\d{1,3})?$")
GRADES = {"A36", "A53", "A500", "A572", "A992", "A325", "A490", "A307", "A615", "A706", "A1085"}
BANNER = re.compile(r"^([A-E])_[A-Z ]+$")
BOILER = re.compile(r"^(project|by|location|date|client|job no\.?|sheet no\.?|company|designer|job number|model name|"
                    r"checked by.*|:|kpff.*|building&safety.*|permits:.*|plb21-\d+|\d{1,2}/\d{1,2}/\d{2,4}|dana point.*|"
                    r"sms.*|1900799|pd|risa outputs|18400 von karman.*|irvine.*|\(949\).*|lic\..*|software copyright.*|"
                    r"kpff consulting engineers|project file.*|project title.*|engineer.*|description:?|"
                    r"may \d+, 2021.*|\d+:\d+ [ap]m|[a-z]+ \d+, 20\d\d)$", re.I)
CONTINUED = re.compile(r"\s*\((?:Continued|cont\.?)\)\s*", re.I)

# entity labels and the scope they live in
LABELS = [
    ("FN", re.compile(r"^F(\d)_N(\d+)$")),            # RISA-3D floor node  F1_N14
    ("FM", re.compile(r"^F(\d)_M(\d+)$")),            # RISA-3D floor member F2_M30
    ("R3D", re.compile(r"^R3D_N(\d+)$")),             # foundation joint from RISA-3D node
    ("FLR", re.compile(r"^FLR_(\d)_N(\d+(?:_\d+)?)$")),  # foundation joint from a RISAFloor floor
    ("M", re.compile(r"^(?:M|PUR)\d+$")),             # RISAFloor member
    ("N", re.compile(r"^N\d+$")),                     # node / point
    ("CS", re.compile(r"^CS\d+$")),                   # column stack
    ("STACK", re.compile(r"^\(([A-E](?:\.\d)?-\d(?:\.\d)?)\)(?:_L\d)?$")),  # grid-named stack (C.8-4)
]
DRAWING_REF = re.compile(r"(\d{1,2})/(S\d+(?:\.\d+){1,3})")
SHEET_REF = re.compile(r"^(S\d+\.\d+\.\d+)")


def _rect(b) -> list[float]:
    return [round(b[0], 1), round(b[1], 1), round(b[2], 1), round(b[3], 1)]


def _lines(page) -> list[dict]:
    out = []
    for b in page.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            t = "".join(s["text"] for s in l["spans"]).strip()
            if t:
                out.append({"text": t, "size": round(max(s["size"] for s in l["spans"]), 1), "rect": _rect(l["bbox"]),
                            "dir": [round(v, 2) for v in l["dir"]]})
    return out


def _page_id(words) -> tuple[str, list] | None:
    cands = [w for w in words if PAGE_ID.match(w[4]) and w[4] not in GRADES]
    tr = [w for w in cands if w[0] > 480 and w[1] < 45]
    lm = [w for w in cands if w[0] < 45 and 40 < w[1] < 130]
    pick = (tr or lm)
    if not pick:
        return None
    w = pick[0]
    return w[4], _rect(w)


def _title(lines: list[dict], words) -> tuple[str, list, list[dict]]:
    """(title, title rect, tables[]). Per output style, first match wins:
    Enercalc   'Steel Beam' + the DESCRIPTION value on the same baseline
    RISA       table titles (11.6 pt, x < 60) / sketch titles (12 pt, rotated); RISA-3D
               output uses 9 pt titles at x < 60 just under the header block
    calc pad   KPFF pad: the 10+ pt heading under the header, else the subject field
    else       first line that is not header boilerplate
    """
    tables = [{"title": CONTINUED.sub(" ", l["text"]).strip(), "rect": l["rect"]} for l in lines
              if l["size"] >= 11.5 and l["dir"] == [1.0, 0.0] and l["rect"][0] < 60 and not BANNER.match(l["text"])]
    desc = next((l for l in lines if l["text"].upper().startswith("DESCRIPTION")), None)
    if desc:
        head = next((l["text"] for l in lines if l["text"] in ("Steel Beam", "Steel Column", "Wood Beam", "Wood Column")), "")
        val = next((l for l in lines if abs(l["rect"][1] - desc["rect"][1]) < 3 and l["rect"][0] > desc["rect"][2] - 1), None)
        txt = (val["text"] if val else desc["text"].split(":", 1)[-1]).strip()
        return (f"{head} - {txt}" if head else txt), (val or desc)["rect"], tables
    if any(l["text"] == "Model Name" for l in lines) and not tables:
        t = next((l for l in sorted(lines, key=lambda l: l["rect"][1])
                  if l["rect"][0] < 60 and 95 < l["rect"][1] < 118 and l["size"] >= 8.5), None)
        if t:
            return CONTINUED.sub(" ", t["text"]).strip(), t["rect"], [{"title": CONTINUED.sub(" ", t["text"]).strip(),
                                                                       "rect": t["rect"]}]
    big = [l for l in lines if l["size"] >= 11.5 and not BANNER.match(l["text"]) and l["text"].upper() != "RISA OUTPUTS"
           and not PAGE_ID.match(l["text"]) and re.search(r"[A-Za-z]{3}", l["text"])]
    if big:
        l = sorted(big, key=lambda l: (l["rect"][1], l["rect"][0]))[0]
        return CONTINUED.sub(" ", l["text"]).strip(), l["rect"], tables
    if any(l["text"] == "sheet no." for l in lines):
        h = [l for l in lines if l["size"] >= 9.8 and 112 < l["rect"][1] < 150 and re.search(r"[A-Za-z]{4}", l["text"])]
        if h:
            return h[0]["text"], h[0]["rect"], tables
        sub = [l for l in lines if 84 < l["rect"][1] < 104 and 270 < l["rect"][0] < 420 and re.search(r"[A-Za-z]{3}", l["text"])
               and not BOILER.match(l["text"])]
        if sub:
            return sub[0]["text"], sub[0]["rect"], tables
    for key in ("Model:",):
        l = next((l for l in lines if l["text"].startswith(key)), None)
        if l:
            return l["text"].split(":", 1)[1].strip(), l["rect"], tables
    for l in sorted(lines, key=lambda l: (l["rect"][1], l["rect"][0])):
        t = l["text"]
        if BOILER.match(t) or len(t) < 4 or re.fullmatch(r"[\d.,\s:'\"%-]+", t) or BANNER.match(t) or PAGE_ID.match(t):
            continue
        return CONTINUED.sub(" ", t).strip(), l["rect"], tables
    return "", None, tables


def _level(title: str, text: str) -> str:
    m = re.search(r"\b(Level\s*\d|Roof)(?![A-Za-z0-9])", title, re.I)  # "Level 2_Design Results" too
    if m:
        v = m.group(1)
        return "Roof" if v.lower() == "roof" else "Level " + v.split()[-1][-1]
    return ""


def _software(text: str, sid: str) -> str:
    if "ENERCALC" in text.upper():
        return "Enercalc"
    if "RISAFloor" in text or (".rfl" in text and sid[:1] in "BD"):
        return "RISAFloor"
    if re.search(r"RISA-?3D", text) or (sid[:1] == "C" and ".rfl" in text):
        return "RISA-3D"
    if "CFS" in text and "Project Name" in text:
        return "CFS Designer"
    return "Spreadsheet / hand calc"


def read_package(path: str, doc_key: str, id_prefix: str | None = None) -> dict:
    doc = pymupdf.open(path)
    pages = []
    for i, page in enumerate(doc):
        words = page.get_text("words")
        lines = _lines(page)
        text = page.get_text()
        pid = _page_id(words) if id_prefix is None else None
        sid, sid_rect = (pid if pid else (f"{id_prefix or doc_key.upper()}-{i + 1}", None))
        title, title_rect, tables = _title(lines, words)
        if not title and i == 0:
            title = "Cover"
        toc = len(re.findall(r"\.{6,}", text)) >= 3
        section = sid[0] if pid else (id_prefix or doc_key.upper())
        banner = next((l["text"] for l in lines if BANNER.match(l["text"])), "")
        tokens: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
        size_hits: dict[str, list] = defaultdict(list)
        size_raw: dict[str, str] = {}
        truncated = []
        refs = []
        for w in words:
            t = w[4].strip().rstrip(",;")
            for kind, rx in LABELS:
                if rx.match(t):
                    if len(tokens[kind][t]) < 4:
                        tokens[kind][t].append(_rect(w))
                    break
            # RISA joins label and shape: "1 W18X283" is fine, "HSS8X8X3" is RISA eighths
            for part in re.split(r"(?<=[0-9/])(?=(?:HSS|W|MC|C|L)\d)", t):
                info = sizes.norm(part)
                if info:
                    if len(size_hits[info["norm"]]) < 6:
                        size_hits[info["norm"]].append(_rect(w))
                    size_raw.setdefault(info["norm"], part)
                elif sizes.is_truncated_size(part):
                    truncated.append({"text": part, "rect": _rect(w)})
        for l in lines:
            for m in DRAWING_REF.finditer(l["text"]):
                refs.append({"detail": m.group(1), "sheet": m.group(2), "text": m.group(0), "rect": l["rect"]})
        if not sid.startswith("A"):
            sm = None
        rows = _rows(words)
        if sid.startswith("A"):
            sr = next((r for r in rows if r["cells"] and r["cells"][0].startswith("Subtotal")), None)
            sm = {"text": " ".join(sr["cells"]), "rect": sr["rect"]} if sr else None
        pages.append({
            "id": f"{doc_key}:{sid}", "rows": rows, "doc": doc_key, "page": i + 1, "sheet_id": sid, "sheet_rect": sid_rect,
            "section": section, "title": title or "(untitled)", "title_rect": title_rect, "tables": tables,
            "banner": banner, "level": _level(title, text), "software": _software(text, sid), "toc": toc,
            "width": page.rect.width, "height": page.rect.height,
            "labels": {k: dict(v) for k, v in tokens.items()}, "sizes": dict(size_hits), "size_raw": size_raw,
            "truncated": truncated[:20], "drawing_refs": refs, "lines": lines,
            "subtotal": sm,
        })
    # sections carry forward over pages without their own id (none expected in KPFF output)
    _group(pages)
    return {"pages": pages, "meta": {"page_count": len(doc)}}


STAMP = re.compile(r"(Permits:|Building&Safety:|OCPWAzarvandB|PLB21-0900|BNR21-0246,?|ELE21-0853,?|MEC21-0514,?|12/22/2025)")


def _rows(words) -> list[dict]:
    """Table rows: horizontal words clustered by centre line (3 pt), county stamp text removed."""
    ws = []
    for w in words:
        if len(w[4]) >= 3 and (w[3] - w[1]) > 2 * (w[2] - w[0]):  # rotated text, not a table cell
            continue
        t = STAMP.sub("", w[4])
        if t:
            ws.append((w[0], w[1], w[2], w[3], t))
    ws.sort(key=lambda w: (w[1] + w[3]) / 2)
    rows, cur, cy = [], [], None
    for w in ws:
        c = (w[1] + w[3]) / 2
        if cur and abs(c - cy) > 3:
            rows.append(cur)
            cur = []
        if not cur:
            cy = c
        cur.append(w)
    if cur:
        rows.append(cur)
    out = []
    for r in rows:
        r.sort(key=lambda w: w[0])
        out.append({"cells": [w[4] for w in r], "rect": _rect((r[0][0], min(w[1] for w in r), r[-1][2], max(w[3] for w in r)))})
    return out


def _norm_title(t: str) -> str:
    return re.sub(r"[^a-z0-9]", "", CONTINUED.sub("", t).lower())


def _group(pages: list[dict]) -> None:
    cur = None
    for p in pages:
        key = (p["section"], _norm_title(p["title"]))
        if cur is None or cur[0] != key:
            cur = (key, f"{p['doc']}:{p['sheet_id']}")
        p["group"] = cur[1]
