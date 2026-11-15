"""Calc graph from a real calc package: one node per calc page, keyed by the engineer's
sheet number (the "sheet no." on the calc pad: A1, B10, C23 ...), grouped by section (A-E) and by
sub-calc (consecutive pages carrying the same table / sketch title).

Every token the graph or the mapper uses (entity labels, member sizes, drawing
references, load names) is kept with the PDF-point box of the word(s) it came from,
so any node or edge can be shown on the original page with a highlight.

Set conventions come from the set's profile (calcgraph/profiles/*.yaml): page id regex and
the regions it is looked for in (top-right corner; left margin of rotated RISA sketch pages),
excluded words (material grades), banner / boilerplate / stamp text, RISA label regexes,
title rules per output style, software detectors and the section map (subtotal rows).
A package without page ids (the stair calcs) gets ids <PREFIX>-<page>.
"""
from __future__ import annotations

import re
from collections import defaultdict

import pymupdf

from . import profiles, sizes

# the generic profile's page-id rule, for callers that have no set profile in hand
PAGE_ID = profiles.load("default").calcs.page_id.regex


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


def _page_id(words, pf) -> tuple[str, list] | None:
    pi = pf.calcs.page_id
    cands = [w for w in words if pi.regex.match(w[4]) and w[4] not in pi.exclude]
    for region in pi.regions:
        pick = [w for w in cands if region.holds(w)]
        if pick:
            return pick[0][4], _rect(pick[0])
    return None


def _title(lines: list[dict], words, pf) -> tuple[str, list, list[dict]]:
    """(title, title rect, tables[]). Per output style, first match wins:
    Enercalc   'Steel Beam' + the DESCRIPTION value on the same baseline
    RISA       table titles (11.6 pt, x < 60) / sketch titles (12 pt, rotated); RISA-3D
               output uses 9 pt titles at x < 60 just under the header block
    calc pad   firm calc pad: the heading under the header, else the subject field
    else       first line that is not header boilerplate
    """
    C, T = pf.calcs, pf.calcs.title
    CONTINUED, BANNER, PAGE_ID, BOILER = C.continued_regex, C.banner_regex, C.page_id.regex, C.boilerplate_rx
    tables = [{"title": CONTINUED.sub(" ", l["text"]).strip(), "rect": l["rect"]} for l in lines
              if l["size"] >= T.table_title_min_size and l["dir"] == [1.0, 0.0] and l["rect"][0] < T.table_title_x_max
              and not BANNER.match(l["text"])]
    desc = next((l for l in lines if l["text"].upper().startswith(T.description_prefix)), None)
    if desc:
        head = next((l["text"] for l in lines if l["text"] in T.design_heads), "")
        val = next((l for l in lines if abs(l["rect"][1] - desc["rect"][1]) < 3 and l["rect"][0] > desc["rect"][2] - 1), None)
        txt = (val["text"] if val else desc["text"].split(":", 1)[-1]).strip()
        return (f"{head} - {txt}" if head else txt), (val or desc)["rect"], tables
    r3 = T.risa3d
    if any(l["text"] == r3.marker_line for l in lines) and not tables:
        # every RISA-3D table title on the page (same style: >= min_size, x < x_max, below the header block);
        # the first one, just under the header, is the page title. A frame page prints several member tables
        # (beams, then columns, then reactions): each one is a table of this page, not only the first
        r3t = [{"title": CONTINUED.sub(" ", l["text"]).strip(), "rect": l["rect"]}
               for l in sorted(lines, key=lambda l: (l["rect"][1], l["rect"][0]))
               if l["rect"][0] < r3.x_max and l["rect"][1] > r3.y.lo and l["size"] >= r3.min_size
               and l["dir"] == [1.0, 0.0] and not BANNER.match(l["text"])]
        t = next((x for x in r3t if x["rect"][1] < r3.y.hi), None)
        if t:
            return t["title"], t["rect"], r3t
    big = [l for l in lines if l["size"] >= T.table_title_min_size and not BANNER.match(l["text"])
           and l["text"].upper() not in T.big_line_skip
           and not PAGE_ID.match(l["text"]) and re.search(r"[A-Za-z]{3}", l["text"])]
    if big:
        l = sorted(big, key=lambda l: (l["rect"][1], l["rect"][0]))[0]
        return CONTINUED.sub(" ", l["text"]).strip(), l["rect"], tables
    pad = T.pad
    if any(l["text"] == pad.marker_line for l in lines):
        h = [l for l in lines if l["size"] >= pad.heading_min_size and pad.heading_y.lo < l["rect"][1] < pad.heading_y.hi
             and re.search(r"[A-Za-z]{4}", l["text"])]
        if h:
            return h[0]["text"], h[0]["rect"], tables
        sub = [l for l in lines if pad.subject_y.lo < l["rect"][1] < pad.subject_y.hi and pad.subject_x.lo < l["rect"][0] < pad.subject_x.hi
               and re.search(r"[A-Za-z]{3}", l["text"])
               and not BOILER.match(l["text"])]
        if sub:
            return sub[0]["text"], sub[0]["rect"], tables
    for key in T.field_keys:
        l = next((l for l in lines if l["text"].startswith(key)), None)
        if l:
            return l["text"].split(":", 1)[1].strip(), l["rect"], tables
    for l in sorted(lines, key=lambda l: (l["rect"][1], l["rect"][0])):
        t = l["text"]
        if BOILER.match(t) or len(t) < 4 or re.fullmatch(r"[\d.,\s:'\"%-]+", t) or BANNER.match(t) or PAGE_ID.match(t):
            continue
        return CONTINUED.sub(" ", t).strip(), l["rect"], tables
    return "", None, tables


def _level(title: str, pf) -> str:
    m = pf.calcs.level_regex.search(title)  # "Level 2_Design Results" too
    if m:
        v = m.group(1)
        return "Roof" if v.lower() == "roof" else "Level " + v.split()[-1][-1]
    return ""


def _signature_text(lines: list[dict], width: float, height: float, C) -> str:
    """The lines a program signs a page with: those in the profile's header / footer bands, measured
    across the line's own baseline (a rotated sketch page prints its footer up the long edge)."""
    b = C.software_signature_band
    out = []
    for l in lines:
        x0, y0, x1, y1 = l["rect"]
        if abs(l["dir"][0]) >= abs(l["dir"][1]):
            hit = y1 <= b.top * height or y0 >= (1 - b.bottom) * height
        else:
            e = max(b.top, b.bottom) * width
            hit = x1 <= e or x0 >= width - e
        if hit:
            out.append(l["text"])
    return "\n".join(out)


def _software(text: str, sid: str, pf) -> str:
    for det in pf.calcs.software:
        for rule in det.any:
            if all(rx.search(text) for rx in rule.all) and (rule.sheet_id_first is None or sid[:1] in rule.sheet_id_first):
                return det.name
    return pf.calcs.fallback_software


def read_package(path: str, doc_key: str, id_prefix: str | None = None,
                 profile: "profiles.Profile | str | None" = None) -> dict:
    pf = profiles.resolve(profile, path)
    C = pf.calcs
    labels = [(lb.kind, lb.regex) for lb in C.labels]
    doc = pymupdf.open(path)
    pages = []
    for i, page in enumerate(doc):
        words = page.get_text("words")
        lines = _lines(page)
        text = page.get_text()
        pid = _page_id(words, pf) if id_prefix is None else None
        sid, sid_rect = (pid if pid else (f"{id_prefix or doc_key.upper()}-{i + 1}", None))
        title, title_rect, tables = _title(lines, words, pf)
        if not title and i == 0:
            title = "Cover"
        if title_rect is None:   # no title on the page (a scanned page has no text at all): the page is the evidence
            title_rect = [0.0, 0.0, round(page.rect.width, 1), round(page.rect.height, 1)]
        toc = len(re.findall(r"\.{6,}", text)) >= C.toc_min_leaders
        section = sid[0] if pid else (id_prefix or doc_key.upper())
        software = _software(_signature_text(lines, page.rect.width, page.rect.height, C) if C.software_signature_band else text, sid, pf)
        risa = C.risa_sizes(software)
        banner = next((l["text"] for l in lines if C.banner_regex.match(l["text"])), "")
        tokens: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
        size_hits: dict[str, list] = defaultdict(list)
        size_raw: dict[str, str] = {}
        truncated = []
        refs = []
        for w in words:
            t = w[4].strip().rstrip(",;")
            for kind, rx in labels:
                if rx.match(t):
                    if len(tokens[kind][t]) < 4:
                        tokens[kind][t].append(_rect(w))
                    break
            # RISA joins label and shape: "1 W18X283" is fine; "HSS8X8X3" is RISA sixteenths (risa pages only)
            for part in re.split(r"(?<=[0-9/])(?=(?:HSS|W|MC|C|L)\d)", t):
                info = sizes.norm(part, risa=risa)
                if info:
                    if len(size_hits[info["norm"]]) < 6:
                        size_hits[info["norm"]].append(_rect(w))
                    size_raw.setdefault(info["norm"], part)
                elif sizes.is_truncated_size(part):
                    truncated.append({"text": part, "rect": _rect(w)})
        for l in lines:
            for m in C.drawing_ref_regex.finditer(l["text"]):
                refs.append({"detail": m.group(1), "sheet": m.group(2), "text": m.group(0), "rect": l["rect"]})
        sm = None
        rows = _rows(words, C.stamp_text_regex)
        sub_pre = (C.sections.get(section) or profiles.Section(title="")).subtotal_row_prefix
        if sub_pre:
            sr = next((r for r in rows if r["cells"] and r["cells"][0].startswith(sub_pre)), None)
            sm = {"text": " ".join(sr["cells"]), "rect": sr["rect"]} if sr else None
        pages.append({
            "id": f"{doc_key}:{sid}", "rows": rows, "doc": doc_key, "page": i + 1, "sheet_id": sid, "sheet_rect": sid_rect,
            "section": section, "title": title or "(untitled)", "title_rect": title_rect, "tables": tables,
            "banner": banner, "level": _level(title, pf), "software": software, "toc": toc,
            "width": page.rect.width, "height": page.rect.height,
            "labels": {k: dict(v) for k, v in tokens.items()}, "sizes": dict(size_hits), "size_raw": size_raw,
            "truncated": truncated[:20], "drawing_refs": refs, "lines": lines,
            "subtotal": sm,
            # provenance of the sheet node: a sheet id the profile's rule found, else an id made from the page number
            "rule": "calcpkg_ingest.sheet_id_and_title" if pid else "calcpkg_ingest.page_number_id",
            "confidence": 1.0 if pid else 0.5,
        })
    # sections carry forward over pages without their own id (none expected in calc-pad output)
    _group(pages, C.continued_regex)
    return {"pages": pages, "meta": {"page_count": len(doc)}}




def _rows(words, stamp=None) -> list[dict]:
    """Table rows: horizontal words clustered by centre line (3 pt), the profile's stamp text removed."""
    ws = []
    for w in words:
        if len(w[4]) >= 3 and (w[3] - w[1]) > 2 * (w[2] - w[0]):  # rotated text, not a table cell
            continue
        t = stamp.sub("", w[4]) if stamp else w[4]
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


def _norm_title(t: str, continued) -> str:
    return re.sub(r"[^a-z0-9]", "", continued.sub("", t).lower())


def _group(pages: list[dict], continued) -> None:
    cur = None
    for p in pages:
        key = (p["section"], _norm_title(p["title"], continued))
        if cur is None or cur[0] != key:
            cur = (key, f"{p['doc']}:{p['sheet_id']}")
        p["group"] = cur[1]
