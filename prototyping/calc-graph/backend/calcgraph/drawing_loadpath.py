"""Load-path edges between drawing-set elements, from what the sheets show.

Edges point the way load flows (carried -> support), as in loadpath.py for IFC.
Each edge names the rule that produced it and carries evidence boxes on the sheet(s).

How a tag finds the thing it labels (vector geometry, page.get_drawings()):
  column tags   follow the LEADER: a thin line starting at the tag (often an underline
                first, then the angled leader); its far end is the column position.
  beam tags     the drawn member line the tag sits on (parallel, within 26 pt).
Sheets are registered to each other by their grid bubbles (same labels, per-axis
offset), so a point on the Level 2 plan can be looked up on the foundation plan.

Rules:
  beam->column     an end of the beam's drawn line is within 14 pt of a column position
                   (leader end) on the same plan or on the plan of the level below
  beam->beam       an end of the beam's line stops within 12 pt of the interior of another tagged
                   beam's line (girder)
  column->column   a column position on an upper plan within 14 pt of a column position
                   on the plan below (after grid registration)
  column->footing  a footing mark sits at the corner of its footing: the column at
                   distance between 0.4 x and 0.71 x the scheduled footing width (+40 pt for
                   the mark box) from the mark, nearest such column wins; scale from the
                   sheet's grid dimensions is 1/8" = 1'-0" (9 pt / ft), checked below
Unresolved beam ends and column tags whose leader cannot be followed are counted, not guessed.
"""
from __future__ import annotations

import math
from collections import defaultdict

import pymupdf

TOL_PERP = 26
TOL_COL = 14
TOL_ON = 12
PT_PER_FT = 9.0  # 1/8" = 1'-0"


def _all_segments(page) -> list[tuple]:
    out = []
    for d in page.get_drawings():
        if d.get("color") is None:
            continue
        w = d.get("width") or 0
        for it in d["items"]:
            if it[0] == "l":
                a, b = it[1], it[2]
                if math.hypot(a.x - b.x, a.y - b.y) > 2:
                    out.append((a.x, a.y, b.x, b.y, w))
    return out


def _axis(segs: list[tuple]) -> tuple[list, list]:
    hs, vs = [], []
    for x0, y0, x1, y1, w in segs:
        if abs(y0 - y1) < 0.8 and abs(x0 - x1) >= 25:
            hs.append((min(x0, x1), max(x0, x1), (y0 + y1) / 2, w))
        elif abs(x0 - x1) < 0.8 and abs(y0 - y1) >= 25:
            vs.append((min(y0, y1), max(y0, y1), (x0 + x1) / 2, w))
    return _merge(hs), _merge(vs)


def _merge(segs: list) -> list:
    by: dict[int, list] = defaultdict(list)
    for s in segs:
        by[round(s[2] * 2)].append(s)
    out = []
    for _, ss in by.items():
        ss.sort()
        cur = list(ss[0])
        for s in ss[1:]:
            if s[0] <= cur[1] + 2:
                cur[1] = max(cur[1], s[1])
                cur[3] = max(cur[3], s[3])
            else:
                out.append(tuple(cur))
                cur = list(s)
        out.append(tuple(cur))
    return out


def _near_box(x, y, b, tol):
    return b[0] - tol <= x <= b[2] + tol and b[1] - tol <= y <= b[3] + tol


def follow_leader(bbox: list[float], segs: list[tuple]) -> dict | None:
    """Far end of the leader that starts at a tag. An underline (horizontal, along the
    text) may come first; the first non-underline segment ends the leader."""
    thin = [s for s in segs if s[4] <= 0.8 and math.hypot(s[0] - s[2], s[1] - s[3]) < 300]
    best = None
    for s in thin:
        for (x, y), (ox, oy) in (((s[0], s[1]), (s[2], s[3])), ((s[2], s[3]), (s[0], s[1]))):
            if not _near_box(x, y, bbox, 6) or _near_box(ox, oy, bbox, 2):
                continue
            path, cur = [s], (ox, oy)
            under = abs(s[1] - s[3]) < 0.8 and bbox[1] - 2 <= s[1] <= bbox[3] + 6
            while under and len(path) < 3:
                nxt = None
                for t in thin:
                    if t in path:
                        continue
                    for (a, b_), (c, d) in (((t[0], t[1]), (t[2], t[3])), ((t[2], t[3]), (t[0], t[1]))):
                        if math.hypot(a - cur[0], b_ - cur[1]) < 1.5:
                            nxt = (t, (c, d))
                            break
                    if nxt:
                        break
                if not nxt:
                    break
                path.append(nxt[0])
                cur = nxt[1]
                under = abs(nxt[0][1] - nxt[0][3]) < 0.8
            if under:  # only an underline - no leader
                continue
            length = sum(math.hypot(p[0] - p[2], p[1] - p[3]) for p in path)
            if best is None or length > best["length"]:
                best = {"end": (round(cur[0], 1), round(cur[1], 1)), "length": round(length, 1),
                        "path": [[round(v, 1) for v in p[:4]] for p in path]}
    return best


def _line_for(el: dict, hs: list, vs: list):
    x0, y0, x1, y1 = el["bbox"]
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    if el["vertical_text"]:
        c = [(abs(s[2] - cx), s) for s in vs if s[0] - 2 <= cy <= s[1] + 2 and abs(s[2] - cx) <= TOL_PERP
             and s[1] - s[0] >= 1.5 * (y1 - y0)]
        if not c:
            return None
        s = min(c, key=lambda t: (t[0], -(t[1][1] - t[1][0])))[1]
        return {"axis": "v", "a": (s[2], s[0]), "b": (s[2], s[1])}
    c = [(abs(s[2] - cy), s) for s in hs if s[0] - 2 <= cx <= s[1] + 2 and abs(s[2] - cy) <= TOL_PERP
         and s[1] - s[0] >= 1.5 * (x1 - x0)]
    if not c:
        return None
    s = min(c, key=lambda t: (t[0], -(t[1][1] - t[1][0])))[1]
    return {"axis": "h", "a": (s[0], s[2]), "b": (s[1], s[2])}


def _register(src: dict, dst: dict):
    """Per-axis offset that maps a point on sheet `src` onto sheet `dst` (shared grid labels)."""
    def off(a, b):
        da = {g["label"]: g["pos"] for g in a}
        d = [g["pos"] - da[g["label"]] for g in b if g["label"] in da]
        return sum(d) / len(d) if d else None
    ox, oy = off(src["grid"]["cols"], dst["grid"]["cols"]), off(src["grid"]["rows"], dst["grid"]["rows"])
    if ox is None or oy is None:
        return None
    return lambda p: (p[0] + ox, p[1] + oy)


def _box(p, r=7):
    return [round(p[0] - r, 1), round(p[1] - r, 1), round(p[0] + r, 1), round(p[1] + r, 1)]


def _ev(el: dict, note: str = "", extra_rects=None) -> dict:
    return {"doc": el["doc"], "page": el["page"], "sheet": el["sheet"], "rects": el["rects"] + (extra_rects or []),
            "text": el["text"], "note": note}


def infer(doc_path: str, sheets: list[dict], elements: list[dict]) -> tuple[list[dict], dict]:
    from .drawing_ingest import grid_ref

    doc = pymupdf.open(doc_path)
    by_sheet: dict[str, list[dict]] = defaultdict(list)
    for e in elements:
        by_sheet[e["sheet"]].append(e)
    plans = [s for s in sheets if s["kind"] in ("framing", "foundation") and s["grid"]["cols"]]
    stack = [s for s in plans if s["kind"] == "foundation"]
    stack += sorted((s for s in plans if s["kind"] == "framing" and s["level"] != "Roof"), key=lambda s: s["level"])
    stack += [s for s in plans if s["kind"] == "framing" and s["level"] == "Roof"]
    stats: dict[str, int] = defaultdict(int)
    edges: dict[tuple, dict] = {}

    def add(src, dst, rule, evidence):
        k = (src["id"], dst["id"])
        if k in edges or src["id"] == dst["id"]:
            return
        edges[k] = {"src": src["id"], "dst": dst["id"], "rule": rule, "evidence": evidence}
        stats[rule] += 1

    segs_of, cols_of = {}, {}
    # 1. column positions from leaders
    for s in stack:
        segs = _all_segments(doc[s["page"] - 1])
        segs_of[s["sheet"]] = segs
        cols = []
        for e in by_sheet[s["sheet"]]:
            if e["cat"] != "Column":
                continue
            stats["column tags"] += 1
            ld = follow_leader(e["bbox"], segs)
            if not ld:
                stats["column tags without a followable leader"] += 1
                continue
            e["leader"] = ld
            e["at"] = list(ld["end"])
            g = grid_ref(ld["end"][0], ld["end"][1], s["grid"])
            e["grid"] = g["ref"]
            e["grid_node"] = g["node"] if g["node_dist"] is not None and g["node_dist"] <= 14 else None
            e["grid_node_dist"] = g["node_dist"]
            e["rects"] = e["rects"] + [_box(ld["end"], 6)]
            e["params"]["position"] = f"leader end at {g['ref']}" + (f" (on grid node {e['grid_node']})" if e["grid_node"] else "")
            cols.append(e)
            stats["column tags located by leader"] += 1
        cols_of[s["sheet"]] = cols

    def cols_near(p, sheet_idx_list, own_sheet):
        out = []
        for j in sheet_idx_list:
            sj = stack[j]
            mp = (lambda q: q) if sj["sheet"] == own_sheet["sheet"] else _register(own_sheet, sj)
            if mp is None:
                continue
            q = mp(p)
            for c in cols_of[sj["sheet"]]:
                d = math.hypot(c["at"][0] - q[0], c["at"][1] - q[1])
                if d <= TOL_COL:
                    out.append((d, c, sj["sheet"]))
            if out:
                break
        return sorted(out, key=lambda t: t[0])

    for li, s in enumerate(stack):
        # 2. beams
        if s["kind"] == "framing":
            hs, vs = _axis(segs_of[s["sheet"]])
            beams = [e for e in by_sheet[s["sheet"]] if e["cat"] == "Beam" and e["family"] == "W"]
            lines = {}
            for b in beams:
                ln = _line_for(b, hs, vs)
                if ln:
                    lines[b["id"]] = ln
                    b["line"] = [round(v, 1) for v in (*ln["a"], *ln["b"])]
            stats["beam tags"] += len(beams)
            stats["beam tags on a drawn line"] += len(lines)
            below = [li, li - 1] if li > 0 else [li]
            for b in beams:
                ln = lines.get(b["id"])
                if not ln:
                    continue
                for end in (ln["a"], ln["b"]):
                    hit = cols_near(end, [li], s) or cols_near(end, [j for j in below if j != li], s)
                    if hit:
                        d, c, on = hit[0]
                        add(b, c, "beam->column", [
                            _ev(b, f"tag on the drawn beam line; line end {d:.0f} pt from the column"),
                            {"doc": "plans", "page": s["page"], "sheet": s["sheet"], "rects": [_box(end)],
                             "text": "beam line end", "note": "end of the drawn beam line"},
                            _ev(c, f"column position (leader end) on {on}")])
                        stats["beam ends resolved"] += 1
                        continue
                    done = False
                    for ob in beams:
                        o = lines.get(ob["id"])
                        if ob is b or not o or o["axis"] == ln["axis"]:
                            continue
                        (ax, ay), (bx, by) = o["a"], o["b"]
                        if (o["axis"] == "h" and ax + 3 < end[0] < bx - 3 and abs(end[1] - ay) <= TOL_ON) or \
                           (o["axis"] == "v" and ay + 3 < end[1] < by - 3 and abs(end[0] - ax) <= TOL_ON):
                            add(b, ob, "beam->beam", [
                                _ev(b, "beam line ends on another beam's line"),
                                {"doc": "plans", "page": s["page"], "sheet": s["sheet"], "rects": [_box(end)],
                                 "text": "junction", "note": "beam line end on the girder"},
                                _ev(ob, "supporting beam (girder)")])
                            done = True
                            break
                    stats["beam ends resolved" if done else "beam ends unresolved"] += 1
        # 3. column stacks
        if li > 0:
            for c in cols_of[s["sheet"]]:
                hit = cols_near(tuple(c["at"]), [li - 1, li - 2] if li > 1 else [li - 1], s)
                if hit:
                    d, below_c, on = hit[0]
                    add(c, below_c, "column->column", [_ev(c, "column position (leader end)"),
                                                       _ev(below_c, f"column below on {on}, {d:.0f} pt after grid registration")])
        # 4. footings
        if s["kind"] == "foundation":
            for f in by_sheet[s["sheet"]]:
                if f["cat"] != "Footing":
                    continue
                sch = f.get("schedule")
                width = (sch["width_ft"] if sch else 4.0) * PT_PER_FT
                fx, fy = (f["bbox"][0] + f["bbox"][2]) / 2, (f["bbox"][1] + f["bbox"][3]) / 2
                cand = []
                for c in cols_of[s["sheet"]]:
                    d = math.hypot(c["at"][0] - fx, c["at"][1] - fy)
                    if 0.4 * width <= d <= 0.71 * width + 40:
                        cand.append((d, c))
                if cand:
                    d, c = min(cand, key=lambda t: t[0])
                    add(c, f, "column->footing", [
                        _ev(c, "column position (leader end)"),
                        _ev(f, f"footing mark {d:.0f} pt from the column; scheduled width "
                               f"{width / PT_PER_FT:.1f} ft = {width:.0f} pt at 1/8\" = 1'-0\"")])
                else:
                    stats["footing marks with no column in range"] += 1
    return list(edges.values()), dict(stats)
