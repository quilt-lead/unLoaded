"""Calc package -> design RECORDS (the engineer's unit), not pages.

Hierarchy: package -> section (A-E) -> run (RISAFloor gravity model, RISA-3D frame model,
RISAFoundation, Enercalc, CFS Designer, spreadsheet / hand calc) -> report table
("Beam Design for Hot Rolled : Roof") -> RECORD (member M19 @ Level 2, column stack
(C.8-4), footing FLR_1_N15, one Enercalc beam over E21-E22) -> values. A page is only an
evidence location: every table row a record is built from keeps doc, page, sheet id, the
row's PDF-point box and its cells.

Deterministic, no AI pass:
- RISA tables: title = BoldItalic line at the left margin; cells come from the vertical
  cell-border segments RISA draws per row (RISAFloor / RISAFoundation); RISA-3D draws none,
  so its columns come from the x-gaps no word crosses in that table. Text is read per
  character so glued words ("Gr....Gravity") split at the border. "(Continued)" titles
  carry a table across pages; blank key cells (the "End" row of a beam, the "Roof" row of
  a column stack) inherit the key above.
- Pages that are not RISA tables (hand calcs, Enercalc, CFS, sketches) become one record
  per sub-calc (consecutive pages with the same title, as calcpkg_ingest groups them).
- Load path joins say what they rest on: exact (a shared label printed on both rows),
  inferred (coordinates or sketch geometry), absent (nothing in the package joins them).
- Positional element<->record matching fits a rigid 2D transform (rotation / mirror
  allowed) from drawing-grid feet to calc-model feet on columns, and reports residuals.

Set conventions (stamp / commentary colours, section -> run map, run descriptions, which sheets
the positional fit uses, the floor whose points name the footings) come from the set's profile
(calcgraph/profiles/*.yaml); `build` resolves it from the file names unless one is passed.
"""
from __future__ import annotations

import math
import re
from collections import defaultdict

import pymupdf

from . import calcpkg_ingest, profiles, sizes

CONT = re.compile(r"\s*\((?:Continued|cont\.?)\)\s*$", re.I)


def _r(b) -> list[float]:
    return [round(b[0], 1), round(b[1], 1), round(b[2], 1), round(b[3], 1)]


def _num(s):
    if s is None:
        return None
    t = str(s).replace(",", "").strip()
    try:
        return float(t)
    except ValueError:
        return None


def _norm_name(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


# ---------------------------------------------------------------- page primitives

def _chars(page, stamp_colors=()) -> list[tuple]:
    """Horizontal characters (x0, y0, x1, y1, cy, c, size), stamp text (by span colour) removed."""
    out = []
    for b in page.get_text("rawdict")["blocks"]:
        for l in b.get("lines", []):
            if l["dir"] != (1.0, 0.0):
                continue
            for s in l["spans"]:
                if s["color"] in stamp_colors:
                    continue
                for ch in s["chars"]:
                    x0, y0, x1, y1 = ch["bbox"]
                    out.append((x0, y0, x1, y1, (y0 + y1) / 2, ch["c"], s["size"]))
    return out


def _vsegs(page) -> list[tuple]:
    out = []
    for d in page.get_drawings():
        for it in d["items"]:
            if it[0] == "l":
                p, q = it[1], it[2]
                if abs(p.x - q.x) < 0.3 and abs(p.y - q.y) > 3:
                    out.append((round(p.x, 1), min(p.y, q.y), max(p.y, q.y)))
    return out


def _text(chs) -> str:
    chs = sorted(chs, key=lambda c: c[0])
    out, prev = "", None
    for c in chs:
        if prev is not None and c[0] - prev[2] > 0.22 * c[6]:
            out += " "
        out += c[5]
        prev = c
    return re.sub(r"\s+", " ", out).strip()


def _cluster_rows(chs, tol=3.0) -> list[list]:
    rows, cur, cy = [], [], None
    for c in sorted(chs, key=lambda c: c[4]):
        if cur and abs(c[4] - cy) > tol:
            rows.append(cur)
            cur = []
        if not cur:
            cy = c[4]
        cur.append(c)
    if cur:
        rows.append(cur)
    return rows


def _gap_bounds(rows) -> list[float]:
    """Column borders for a table without drawn cell borders: x-gaps no word crosses."""
    spans = []
    for r in rows:
        for w in _words(r):
            spans.append((w[0], w[1]))
    if not spans:
        return []
    spans.sort()
    bounds, end = [spans[0][0] - 1], spans[0][1]
    for a, b in spans[1:]:
        if a > end + 2.5:
            bounds.append((end + a) / 2)
        end = max(end, b)
    bounds.append(end + 1)
    return bounds


def _words(chs) -> list[tuple]:
    chs = sorted(chs, key=lambda c: c[0])
    out, cur = [], []
    for c in chs:
        if cur and (c[0] - cur[-1][2] > 0.22 * c[6] or c[5] == " "):
            if cur:
                out.append((cur[0][0], cur[-1][2], cur))
            cur = [] if c[5] == " " else [c]
            continue
        if c[5] != " ":
            cur.append(c)
    if cur:
        out.append((cur[0][0], cur[-1][2], cur))
    return out


def _split(chs, bounds) -> list[str]:
    cells = [[] for _ in range(len(bounds) - 1)]
    for c in chs:
        cx = (c[0] + c[2]) / 2
        for i in range(len(bounds) - 1):
            if bounds[i] <= cx < bounds[i + 1]:
                cells[i].append(c)
                break
    return [_text(c) for c in cells]


def _clean_hdr(h: str) -> str:
    """RISA truncates headers with an ellipsis that spills over the cell border: '.Max End R...'."""
    return re.sub(r"[.\s]+$", "", re.sub(r"^[.\s]+", "", h))


def _clean_val(v: str) -> str:
    return re.sub(r"^\.+\s+", "", v).strip()


def _row_bounds(vs, y0, y1) -> list[float]:
    xs = sorted({v[0] for v in vs if v[1] <= y0 + 2 and v[2] >= y1 - 2})
    out = []
    for x in xs:
        if not out or x - out[-1] > 1.0:
            out.append(x)
    return out


# ---------------------------------------------------------------- RISA tables

def _page_run(text: str, footers) -> str | None:
    for run, marker in footers:
        if marker in text:
            return run
    return None


def read_tables(doc, doc_key: str, page_meta: dict, pf) -> dict:
    """{(run, title): {"run", "title", "header", "rows": [...]}} for every RISA table."""
    footers = pf.calcs.run_footers
    tables: dict[tuple, dict] = {}
    order = []
    for pno, page in enumerate(doc, 1):
        text = page.get_text()
        run = _page_run(text, footers)
        if not run:
            continue
        meta = page_meta[pno]
        titles, footer_y = [], page.rect.height - 40
        for b in page.get_text("dict")["blocks"]:
            for l in b.get("lines", []):
                t = "".join(s["text"] for s in l["spans"]).strip()
                if not t:
                    continue
                if any(t.startswith(m) for _, m in footers):
                    footer_y = min(footer_y, l["bbox"][1])
                if (l["dir"] == (1.0, 0.0) and l["bbox"][0] < 60 and l["bbox"][1] > 90
                        and all("BoldItalic" in s["font"] for s in l["spans"] if s["text"].strip())):
                    titles.append((l["bbox"][1], l["bbox"][3], CONT.sub("", t).strip(), _r(l["bbox"])))
        titles.sort()
        if not titles:
            continue
        chars = _chars(page, set(pf.calcs.stamp_colors))
        vs = _vsegs(page)
        for i, (ty0, ty1, title, trect) in enumerate(titles):
            yend = titles[i + 1][0] if i + 1 < len(titles) else footer_y
            region = [c for c in chars if ty1 + 1 < c[4] < yend - 1]
            rows = _cluster_rows(region)
            if len(rows) < 2:
                continue
            header, data = rows[0], rows[1:]
            key = (run, title)
            if key not in tables:
                tables[key] = {"run": run, "title": title, "header": None, "rows": [], "pages": []}
                order.append(key)
            tb = tables[key]
            tb["pages"].append(meta["page"])
            data_b = []
            for r in data:
                y0, y1 = min(c[1] for c in r), max(c[3] for c in r)
                data_b.append((r, y0, y1, _row_bounds(vs, y0, y1)))
            tb.setdefault("columns_from", "cell borders")
            if not any(len(b[3]) >= 3 for b in data_b):          # RISA-3D: no drawn borders
                gb = _gap_bounds(data)
                data_b = [(r, y0, y1, gb) for r, y0, y1, _ in data_b]
                tb["columns_from"] = "x-gaps (no cell borders drawn; check headers)"
            ref = next((b[3] for b in data_b if len(b[3]) >= 3), None)
            if not ref:
                continue
            hdr = [_clean_hdr(h) for h in _split(header, ref)]
            hnames, seen = [], defaultdict(int)
            for j, h in enumerate(hdr):
                h = h or f"col{j}"
                seen[h] += 1
                hnames.append(h if seen[h] == 1 else f"{h} #{seen[h]}")
            if tb["header"] is None:
                tb["header"] = hnames
            for r, y0, y1, bnd in data_b:
                if len(bnd) < 3:
                    continue
                cells = [_clean_val(c) for c in _split(r, bnd)]
                if not any(cells) or "No Data to Print" in " ".join(cells):
                    continue
                names = tb["header"] if len(tb["header"]) == len(cells) else hnames
                if len(names) != len(cells):
                    names = [f"col{j}" for j in range(len(cells))]
                tb["rows"].append({
                    "doc": doc_key, "page": meta["page"], "sheet": meta["sheet_id"], "table": title,
                    "bbox": _r((min(c[0] for c in r), y0, max(c[2] for c in r), y1)),
                    "cells": dict(zip(names, cells)), "title_rect": trect,
                })
    return {k: tables[k] for k in order}


# ---------------------------------------------------------------- records

LEVEL_RX = re.compile(r"\s*:\s*(Level \d+|Roof)\s*$")


def _split_title(title: str) -> tuple[str, str]:
    m = LEVEL_RX.search(title)
    if m:
        return title[:m.start()].strip(), m.group(1)
    return title, ""


def _rtype(run: str, base: str) -> str:
    if base == "Project Grid Lines":
        return "grid_line"
    if run == "risafloor":
        if base == "Point Locations":
            return "node"
        if base in ("Columns", "Column Design Parameters", "Column Stacks", "Hot Rolled Steel Column Code Checks") \
                or base.startswith("Column Forces/Moments"):
            return "column_stack"
        if base.startswith("Beam ") or base == "Hot Rolled":
            return "member"
        if base == "Uniform Area Loads":
            return "area_load_def"
        if base in ("Tapered Area Loads", "Line Loads", "Point Loads"):
            return "floor_load"
    if run == "risa3d":
        if base.startswith(("Node ", "Envelope Node")):
            return "r3d_node"
        if base.startswith(("Member", "Hot Rolled Steel Design", "Envelope AA", "Envelope AISC")):
            return "r3d_member"
    if run == "risafloor" and base == "Floors":
        return "floor"
    if run == "risafoundation":
        if base.startswith(("Point Loads and Moments", "Footing", "Envelope Footing")):
            return "footing"
    return "parameter"


KEY_PREF = re.compile(r"^(Node Label|Label|Stack Label|Stack|Beam|Joint|Column St.*|Member Label|Member)$", re.I)


def _key_col(header: list[str]) -> str | None:
    cols = header[1:] if header and header[0] in ("", "col0") else header
    for h in cols:
        if KEY_PREF.match(h.strip()):
            return h
    return cols[0] if cols else None


def _stack_label(s: str) -> str:
    return re.sub(r"_L\d+$", "", s)


FOOT_LABEL = re.compile(r"^(R3D_N\d|FLR_\d)")


def _resolve_trunc(key: str, tables: dict, row: dict) -> str:
    """'FLR_1_N1...' -> the one full joint label (from the Point Loads tables, which print
    labels in full) with that prefix that this table does not already print in full; when
    several qualify, take them in the Point Loads order (RISA lists joints in one order)."""
    if not key.endswith(".."):
        return key
    pre = key.rstrip(".")
    full = []
    for (run, title), tb in tables.items():
        if run == "risafoundation" and title.startswith("Point Loads and Moments"):
            for r in tb["rows"]:
                lab = next(iter(v for k, v in r["cells"].items() if k == "Label"), "")
                if lab and not lab.endswith("..") and lab not in full:
                    full.append(lab)
    tb = next(tb for (run, title), tb in tables.items() if title == row["table"] and run == "risafoundation")
    kc = _key_col(tb["header"])
    present = [r["cells"].get(kc, "") for r in tb["rows"]]
    cands = [f for f in full if f.startswith(pre) and f not in present]
    truncs = [p for p in present if p.endswith("..") and p.rstrip(".") == pre]
    k = [i for i, r in enumerate(tb["rows"]) if r is row]
    nth = sum(1 for r in tb["rows"][:k[0]] if r["cells"].get(kc, "").endswith("..") and r["cells"].get(kc, "").rstrip(".") == pre) if k else 0
    if len(cands) == len(truncs) and nth < len(cands):
        row.setdefault("resolved", {})[kc] = {"printed": key, "resolved": cands[nth],
                                              "rule": "truncated joint label resolved by Point Loads order"}
        return cands[nth]
    return key


def build_records(tables: dict) -> dict:
    recs: dict[str, dict] = {}

    def rec(rid, **kw):
        if rid not in recs:
            recs[rid] = {"id": rid, "rows": [], "tables": [], "pages": [], **kw}
        return recs[rid]

    for (run, title), tb in tables.items():
        base, level = _split_title(title)
        rtype = _rtype(run, base)
        hdr = tb["header"] or []
        kc = _key_col(hdr)
        last = None
        for row in tb["rows"]:
            cells = row["cells"]
            key = (cells.get(kc) or "").strip() if kc else ""
            if not key or key in ("Start", "End", "max", "min"):
                key = last
            if key is None:
                continue
            last = key
            if rtype == "column_stack":
                key = _stack_label(key)
            if rtype == "footing" and not FOOT_LABEL.match(key):
                rtype_row = "parameter"
            else:
                rtype_row = rtype
            if rtype_row == "footing":
                key = _resolve_trunc(key, tables, row)
            rtype_eff = rtype_row
            rt = rtype_eff
            if rt == "floor_load":
                sp, ep = cells.get("Start Point"), cells.get("End Point")
                key = f"{cells.get(hdr[0], '')}:{sp}->{ep}" if sp and ep else key
            if rt in ("grid_line", "parameter", "floor_load"):
                rid = f"{run}:{rt}:{base}:{level}:{key}"
            elif rt in ("node", "member"):
                rid = f"{run}:{rt}:{level}:{key}"
            else:
                rid = f"{run}:{rt}:{key}"
            r = rec(rid, type=rt, run=run, label=key,
                    level=level if rt in ("node", "member", "floor_load") else (key if rt == "floor" else ""))
            r["rows"].append(row)
            if title not in r["tables"]:
                r["tables"].append(title)
            if row["page"] not in r["pages"]:
                r["pages"].append(row["page"])
    for r in recs.values():
        r["values"] = _summarise(r)
    return recs


def _cell(row, *names):
    for n in names:
        for k, v in row["cells"].items():
            if k.lower().startswith(n.lower()):
                return v
    return None


def _first(rows, table_prefix):
    return [r for r in rows if r["table"].startswith(table_prefix)]


def _summarise(r: dict) -> dict:
    v: dict = {}
    rows = r["rows"]
    t = r["type"]
    if t == "node":
        row = rows[0]
        v = {"z": _num(_cell(row, "Z")), "x": _num(_cell(row, "X")), "elev_offset": _num(_cell(row, "Elev"))}
    elif t == "member":
        for row in _first(rows, "Beam Primary Data"):
            v.update(start=_cell(row, "Start Point"), end=_cell(row, "End Point"), shape_input=_cell(row, "Shape"),
                     design_rule=_cell(row, "Design Rules"), function=_cell(row, "Function"),
                     release_start=_cell(row, "Start Rel"), release_end=_cell(row, "End Rel"))
        for row in _first(rows, "Hot Rolled"):
            v["length_ft"] = _num(_cell(row, "Length"))
        for row in _first(rows, "Beam Design for Hot Rolled"):
            v.update(size=_cell(row, "Size"), max_start_reaction_k=_num(_cell(row, "Max Start")),
                     max_end_reaction_k=_num(_cell(row, "Max End")), min_start_reaction_k=_num(_cell(row, "Min Start")),
                     min_end_reaction_k=_num(_cell(row, "Min End")), studs=_cell(row, "Studs"))
        for row in _first(rows, "Beam Code Summary"):
            v.update(bending_uc=_num(_cell(row, "Bending")), shear_uc=_num(_cell(row, "Shear")),
                     defl_check=_num(_cell(row, "Defl")), gov_lc=_cell(row, "LC"))
        ends = {}
        for row in _first(rows, "Beam End Reactions"):
            e = (_cell(row, "End") or "").strip()
            if e in ("Start", "End"):
                ends[e.lower()] = {"dl_pre_k": _num(_cell(row, "PreDL")), "dl_k": _num(_cell(row, "DL")),
                                   "ll_k": _num(_cell(row, "LL[")), "roof_k": _num(_cell(row, "Roof[")),
                                   "max_k": _num(_cell(row, "Max")), "page": row["page"], "bbox": row["bbox"]}
        if ends:
            v["end_reactions"] = ends
        s = v.get("size") or v.get("shape_input")
        info = sizes.norm(s or "", risa=True)   # records come only from RISA table pages (run_footers)
        v["size_norm"] = info["norm"] if info else ""
    elif t == "column_stack":
        for row in _first(rows, "Column Stacks"):
            v.update(z=_num(_cell(row, "Z")), x=_num(_cell(row, "X")), grid=_cell(row, "Project"),
                     bot_el=_num(_cell(row, "Bot")), top_el=_num(_cell(row, "...Top", "Top")),
                     shape_family=_cell(row, "Shape"), function=_cell(row, "Material"))
        pts = {}
        for row in rows:
            if row["table"].startswith("Columns :"):
                pts[_split_title(row["table"])[1]] = _cell(row, "Point")
        v["points"] = pts
        for row in _first(rows, "Hot Rolled Steel Column Code Checks"):
            sh = _cell(row, "Shape") or ""
            info = sizes.norm(sh, risa=True)
            v.update(shape=sh, size_norm=info["norm"] if info else "", truncated=sizes.is_truncated_size(sh),
                     uc=_num(_cell(row, "Code")), gov_lc=_cell(row, "LC"))
        ax = {}
        for row in rows:
            if row["table"].startswith("Column Forces/Moments") and row["table"].endswith("Axial Force"):
                fl = _cell(row, "Floor")
                cat = row["table"].split(",", 1)[1].split(":")[0].strip()
                d = ax.setdefault(fl, {})
                if cat.startswith("Dead"):
                    d["dl_pre_k"] = _num(_cell(row, "DLPre"))
                    d["dl_k"] = _num(_cell(row, "DL["))
                    d["max_base_k"] = _num(_cell(row, "Max Base"))
        if ax:
            v["axial"] = ax
    elif t == "footing":
        for row in _first(rows, "Footing Geometry Results"):
            v.update(length_ft=_num(_cell(row, "Length")), width_ft=_num(_cell(row, "Width")),
                     thick_in=_num(_cell(row, "Thickness")), footing_type=_cell(row, "Footing"))
        for row in _first(rows, "Footing Code Check"):
            v.update(bearing_uc=_num(_cell(row, "Bearing Ra")), gov_lc=_cell(row, "Gov LC"))
        loads = {}
        for row in _first(rows, "Point Loads and Moments"):
            cat = re.search(r"\(Cat \d+ : ([^)]+)\)", row["table"])
            if cat and (_cell(row, "Direction") or "").strip() == "Y":
                loads[cat.group(1)] = _num(_cell(row, "Magnitude"))
        if loads:
            v["vertical_loads_k"] = loads
    elif t == "r3d_node":
        for row in _first(rows, "Node Coordinates"):
            v.update(x=_num(_cell(row, "X")), y=_num(_cell(row, "Y")), z=_num(_cell(row, "Z")))
    elif t == "floor":
        row = rows[0]
        v = {"elev_ft": _num(_cell(row, "Elevation")), "area_load_default": _cell(row, "Area Load Default"),
             "floor_type": _cell(row, "Floor Type")}
    elif t == "area_load_def":
        row = rows[0]
        v = {k: row["cells"].get(k) for k in row["cells"] if k}
    return v


def _first_num(row, prefix):
    for k, val in row["cells"].items():
        if k.startswith(prefix) and "[k]" in k:
            n = _num(val)
            if n is not None:
                return n
    return None


# ---------------------------------------------------------------- whole-page calcs

def page_records(pages: list[dict], table_pages: set[tuple], pf) -> dict:
    """One record per sub-calc for pages that are not RISA tables."""
    C = pf.calcs
    groups: dict[str, list] = defaultdict(list)
    for p in pages:
        if (p["doc"], p["page"]) in table_pages or p.get("toc") or p["title"] in C.skip_titles:
            continue
        groups[p["group"]].append(p)
    out = {}
    for gid, ps in groups.items():
        p0 = ps[0]
        sw = p0["software"]
        rotated = (p0["software"] in C.sketch_software and not p0["tables"]
                   and (C.sketch_sections is None or p0["sheet_id"][:1] in C.sketch_sections))
        sec = C.sections.get(p0["section"])
        if sec and sec.record_type and (sec.record_sheet_regex is None or sec.record_sheet_regex.match(p0["sheet_id"])):
            rtype = sec.record_type
        elif rotated:
            rtype = "model_sketch"
        elif sw == "Enercalc":
            rtype = "enercalc_design"
        elif sw == "CFS Designer":
            rtype = "cfs_design"
        else:
            rtype = "hand_calc"
        sids = [p["sheet_id"] for p in ps]
        rid = f"{p0['doc']}:{rtype}:{sids[0]}" + (f"-{sids[-1]}" if len(sids) > 1 else "")
        szs = sorted({s for p in ps for s in p["sizes"]})
        out[rid] = {
            "id": rid, "type": rtype, "run": _run_of(p0, C), "label": p0["title"], "level": p0.get("level", ""),
            "sheets": sids, "pages": [p["page"] for p in ps], "doc": p0["doc"],
            "evidence": [{"doc": p["doc"], "page": p["page"], "sheet": p["sheet_id"],
                          "bbox": p["title_rect"] or p["sheet_rect"], "text": p["title"]} for p in ps],
            "values": {"sizes": szs, "drawing_refs": sorted({r["text"] for p in ps for r in p["drawing_refs"]}),
                       "subtotal": p0.get("subtotal")},
        }
    return out


def _run_of(p, C) -> str:
    """Run id of a page: the profile's (section, software) rules for the main package, else by software."""
    sw = p["software"]
    if p["doc"] != "calcs":
        return f"{p['doc']}:" + C.software_runs.get(sw, sw.lower())
    for rr in C.run_rules:
        if p["section"] == rr.section and (rr.software is None or sw == rr.software):
            return rr.run
    return C.software_runs.get(sw, sw.lower())




# ---------------------------------------------------------------- geometry + load path

def _ref(row, note="") -> dict:
    t = " | ".join(v for v in row["cells"].values() if v)
    return {"doc": row["doc"], "page": row["page"], "sheet": row["sheet"], "table": row["table"],
            "bbox": row["bbox"], "text": t[:160], **({"note": note} if note else {})}


def _row_of(r, table_prefix, pred=None):
    for row in r["rows"]:
        if row["table"].startswith(table_prefix) and (pred is None or pred(row)):
            return row
    return None


def base_level(recs: dict, pf) -> str | None:
    """The RISAFloor floor whose points name the footings (FLR_1_<point>): the profile's, else the
    floor with the lowest elevation in the Floors table."""
    if pf.calcs.lowest_framed_level:
        return pf.calcs.lowest_framed_level
    fl = [r for r in recs.values() if r["type"] == "floor" and r["values"].get("elev_ft") is not None]
    return min(fl, key=lambda r: r["values"]["elev_ft"])["label"] if fl else None


def _levels_top_down(recs: dict) -> list[str]:
    fl = [r for r in recs.values() if r["type"] == "floor" and r["values"].get("elev_ft") is not None]
    return [r["label"] for r in sorted(fl, key=lambda r: -r["values"]["elev_ft"])]


def geometry(recs: dict, pf) -> dict:
    base = base_level(recs, pf)
    nodes = {(r["level"], r["label"]): r["values"] for r in recs.values() if r["type"] == "node"}
    levels = {}
    for r in recs.values():
        if r["type"] == "floor" and r["values"].get("elev_ft") is not None:
            levels[r["label"]] = {"elev_ft": r["values"]["elev_ft"], "source": _ref(r["rows"][0], "RISAFloor Floors table")}
    for r in recs.values():
        if r["type"] != "member":
            continue
        v = r["values"]
        a = nodes.get((r["level"], v.get("start"))) or nodes.get((base, v.get("start")))
        b = nodes.get((r["level"], v.get("end"))) or nodes.get((base, v.get("end")))
        if a and b and a["z"] is not None and b["z"] is not None:
            v["geom"] = {"start": [a["z"], a["x"]], "end": [b["z"], b["x"]],
                         "elev_ft": levels.get(r["level"], {}).get("elev_ft"),
                         "plan_length_ft": round(math.dist((a["z"], a["x"]), (b["z"], b["x"])), 3)}
    return {"levels": levels, "axes": pf.calcs.model_axes_note}


def _on_segment(p, a, b, tol=0.05):
    ax, ay = a
    bx, by = b
    px, py = p
    L2 = (bx - ax) ** 2 + (by - ay) ** 2
    if L2 == 0:
        return False
    t = ((px - ax) * (bx - ax) + (py - ay) * (by - ay)) / L2
    if t <= 1e-3 or t >= 1 - 1e-3:
        return False
    d = abs((bx - ax) * (ay - py) - (ax - px) * (by - ay)) / math.sqrt(L2)
    return d <= tol


def load_path(recs: dict, page_recs: dict, pf) -> tuple[list, dict]:
    base = base_level(recs, pf)
    sk = pf.calcs.area_load_sketches
    edges = []
    E = edges.append
    stacks = {r["label"]: r for r in recs.values() if r["type"] == "column_stack"}
    col_at = {}                     # (level, node) -> stack
    for s in stacks.values():
        for lev, pt in (s["values"].get("points") or {}).items():
            col_at[(lev, pt)] = s
    members = [r for r in recs.values() if r["type"] == "member"]
    nodes = {(r["level"], r["label"]): r for r in recs.values() if r["type"] == "node"}

    # 1. A load-area calc -> RISA Uniform Area Load definition (shared name)
    defs = {_norm_name(r["label"]): r for r in recs.values() if r["type"] == "area_load_def"}
    for pr in page_recs.values():
        if pr["type"] != "load_criteria":
            continue
        d = defs.get(_norm_name(pr["label"]))
        if d:
            E({"src": pr["id"], "dst": d["id"], "kind": "load_area->area_load_def", "join": "exact",
               "rule": "same load-area name (case/punctuation folded)",
               "evidence": {"src": pr["evidence"][:1], "dst": [_ref(d["rows"][0])]}})
        else:
            E({"src": pr["id"], "dst": None, "kind": "load_area->area_load_def", "join": "absent",
               "rule": "no RISA area load carries this name", "evidence": {"src": pr["evidence"][:1], "dst": []}})

    # 1b. area load definition -> floor (Floors 'Area Load Default') -> members of that floor
    floors = {r["label"]: r for r in recs.values() if r["type"] == "floor"}
    for f in floors.values():
        d = defs.get(_norm_name(f["values"].get("area_load_default") or ""))
        if d:
            E({"src": d["id"], "dst": f["id"], "kind": "area_load_def->floor", "join": "exact",
               "rule": f"Floors table names '{f['values']['area_load_default']}' as the Area Load Default of {f['label']}",
               "evidence": {"src": [_ref(d["rows"][0])], "dst": [_ref(f["rows"][0])]}})
    for d in defs.values():
        if not any(e["src"] == d["id"] for e in edges):
            E({"src": d["id"], "dst": None, "kind": "area_load_def->floor", "join": "absent",
               "rule": "not a floor default; its areas are drawn only as polygons on the Area Load Assignments "
                       f"sketches{f' ({sk})' if sk else ''}, no table assigns it to members",
               "evidence": {"src": [_ref(d["rows"][0])], "dst": []}})
    for m in members:
        f = floors.get(m["level"])
        if f:
            pd = _row_of(m, "Beam Primary Data")
            E({"src": f["id"], "dst": m["id"], "kind": "floor->member", "join": "exact",
               "rule": f"member listed in 'Beam Primary Data : {m['level']}' (takes the floor's default area load "
                       f"unless a{f' {sk}' if sk else 'n area-load sketch'} polygon overrides it - overrides are not in any table)",
               "evidence": {"src": [_ref(f["rows"][0])], "dst": [_ref(pd)] if pd else []}})

    # 1c. RISAFloor line / point loads -> the member they sit on (coordinates of their points)
    for fl in [r for r in recs.values() if r["type"] == "floor_load"]:
        for row in fl["rows"]:
            sp, ep = row["cells"].get("Start Point"), row["cells"].get("End Point")
            pt = row["cells"].get("Point Label")
            lev = fl["level"]
            if sp and ep:
                a, b = nodes.get((lev, sp)), nodes.get((lev, ep))
                if not (a and b):
                    continue
                pa, pb = (a["values"]["z"], a["values"]["x"]), (b["values"]["z"], b["values"]["x"])
                hits = [m for m in members if m["level"] == lev and m["values"].get("geom")
                        and _collinear_overlap(pa, pb, m["values"]["geom"]["start"], m["values"]["geom"]["end"])]
                kind = "line_load->member"
            elif pt:
                a = nodes.get((lev, pt))
                if not a:
                    continue
                p0 = (a["values"]["z"], a["values"]["x"])
                hits = [m for m in members if m["level"] == lev and m["values"].get("geom")
                        and (_on_segment(p0, m["values"]["geom"]["start"], m["values"]["geom"]["end"])
                             or pt in (m["values"].get("start"), m["values"].get("end")))]
                kind = "point_load->member"
            else:
                continue
            for m in hits:
                E({"src": fl["id"], "dst": m["id"], "kind": kind, "join": "inferred",
                   "rule": "load points lie on the member line (Point Locations coordinates, tol 0.05 ft)",
                   "evidence": {"src": [_ref(row)], "dst": [_ref(_row_of(m, "Beam Primary Data"))]}})
            if not hits:
                E({"src": fl["id"], "dst": None, "kind": kind, "join": "absent",
                   "rule": "no member lies under the load's points", "evidence": {"src": [_ref(row)], "dst": []}})

    # 2. member end -> support (column stack at the node, else the member the node sits on)
    for m in members:
        v = m["values"]
        g = v.get("geom")
        for end_key, node in (("start", v.get("start")), ("end", v.get("end"))):
            er = _row_of(m, "Beam End Reactions", lambda row, e=end_key: (row["cells"].get("End") or "").lower() == e)
            src_ev = [_ref(er, f"{end_key} reaction")] if er else []
            pd = _row_of(m, "Beam Primary Data")
            if pd:
                src_ev.append(_ref(pd, f"{end_key} node {node}"))
            s = col_at.get((m["level"], node))
            if s:
                crow = _row_of(s, f"Columns : {m['level']}")
                E({"src": m["id"], "dst": s["id"], "kind": "member->column_stack", "join": "exact", "end": end_key,
                   "rule": f"member {end_key} node {node} = column point {node} (Columns : {m['level']})",
                   "evidence": {"src": src_ev, "dst": [_ref(crow)] if crow else []}})
                continue
            hit = None
            if g and node:
                p = g["start"] if end_key == "start" else g["end"]
                for o in members:
                    if o is m or o["level"] != m["level"] or not o["values"].get("geom"):
                        continue
                    og = o["values"]["geom"]
                    if _on_segment(p, og["start"], og["end"]):
                        hit = o
                        break
            if hit:
                nrow = nodes.get((m["level"], node))
                E({"src": m["id"], "dst": hit["id"], "kind": "member->member", "join": "inferred", "end": end_key,
                   "rule": f"node {node} lies on {hit['label']} between its end nodes (Point Locations coordinates, "
                           f"tol 0.05 ft)",
                   "evidence": {"src": src_ev + ([_ref(nrow['rows'][0], 'node coordinates')] if nrow else []),
                                "dst": [_ref(_row_of(hit, 'Beam Primary Data'))] if _row_of(hit, 'Beam Primary Data') else []}})
            else:
                shared = [o for o in members if o is not m and o["level"] == m["level"]
                          and node in (o["values"].get("start"), o["values"].get("end"))]
                E({"src": m["id"], "dst": None, "kind": "member->support", "join": "absent", "end": end_key,
                   "rule": f"node {node} is not a column point and lies inside no other member"
                           + (f"; shares the node with {', '.join(o['label'] for o in shared)} (end-to-end, "
                              "no bearing implied)" if shared else ""),
                   "evidence": {"src": src_ev, "dst": []}})

    # 3. column stack -> footing
    foots = {r["label"]: r for r in recs.values() if r["type"] == "footing"}
    r3d = {r["label"]: r for r in recs.values() if r["type"] == "r3d_node"}
    used = set()
    for s in stacks.values():
        pt = (s["values"].get("points") or {}).get(base)
        f = None
        if pt:
            f = foots.get(f"FLR_1_{pt}") or next((foots[k] for k in foots if re.fullmatch(rf"FLR_1_{pt}_\d+", k)), None)
        if f:
            used.add(f["label"])
            crow = _row_of(s, f"Columns : {base}")
            dl_col = (s["values"].get("axial") or {}).get(base, {}).get("dl_k")
            dl_ft = (f["values"].get("vertical_loads_k") or {}).get("DL")
            agree = dl_col is not None and dl_ft is not None and abs(dl_col - dl_ft) < 0.01
            prow = _row_of(f, "Point Loads and Moments (Cat 1")
            E({"src": s["id"], "dst": f["id"], "kind": "column_stack->footing", "join": "exact",
               "rule": f"footing joint {f['label']} names the stack's {base} point {pt} (RISAFoundation import label "
                       "FLR_<floor>_<point>)",
               "check": {"column_base_dl_k": dl_col, "footing_dl_k": dl_ft, "agree": agree},
               "evidence": {"src": [_ref(crow)] + ([_ref(_row_of(s, "Column Forces/Moments, Dead"))] if
                                                   _row_of(s, "Column Forces/Moments, Dead") else []),
                            "dst": [_ref(f["rows"][0])] + ([_ref(prow)] if prow else [])}})
    for f in foots.values():
        if f["label"] in used:
            continue
        m = re.match(r"^R3D_(N\d+)$", f["label"])
        n = r3d.get(m.group(1)) if m else None
        hit = None
        if n and n["values"].get("x") is not None:
            nx, nz = n["values"]["x"], n["values"]["z"]
            for s in stacks.values():
                sv = s["values"]
                if sv.get("x") is not None and abs(sv["x"] - nx) < 0.05 and abs(sv["z"] - nz) < 0.05:
                    hit = s
                    break
        if hit:
            used.add(f["label"])
            E({"src": hit["id"], "dst": f["id"], "kind": "column_stack->footing", "join": "inferred",
               "rule": f"RISA-3D node {m.group(1)} at X={n['values']['x']}, Z={n['values']['z']} = stack "
                       f"{hit['label']} at X={hit['values']['x']}, Z={hit['values']['z']} (coordinate, tol 0.05 ft)",
               "evidence": {"src": [_ref(_row_of(hit, "Column Stacks"))],
                            "dst": [_ref(_row_of(n, "Node Coordinates")), _ref(f["rows"][0])]}})
        else:
            E({"src": None, "dst": f["id"], "kind": "column_stack->footing", "join": "absent",
               "rule": "footing joint label could not be resolved to a column stack",
               "evidence": {"src": [], "dst": [_ref(f["rows"][0])]}})
    for s in stacks.values():
        if not any(e["src"] == s["id"] and e["kind"] == "column_stack->footing" for e in edges):
            E({"src": s["id"], "dst": None, "kind": "column_stack->footing", "join": "absent",
               "rule": "no RISAFoundation joint names or sits at this stack",
               "evidence": {"src": [_ref(_row_of(s, "Column Stacks"))] if _row_of(s, "Column Stacks") else [], "dst": []}})
    return edges, _reaction_check(edges, recs, stacks)


def _collinear_overlap(pa, pb, a, b, tol=0.05) -> bool:
    L = math.dist(a, b)
    Ll = math.dist(pa, pb)
    if L < 1e-6 or Ll < 1e-6:
        return False
    ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
    for p in (pa, pb):
        if abs((p[0] - a[0]) * uy - (p[1] - a[1]) * ux) > tol:
            return False
    s0 = (pa[0] - a[0]) * ux + (pa[1] - a[1]) * uy
    s1 = (pb[0] - a[0]) * ux + (pb[1] - a[1]) * uy
    return min(L, max(s0, s1)) - max(0, min(s0, s1)) > 0.05


def _reaction_check(edges, recs, stacks) -> dict:
    """Corroborate member->column joins: summed member DL end reactions per stack and level
    vs the RISA column DL axial at each floor: members joined at that floor and every floor above it
    (floors ordered by the RISAFloor Floors elevations)."""
    order = _levels_top_down(recs)
    per = defaultdict(float)
    for e in edges:
        if e["kind"] != "member->column_stack":
            continue
        m = recs[e["src"]]
        er = (m["values"].get("end_reactions") or {}).get(e["end"]) or {}
        if er.get("dl_k") is not None:
            per[(e["dst"], m["level"])] += er["dl_k"]
    out, ok, n = [], 0, 0
    for s in stacks.values():
        ax = s["values"].get("axial") or {}
        expect = 0.0
        for lev in order:
            expect += per.get((s["id"], lev), 0.0)
            col = (ax.get(lev) or {}).get("dl_k")
            if col is None:
                continue
            n += 1
            good = abs(col - expect) <= max(0.05, 0.05 * abs(col))
            ok += good
            out.append({"stack": s["label"], "level": lev, "column_dl_k": col, "sum_member_dl_k": round(expect, 3),
                        "agree": good})
    return {"rows": out, "agree": ok, "checked": n,
            "rule": "sum of DL end reactions of members joined to the stack (exact joins) vs Column Forces DL[k], "
                    "agree within 5 % (column self weight is in the column DL, not in the member sum)"}


# ---------------------------------------------------------------- commentary

def commentary(doc, doc_key: str, page_meta: dict, pf) -> list[dict]:
    COMMENT_COLORS = pf.calcs.comment_colors
    sketches = _sketch_pages(page_meta, pf)
    raw = []
    for pno, page in enumerate(doc, 1):
        for b in page.get_text("dict")["blocks"]:
            for l in b.get("lines", []):
                sp = [s for s in l["spans"] if s["text"].strip()]
                if not sp or sp[0]["color"] not in COMMENT_COLORS:
                    continue
                if any("Bold" in s["font"] for s in sp):
                    continue                                   # section banners, sketch / map titles
                t = "".join(s["text"] for s in l["spans"]).strip()
                if "_" in t or t.startswith("Version:"):
                    continue
                if sp[0]["size"] >= 11.9 and l["dir"] != (1.0, 0.0) and len(t.split()) <= 4 and pno in sketches:
                    continue                                   # rotated sketch title (Helvetica 12)
                raw.append({"page": pno, "bbox": list(l["bbox"]), "dir": l["dir"], "color": sp[0]["color"], "text": t})
    # merge consecutive lines of one note (same page, colour, direction, adjacent)
    notes = []
    for r in raw:
        n = next((n for n in reversed(notes) if n["page"] == r["page"] and n["color"] == r["color"]
                  and n["dir"] == r["dir"] and _gap(n["bbox"], r["bbox"]) < 4), None)
        if n:
            n["text"] += " " + r["text"]
            n["rects"].append(_r(r["bbox"]))
            n["bbox"] = [min(n["bbox"][0], r["bbox"][0]), min(n["bbox"][1], r["bbox"][1]),
                         max(n["bbox"][2], r["bbox"][2]), max(n["bbox"][3], r["bbox"][3])]
        else:
            notes.append({**r, "rects": [_r(r["bbox"])]})
    keep = []
    for n in notes:                     # a note has words; highlighted result values ("641 psf 7.57 ft") do not
        words = [w for w in re.findall(r"[A-Za-z][A-Za-z.&']+", n["text"])
                 if w.lower().strip(".") not in ("psf", "ft", "kips", "kip", "k", "in", "plf", "ksf", "lb", "lbs")]
        if len(words) >= 2:
            keep.append(n)
    out = []
    for i, n in enumerate(keep):
        meta = page_meta[n["page"]]
        out.append({"id": f"{doc_key}:note:{i + 1}", "doc": doc_key, "page": n["page"], "sheet": meta["sheet_id"],
                    "bbox": _r(n["bbox"]), "rects": n["rects"], "colour": COMMENT_COLORS[n["color"]],
                    "text": re.sub(r"\s+", " ", n["text"]).strip()})
    return out


def _sketch_pages(page_meta, pf) -> set:
    return {p for p, m in page_meta.items() if m["software"] in pf.calcs.sketch_software and not m["tables"]}


def _gap(a, b) -> float:
    dx = max(0, max(a[0], b[0]) - min(a[2], b[2]))
    dy = max(0, max(a[1], b[1]) - min(a[3], b[3]))
    return math.hypot(dx, dy)


# ---------------------------------------------------------------- sketch registration

def sketch_fit(doc, page_meta: dict, recs: dict, pf) -> dict:
    """Register each RISAFloor sketch page (rotated plan views, B1-B15) to model feet.
    Anchors: member labels on the 'Member Labels' sketch of that level (B1 Level 2, B2 Roof)
    against member mid-points from the tables. Sketches of one level share the viewport if
    their grid-bubble text sits at the same points; that is checked, not assumed."""
    out = {}
    lab_page = {}
    for pno, m in page_meta.items():
        t = m["title"]
        if m["software"] == "RISAFloor" and "Member Labels" in t:
            lab_page[m["level"]] = pno
    for lev, pno in lab_page.items():
        page = doc[pno - 1]
        pts_s, pts_m, names = [], [], []
        for w in page.get_text("words"):
            key = f"risafloor:member:{lev}:{w[4]}"
            r = recs.get(key)
            if r and r["values"].get("geom"):
                g = r["values"]["geom"]
                pts_s.append(((w[0] + w[2]) / 2, (w[1] + w[3]) / 2))
                pts_m.append(((g["start"][0] + g["end"][0]) / 2, (g["start"][1] + g["end"][1]) / 2))
                names.append(w[4])
        if len(pts_s) < 6:
            continue
        A = _affine_fit(pts_s, pts_m)
        res = [math.dist(_affine_apply(A, p), q) for p, q in zip(pts_s, pts_m)]
        bubbles = _bubbles(page, pf)
        same = []
        for p2, m2 in page_meta.items():
            if m2["software"] == "RISAFloor" and m2["level"] == lev and not m2["tables"] and p2 != pno:
                b2 = _bubbles(doc[p2 - 1], pf)
                shifts = [min(math.dist(p, q) for q in b2[k]) for k in bubbles if k in b2 for p in bubbles[k]]
                common = shifts
                shifts.sort()
                dev = shifts[len(shifts) // 2] if shifts else None      # median: value text can look like a bubble
                same.append({"page": p2, "sheet": m2["sheet_id"], "bubbles_compared": len(common),
                             "median_bubble_shift_pt": round(dev, 2) if dev is not None else None,
                             "same_viewport": dev is not None and len(common) >= 6 and dev < 1.5})
        out[lev] = {"label_page": pno, "label_sheet": page_meta[pno]["sheet_id"], "affine": A,
                    "anchors": len(names), "rms_ft": round(math.sqrt(sum(x * x for x in res) / len(res)), 2),
                    "max_ft": round(max(res), 2), "note": "member label text is placed near, not at, the mid-point",
                    "pages": same}
    return out


def _bubbles(page, pf) -> dict:
    """Grid bubble labels on a sketch -> list of their centres (each label prints at both ends)."""
    out = defaultdict(list)
    for w in page.get_text("words"):
        if pf.calcs.sketch_bubble_regex.fullmatch(w[4]) and (w[2] - w[0]) < 15:
            out[w[4]].append(((w[0] + w[2]) / 2, (w[1] + w[3]) / 2))
    return out


def _affine_fit(src, dst):
    import numpy as np
    S = np.array([[x, y, 1.0] for x, y in src])
    D = np.array(dst)
    sol, *_ = np.linalg.lstsq(S, D, rcond=None)
    return [[round(float(v), 6) for v in row] for row in sol.T]


def _affine_apply(A, p):
    return (A[0][0] * p[0] + A[0][1] * p[1] + A[0][2], A[1][0] * p[0] + A[1][1] * p[1] + A[1][2])


def attach_commentary(notes: list, recs: dict, page_recs: dict, fits: dict, page_meta: dict, pf) -> None:
    by_page = defaultdict(list)
    for r in list(recs.values()):
        for row in r["rows"]:
            by_page[(row["doc"], row["page"])].append((r, row["bbox"]))
    for r in page_recs.values():
        for ev in r["evidence"]:
            by_page[(ev["doc"], ev["page"])].append((r, ev["bbox"] or [0, 0, 0, 0]))
    for n in notes:
        n["attached"] = []
        meta = page_meta[n["page"]]
        lev = meta.get("level")
        fit = fits.get(lev) if meta["software"] == "RISAFloor" else None
        if fit and any(p["page"] == n["page"] and p["same_viewport"] for p in fit["pages"]):
            cx, cy = (n["bbox"][0] + n["bbox"][2]) / 2, (n["bbox"][1] + n["bbox"][3]) / 2
            mx, mz = _affine_apply(fit["affine"], (cx, cy))[::-1]
            best = None
            for r in recs.values():
                g = r["values"].get("geom") if r["type"] == "member" and r["level"] == lev else None
                if g:
                    d = _seg_dist((mz, mx), g["start"], g["end"])
                    if best is None or d < best[0]:
                        best = (d, r)
            if best:
                n["attached"].append({"record": best[1]["id"], "join": "inferred",
                                      "rule": f"note position on {meta['sheet_id']} mapped through the "
                                              f"{fit['label_sheet']} label fit (same viewport) -> nearest member, "
                                              f"{best[0]:.1f} ft"})
        for m in pf.calcs.note_grid_ref_regex.finditer(n["text"]):
            sid = f"risafloor:column_stack:({m.group(1)}-{m.group(2)})"
            if sid in recs:
                n["attached"].append({"record": sid, "join": "exact",
                                      "rule": f"note names grid {m.group(1)}/{m.group(2)} = stack ({m.group(1)}-{m.group(2)})"})
        cands = by_page.get((n["doc"], n["page"]), [])
        if cands:
            best = min(cands, key=lambda c: _gap(n["bbox"], c[1]))
            n["attached"].append({"record": best[0]["id"], "join": "page",
                                  "rule": "nearest record evidence on the same page"})


def _seg_dist(p, a, b) -> float:
    ax, ay = a
    bx, by = b
    L2 = (bx - ax) ** 2 + (by - ay) ** 2
    if L2 == 0:
        return math.dist(p, a)
    t = max(0, min(1, ((p[0] - ax) * (bx - ax) + (p[1] - ay) * (by - ay)) / L2))
    return math.dist(p, (ax + t * (bx - ax), ay + t * (by - ay)))


# ---------------------------------------------------------------- drawing grid feet

FTIN = re.compile(r"^(\d+)' ?- ?(\d+)(?: (\d)/(\d))?\"$")


def _ftin(t: str):
    m = FTIN.match(t.strip())
    if not m:
        return None
    v = int(m.group(1)) + int(m.group(2)) / 12
    if m.group(3):
        v += int(m.group(3)) / int(m.group(4)) / 12
    return v


def grid_feet(plans_doc, sheet: dict) -> dict | None:
    """Per-axis pt->ft map for one plan sheet from its grid bubbles and the dimension
    strings between adjacent bubbles. u = feet from the first column bubble along +x,
    v = feet from the first row bubble along +y."""
    page = plans_doc[sheet["page"] - 1]
    g = sheet.get("grid") or {}
    cols, rows = g.get("cols") or [], g.get("rows") or []
    if len(cols) < 3 or len(rows) < 3:
        return None
    dims = []
    for b in page.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            t = "".join(s["text"] for s in l["spans"]).strip()
            v = _ftin(t)
            if v is not None:
                dims.append((l["bbox"], l["dir"], v, t))
    top = min(r[1] for c in cols for r in c["rects"])
    left = min(r[0] for rw in rows for r in rw["rects"])

    def axis(lines, horizontal):
        lines = sorted(lines, key=lambda c: c["pos"])
        ft = [0.0]
        ev = []
        for a, b in zip(lines, lines[1:]):
            cand = []
            for bb, d, v, t in dims:
                if horizontal and d == (1.0, 0.0) and a["pos"] < (bb[0] + bb[2]) / 2 < b["pos"] and top < bb[1] < top + 150:
                    cand.append((bb[1], v, t, bb))
                if not horizontal and d == (0.0, -1.0) and a["pos"] < (bb[1] + bb[3]) / 2 < b["pos"] and left < bb[0] < left + 150:
                    cand.append((bb[0], v, t, bb))
            if not cand:
                return None
            c = min(cand)
            ft.append(ft[-1] + c[1])
            ev.append({"from": a["label"], "to": b["label"], "text": c[2], "ft": round(c[1], 4), "bbox": _r(c[3]),
                       "pt": round(b["pos"] - a["pos"], 2)})
        pts = [l["pos"] for l in lines]
        s = sum(e["pt"] * e["ft"] for e in ev) / sum(e["ft"] ** 2 for e in ev)
        resid = [abs((p - pts[0]) / s - f) for p, f in zip(pts, ft)]
        return {"labels": [l["label"] for l in lines], "pt": pts, "ft": ft, "dims": ev, "pt_per_ft": round(s, 4),
                "max_resid_ft": round(max(resid), 3)}

    ax_u, ax_v = axis(cols, True), axis(rows, False)
    if not ax_u or not ax_v:
        return None
    return {"sheet": sheet["sheet"], "page": sheet["page"], "u": ax_u, "v": ax_v}


def _pt2ft(ax, p):
    pts, ft = ax["pt"], ax["ft"]
    i = 0
    while i < len(pts) - 2 and p > pts[i + 1]:
        i += 1
    return ft[i] + (p - pts[i]) * (ft[i + 1] - ft[i]) / (pts[i + 1] - pts[i])


def to_feet(cal, x, y):
    return (_pt2ft(cal["u"], x), _pt2ft(cal["v"], y))


# ---------------------------------------------------------------- transform + matching

ORIENTS = [((1, 0), (0, 1)), ((0, -1), (1, 0)), ((-1, 0), (0, -1)), ((0, 1), (-1, 0)),
           ((1, 0), (0, -1)), ((0, 1), (1, 0)), ((-1, 0), (0, 1)), ((0, -1), (-1, 0))]


def _apply(T, p):
    (a, b), (c, d) = T["R"]
    return (a * p[0] + b * p[1] + T["t"][0], c * p[0] + d * p[1] + T["t"][1])


def _match_pts(T, dpts, mpts, tol):
    pairs, used = [], set()
    cand = []
    for i, p in enumerate(dpts):
        q = _apply(T, p)
        for j, m in enumerate(mpts):
            d = math.dist(q, m)
            if d <= tol:
                cand.append((d, i, j))
    cand.sort()
    di = set()
    for d, i, j in cand:
        if i in di or j in used:
            continue
        di.add(i)
        used.add(j)
        pairs.append((i, j, d))
    return pairs


def _kabsch(src, dst, mirror: bool):
    """Least-squares rotation (+ fixed mirror) and translation, no scale."""
    import numpy as np
    S = np.array(src, float)
    D = np.array(dst, float)
    if mirror:
        S = S * np.array([1, -1])
    cs, cd = S.mean(0), D.mean(0)
    H = (S - cs).T @ (D - cd)
    U, _, Vt = np.linalg.svd(H)
    R = Vt.T @ U.T
    if np.linalg.det(R) < 0:
        Vt[-1] *= -1
        R = Vt.T @ U.T
    M = R @ (np.diag([1, -1]) if mirror else np.eye(2))
    t = cd - (R @ cs)
    return {"R": [[float(M[0][0]), float(M[0][1])], [float(M[1][0]), float(M[1][1])]], "t": [float(t[0]), float(t[1])],
            "rot_deg": round(math.degrees(math.atan2(R[1][0], R[0][0])), 3), "mirror": mirror}


def fit_transform(dpts, mpts, tol=2.0):
    best = None
    for R in ORIENTS:
        mirror = (R[0][0] * R[1][1] - R[0][1] * R[1][0]) < 0
        for p in dpts:
            for m in mpts:
                T = {"R": R, "t": (m[0] - (R[0][0] * p[0] + R[0][1] * p[1]), m[1] - (R[1][0] * p[0] + R[1][1] * p[1]))}
                pairs = _match_pts(T, dpts, mpts, tol)
                score = (len(pairs), -sum(d for *_, d in pairs))
                if best is None or score > best[0]:
                    best = (score, T, pairs, mirror)
    _, T, pairs, mirror = best
    for _ in range(5):
        T = _kabsch([dpts[i] for i, _, _ in pairs], [mpts[j] for _, j, _ in pairs], mirror)
        pairs = _match_pts(T, dpts, mpts, tol)
    res = [d for *_, d in pairs]
    return T, pairs, {"inliers": len(pairs), "drawn": len(dpts), "model": len(mpts),
                      "rms_ft": round(math.sqrt(sum(r * r for r in res) / len(res)), 3) if res else None,
                      "max_ft": round(max(res), 3) if res else None, "tol_ft": tol}


def positional_sheets(graph: dict, pf) -> tuple[str | None, dict[str, str]]:
    """(column sheet, {beam sheet: calc level}) from the profile, else from the sheet kinds:
    the first foundation plan, and every framing plan that has a level."""
    P, fk = pf.positional, pf.drawings.levels.foundation_kinds
    col = P.column_sheet or next((s["sheet"] for s in graph["sheets"] if s.get("kind") in fk), None)
    beams = P.beam_sheets if P.beam_sheets is not None else {
        s["sheet"]: s["level"] for s in graph["sheets"] if s.get("kind") == "framing" and s.get("level")}
    return col, beams


def positional(graph: dict, plans_path: str, recs: dict, pf) -> dict:
    pdoc = pymupdf.open(plans_path)
    sheets = {s["sheet"]: s for s in graph["sheets"]}
    col_sheet, beam_sheets = positional_sheets(graph, pf)
    cals = {}
    for sh in ([col_sheet] if col_sheet else []) + [b for b in beam_sheets if b != col_sheet]:
        if sh in sheets:
            c = grid_feet(pdoc, sheets[sh])
            if c:
                cals[sh] = c
    out = {"calibration": {k: {"u": {kk: v["u"][kk] for kk in ("labels", "ft", "pt_per_ft", "max_resid_ft", "dims")},
                               "v": {kk: v["v"][kk] for kk in ("labels", "ft", "pt_per_ft", "max_resid_ft", "dims")}}
                           for k, v in cals.items()}}
    if col_sheet not in cals:
        out["kept"] = False
        out["reason"] = f"{col_sheet or 'no foundation plan'}{' grid' if col_sheet else ''} could not be calibrated"
        return out
    cal = cals[col_sheet]
    cols = [e for e in graph["elements"] if e["sheet"] == col_sheet and e.get("cat") == "Column" and e.get("at")]
    stacks = [r for r in recs.values() if r["type"] == "column_stack" and r["values"].get("z") is not None]
    dpts = [to_feet(cal, *e["at"]) for e in cols]
    mpts = [(s["values"]["z"], s["values"]["x"]) for s in stacks]
    T, pairs, stats = fit_transform(dpts, mpts)
    keep = stats["inliers"] >= 8 and stats["rms_ft"] is not None and stats["rms_ft"] <= 1.0
    # residuals of every drawn column to its nearest stack under the fit (not only inliers)
    allres = []
    for i, p in enumerate(dpts):
        q = _apply(T, p)
        j = min(range(len(mpts)), key=lambda j: math.dist(q, mpts[j]))
        allres.append(round(math.dist(q, mpts[j]), 2))
    col_pairs = []
    for i, j, d in pairs:
        e, s = cols[i], stacks[j]
        ds, ms = e.get("size_norm") or "", s["values"].get("size_norm") or ""
        col_pairs.append({"element": e["id"], "record": s["id"], "dist_ft": round(d, 3), "drawn_size": e.get("size"),
                          "calc_size": s["values"].get("shape"), "size_agree": (ds == ms) if ds and ms else None,
                          "drawn_grid": e.get("grid"), "calc_grid": s["label"], "drawn_type": e["type"],
                          "element_bbox": e["bbox"], "element_page": e["page"]})
    out["transform"] = {"from": f"drawing grid feet on {col_sheet} (u from grid " + cal["u"]["labels"][0] + " along +x, v from grid "
                        + cal["v"]["labels"][0] + " along +y)", "to": "RISAFloor plan feet (Z, X)",
                        "R": [[round(v, 6) for v in r] for r in T["R"]], "t": [round(v, 3) for v in T["t"]],
                        "rotation_deg": T.get("rot_deg"), "mirror": T.get("mirror"), **stats,
                        "all_drawn_nearest_ft": allres}
    out["column_pairs"] = col_pairs
    out["grid_anchored"] = _grid_anchor_hypotheses(cal, recs, dpts, mpts, cols, stacks)
    out["kept"] = keep
    out["reason"] = (f"{stats['inliers']} of {stats['drawn']} drawn columns land on a RISA stack within "
                     f"{stats['tol_ft']} ft, RMS {stats['rms_ft']} ft" + ("" if keep else " - not clearly small, dropped"))
    if not keep:
        return out
    beams = {}
    for sh, lev in beam_sheets.items():
        if sh not in cals:
            continue
        c = cals[sh]
        drawn = []
        for e in graph["elements"]:
            if e["sheet"] == sh and e.get("line") and e.get("cat") == "Beam":
                x0, y0, x1, y1 = e["line"]
                a = _apply(T, to_feet(c, x0, y0))
                b = _apply(T, to_feet(c, x1, y1))
                drawn.append((e, a, b))
        mem = [r for r in recs.values() if r["type"] == "member" and r["level"] == lev and r["values"].get("geom")]
        beams[lev] = _match_beams(drawn, mem, sh)
    out["beam_pairs"] = beams
    return out


def _grid_anchor_hypotheses(cal, recs, dpts, mpts, cols, stacks, tol=2.0) -> list[dict]:
    """Second hypothesis family: the two documents share grid LABELS, so anchor one numbered and one
    lettered label that both use, with each axis running the way its labels run (no fitting)."""
    calc_grid = {}
    for r in recs.values():
        if r["run"] == "risafloor" and r["type"] == "grid_line":
            row = r["rows"][0]["cells"]
            sz, sx = _num(row.get("Start Z [ft]")), _num(row.get("Start X [ft]"))
            ez, ex = _num(row.get("End Z [ft]")), _num(row.get("End X [ft]"))
            if sz is not None and sz == ez:
                calc_grid[r["label"]] = ("z", sz)
            elif sx is not None and sx == ex:
                calc_grid[r["label"]] = ("x", sx)
    du = dict(zip(cal["u"]["labels"], cal["u"]["ft"]))
    dv = dict(zip(cal["v"]["labels"], cal["v"]["ft"]))

    def direction(labels_pos: dict, key):
        ks = sorted(labels_pos, key=key)
        return 1 if labels_pos[ks[-1]] > labels_pos[ks[0]] else -1

    num = lambda k: float(k)
    let = lambda k: (k[0], float(k[2:]) if "." in k else 0.0)
    cz = {k: v for k, (a, v) in calc_grid.items() if a == "z"}
    cx = {k: v for k, (a, v) in calc_grid.items() if a == "x"}
    su = direction(du, num) * direction(cz, num)
    sv = direction(dv, let) * direction(cx, let)
    out = []
    for n in sorted(set(du) & set(cz), key=num):
        for l in sorted(set(dv) & set(cx), key=let):
            T = {"R": ((su, 0), (0, sv)), "t": (cz[n] - su * du[n], cx[l] - sv * dv[l])}
            pairs = _match_pts(T, dpts, mpts, tol)
            res = [d for *_, d in pairs]
            out.append({"anchor": f"drawing {l}/{n} = calc {l}/{n}", "Z": f"{cz[n]} {'+' if su > 0 else '-'} (u - {du[n]:.2f})",
                        "X": f"{cx[l]} {'+' if sv > 0 else '-'} (v - {dv[l]:.2f})", "inliers": len(pairs),
                        "rms_ft": round(math.sqrt(sum(r * r for r in res) / len(res)), 3) if res else None,
                        "pairs": [{"element": cols[i]["id"], "drawn": f"{cols[i].get('size')} @ {cols[i].get('grid')}",
                                   "record": stacks[j]["id"], "calc": f"{stacks[j]['values'].get('shape')} @ {stacks[j]['label']}",
                                   "dist_ft": round(d, 2)} for i, j, d in pairs]})
    return out


def _match_beams(drawn, mem, sheet):
    """Pair each RISA member with the drawn beam line that is collinear with it (angle
    <= 5 deg, perpendicular offset <= 1.5 ft) and covers the most of its length (>= 50 %)."""
    pairs, unmatched_m = [], []
    used = defaultdict(list)
    for r in mem:
        g = r["values"]["geom"]
        a, b = g["start"], g["end"]
        L = math.dist(a, b)
        if L < 0.5:
            continue
        ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        best = None
        for e, p, q in drawn:
            Ld = math.dist(p, q)
            if Ld < 0.5:
                continue
            vx, vy = (q[0] - p[0]) / Ld, (q[1] - p[1]) / Ld
            ang = math.degrees(math.acos(min(1, abs(ux * vx + uy * vy))))
            if ang > 5:
                continue
            off = max(abs((p[0] - a[0]) * uy - (p[1] - a[1]) * ux), abs((q[0] - a[0]) * uy - (q[1] - a[1]) * ux))
            if off > 1.5:
                continue
            s0 = (p[0] - a[0]) * ux + (p[1] - a[1]) * uy
            s1 = (q[0] - a[0]) * ux + (q[1] - a[1]) * uy
            lo, hi = max(0, min(s0, s1)), min(L, max(s0, s1))
            cover = max(0, hi - lo) / L
            if cover < 0.5:
                continue
            mid_d = math.dist(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2), ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2))
            cand = (cover, -off, e, mid_d, ang, off, Ld)
            if best is None or cand[:2] > best[:2]:
                best = cand
        if not best:
            unmatched_m.append(r["id"])
            continue
        cover, _, e, mid_d, ang, off, Ld = best
        ds, ms = e.get("size_norm") or "", r["values"].get("size_norm") or ""
        used[e["id"]].append(r["label"])
        pairs.append({"element": e["id"], "record": r["id"], "member": r["label"], "drawn_size": e.get("size"),
                      "calc_size": r["values"].get("size") or r["values"].get("shape_input"),
                      "size_agree": (ds == ms) if ds and ms else None, "coverage": round(cover, 2),
                      "offset_ft": round(off, 2), "angle_deg": round(ang, 2), "midpoint_dist_ft": round(mid_d, 2),
                      "drawn_len_ft": round(Ld, 2), "calc_len_ft": r["values"]["geom"]["plan_length_ft"],
                      "element_bbox": e["bbox"], "element_page": e["page"], "sheet": sheet})
    drawn_ids = {e["id"] for e, *_ in drawn}
    return {"pairs": pairs, "unmatched_members": unmatched_m,
            "unmatched_drawn": sorted(drawn_ids - set(used)),
            "drawn_matching_several_members": {k: v for k, v in used.items() if len(v) > 1},
            "counts": {"drawn": len(drawn), "members": len(mem), "pairs": len(pairs),
                       "size_agree": sum(1 for p in pairs if p["size_agree"] is True),
                       "size_disagree": sum(1 for p in pairs if p["size_agree"] is False),
                       "size_unknown": sum(1 for p in pairs if p["size_agree"] is None)}}


# ---------------------------------------------------------------- entry point

def build(calc_paths: list[tuple[str, str, str | None]], graph: dict | None = None, plans_path: str | None = None,
          profile: "profiles.Profile | str | None" = None) -> dict:
    pf = profiles.resolve(profile, plans_path, *[c[0] for c in calc_paths])
    all_pages, recs, notes, fits, table_pages, tables_out = [], {}, [], {}, set(), []
    for path, key, prefix in calc_paths:
        pk = calcpkg_ingest.read_package(path, key, prefix, profile=pf)
        pages = pk["pages"]
        all_pages += pages
        meta = {p["page"]: p for p in pages}
        doc = pymupdf.open(path)
        tables = read_tables(doc, key, meta, pf)
        for (run, title), tb in tables.items():
            tables_out.append({"doc": key, "run": run, "title": title, "header": tb["header"], "rows": len(tb["rows"]),
                               "columns_from": tb.get("columns_from"),
                               "pages": sorted(set(tb["pages"]))})
            for row in tb["rows"]:
                table_pages.add((key, row["page"]))
        r = build_records(tables)
        recs.update(r)
        notes += commentary(doc, key, meta, pf)
        if key == "calcs":
            geometry_info = geometry(recs, pf)
            fits = sketch_fit(doc, meta, recs, pf)
            calc_meta = meta
    prec = page_records(all_pages, table_pages, pf)
    edges, rcheck = load_path(recs, prec, pf)
    calc_notes = [n for n in notes if n["doc"] == "calcs"]
    attach_commentary(calc_notes, recs, prec, fits, calc_meta, pf)
    for (path, key, prefix) in calc_paths:
        if key != "calcs":
            m = {p["page"]: p for p in all_pages if p["doc"] == key}
            attach_commentary([n for n in notes if n["doc"] == key], recs, prec, {}, m, pf)
    pos = positional(graph, plans_path, recs, pf) if graph and plans_path else {"kept": False, "reason": "no drawing set"}
    allrecs = {**recs, **prec}
    for r in allrecs.values():
        r["section"] = _section(r, calc_meta)
    return {"runs": dict(pf.calcs.runs), "tables": tables_out, "records": list(allrecs.values()), "geometry": geometry_info,
            "load_path": edges, "reaction_check": rcheck, "commentary": notes, "sketch_fit": fits,
            "positional": pos, "stats": _stats(allrecs, edges, notes, pos)}


def _section(r, meta) -> str:
    if r.get("rows"):
        return (r["rows"][0]["sheet"] or "?")[:1]
    return (r.get("sheets") or ["?"])[0][:1] if r.get("doc") == "calcs" else r.get("doc", "")


def _stats(recs, edges, notes, pos) -> dict:
    by = defaultdict(int)
    for r in recs.values():
        by[f"{r['run']} / {r['type']}"] += 1
    ek = defaultdict(int)
    for e in edges:
        ek[f"{e['kind']} [{e['join']}]"] += 1
    s = {"records": len(recs), "records_by_run_type": dict(sorted(by.items())),
         "rows": sum(len(r.get("rows", [])) for r in recs.values()),
         "load_path_edges": dict(sorted(ek.items())),
         "join_kinds": {k: sum(1 for e in edges if e["join"] == k) for k in ("exact", "inferred", "absent")},
         "commentary": len(notes), "commentary_attached": sum(1 for n in notes if n.get("attached"))}
    if pos.get("beam_pairs"):
        s["beam_pairs"] = {lev: v["counts"] for lev, v in pos["beam_pairs"].items()}
    if pos.get("transform"):
        s["transform"] = {k: pos["transform"][k] for k in ("inliers", "drawn", "model", "rms_ft", "max_ft")} | {"kept": pos["kept"]}
    return s
