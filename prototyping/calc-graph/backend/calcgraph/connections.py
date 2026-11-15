"""Connections as first-class nodes, read off a drawing set (no BIM model).

Two node kinds:

- connection TYPE: one per typical / connection detail drawn on an S8.x sheet
  ("16/S8.2.2 HSS BEAM-COLUMN AT SCREEN/PARAPET"), with the detail panel's bbox,
  its title words, and the bolt / weld / plate / anchor lines printed inside it.
- connection INSTANCE: one per place the drawings say that detail (or a framing-plan
  connection symbol) occurs, with sheet, bbox, grid ref and the drawn element(s) it
  joins.

Deterministic rules, each recorded on the node it produced:

- detail title bar (S8 sheets), either layout: (a) a big detail number (h ~25 pt) with the
  title words (h ~19 pt) on the same baseline to its LEFT, right of the previous number on
  that row; the panel is the area above the bar, up to the bar above in the same column;
  (b) the number in a bubble LEFT of the title, over the sheet's own number; the panel is the
  drawn rectangle around the bar (else the area above it).
- callout bubble: a sheet-number word (S8.2.2) with a label word (16) centred directly
  above it, both inside a drawn circle. The bubble's leader (a line leaving the circle)
  is followed to its far end; that end is the instance's location.
- text reference: "PER 13/ S8.2.1" or "1/S5.0.3" in a text line (the number and the
  sheet may be split over two words).
- framing-plan symbols, defined by the plan's own legend ("INDICATES DRAG CONNECTION
  PER 1/ S8.2.3"): filled triangle = moment resisting frame connection, open triangle
  = moment connection at cantilevered framing, filled circle = drag connection,
  filled diamond = full height stiffener connection, double-headed arrow = kicker
  brace. The classifier is checked against the legend's own exemplars on every run; a kind
  whose exemplar the built-in classifier does not recognise (a set that draws it differently)
  is found by the exemplar's own shape instead (filled polygon, edge lengths, any rotation).
- attachment: nearest drawn element(s) of the drawing-set element source (beam drawn
  line, column position, else tag bbox), on the same sheet, within a stated distance.

Set conventions come from the set's profile (calcgraph/profiles/*.yaml): which sheets hold the
connection-type details and their category by sheet prefix, detail title-bar text heights, the
sheet-number and detail-reference regexes, the plan legend phrases -> symbol kinds, and the calc
connection rules. `build` resolves the profile from the file names unless one is passed.
"""
from __future__ import annotations

import math
import re
from collections import Counter, defaultdict

import pymupdf

from . import profiles, sizes
from .drawing_ingest import grid_ref

LABEL_RE = re.compile(r"^(?:\d{1,2}[A-Z]?|[A-Z])$")


def _r(b) -> list[float]:
    return [round(b[0], 1), round(b[1], 1), round(b[2], 1), round(b[3], 1)]


def _c(b) -> tuple[float, float]:
    return ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)


def _h(w) -> float:
    return w[3] - w[1]


def _category(sheet: str, pf) -> str:
    for c in pf.drawings.details.categories:
        if sheet.startswith(c.prefix):
            return c.category
    return "other"


def _lines(words) -> list[dict]:
    """Text lines as PyMuPDF groups them (block, line), words in reading order."""
    by: dict[tuple, list] = defaultdict(list)
    for w in words:
        by[(w[5], w[6])].append(w)
    out = []
    for k, ws in by.items():
        ws.sort(key=lambda w: w[7])
        out.append({"key": k, "words": ws, "text": " ".join(w[4] for w in ws),
                    "rect": [min(w[0] for w in ws), min(w[1] for w in ws), max(w[2] for w in ws), max(w[3] for w in ws)]})
    return out


# ----------------------------------------------------------------------------- details


def read_details(page, sheet: dict, pf) -> list[dict]:
    dt = pf.drawings.details
    nlo, nhi = dt.number_height_pt
    tlo, thi = dt.title_height_pt
    x_max = dt.x_max.at(page.rect.width)
    words = page.get_text("words")
    nums = [w for w in words if re.fullmatch(r"\d{1,2}[A-Z]?", w[4]) and nlo <= _h(w) <= nhi and w[0] < x_max]
    rows: dict[int, list] = defaultdict(list)
    for n in nums:
        rows[round(_c(n)[1] / 8)].append(n)
    bars = []
    for _, ns in rows.items():
        ns.sort(key=lambda w: w[0])
        for i, n in enumerate(ns):
            left = ns[i - 1][2] + 4 if i else 40.0
            cy = _c(n)[1]
            tw = [w for w in words if tlo <= _h(w) < thi and abs(_c(w)[1] - cy) < 6.5 and left < w[0] and w[2] < n[0]]
            tw.sort(key=lambda w: w[0])
            # keep the contiguous run nearest the number: sub-view captions further left on the same
            # baseline (whole-sheet details) are separated by a wide gap
            run = []
            for w in reversed(tw):
                if run and run[-1][0] - w[2] > 45:
                    break
                run.append(w)
            tw = run[::-1]
            # scale text (small) between title and number, e.g. 1" = 1'-0" / NTS
            sc = [w for w in words if _h(w) < 13 and abs(_c(w)[1] - cy) < 6 and (tw[-1][2] if tw else left) < w[0] < n[0]]
            bars.append({"num": n, "left": left, "title_words": tw, "scale_words": sorted(sc, key=lambda w: w[0])})
    out = []
    for b in bars:
        n = b["num"]
        x0, x1 = b["left"], n[2] + 4
        above = [o["num"] for o in bars if o["num"][3] < n[1] - 30 and o["left"] < x1 - 20 and o["num"][2] + 4 > x0 + 20]
        y0 = max((a[3] + 4 for a in above), default=40.0)
        panel = [x0, y0, x1, n[3] + 3]
        title = " ".join(w[4] for w in b["title_words"])
        did = f"{n[4]}/{sheet['sheet']}"
        inside = [w for w in words if panel[0] <= w[0] and w[2] <= panel[2] and panel[1] <= w[1] and w[3] <= n[1] - 2]
        spec, seen = [], set()
        for ln in _lines(inside):
            t = ln["text"].strip()
            if dt.spec_regex.search(t.upper()) and t not in seen:
                seen.add(t)
                spec.append({"text": t, "rect": _r(ln["rect"])})
        szs = sorted({sizes.norm(w[4])["norm"] for w in inside if sizes.norm(w[4])})
        out.append({
            "id": did, "node_type": "connection_type", "detail": n[4], "sheet": sheet["sheet"], "page": sheet["page"],
            "doc": "plans", "sheet_title": sheet.get("title", ""), "category": _category(sheet["sheet"], pf),
            "title": title, "is_connection": bool(dt.connection_title_regex.search(title.upper())),
            "scale": " ".join(w[4] for w in b["scale_words"]),
            "bbox": _r(panel), "number_rect": _r(n), "title_rects": [_r(w) for w in b["title_words"]],
            "spec": spec, "sizes": szs, "rule": "detail title bar: number h~25pt, title words h~19pt left of it",
        })
    used = {(round(b["num"][0]), round(b["num"][1])) for b in bars}
    out += _details_bubble_left(page, words, sheet, pf, used)
    out.sort(key=lambda d: (int(re.match(r"\d+", d["detail"]).group()), d["detail"]))
    return out


def _details_bubble_left(page, words, sheet: dict, pf, used: set) -> list[dict]:
    """The other common title-bar layout: the detail number sits in a circle LEFT of the title, over the
    sheet number ("1" over "S-501" in a bubble, then "SMF MOMENT CONNECTION MC-1 (RBS)" on the bar).
    A bubble is a TITLE (not a callout to the detail) when the sheet under the number is this sheet,
    title-height words start right of the circle on the number's row, and a drawn rule underlines them. The panel is the smallest drawn
    rectangle around bubble + title, else the area above the bar (as for the number-right layout)."""
    dt = pf.drawings.details
    tlo, thi = dt.title_height_pt
    x_max = dt.x_max.at(page.rect.width)
    drawings = page.get_drawings()
    circles = _circles(drawings)
    segs = _segments(drawings)
    rects = []
    for d in drawings:
        for it in d["items"]:
            if it[0] == "re" and d.get("color") is not None:
                rects.append(pymupdf.Rect(it[1]))
    bars = []
    for n in words:
        if not re.fullmatch(r"\d{1,2}[A-Z]?", n[4]) or (round(n[0]), round(n[1])) in used or n[0] >= x_max:
            continue
        below = [w for w in words if w[4] == sheet["sheet"] and abs(_c(w)[0] - _c(n)[0]) < 7 and 0 <= w[1] - n[3] < 9]
        if not below:
            continue
        s = below[0]
        mx, my = _c(n)[0], (n[3] + s[1]) / 2
        circ = [c for c in circles if math.hypot(c[0] - mx, c[1] - my) < 8 and 10 <= c[2] <= 30]
        if not circ:
            continue
        cx, cy, r = min(circ, key=lambda c: math.hypot(c[0] - mx, c[1] - my))
        ny = _c(n)[1]
        cand = sorted((w for w in words if tlo <= _h(w) < thi and abs(_c(w)[1] - ny) < 6.5 and w[0] > cx + r - 2),
                      key=lambda w: w[0])
        run = []
        for w in cand:
            if (not run and w[0] - (cx + r) > 40) or (run and w[0] - run[-1][2] > 45):
                break
            run.append(w)
        if not run:
            continue
        # a title bar is underlined: a drawn horizontal rule just below the title words, at least as wide
        tx0, tx1, tb = run[0][0], run[-1][2], max(w[3] for w in run)
        if not any(abs(q[1] - q[3]) < 0.5 and -2 <= q[1] - tb <= 10 and min(q[0], q[2]) <= tx0 + 4
                   and max(q[0], q[2]) >= tx0 + 0.8 * (tx1 - tx0) for q in segs):
            continue
        sc = sorted((w for w in words if _h(w) < 13 and run[0][0] - 2 <= w[0] and 0 <= w[1] - run[0][3] < 14),
                    key=lambda w: w[0])
        sc = [w for w in sc if abs(w[1] - sc[0][1]) < 2] if sc and sc[0][4].upper().startswith("SCALE") else []
        bars.append({"num": n, "sheet_word": s, "circle": (cx, cy, r), "title_words": run, "scale_words": sc})
    out = []
    for b in bars:
        n, (cx, cy, r) = b["num"], b["circle"]
        bar = pymupdf.Rect(cx - r, cy - r, max(w[2] for w in b["title_words"]), cy + r)
        box = [q for q in rects if q.contains(bar) and q.width < page.rect.width * 0.9]
        if box:
            q = min(box, key=lambda q: q.width * q.height)
            panel, how = [q.x0, q.y0, q.x1, q.y1], "the drawn rectangle around bubble + title"
        else:
            right = [o["circle"][0] - o["circle"][2] for o in bars if abs(o["circle"][1] - cy) < 8 and o["circle"][0] > cx]
            x0, x1 = cx - r - 8, (min(right) - 4) if right else x_max
            above = [o["circle"] for o in bars if o["circle"][1] + o["circle"][2] < cy - r - 30
                     and o["circle"][0] - o["circle"][2] < x1 - 20 and o["circle"][0] + o["circle"][2] > x0 + 20]
            panel, how = [x0, max((a[1] + a[2] + 4 for a in above), default=40.0), x1, cy + r + 3], "the area above the bar"
        title = " ".join(w[4] for w in b["title_words"])
        inside = [w for w in words if panel[0] <= w[0] and w[2] <= panel[2] and panel[1] <= w[1] and w[3] <= cy - r - 2]
        spec, seen = [], set()
        for ln in _lines(inside):
            t = ln["text"].strip()
            if dt.spec_regex.search(t.upper()) and t not in seen:
                seen.add(t)
                spec.append({"text": t, "rect": _r(ln["rect"])})
        szs = sorted({sizes.norm(w[4])["norm"] for w in inside if sizes.norm(w[4])})
        out.append({
            "id": f"{n[4]}/{sheet['sheet']}", "node_type": "connection_type", "detail": n[4], "sheet": sheet["sheet"],
            "page": sheet["page"], "doc": "plans", "sheet_title": sheet.get("title", ""), "category": _category(sheet["sheet"], pf),
            "title": title, "is_connection": bool(dt.connection_title_regex.search(title.upper())),
            "scale": " ".join(w[4] for w in b["scale_words"]),
            "bbox": _r(panel), "number_rect": _r(n), "title_rects": [_r(w) for w in b["title_words"]],
            "spec": spec, "sizes": szs,
            "rule": f"detail title bar: number over this sheet's number in a bubble LEFT of the title; panel = {how}",
        })
    return out


# ----------------------------------------------------------------------------- vector helpers


def _segments(drawings) -> list[tuple]:
    out = []
    for d in drawings:
        if d.get("color") is None:
            continue
        w = d.get("width") or 0
        for it in d["items"]:
            if it[0] == "l":
                a, b = it[1], it[2]
                out.append((a.x, a.y, b.x, b.y, w))
    return out


def _circles(drawings) -> list[tuple]:
    """Stroked closed curves ~ circles: (cx, cy, r)."""
    out, halves = [], []
    for d in drawings:
        if d.get("color") is None or not d["items"]:
            continue
        nc = sum(1 for it in d["items"] if it[0] == "c")
        if nc < 2:
            continue
        r = d["rect"]
        if 14 <= r.width <= 60 and abs(r.width - r.height) < 2.5 and nc >= 4:
            out.append(((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2, r.width / 2))
        elif 14 <= max(r.width, r.height) <= 60 and abs(max(r.width, r.height) - 2 * min(r.width, r.height)) < 2.5:
            halves.append(r)  # the sheets draw bubbles as two semicircles
    for i, a in enumerate(halves):
        for b in halves[i + 1:]:
            u = pymupdf.Rect(a) | b
            if abs(u.width - u.height) < 2.5 and abs(u.width - max(a.width, a.height)) < 1.5 and \
                    (abs(a.y1 - b.y0) < 1 or abs(b.y1 - a.y0) < 1 or abs(a.x1 - b.x0) < 1 or abs(b.x1 - a.x0) < 1):
                out.append(((u.x0 + u.x1) / 2, (u.y0 + u.y1) / 2, u.width / 2))
    return out


def _follow(start: tuple, first: tuple, segs: list, max_steps: int = 4) -> tuple[tuple, list]:
    path, cur = [first], start
    for _ in range(max_steps - 1):
        nxt = None
        for t in segs:
            if t in path or t[4] > 1.0:
                continue
            for (a, b_), (c, d) in (((t[0], t[1]), (t[2], t[3])), ((t[2], t[3]), (t[0], t[1]))):
                if math.hypot(a - cur[0], b_ - cur[1]) < 1.2 and math.hypot(c - a, d - b_) > 2:
                    nxt = (t, (c, d))
                    break
            if nxt:
                break
        if not nxt:
            break
        path.append(nxt[0])
        cur = nxt[1]
    return cur, path


def _leader(cx: float, cy: float, r: float, segs: list) -> dict | None:
    """A thin line leaving the bubble's circle; follow its chain to the far end."""
    best = None
    for s in segs:
        if s[4] > 1.0:
            continue
        for (x, y), (ox, oy) in (((s[0], s[1]), (s[2], s[3])), ((s[2], s[3]), (s[0], s[1]))):
            d0, d1 = math.hypot(x - cx, y - cy), math.hypot(ox - cx, oy - cy)
            # leaders start on the circle or a little off it (the sheets leave a gap of up to ~9 pt)
            if r - 1.5 <= d0 <= r + 10 and d1 > d0 + 6:
                end, path = _follow((ox, oy), s, segs)
                length = sum(math.hypot(p[0] - p[2], p[1] - p[3]) for p in path)
                if length < 12:
                    continue
                if best is None or length > best["length"]:
                    best = {"end": (round(end[0], 1), round(end[1], 1)), "length": round(length, 1),
                            "path": [[round(v, 1) for v in p[:4]] for p in path]}
    return best


# ----------------------------------------------------------------------------- callouts / refs


def find_callouts(page, words, drawings, circles, segs, sheet_re) -> list[dict]:
    out = []
    for s in words:
        if not sheet_re.match(s[4]) or _h(s) > 13:
            continue
        scx = _c(s)[0]
        # the label is usually the bigger, bolder text of the bubble: allow up to 1.6x the sheet word's height
        labs = [w for w in words if LABEL_RE.match(w[4]) and abs(_c(w)[0] - scx) < 7 and 0 <= s[1] - w[3] < 9
                and _h(w) <= max(13, 1.6 * _h(s))]
        if not labs:
            continue
        lab = min(labs, key=lambda w: s[1] - w[3])
        mx, my = (_c(lab)[0] + _c(s)[0]) / 2, (lab[1] + s[3]) / 2
        circ = [c for c in circles if math.hypot(c[0] - mx, c[1] - my) < 6 and c[2] < 30]
        if not circ:
            continue
        cx, cy, r = min(circ, key=lambda c: math.hypot(c[0] - mx, c[1] - my))
        ld = _leader(cx, cy, r, segs)
        near = [w for w in words if w[4] in ("TYP", "TYP.", "SIM", "SIM.", "OH", "(TYP)") and
                math.hypot(_c(w)[0] - cx, _c(w)[1] - cy) < r + 30]
        out.append({"label": lab[4], "target_sheet": s[4], "ref": f"{lab[4]}/{s[4]}", "center": (round(cx, 1), round(cy, 1)),
                    "radius": round(r, 1), "bbox": _r([cx - r, cy - r, cx + r, cy + r]), "rects": [_r(lab), _r(s)],
                    "leader": ld, "flags": sorted({w[4].strip("().").upper() for w in near})})
    return out


def find_text_refs(words, text_ref) -> list[dict]:
    out = []
    for ln in _lines(words):
        t = ln["text"]
        for m in text_ref.finditer(t):
            # map character span back to words
            pos, rects = 0, []
            for w in ln["words"]:
                a, b = pos, pos + len(w[4])
                if b > m.start() and a < m.end():
                    rects.append(_r(w))
                pos = b + 1
            ctx = t[max(0, m.start() - 60):m.end() + 20].strip()
            out.append({"ref": f"{m.group(1)}/{m.group(2)}", "label": m.group(1), "target_sheet": m.group(2),
                        "rects": rects, "bbox": _r([min(r[0] for r in rects), min(r[1] for r in rects),
                                                    max(r[2] for r in rects), max(r[3] for r in rects)]),
                        "line": t, "context": ctx, "line_key": ln["key"], "line_rect": _r(ln["rect"])})
    return out


# ----------------------------------------------------------------------------- framing-plan symbols


def _fills(drawings, black: bool) -> list:
    want = (0.0, 0.0, 0.0) if black else (1.0, 1.0, 1.0)
    return [d["rect"] for d in drawings if d["type"] == "f" and d.get("fill") == want]


def _classify_fill(r, segs) -> str | None:
    R = pymupdf.Rect(r.x0 - 1, r.y0 - 1, r.x1 + 1, r.y1 + 1)
    ins = [s for s in segs if R.contains(pymupdf.Point(s[0], s[1])) and R.contains(pymupdf.Point(s[2], s[3]))]
    ax = sum(1 for s in ins if (abs(s[0] - s[2]) < 0.3 or abs(s[1] - s[3]) < 0.3) and max(abs(s[0] - s[2]), abs(s[1] - s[3])) > 5)
    dg = sum(1 for s in ins if abs(s[0] - s[2]) > 2 and abs(s[1] - s[3]) > 2)
    tiny = sum(1 for s in ins if math.hypot(s[0] - s[2], s[1] - s[3]) < 2)
    w, h = r.width, r.height
    if tiny > 5 and abs(w - h) < 1.5 and 7.5 <= w <= 11:
        return "drag"
    if dg >= 4 and {round(min(w, h)), round(max(w, h))} <= {9, 13, 14} and abs(w - h) > 3:
        return "stiffener"
    if ax >= 1 and 2 <= dg <= 3 and abs(w - h) > 3 and 8 <= min(w, h) <= 10 and 12.5 <= max(w, h) <= 14.5:
        return "triangle"
    return None


def _open_triangles(segs, black_fills) -> list:
    """Stroked triangles (axis-aligned base ~13.5 pt, apex ~9 pt away) not covered by a black fill."""
    out = []
    base = [s for s in segs if 12.5 <= math.hypot(s[0] - s[2], s[1] - s[3]) <= 14.5 and
            (abs(s[0] - s[2]) < 0.3 or abs(s[1] - s[3]) < 0.3) and s[4] >= 1.2]
    for b in base:
        ends = ((b[0], b[1]), (b[2], b[3]))
        diag = [s for s in segs if abs(s[0] - s[2]) > 2 and abs(s[1] - s[3]) > 2 and 7 < math.hypot(s[0] - s[2], s[1] - s[3]) < 13]
        hit = []
        for e in ends:
            for s in diag:
                for p, q in (((s[0], s[1]), (s[2], s[3])), ((s[2], s[3]), (s[0], s[1]))):
                    if math.hypot(p[0] - e[0], p[1] - e[1]) < 1.2:
                        hit.append(q)
        apex = [q for q in hit if sum(1 for o in hit if math.hypot(o[0] - q[0], o[1] - q[1]) < 1.5) >= 2]
        if not apex:
            continue
        xs = [ends[0][0], ends[1][0], apex[0][0]]
        ys = [ends[0][1], ends[1][1], apex[0][1]]
        r = pymupdf.Rect(min(xs), min(ys), max(xs), max(ys))
        cx, cy = (r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2
        if any(f.x0 - 1 <= cx <= f.x1 + 1 and f.y0 - 1 <= cy <= f.y1 + 1 for f in black_fills):
            continue
        if any(abs(o.x0 - r.x0) < 1 and abs(o.y0 - r.y0) < 1 for o in out):
            continue
        out.append(r)
    return out


def _kickers(drawings, segs) -> list:
    heads = [r for r in _fills(drawings, True) if 3.5 <= r.width <= 6 and 3.5 <= r.height <= 6]
    out = []
    for s in segs:
        L = math.hypot(s[0] - s[2], s[1] - s[3])
        if not 12 <= L <= 90:
            continue
        a = [h for h in heads if math.hypot((h.x0 + h.x1) / 2 - s[0], (h.y0 + h.y1) / 2 - s[1]) < 5]
        b = [h for h in heads if math.hypot((h.x0 + h.x1) / 2 - s[2], (h.y0 + h.y1) / 2 - s[3]) < 5]
        if a and b:
            r = pymupdf.Rect(min(s[0], s[2]) - 3, min(s[1], s[3]) - 3, max(s[0], s[2]) + 3, max(s[1], s[3]) + 3)
            if not any(abs(o.x0 - r.x0) < 2 and abs(o.y0 - r.y0) < 2 for o in out):
                out.append(r)
    return out


def find_symbols(drawings, segs, region) -> list[dict]:
    """All framing-plan connection symbols inside region (x0, y0, x1, y1)."""
    def inr(r):
        return region[0] <= r.x0 and r.x1 <= region[2] and region[1] <= r.y0 and r.y1 <= region[3]

    black = [r for r in _fills(drawings, True) if inr(r)]
    out, seen = [], set()
    for r in black:
        if not (7 <= r.width <= 16 and 7 <= r.height <= 16):
            continue
        k = _classify_fill(r, segs)
        if not k:
            continue
        key = (round(r.x0), round(r.y0))
        if key in seen:
            continue
        seen.add(key)
        out.append({"kind": "mrf" if k == "triangle" else k, "rect": r})
    for r in _open_triangles([s for s in segs if inr(pymupdf.Rect(min(s[0], s[2]), min(s[1], s[3]), max(s[0], s[2]) + .01,
                                                                    max(s[1], s[3]) + .01))], black):
        out.append({"kind": "moment_cantilever", "rect": r})
    for r in _kickers([d for d in drawings if inr(d["rect"])], segs):
        if inr(r):
            out.append({"kind": "kicker", "rect": r})
    return out


def _poly_sig(d) -> tuple | None:
    """Rotation-invariant shape signature of a filled polygon: its sorted edge lengths."""
    if d.get("type") not in ("f", "fs") or d.get("fill") != (0.0, 0.0, 0.0) or not d["items"]:
        return None
    if any(it[0] != "l" for it in d["items"]):
        return None
    return tuple(sorted(round(math.hypot(it[1].x - it[2].x, it[1].y - it[2].y), 1) for it in d["items"]))


def legend_templates(drawings, legend: dict, lx0: float) -> dict:
    """Symbol kind -> shape signatures of the filled polygons drawn in that legend row's symbol column."""
    out = {}
    for kind, v in legend.items():
        y0, y1 = v["rect"][1] - 14, v["rect"][3] + 8
        sigs = []
        for d in drawings:
            r = d["rect"]
            if lx0 - 120 <= r.x0 and r.x1 <= lx0 - 5 and y0 <= (r.y0 + r.y1) / 2 <= y1:
                sg = _poly_sig(d)
                if sg and 4 <= max(r.width, r.height) <= 20 and sg not in sigs:
                    sigs.append(sg)
        if sigs:
            out[kind] = sigs
    return out


def find_by_template(drawings, templates: dict, region, tol: float = 0.6) -> list[dict]:
    """Filled polygons in region whose edge lengths match a legend exemplar (any rotation / mirror)."""
    out, seen = [], set()
    for d in drawings:
        r = d["rect"]
        if not (region[0] <= r.x0 and r.x1 <= region[2] and region[1] <= r.y0 and r.y1 <= region[3]):
            continue
        sg = _poly_sig(d)
        if not sg:
            continue
        for kind, sigs in templates.items():
            if any(len(t) == len(sg) and all(abs(a - b) <= tol for a, b in zip(t, sg)) for t in sigs):
                key = (round(r.x0), round(r.y0))
                if key not in seen:
                    seen.add(key)
                    out.append({"kind": kind, "rect": pymupdf.Rect(r)})
                break
    return out


def read_legend(words, cutoff: float, pf) -> tuple[dict, list]:
    """Symbol kind -> {detail ref, legend text, rects} from the plan's symbol legend (profile phrases)."""
    lg = pf.drawings.symbol_legend
    lines = [ln for ln in _lines(words) if ln["rect"][0] >= cutoff - 200]
    refs = find_text_refs([w for w in words if w[0] >= cutoff - 200], pf.drawings.details.text_ref_regex)
    legend, rows = {}, []
    blocks: dict[int, list] = defaultdict(list)
    for ln in lines:
        blocks[ln["key"][0]].append(ln)
    for bno, lns in blocks.items():
        text = " ".join(ln["text"] for ln in sorted(lns, key=lambda x: x["rect"][1]))
        for ent in lg.entries:
            key, kind = ent.phrase, ent.kind
            if text.upper().startswith(lg.line_prefix) and key in text.upper():
                rect = [min(ln["rect"][0] for ln in lns), min(ln["rect"][1] for ln in lns),
                        max(ln["rect"][2] for ln in lns), max(ln["rect"][3] for ln in lns)]
                ref = [r for r in refs if rect[1] - 3 <= _c(r["bbox"])[1] <= rect[3] + 3 and r["bbox"][0] > rect[0]]
                legend[kind] = {"kind": kind, "name": ent.name, "text": text.strip() +
                                (" " + ref[0]["context"].split("PER")[-1].strip() if ref else ""),
                                "detail": ref[0]["ref"].rstrip(".") if ref else None, "rect": _r(rect),
                                "ref_rects": ref[0]["rects"] if ref else []}
                rows.append(rect)
    return legend, rows


# ----------------------------------------------------------------------------- attachment


def _elem_geom(e: dict):
    if e.get("line"):
        x0, y0, x1, y1 = e["line"]
        return ("seg", (x0, y0, x1, y1))
    if e.get("at"):
        return ("pt", tuple(e["at"]))
    return ("box", tuple(e["bbox"]))


def _dist(p, g) -> float:
    kind, v = g
    x, y = p
    if kind == "pt":
        return math.hypot(x - v[0], y - v[1])
    if kind == "box":
        dx = max(v[0] - x, 0, x - v[2])
        dy = max(v[1] - y, 0, y - v[3])
        return math.hypot(dx, dy)
    x0, y0, x1, y1 = v
    L2 = (x1 - x0) ** 2 + (y1 - y0) ** 2
    t = 0 if L2 == 0 else max(0, min(1, ((x - x0) * (x1 - x0) + (y - y0) * (y1 - y0)) / L2))
    return math.hypot(x - (x0 + t * (x1 - x0)), y - (y0 + t * (y1 - y0)))


def _end_dist(p, g) -> float | None:
    if g[0] != "seg":
        return None
    x0, y0, x1, y1 = g[1]
    return min(math.hypot(p[0] - x0, p[1] - y0), math.hypot(p[0] - x1, p[1] - y1))


def attach(p: tuple, els: list[dict], *, max_d: float, want: int = 2, symbol: bool = False) -> list[dict]:
    """Nearest drawn elements to point p (same sheet), one per category. For a plan symbol a
    second beam is kept when the first ENDS at the symbol and the second runs THROUGH it.
    Roles state geometry only (ends at / runs through); which member the detail designs is
    not inferred. The beam lines come from drawing_loadpath and can over-merge collinear
    beams, so "runs through" can be a merged line."""
    cand = []
    for e in els:
        g = _elem_geom(e)
        d = _dist(p, g)
        lim = max_d
        if symbol:  # a symbol is ~9-14 pt: it must touch the drawn member; a tag box only counts when it touches the symbol
            lim = {"seg": 14, "pt": 22, "box": 8}[g[0]]
        if d <= lim:
            ed = _end_dist(p, g)
            cand.append({"id": e["id"], "cat": e["cat"], "type": e["type"], "size": e["size"] or e["mark"],
                         "dist": round(d, 1), "geom": g[0], "at_end": ed is not None and ed <= max_d,
                         "end_dist": None if ed is None else round(ed, 1)})
    # a symbol sits at the END of the member it marks: try end-on beams before beams running past
    cand.sort(key=lambda c: (symbol and c["cat"] == "Beam" and not (c["at_end"] and (c["end_dist"] or 0) <= 22), c["dist"]))
    out, cats = [], set()
    for c in cand:
        if c["cat"] in cats:
            first = next(o for o in out if o["cat"] == c["cat"])
            if not (symbol and c["cat"] == "Beam" and first.get("role") == "beam line ends at the symbol" and c["geom"] == "seg"
                    and not (c["at_end"] and (c["end_dist"] or 0) <= 6)
                    and not any(str(o.get("role", "")).startswith("beam line runs") for o in out)):
                continue
            c["role"] = "beam line runs through the symbol"
            out.append(c)
            continue
        cats.add(c["cat"])
        if c["cat"] == "Beam" and c["geom"] == "seg":
            c["role"] = "beam line ends at the symbol" if c["at_end"] and (c["end_dist"] or 0) <= 22 else "beam line passes near the symbol"
        elif c["cat"] == "Column":
            c["role"] = "column at the symbol"
        out.append(c)
        if len(out) >= want + (1 if symbol else 0):
            break
    return out


# ----------------------------------------------------------------------------- calc package


def scan_calcs(calc_docs: list[tuple[str, str]], calc_ids: dict, detail_ids: dict, pf) -> dict:
    """calc_docs: [(doc key, path)]. Returns per-page hits, detail references from calc pages,
    and a verdict per rule. calc_ids maps (doc, page) -> calc node id of the set graph."""
    CALC_ID, SHEET_RE = pf.calcs.page_id.regex, pf.drawings.title_block.sheet_number_regex
    TEXT_REF = pf.drawings.details.text_ref_regex
    hits, refs = [], []
    for key, path in calc_docs:
        doc = pymupdf.open(path)
        for i, page in enumerate(doc):
            text = page.get_text()
            words = page.get_text("words")
            cid = calc_ids.get((key, i + 1)) or next((ln for ln in text.splitlines() if CALC_ID.match(ln.strip())), f"{key}-{i + 1}")
            for cr in pf.calcs.connection_rules:
                rid, rx, what, designs = cr.id, cr.regex, cr.what, cr.designs_connection
                ms = list(rx.finditer(text))
                if not ms:
                    continue
                snippet = text[max(0, ms[0].start() - 120):ms[0].end() + 160].replace("\n", " | ")
                rects = []
                for q in {m.group(0) for m in ms}:
                    rects += [_r(r) for r in page.search_for(q)][:6]
                if rid == "risa_connection_props":
                    seg = text[ms[0].end():ms[0].end() + 4000]
                    seg = seg.split("Frame / HR")[0]
                    conn_vals = re.findall(r"\n(None|Fixed|Pinned|[A-Z][\w-]*Conn\w*)\n", seg)
                    what = what + f"; Start/End Conn values: {dict(Counter(v for v in conn_vals if v != 'Fixed'))}"
                hits.append({"doc": key, "page": i + 1, "calc": cid, "rule": rid, "what": what, "designs_connection": designs,
                             "count": len(ms), "snippet": snippet[:400], "rects": rects})
            # detail references printed on calc sketches: "17" above "S8.2.2", or "17/S8.2.2"
            for s in words:
                if not SHEET_RE.match(s[4].rstrip(".")):
                    continue
                sh = s[4].rstrip(".")
                labs = [w for w in words if LABEL_RE.match(w[4]) and abs(_c(w)[0] - _c(s)[0]) < 8 and 0 <= s[1] - w[3] < 9]
                pre = [w for w in words if (w[5], w[6]) == (s[5], s[6]) and w[7] == s[7] - 1 and re.fullmatch(r"\d{1,2}/?", w[4])]
                for lab in labs[:1] + pre[:1]:
                    ref = f"{lab[4].rstrip('/')}/{sh}"
                    ctx = [w for w in words if abs(_c(w)[1] - _c(s)[1]) < 30 and abs(_c(w)[0] - _c(s)[0]) < 160]
                    refs.append({"doc": key, "page": i + 1, "calc": cid, "ref": ref, "known_detail": detail_ids.get(ref) == "connection_type", "target_kind": detail_ids.get(ref, "not found"),
                                 "rects": [_r(lab), _r(s)], "context": " ".join(w[4] for w in sorted(ctx, key=lambda w: (round(w[1] / 4), w[0])))[:200]})
            for m in TEXT_REF.finditer(text):
                ref = f"{m.group(1)}/{m.group(2)}"
                refs.append({"doc": key, "page": i + 1, "calc": cid, "ref": ref, "known_detail": detail_ids.get(ref) == "connection_type", "target_kind": detail_ids.get(ref, "not found"), "rects": [],
                             "context": text[max(0, m.start() - 80):m.end() + 40].replace("\n", " | ")})
    return {"hits": hits, "detail_refs": refs}


# ----------------------------------------------------------------------------- build


def build(plans_path: str, sheets: list[dict], elements: list[dict], calc_docs: list[tuple[str, str]], calc_ids: dict,
          profile: "profiles.Profile | str | None" = None) -> dict:
    pf = profiles.resolve(profile, plans_path, *[p for _, p in calc_docs])
    D = pf.drawings
    SHEET_RE, TEXT_REF = D.title_block.sheet_number_regex, D.details.text_ref_regex
    is_type_sheet = lambda sh: bool(D.details.type_sheet_regex.match(sh))  # noqa: E731
    SYMBOL_NAMES = {e.kind: e.name for e in D.symbol_legend.entries}
    doc = pymupdf.open(plans_path)
    els_by_sheet: dict[str, list] = defaultdict(list)
    for e in elements:
        els_by_sheet[e["sheet"]].append(e)

    types: list[dict] = []
    views: list[dict] = []  # plans / elevations / sections / enlarged views: where a connection callout may sit
    for s in sheets:
        if s.get("kind") in D.no_tag_kinds:
            continue
        for d in read_details(doc[s["page"] - 1], s, pf):
            if is_type_sheet(s["sheet"]):
                types.append(d)
            elif D.details.other_sheet_connection_regex.search(d["title"].upper()):
                d["category"] = "enlarged-sheet detail"
                d["rule"] += "; non-S8 detail kept as a connection type because its title names a connection"
                types.append(d)
            else:
                views.append({k: d[k] for k in ("id", "sheet", "page", "title", "bbox", "number_rect", "title_rects")})
    tmap = {t["id"]: t for t in types}

    def resolve(ref):
        """'2B/S8.2.7' is sub-view B drawn inside detail 2 of S8.2.7: (type id, sub-view) or (None, None)."""
        if not ref:
            return None, None
        if ref in tmap:
            return ref, None
        m = re.fullmatch(r"(\d{1,2})([A-Z])/(S[\d.]+)", ref)
        if m and f"{m.group(1)}/{m.group(3)}" in tmap:
            return f"{m.group(1)}/{m.group(3)}", m.group(2)
        return None, None
    vmap = {v["id"]: v for v in views}

    instances, other_callouts, note_refs, detail_refs, legend_check, legends = [], [], [], [], {}, {}
    stats = Counter()
    for s in sheets:
        page = doc[s["page"] - 1]
        words = page.get_text("words")
        drawings = page.get_drawings()
        segs = _segments(drawings)
        circles = _circles(drawings)
        cutoff = s.get("cutoff") or D.title_block.x_min.at(page.rect.width)
        grid = s.get("grid") or {"cols": [], "rows": []}
        has_grid = bool(grid["cols"] and grid["rows"])
        els = els_by_sheet.get(s["sheet"], [])
        panels = [t for t in types if t["sheet"] == s["sheet"]]
        vpanels = [v for v in views if v["sheet"] == s["sheet"]]

        def host_view(p):
            return next((v["id"] for v in vpanels if v["bbox"][0] <= p[0] <= v["bbox"][2] and v["bbox"][1] <= p[1] <= v["bbox"][3]), None)

        def host_panel(p):
            return next((t["id"] for t in panels if t["bbox"][0] <= p[0] <= t["bbox"][2] and t["bbox"][1] <= p[1] <= t["bbox"][3]), None)

        def gref(p):
            return grid_ref(p[0], p[1], grid) if has_grid else {"ref": "", "node": None, "node_dist": None}

        bubbles = find_callouts(page, words, drawings, circles, segs, SHEET_RE)
        bubble_zones = [(b["center"], b["radius"]) for b in bubbles]
        for b in bubbles:
            p = b["leader"]["end"] if b["leader"] else b["center"]
            in_draw = b["center"][0] < cutoff
            rec = {"sheet": s["sheet"], "page": s["page"], "doc": "plans", "ref": b["ref"], "bbox": b["bbox"], "rects": b["rects"],
                   "leader": b["leader"], "point": [round(p[0], 1), round(p[1], 1)], "flags": b["flags"]}
            if not in_draw:
                stats["callout bubbles in notes column (skipped)"] += 1
                continue
            if is_type_sheet(s["sheet"]):
                hp = host_panel(b["center"])
                detail_refs.append(rec | {"via": "callout bubble", "from_detail": hp, "known": bool(resolve(b["ref"])[0]),
                                          "type_id": resolve(b["ref"])[0], "subview": resolve(b["ref"])[1]})
                continue
            if not resolve(b["ref"])[0]:
                other_callouts.append(rec | {"kind": "view callout (section / elevation / enlarged plan)" if b["ref"] in vmap
                                             else "callout to a view not found", "point_grid": gref(p)["ref"]})
                continue
            instances.append(rec | {"via": "callout bubble", "symbol": None, "in_view": host_view(p),
                                    "attach_from": "leader end" if b["leader"] else "bubble centre (no leader found)"})
            stats["instances: callout bubble"] += 1

        trefs = find_text_refs(words, TEXT_REF)
        legend, legend_rows = ({}, [])
        if s.get("kind") in D.symbol_legend.sheet_kinds:
            legend, legend_rows = read_legend(words, cutoff, pf)
            legends[s["sheet"]] = legend
        for t in trefs:
            p = _c(t["bbox"])
            rec = {"sheet": s["sheet"], "page": s["page"], "doc": "plans", "ref": t["ref"].rstrip("."), "bbox": t["bbox"],
                   "rects": t["rects"], "context": t["context"]}
            rec["ref"] = re.sub(r"\.$", "", rec["ref"])
            if is_type_sheet(s["sheet"]):
                detail_refs.append(rec | {"via": "text reference", "from_detail": host_panel(p),
                                          "known": bool(resolve(rec["ref"])[0]), "type_id": resolve(rec["ref"])[0],
                                          "subview": resolve(rec["ref"])[1]})
            elif p[0] >= cutoff or s.get("kind") in D.no_tag_kinds:
                note_refs.append(rec | {"legend": any(r[1] - 3 <= p[1] <= r[3] + 3 for r in legend_rows)})
            elif is_type_sheet(rec["ref"].split("/")[1]) or resolve(rec["ref"])[0]:
                instances.append(rec | {"via": "text reference", "symbol": None, "in_view": host_view(p), "point": [round(p[0], 1), round(p[1], 1)],
                                        "attach_from": "text reference position", "leader": None, "flags": []})
                stats["instances: text reference"] += 1
            else:
                other_callouts.append(rec | {"kind": "text reference to a non-S8 sheet", "point": [round(p[0], 1), round(p[1], 1)]})

        if s.get("kind") in D.symbol_legend.sheet_kinds and legend:
            # classifier self-check on the legend's own exemplars (symbol column left of the legend text)
            lx0 = min(v["rect"][0] for v in legend.values())
            ex = find_symbols(drawings, segs, (lx0 - 120, min(v["rect"][1] for v in legend.values()) - 15, lx0 - 5,
                                               max(v["rect"][3] for v in legend.values()) + 15))
            got = {}
            for kind, v in legend.items():
                row = [e for e in ex if v["rect"][1] - 14 <= (e["rect"].y0 + e["rect"].y1) / 2 <= v["rect"][3] + 8]
                got[kind] = sorted({e["kind"] for e in row})
            legend_check[s["sheet"]] = {k: {"expected": k, "classified": v, "ok": v == [k]} for k, v in got.items()}
            mg = D.drawing_area_margin_pt
            area = (mg, mg, cutoff, page.rect.height - mg)
            syms = find_symbols(drawings, segs, area)
            # a kind the built-in shape classifier does not recognise on the legend's OWN exemplar is drawn
            # differently on this set: find it by the exemplar's shape instead (template from the legend)
            failed = {k for k, v in legend_check[s["sheet"]].items() if not v["ok"]}
            if failed:
                tpl = {k: v for k, v in legend_templates(drawings, {k: legend[k] for k in failed}, lx0).items()}
                syms = [x for x in syms if x["kind"] not in tpl] + find_by_template(drawings, tpl, area)
                for k in failed:
                    legend_check[s["sheet"]][k]["template"] = tpl.get(k)
                    legend_check[s["sheet"]][k]["fallback"] = "legend exemplar shape" if k in tpl else "none (no filled exemplar)"
            for sym in syms:
                r = sym["rect"]
                p = ((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2)
                if any(math.hypot(p[0] - c[0], p[1] - c[1]) < rr + 14 for c, rr in bubble_zones):
                    stats["symbols skipped: part of a section/callout marker"] += 1
                    continue
                lg = legend.get(sym["kind"], {})
                instances.append({"sheet": s["sheet"], "page": s["page"], "doc": "plans", "in_view": host_view(p),
                                  "ref": lg.get("detail") or ("per frame elevation" if sym["kind"] == "mrf" else None),
                                  "bbox": _r(r), "rects": [_r(r)], "via": "plan symbol", "symbol": sym["kind"],
                                  "symbol_name": SYMBOL_NAMES.get(sym["kind"], sym["kind"]), "legend_text": lg.get("text"),
                                  "point": [round(p[0], 1), round(p[1], 1)], "attach_from": "symbol centre", "leader": None, "flags": []})
                stats[f"instances: plan symbol {sym['kind']}"] += 1

        # attach every instance found on this sheet
        for ins in instances:
            if ins["sheet"] != s["sheet"] or "attached" in ins:
                continue
            p = tuple(ins["point"])
            g = gref(p)
            ins["grid"], ins["grid_node"] = g["ref"], g["node"]
            max_d = 22 if ins["via"] == "plan symbol" else (30 if ins["leader"] else 60)
            lim_txt = ("14 pt of a followed beam line, 22 pt of a column position, 8 pt of a tag box" if ins["via"] == "plan symbol"
                       else f"{max_d} pt")
            ins["attached"] = attach(p, els, max_d=max_d, want=3 if ins["via"] == "plan symbol" else 2,
                                     symbol=ins["via"] == "plan symbol")
            ins["attach_rule"] = (f"nearest drawn element per category within {lim_txt} of the {ins['attach_from']} "
                                  f"(beam = its followed drawn line, column = its leader-end position, else the tag box)")
            if not ins["attached"]:
                near = attach(p, els, max_d=1e9, want=1)
                if not els:
                    ins["unattached_reason"] = "no element tag on this sheet (drawing-set element source has none here)"
                else:
                    ins["unattached_reason"] = (f"nearest element {near[0]['id']} ({near[0]['size']}) is {near[0]['dist']} pt away, "
                                                f"beyond the limit ({lim_txt})")
                    ins["nearest_beyond_limit"] = near[0]

    # instances on a sheet with no usable element nearby (wall sections say "HSS PER PLAN"): locate them through the
    # callouts that point at the view they sit in (section cut on an elevation / plan) - indirect, flagged as such.
    for ins in instances:
        if ins["attached"] or not ins.get("in_view"):
            continue
        refs_to_view = [o for o in other_callouts if o["ref"] == ins["in_view"]]
        loc = []
        for o in refs_to_view:
            near = attach(tuple(o["point"]), els_by_sheet.get(o["sheet"], []), max_d=60, want=2)
            loc.append({"sheet": o["sheet"], "page": o["page"], "callout_ref": o["ref"], "bbox": o["bbox"], "rects": o["rects"],
                        "point": o["point"], "grid": o.get("point_grid", ""), "near_elements": near})
        if loc:
            ins["located_via_view"] = loc
            ins["view_elements"] = [n for l in loc for n in l["near_elements"]]
            ins["view_rule"] = ("indirect: the instance sits in view " + ins["in_view"] + "; that view's callout(s) on other sheets give its "
                                "location, and elements within 60 pt of those callouts are listed (not a direct attachment)")

    # instance ids + link to type
    per_sheet = Counter()
    for ins in instances:
        per_sheet[ins["sheet"]] += 1
        ins["id"] = f"conn@{ins['sheet']}#{per_sheet[ins['sheet']]:03d}"
        ins["node_type"] = "connection_instance"
        ins["type_id"], ins["subview"] = resolve(ins["ref"])
        if ins["ref"] and not ins["type_id"] and ins["ref"] != "per frame elevation":
            ins["missing_type"] = True
    calc = scan_calcs(calc_docs, calc_ids, {**{v: "view" for v in vmap}, **{t: "connection_type" for t in tmap}}, pf)
    for t in types:
        t["instances"] = [i["id"] for i in instances if i["type_id"] == t["id"]]
        t["referenced_from_details"] = sorted({r["from_detail"] for r in detail_refs if r.get("type_id") == t["id"] and r.get("from_detail")})
        t["calc_refs"] = [{"doc": r["doc"], "page": r["page"], "calc": r["calc"], "rects": r["rects"], "context": r["context"]}
                          for r in calc["detail_refs"] if r["ref"] == t["id"]]
    for x in types + instances:  # deterministic detail-title / callout / symbol rules: the producer states confidence
        x.setdefault("confidence", 1.0)
    return {"types": types, "views": views, "instances": instances, "other_callouts": other_callouts, "note_refs": note_refs,
            "detail_refs": detail_refs, "legends": legends, "legend_check": legend_check, "calc": calc, "stats": dict(stats)}
