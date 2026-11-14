"""Connections as first-class nodes, read off a drawing set (no BIM model).

Two node kinds:

- connection TYPE: one per typical / connection detail drawn on an S8.x sheet
  ("16/S8.2.2 HSS BEAM-COLUMN AT SCREEN/PARAPET"), with the detail panel's bbox,
  its title words, and the bolt / weld / plate / anchor lines printed inside it.
- connection INSTANCE: one per place the drawings say that detail (or a framing-plan
  connection symbol) occurs, with sheet, bbox, grid ref and the drawn element(s) it
  joins.

Deterministic rules, each recorded on the node it produced:

- detail title bar (S8 sheets): a big detail number (h ~25 pt) with the title words
  (h ~19 pt) on the same baseline to its LEFT, right of the previous number on that
  row; the panel is the area above the bar, up to the bar above in the same column.
- callout bubble: a sheet-number word (S8.2.2) with a label word (16) centred directly
  above it, both inside a drawn circle. The bubble's leader (a line leaving the circle)
  is followed to its far end; that end is the instance's location.
- text reference: "PER 13/ S8.2.1" or "1/S5.0.3" in a text line (the number and the
  sheet may be split over two words).
- framing-plan symbols, defined by the plan's own legend ("INDICATES DRAG CONNECTION
  PER 1/ S8.2.3"): filled triangle = moment resisting frame connection, open triangle
  = moment connection at cantilevered framing, filled circle = drag connection,
  filled diamond = full height stiffener connection, double-headed arrow = kicker
  brace. The classifier is checked against the legend's own exemplars on every run.
- attachment: nearest drawn element(s) of the drawing-set element source (beam drawn
  line, column position, else tag bbox), on the same sheet, within a stated distance.
"""
from __future__ import annotations

import math
import re
from collections import Counter, defaultdict

import pymupdf

from . import sizes
from .drawing_ingest import grid_ref

SHEET_RE = re.compile(r"^S\d+(?:\.\d+){1,3}$")
LABEL_RE = re.compile(r"^(?:\d{1,2}[A-Z]?|[A-Z])$")
TEXT_REF = re.compile(r"(?<![\w/.])(\d{1,2}[A-Z]?)\s*/\s*(S\d+(?:\.\d+){1,3})(?!\d)")

DETAIL_CATEGORY = [  # (sheet prefix, category)
    ("S8.0.1", "foundation"), ("S8.0.2", "slab on grade"), ("S8.0.3", "concrete"),
    ("S8.2.3", "steel drag"), ("S8.2.4", "steel deck"), ("S8.2.5", "steel deck"),
    ("S8.2.6", "moment frame"), ("S8.2", "steel"), ("S8.4", "metal stud"),
    ("S8.6", "wood"), ("S8.8", "stair"),
]
NON_S8_CONN = re.compile(r"\bCONN(?:ECTION)?S?\b|BASE DETAIL|BASEPLATE|BASE PLATE")
CONN_WORDS = re.compile(r"\b(CONN(?:ECTION)?S?|BASEPLATE|BASE PLATE|SPLICE|DRAG|COLLECTOR|KICKER|BRACE|STIFFENER|"
                        r"ANCHOR(?:AGE)?|WELD|BOLT|SEAT|BEARING|CLIP|HANGER|TO|AT|WUF-W|EMBED|DOWEL|LEDGER)\b")
SPEC_WORDS = re.compile(r"(BOLT|A325|A490|F1554|WELD|FILLET|CJP|PJP|\bPL\s?\d|\bPL\b|PLATE|ANCHOR|ROD|STIFF|"
                        r"SHEAR TAB|CLIP|SCREW|#\d+|HSA|EMBED|DOWEL|\bL\d|ANGLE|NELSON|STUD|WASHER|NUT|DOUBLER|GUSSET|"
                        r"SIMPSON|HILTI|EPOXY|KWIK|TITEN|PAF|PIN)")

SYMBOL_KINDS = {
    "mrf": "Moment resisting frame connection",
    "moment_cantilever": "Moment connection at cantilevered framing",
    "drag": "Drag connection",
    "stiffener": "Full height stiffener connection",
    "kicker": "Kicker brace",
}
LEGEND_KEYS = [  # legend text -> symbol kind
    ("MOMENT RESISTING FRAME", "mrf"), ("MOMENT CONNECTION AT", "moment_cantilever"),
    ("DRAG CONNECTION", "drag"), ("FULL HEIGHT STIFFENER", "stiffener"), ("KICKER BRACE", "kicker"),
]


def _r(b) -> list[float]:
    return [round(b[0], 1), round(b[1], 1), round(b[2], 1), round(b[3], 1)]


def _c(b) -> tuple[float, float]:
    return ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)


def _h(w) -> float:
    return w[3] - w[1]


def _category(sheet: str) -> str:
    for pre, cat in DETAIL_CATEGORY:
        if sheet.startswith(pre):
            return cat
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


def read_details(page, sheet: dict) -> list[dict]:
    words = page.get_text("words")
    nums = [w for w in words if re.fullmatch(r"\d{1,2}[A-Z]?", w[4]) and 22 <= _h(w) <= 28 and w[0] < 2720]
    rows: dict[int, list] = defaultdict(list)
    for n in nums:
        rows[round(_c(n)[1] / 8)].append(n)
    bars = []
    for _, ns in rows.items():
        ns.sort(key=lambda w: w[0])
        for i, n in enumerate(ns):
            left = ns[i - 1][2] + 4 if i else 40.0
            cy = _c(n)[1]
            tw = [w for w in words if 15 <= _h(w) < 22 and abs(_c(w)[1] - cy) < 6.5 and left < w[0] and w[2] < n[0]]
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
            if SPEC_WORDS.search(t.upper()) and t not in seen:
                seen.add(t)
                spec.append({"text": t, "rect": _r(ln["rect"])})
        szs = sorted({sizes.norm(w[4])["norm"] for w in inside if sizes.norm(w[4])})
        out.append({
            "id": did, "node_type": "connection_type", "detail": n[4], "sheet": sheet["sheet"], "page": sheet["page"],
            "doc": "plans", "sheet_title": sheet.get("title", ""), "category": _category(sheet["sheet"]),
            "title": title, "is_connection": bool(CONN_WORDS.search(title.upper())),
            "scale": " ".join(w[4] for w in b["scale_words"]),
            "bbox": _r(panel), "number_rect": _r(n), "title_rects": [_r(w) for w in b["title_words"]],
            "spec": spec, "sizes": szs, "rule": "detail title bar: number h~25pt, title words h~19pt left of it",
        })
    out.sort(key=lambda d: (int(re.match(r"\d+", d["detail"]).group()), d["detail"]))
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


def find_callouts(page, words, drawings, circles, segs) -> list[dict]:
    out = []
    for s in words:
        if not SHEET_RE.match(s[4]) or _h(s) > 13:
            continue
        scx = _c(s)[0]
        labs = [w for w in words if LABEL_RE.match(w[4]) and abs(_c(w)[0] - scx) < 7 and 0 <= s[1] - w[3] < 9 and _h(w) <= 13]
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


def find_text_refs(words) -> list[dict]:
    out = []
    for ln in _lines(words):
        t = ln["text"]
        for m in TEXT_REF.finditer(t):
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


def read_legend(words, cutoff: float) -> tuple[dict, list]:
    """Symbol kind -> {detail ref, legend text, rects} from the plan's FRAMING PLAN SYMBOLS legend."""
    lines = [ln for ln in _lines(words) if ln["rect"][0] >= cutoff - 200]
    refs = find_text_refs([w for w in words if w[0] >= cutoff - 200])
    legend, rows = {}, []
    blocks: dict[int, list] = defaultdict(list)
    for ln in lines:
        blocks[ln["key"][0]].append(ln)
    for bno, lns in blocks.items():
        text = " ".join(ln["text"] for ln in sorted(lns, key=lambda x: x["rect"][1]))
        for key, kind in LEGEND_KEYS:
            if text.upper().startswith("INDICATES") and key in text.upper():
                rect = [min(ln["rect"][0] for ln in lns), min(ln["rect"][1] for ln in lns),
                        max(ln["rect"][2] for ln in lns), max(ln["rect"][3] for ln in lns)]
                ref = [r for r in refs if rect[1] - 3 <= _c(r["bbox"])[1] <= rect[3] + 3 and r["bbox"][0] > rect[0]]
                legend[kind] = {"kind": kind, "name": SYMBOL_KINDS[kind], "text": text.strip() +
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


CALC_RULES = [  # (rule id, regex, what it shows, designs a connection?)
    ("hand_conn_design", re.compile(r"CONN\s*DESIG|CONN\s*[12]\b|CONN[12]", re.I), "hand calc titled CONN DESIGN / CONN1 / CONN2", True),
    ("weld_check", re.compile(r"WELD", re.I), "weld check text", True),
    ("bolt", re.compile(r"\bBOLTS?\b|A325|A490", re.I), "bolt text", True),
    ("simpson_connector", re.compile(r"Simpson Strong-Tie® Connectors? @", re.I), "CFS tool Simpson connector interaction at stud supports", True),
    ("clip_shear_conn", re.compile(r"Shear Connection\s+w/ clip", re.I), "CFS web crippling support = shear connection w/ clip", False),
    ("risa_connection_props", re.compile(r"Member RISAConnection Properties", re.I), "RISA-3D member connection table (Start/End Conn)", False),
    ("seismic_conn_rule", re.compile(r"SMF-WUF-W", re.I), "RISA seismic design rule: prequalified SMF connection type WUF-W", False),
    ("anchorage_note", re.compile(r"anchorage", re.I), "anchorage note", False),
    ("stiffener_plate", re.compile(r"STIFF(?:E)?NER\s*PL|STIFF PL", re.I), "stiffener plate on a sketch", False),
]
CALC_ID = re.compile(r"^[A-E]\d{1,3}(?:_\d{1,3})?$")


def scan_calcs(calc_docs: list[tuple[str, str]], calc_ids: dict, detail_ids: dict) -> dict:
    """calc_docs: [(doc key, path)]. Returns per-page hits, detail references from calc pages,
    and a verdict per rule. calc_ids maps (doc, page) -> calc node id of the set graph."""
    hits, refs = [], []
    for key, path in calc_docs:
        doc = pymupdf.open(path)
        for i, page in enumerate(doc):
            text = page.get_text()
            words = page.get_text("words")
            cid = calc_ids.get((key, i + 1)) or next((ln for ln in text.splitlines() if CALC_ID.match(ln.strip())), f"{key}-{i + 1}")
            for rid, rx, what, designs in CALC_RULES:
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


def build(plans_path: str, sheets: list[dict], elements: list[dict], calc_docs: list[tuple[str, str]], calc_ids: dict) -> dict:
    doc = pymupdf.open(plans_path)
    els_by_sheet: dict[str, list] = defaultdict(list)
    for e in elements:
        els_by_sheet[e["sheet"]].append(e)

    types: list[dict] = []
    views: list[dict] = []  # plans / elevations / sections / enlarged views: where a connection callout may sit
    for s in sheets:
        if s.get("kind") == "notes":
            continue
        for d in read_details(doc[s["page"] - 1], s):
            if s["sheet"].startswith("S8"):
                types.append(d)
            elif NON_S8_CONN.search(d["title"].upper()):
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
        cutoff = s.get("cutoff") or 2690
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

        bubbles = find_callouts(page, words, drawings, circles, segs)
        bubble_zones = [(b["center"], b["radius"]) for b in bubbles]
        for b in bubbles:
            p = b["leader"]["end"] if b["leader"] else b["center"]
            in_draw = b["center"][0] < cutoff
            rec = {"sheet": s["sheet"], "page": s["page"], "doc": "plans", "ref": b["ref"], "bbox": b["bbox"], "rects": b["rects"],
                   "leader": b["leader"], "point": [round(p[0], 1), round(p[1], 1)], "flags": b["flags"]}
            if not in_draw:
                stats["callout bubbles in notes column (skipped)"] += 1
                continue
            if s["sheet"].startswith("S8"):
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

        trefs = find_text_refs(words)
        legend, legend_rows = ({}, [])
        if s.get("kind") == "framing":
            legend, legend_rows = read_legend(words, cutoff)
            legends[s["sheet"]] = legend
        for t in trefs:
            p = _c(t["bbox"])
            rec = {"sheet": s["sheet"], "page": s["page"], "doc": "plans", "ref": t["ref"].rstrip("."), "bbox": t["bbox"],
                   "rects": t["rects"], "context": t["context"]}
            rec["ref"] = re.sub(r"\.$", "", rec["ref"])
            if s["sheet"].startswith("S8"):
                detail_refs.append(rec | {"via": "text reference", "from_detail": host_panel(p),
                                          "known": bool(resolve(rec["ref"])[0]), "type_id": resolve(rec["ref"])[0],
                                          "subview": resolve(rec["ref"])[1]})
            elif p[0] >= cutoff or s.get("kind") == "notes":
                note_refs.append(rec | {"legend": any(r[1] - 3 <= p[1] <= r[3] + 3 for r in legend_rows)})
            elif rec["ref"].split("/")[1].startswith("S8") or resolve(rec["ref"])[0]:
                instances.append(rec | {"via": "text reference", "symbol": None, "in_view": host_view(p), "point": [round(p[0], 1), round(p[1], 1)],
                                        "attach_from": "text reference position", "leader": None, "flags": []})
                stats["instances: text reference"] += 1
            else:
                other_callouts.append(rec | {"kind": "text reference to a non-S8 sheet", "point": [round(p[0], 1), round(p[1], 1)]})

        if s.get("kind") == "framing" and legend:
            # classifier self-check on the legend's own exemplars (symbol column left of the legend text)
            lx0 = min(v["rect"][0] for v in legend.values())
            ex = find_symbols(drawings, segs, (lx0 - 120, min(v["rect"][1] for v in legend.values()) - 15, lx0 - 5,
                                               max(v["rect"][3] for v in legend.values()) + 15))
            got = {}
            for kind, v in legend.items():
                row = [e for e in ex if v["rect"][1] - 14 <= (e["rect"].y0 + e["rect"].y1) / 2 <= v["rect"][3] + 8]
                got[kind] = sorted({e["kind"] for e in row})
            legend_check[s["sheet"]] = {k: {"expected": k, "classified": v, "ok": v == [k]} for k, v in got.items()}
            syms = find_symbols(drawings, segs, (40, 40, cutoff, 2120))
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
                                  "symbol_name": SYMBOL_KINDS[sym["kind"]], "legend_text": lg.get("text"),
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
    calc = scan_calcs(calc_docs, calc_ids, {**{v: "view" for v in vmap}, **{t: "connection_type" for t in tmap}})
    for t in types:
        t["instances"] = [i["id"] for i in instances if i["type_id"] == t["id"]]
        t["referenced_from_details"] = sorted({r["from_detail"] for r in detail_refs if r.get("type_id") == t["id"] and r.get("from_detail")})
        t["calc_refs"] = [{"doc": r["doc"], "page": r["page"], "calc": r["calc"], "rects": r["rects"], "context": r["context"]}
                          for r in calc["detail_refs"] if r["ref"] == t["id"]]
    return {"types": types, "views": views, "instances": instances, "other_callouts": other_callouts, "note_refs": note_refs,
            "detail_refs": detail_refs, "legends": legends, "legend_check": legend_check, "calc": calc, "stats": dict(stats)}
