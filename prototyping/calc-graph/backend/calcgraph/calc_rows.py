"""Calc package -> RECORDS keyed by what each record PRINTS, for any output style.

    read_records(pages, known) -> {"records": [...], "unreadable_pages": [...], "stats": {...}}

`pages` is calcpkg_ingest.read_package(...)["pages"] (page id, software, title, rows); `known`
maps a printed token to a registry node id ({"G-L2-1-AB": "G-L2-1-AB", "ST-3": "DETAIL:ST-3",
"SMF-A": "FRAME:SMF-A"}), built by the caller from the model / drawings - this module knows no
naming convention of its own.

Why not calc_records.py: that reader is built on RISA report tables (cell-border segments, RISA
entity labels M12 / N4, RISA table titles); a RAM summary, an Excel schedule, a Mathcad sheet, an
Enercalc page or a hand calc gives it no table rows (0 rows on the synthetic v2 package). The
engineer's record is recognisable in every style by the same thing: the row or block that names
the element (or typical detail, or frame) it designs.

Rules, each recorded on the record it produced:
- anchor: a text row whose first token (or dotted piece of one: Mathcad "phiRn.DC-1") that resolves
  through `known` names the record's subject
  (that token = the anchor; later known tokens on the row are MENTIONS)
- the identifier must lead the row (first or second cell: a row index or a "DESCRIPTION:" label
  may precede it); prose that names an element mid-sentence is a mention, not a record; a later
  identifier on the row starts a side-by-side record only when the cells after it repeat the
  shape of the cells after the first ("DC-1 := 60 kip  BG-1 := 250 kip"); a next line that
  restates the same subject continues the record
- table: anchors whose x positions agree (+-6 pt, at least 3 of them) are rows of one table
  column; a table record is its anchor row plus continuation rows below it (no anchor, starting
  at or right of the anchor x) until the next anchor or a gap of more than 1.8 line pitches; when
  another table column sits to the right on the same rows, the record stops short of it
- block: any other anchor (an Enercalc page title, a hand-calc heading, a worked example) owns
  the rows from it down to the next anchor row, the next section heading of the same rank (a row
  printed at the anchor row's heading size, when that is larger than the page's body text: a RISA
  "Load Combinations" table after the "SCBF-1 Story Drift" section is not part of it; the subject
  field "DESCRIPTION: <member>" is not a heading and keeps its page) or the end of the page body
- no anchor on a page: a page with >= 5 lines carrying an assignment (" = ", ":=") is one record (a calc sheet, its tables
  included); else rows of a numeric table (>= 5 cells, >= 50 % numeric, text first cell; a
  spreadsheet's row-number gutter dropped) are one record each; else the page holds no record
  (cover, contents, model sketch)
- page body excludes the header / footer bands (top 12 %, bottom 7 %) and rows that start with a
  header field of the profile's boilerplate ("Model Name", "Job Number" ...)
- one record per subject per page: rows of several tables / blocks on one page that name the same
  subject are occurrences of ONE record (same id; the caller adds an occurrence per row)
- a page with no text layer is reported unreadable (no OCR here), never guessed
"""
from __future__ import annotations

import re
from collections import defaultdict

HEAD, FOOT = 0.12, 0.07
_NUM = re.compile(r"^[-+]?[\d,]*\.?\d+(?:/\d+)?[%']?$|^-$")


def _tok(s: str) -> str:
    return s.strip().strip(",;:()[]")


def _parts(cell: str) -> list[str]:
    """A cell and its pieces: Mathcad glues names to variables ("phiRn.DC-1"), tables to punctuation."""
    t = _tok(cell)
    return list(dict.fromkeys([t] + [_tok(x) for x in re.split(r"[.:=,;()\[\]/]", t) if len(_tok(x)) >= 2]))


def _union(rects) -> list[float]:
    return [round(min(r[0] for r in rects), 2), round(min(r[1] for r in rects), 2),
            round(max(r[2] for r in rects), 2), round(max(r[3] for r in rects), 2)]


def _words_rows(page: dict) -> list[dict]:
    """calcpkg rows carry cells + a row rect; rebuild per-word x positions from the page lines."""
    rows = []
    H = page["height"]
    for r in page["rows"]:
        x0, y0, x1, y1 = r["rect"]
        if y1 < HEAD * H or y0 > (1 - FOOT) * H:
            continue
        rows.append({"cells": r["cells"], "rect": r["rect"]})
    return rows


def _shape(cell: str) -> str:
    return re.sub(r"[A-Za-z]+[-.]?\d+[A-Za-z0-9-]*", "ID", re.sub(r"[\d,.]+", "#", cell))


def _word_x(page: dict, row: dict, cell: str, nth: int) -> float:
    """x of the nth occurrence of a word on the row band (page lines are split into words by position)."""
    y = (row["rect"][1] + row["rect"][3]) / 2
    xs = []
    for ln in page["lines"]:
        if ln["rect"][1] <= y <= ln["rect"][3] and cell in ln["text"]:
            xs.append(ln["rect"][0] + (ln["rect"][2] - ln["rect"][0]) * ln["text"].index(cell) / max(1, len(ln["text"])))
    xs.sort()
    return xs[min(nth, len(xs) - 1)] if xs else row["rect"][0]


def _cell_x(page: dict, row: dict, token: str) -> float:
    """x of a token in a row: the page line that holds it on the row's band, else the row start."""
    for ln in page["lines"]:
        lr = ln["rect"]
        if lr[1] <= (row["rect"][1] + row["rect"][3]) / 2 <= lr[3] and token in ln["text"].split():
            return lr[0]
    return row["rect"][0]


def _row_size(page: dict, row: dict) -> float:
    """Largest font size of the page lines on a row's band."""
    y = (row["rect"][1] + row["rect"][3]) / 2
    return max((ln.get("size") or 0.0 for ln in page["lines"] if ln["rect"][1] <= y <= ln["rect"][3]), default=0.0)


def read_records(pages: list[dict], known: dict[str, str], boiler: re.Pattern | None = None,
                 subject_field: str = "DESCRIPTION") -> dict:
    """boiler: the profile's header-line regex (calcs.boilerplate_rx); a row that starts with a header
    field ("Model Name : ...", "Job Number : ...") is page header, never a record anchor - except the
    subject field (calcs.title.description_prefix, Enercalc's "DESCRIPTION: <member>"), which names
    what the page designs."""
    out, unreadable, stats = [], [], defaultdict(int)
    for p in pages:
        if not p["lines"]:
            unreadable.append({"page": p["page"], "sheet": p["sheet_id"], "reason": "no text layer (scanned page, no OCR)"})
            continue
        if p.get("toc") or p["title"] in ("Cover", "TOC"):
            continue
        rows = _words_rows(p)
        if not rows:
            continue
        # anchors
        anchors = []
        for i, r in enumerate(rows):
            if boiler is not None and any(boiler.match(" ".join(r["cells"][:k])) for k in (1, 2, 3)) \
                    and not r["cells"][0].upper().startswith(subject_field.upper()):
                continue
            cells = r["cells"]
            hits = [(j, t, known[t]) for j, c in enumerate(cells) for t in _parts(c) if t in known]
            if not hits or hits[0][0] > 1:
                continue        # prose that mentions an identifier mid-sentence does not start a record
            # a later identifier starts a SIDE-BY-SIDE record only when the cells after it repeat the shape of
            # the cells after the first one ("phiRn.DC-1 := 60 kip  phiRn.BG-1 := 250 kip"); else it is a mention
            heads = [hits[0]]
            for h in hits[1:]:
                seg = [_shape(c) for c in cells[heads[-1][0] + 1:h[0]]]
                if seg and seg == [_shape(c) for c in cells[h[0] + 1:h[0] + 1 + len(seg)]]:
                    heads.append(h)
            for n, (j, tok, node) in enumerate(heads):
                j_end = heads[n + 1][0] if n + 1 < len(heads) else len(cells)
                ment = [nd for (jj, _, nd) in hits if j < jj < j_end and nd != node]
                x = _cell_x(p, r, cells[j]) if n == 0 else _word_x(p, r, cells[j], n)
                prev = [a for a in anchors if a["row"] == i - 1 - len(a.get("also", [])) and abs(a["x"] - x) <= 12
                        and a["node"] == node]
                if prev:
                    prev[0]["also"] = prev[0].get("also", []) + [i]   # the next line restates the subject
                    continue
                anchors.append({"row": i, "node": node, "token": tok, "x": x, "mentions": list(dict.fromkeys(ment))})
        if anchors:
            # columns of anchors at the same x
            groups: list[list[dict]] = []
            for a in sorted(anchors, key=lambda a: a["x"]):
                if groups and abs(groups[-1][0]["x"] - a["x"]) <= 6:
                    groups[-1].append(a)
                else:
                    groups.append([a])
            table_x = sorted(g[0]["x"] for g in groups if len(g) >= 3)
            arow = {a["row"] for a in anchors}
            also = {k for a in anchors for k in a.get("also", [])}
            pitch = sorted(rows[i + 1]["rect"][1] - rows[i]["rect"][1] for i in range(len(rows) - 1)) or [12.0]
            pitch = pitch[len(pitch) // 2] or 12.0
            sizes = sorted(_row_size(p, r) for r in rows)
            body_size = sizes[len(sizes) // 2] if sizes else 0.0
            for a in anchors:
                is_table = any(abs(a["x"] - x) <= 6 for x in table_x)
                head_size = _row_size(p, rows[a["row"]])
                # a heading anchor ("SCBF-1 Story Drift ..."), not the subject field (Enercalc's
                # "DESCRIPTION: <member>" owns its whole page)
                is_heading = (not is_table and head_size > body_size + 0.5
                              and not rows[a["row"]]["cells"][0].upper().startswith(subject_field.upper()))

                def xr_of(k):   # another table column's anchor further right on the same row bounds this record:
                    xs = [b["x"] for b in anchors if b["row"] == k and b["x"] > a["x"] + 6 and any(abs(b["x"] - x) <= 6 for x in table_x)]
                    if not xs:
                        return 1e9
                    y = (rows[k]["rect"][1] + rows[k]["rect"][3]) / 2   # ... at the end of its last text left of that column
                    ends = [ln["rect"][2] for ln in p["lines"] if ln["rect"][1] <= y <= ln["rect"][3]
                            and ln["rect"][0] >= a["x"] - 4 and ln["rect"][2] <= min(xs) - 1]
                    return max(ends) if ends else min(xs) - 2
                xr = xr_of(a["row"])
                rects = [[max(a["x"], rows[a["row"]]["rect"][0]), rows[a["row"]]["rect"][1],
                          min(xr, rows[a["row"]]["rect"][2]), rows[a["row"]]["rect"][3]]]
                last = rows[a["row"]]
                nxt_anchor = [b["row"] for b in anchors if b["row"] > a["row"] and (not is_table or abs(b["x"] - a["x"]) <= 6
                                                                                   or b["x"] < a["x"])]
                stop = min(nxt_anchor) if nxt_anchor else len(rows)
                for k in range(a["row"] + 1, stop):
                    r = rows[k]
                    if k not in a.get("also", []) and k in also:
                        break
                    if is_table and k not in a.get("also", []) and (r["rect"][1] - last["rect"][3] > 1.8 * pitch
                                                                    or r["rect"][0] < a["x"] - 4 or k in arow):
                        break
                    if k in arow:
                        break
                    if is_heading and k not in a.get("also", []) and abs(_row_size(p, r) - head_size) <= 0.05:
                        break   # the next section heading of the same rank ends the block
                    rects.append([r["rect"][0] if k in a.get("also", []) else max(a["x"] if is_table else r["rect"][0], r["rect"][0]),
                                  r["rect"][1], min(xr_of(k), r["rect"][2]),
                                  r["rect"][3]])
                    last = r
                rects = [q for q in rects if q[2] > q[0]]
                text = " ".join(rows[a["row"]]["cells"])[:120]
                out.append({"page": p["page"], "sheet": p["sheet_id"], "software": p["software"], "title": p["title"],
                            "anchor": a["token"], "subject": a["node"], "mentions": a["mentions"], "bbox": _union(rects),
                            "how": "calc_row" if is_table else "calc_block", "text": text,
                            "rule": ("table row: anchor column of >= 3 aligned identifiers + its continuation rows" if is_table
                                     else "block: identifier heading down to the next identifier or the page end")})
                stats["table_rows" if is_table else "blocks"] += 1
            continue
        # no anchor: a calc sheet (its tables are part of the calc), else numeric table rows, else nothing
        eq = [ln for ln in p["lines"] if re.search(r"\s=\s|:=", ln["text"]) and HEAD * p["height"] < ln["rect"][1] < (1 - FOOT) * p["height"]]
        def body(cells):   # a spreadsheet printout's row-number gutter is not a cell of the table
            return cells[1:] if len(cells) > 2 and re.fullmatch(r"\d{1,3}", cells[0]) and not _NUM.match(cells[1]) else cells
        trows = [r for r in rows if len(body(r["cells"])) >= 5 and not _NUM.match(body(r["cells"])[0])
                 and sum(bool(_NUM.match(c)) for c in body(r["cells"])) >= 0.5 * len(body(r["cells"]))]
        if len(trows) >= 2 and len(eq) < 5:
            for r in trows:
                out.append({"page": p["page"], "sheet": p["sheet_id"], "software": p["software"], "title": p["title"],
                            "anchor": r["cells"][0], "subject": None, "mentions": [], "bbox": [round(v, 2) for v in r["rect"]],
                            "how": "calc_row", "text": " ".join(r["cells"])[:120],
                            "rule": "numeric table row (no registry identifier printed): one record per row"})
                stats["numeric_rows"] += 1
            continue
        if len(eq) >= 5:
            out.append({"page": p["page"], "sheet": p["sheet_id"], "software": p["software"], "title": p["title"],
                        "anchor": None, "subject": None, "mentions": [], "bbox": _union([r["rect"] for r in rows]),
                        "how": "calc_block", "text": p["title"][:120],
                        "rule": "calc sheet with no identifier: the page body is one record"})
            stats["page_records"] += 1
    # one record per subject per page: a page that prints the same member in several tables (RISA's
    # girder check, its F2.3 table and its governing-combination table; a worked example and its summary
    # row) prints ONE design record of it - each row is an occurrence of that record, sharing its id
    seen: dict[tuple, str] = {}
    per_sheet: dict[str, int] = defaultdict(int)
    for r in out:
        k = (r["page"], r["subject"]) if r["subject"] else None
        if k in seen:
            r["id"] = seen[k]
            stats["same_subject_rows_merged"] += 1
            continue
        per_sheet[r["sheet"]] += 1
        r["id"] = f"REC:{r['sheet']}#{per_sheet[r['sheet']]}"
        if k:
            seen[k] = r["id"]
    return {"records": out, "unreadable_pages": unreadable, "stats": dict(stats)}
