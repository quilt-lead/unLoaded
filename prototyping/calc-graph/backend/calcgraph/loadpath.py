"""Infer load-path edges (src carries load to dst) from element geometry.

Deterministic contact rules on world-space boxes and member axes:

- slab-on-beam: a Slab whose underside sits on a Beam's top (within TOL) with plan overlap
- connection: a Connection (plate) touching two or more members is a node BETWEEN them: it
  joins the SUPPORTED member to the SUPPORTING one: footing < column < beam < brace by rank;
  between two beams the one whose end is at the plate is supported and the one running
  through is supporting; between two columns (column on pier) the upper one is supported;
  among candidates the member whose axis the plate sits on wins. Edges: supported ->
  supporting (kind frames-into, or bears-on for column -> pier / footing) carrying
  via = the plate, plus supported -> plate and plate -> supporting (kind connected-by).
- direct bearing: a Beam end touching a Column or Wall with no plate between them -> beam -> column;
  a Beam end inside a Footing (grade beam) -> beam -> footing; a Column bottom on a Footing
  or on the top of another Column (pier) with no plate -> bears-on
- brace: a Brace's LOWER end touching a Column (else Footing) -> brace -> that element; its
  UPPER end touching a Beam (chevron work point) -> brace -> beam

Edge kinds: frames-into / bears-on are the load path proper; connected-by edges record the
connection node on that path (scorers that model plates as path nodes read those).

Every edge carries the rule and the gap measured, so a reviewer can see why it exists.
"""
from __future__ import annotations

import numpy as np

TOL = 0.025  # m; contact tolerance
RANK = {"Footing": 0, "Pile": 0, "Column": 1, "Wall": 1, "Beam": 2, "Brace": 3}


def _box(e):
    g = e["geom"]
    return np.array(g["min"]), np.array(g["max"])


def _box_gap(a, b) -> float:
    (amn, amx), (bmn, bmx) = a, b
    d = np.maximum(0, np.maximum(amn - bmx, bmn - amx))
    return float(np.linalg.norm(d))


def _pt_gap(p, b) -> float:
    mn, mx = b
    d = np.maximum(0, np.maximum(mn - p, p - mx))
    return float(np.linalg.norm(d))


def _ends(e):
    g = e["geom"]
    return np.array(g["p1"]), np.array(g["p2"])


def infer(elements: list[dict]) -> list[dict]:
    els = [e for e in elements if e.get("geom")]
    boxes = {e["global_id"]: _box(e) for e in els}
    by_cat: dict[str, list[dict]] = {}
    for e in els:
        by_cat.setdefault(e["cat"], []).append(e)
    edges: dict[tuple[str, str], dict] = {}

    def add(s, d, rule, gap, kind="frames-into", via=None):
        if s == d:
            return
        e = {"src": s, "dst": d, "kind": kind, "rule": rule, "gap_m": round(gap, 4)}
        if via:
            e["via"] = via
        edges.setdefault((s, d), e)

    beams = by_cat.get("Beam", [])
    cols = by_cat.get("Column", []) + by_cat.get("Wall", [])
    ftgs = by_cat.get("Footing", []) + by_cat.get("Pile", [])
    members = beams + cols + ftgs + by_cat.get("Brace", [])

    # slab on beams
    for s in by_cat.get("Slab", []):
        smn, smx = boxes[s["global_id"]]
        for b in beams:
            bmn, bmx = boxes[b["global_id"]]
            if abs(smn[2] - bmx[2]) <= TOL and (min(smx[0], bmx[0]) - max(smn[0], bmn[0]) > TOL) \
                    and (min(smx[1], bmx[1]) - max(smn[1], bmn[1]) > -TOL):
                add(s["global_id"], b["global_id"], "slab bears on beam top", abs(smn[2] - bmx[2]), "bears-on")

    # connections
    plated: set[tuple[str, str]] = set()
    for p in by_cat.get("Connection", []):
        pb = boxes[p["global_id"]]
        pc = (pb[0] + pb[1]) / 2
        touch = [m for m in members if _box_gap(pb, boxes[m["global_id"]]) <= TOL]
        if len(touch) < 2:
            continue

        def end_dist(m):
            a, b = _ends(m)
            return min(np.linalg.norm(a - pc), np.linalg.norm(b - pc))

        def axis_dist(m):
            a, b = _ends(m)
            d = b - a
            n = np.linalg.norm(d)
            if n < 1e-9:
                return float(np.linalg.norm(pc - a))
            t = np.clip(np.dot(pc - a, d) / n**2, 0.0, 1.0)
            return float(np.linalg.norm(pc - (a + t * d)))

        def zmin(m):
            return boxes[m["global_id"]][0][2]

        # supporting = lowest rank; among beams the one NOT ending at the plate; among columns the lower
        touch.sort(key=lambda m: (RANK.get(m["cat"], 5), -end_dist(m) if m["cat"] == "Beam" else zmin(m)))
        sup = touch[0]
        rest = [m for m in touch[1:] if not (m["cat"] == sup["cat"] == "Beam" and end_dist(m) > 0.6)]
        if sup["cat"] == "Column":
            rest = [m for m in rest if not (m["cat"] == "Column" and zmin(m) <= zmin(sup) + TOL)]
        if not rest:
            continue
        # supported = the member whose axis the plate sits on, then highest rank, then ending at the plate
        # (a plate sits ON its supported member's axis; a brace or beam merely passing by is not it)
        rest.sort(key=lambda m: (round(axis_dist(m), 1), -RANK.get(m["cat"], 5), end_dist(m)))
        sp = rest[0]
        pid = p["global_id"]
        kind = "bears-on" if sp["cat"] == "Column" else "frames-into"
        add(sp["global_id"], sup["global_id"], f"{sp['cat'].lower()} -> {sup['cat'].lower()} via connection", 0.0, kind, via=pid)
        add(sp["global_id"], pid, f"{sp['cat'].lower()} framed to connection", _box_gap(pb, boxes[sp["global_id"]]), "connected-by")
        add(pid, sup["global_id"], f"connection bears on {sup['cat'].lower()}", _box_gap(pb, boxes[sup["global_id"]]), "connected-by")
        plated.add((sp["global_id"], sup["global_id"]))

    # direct beam end -> column
    for b in beams:
        for end in _ends(b):
            for c in cols:
                gap = _pt_gap(end, boxes[c["global_id"]])
                if gap <= TOL and (b["global_id"], c["global_id"]) not in plated:
                    add(b["global_id"], c["global_id"], f"beam end bears on {c['cat'].lower()} (no connection element)", gap)
            for f in ftgs:
                gap = _pt_gap(end, boxes[f["global_id"]])
                if gap <= TOL and (b["global_id"], f["global_id"]) not in plated:
                    add(b["global_id"], f["global_id"], "grade beam end bears on footing", gap)

    # column bottom -> footing (or -> the column / pier below) directly, only when nothing
    # (a base plate) already carries it down
    has_down = {s for (s, _d) in edges}
    for c in by_cat.get("Column", []):
        if c["global_id"] in has_down:
            continue
        # a column (or pier) is vertical by definition: its bottom is the centre of its box's
        # underside (a squat pier's PCA axis can come out horizontal)
        cmn, cmx = boxes[c["global_id"]]
        bottom = np.array([(cmn[0] + cmx[0]) / 2, (cmn[1] + cmx[1]) / 2, cmn[2]])
        done = False
        for f in ftgs:
            gap = _pt_gap(bottom, boxes[f["global_id"]])
            if gap <= 0.1:
                add(c["global_id"], f["global_id"], "column bears on footing", gap, "bears-on")
                done = True
        if done:
            continue
        for o in by_cat.get("Column", []):
            if o is c:
                continue
            omn, omx = boxes[o["global_id"]]
            if abs(omx[2] - cmn[2]) <= TOL and _pt_gap(bottom, (omn, omx)) <= TOL:
                add(c["global_id"], o["global_id"], "column bears on the column / pier below", abs(omx[2] - cmn[2]), "bears-on")

    # braces: lower end
    for br in by_cat.get("Brace", []):
        a, b2 = _ends(br)
        low = a if a[2] < b2[2] else b2
        best = None
        for m in cols + ftgs:
            gap = _pt_gap(low, boxes[m["global_id"]])
            if gap <= TOL and (best is None or RANK.get(m["cat"], 5) > RANK.get(best[0]["cat"], 5)):
                best = (m, gap)
        if best:
            add(br["global_id"], best[0]["global_id"], f"brace lower end on {best[0]['cat'].lower()}", best[1])
        high = b2 if a[2] < b2[2] else a
        for bm in beams:
            gap = _pt_gap(high, boxes[bm["global_id"]])
            if gap <= TOL:
                add(br["global_id"], bm["global_id"], "brace upper end at beam (work point)", gap)
    return sorted(edges.values(), key=lambda e: (e["src"], e["dst"]))
