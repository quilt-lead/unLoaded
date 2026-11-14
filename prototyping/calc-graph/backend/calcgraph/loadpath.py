"""Infer load-path edges (src carries load to dst) from element geometry.

Deterministic contact rules on world-space boxes and member axes:

- slab-on-beam: a Slab whose underside sits on a Beam's top (within TOL) with plan overlap
- connection: a Connection (plate) touching two or more members joins the SUPPORTED
  member to the SUPPORTING one: footing < column < beam by rank; between two beams the
  one whose end is at the plate is supported and the one running through is supporting.
  Edge: supported -> plate -> supporting.
- direct bearing: a Beam end touching a Column or Wall with no plate between them -> beam -> column;
  a Column bottom touching a Footing directly -> column -> footing
- brace: a Brace's LOWER end touching a Column (else Footing) -> brace -> that element

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

    def add(s, d, rule, gap):
        if s == d:
            return
        edges.setdefault((s, d), {"src": s, "dst": d, "kind": "load_path", "rule": rule, "gap_m": round(gap, 4)})

    beams = by_cat.get("Beam", [])
    cols = by_cat.get("Column", []) + by_cat.get("Wall", [])
    ftgs = by_cat.get("Footing", []) + by_cat.get("Pile", [])
    members = beams + cols + ftgs

    # slab on beams
    for s in by_cat.get("Slab", []):
        smn, smx = boxes[s["global_id"]]
        for b in beams:
            bmn, bmx = boxes[b["global_id"]]
            if abs(smn[2] - bmx[2]) <= TOL and (min(smx[0], bmx[0]) - max(smn[0], bmn[0]) > TOL) \
                    and (min(smx[1], bmx[1]) - max(smn[1], bmn[1]) > -TOL):
                add(s["global_id"], b["global_id"], "slab bears on beam top", abs(smn[2] - bmx[2]))

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

        # supporting = lowest rank; among equal-rank beams, the one NOT ending at the plate
        touch.sort(key=lambda m: (RANK.get(m["cat"], 5), -end_dist(m)))
        sup = touch[0]
        rest = [m for m in touch[1:] if not (m["cat"] == sup["cat"] == "Beam" and end_dist(m) > 0.6)]
        if not rest:
            continue
        # supported = highest rank, member ending at the plate
        rest.sort(key=lambda m: (-RANK.get(m["cat"], 5), end_dist(m)))
        sp = rest[0]
        add(sp["global_id"], p["global_id"], f"{sp['cat'].lower()} framed to connection", _box_gap(pb, boxes[sp["global_id"]]))
        add(p["global_id"], sup["global_id"], f"connection bears on {sup['cat'].lower()}", _box_gap(pb, boxes[sup["global_id"]]))
        plated.add((sp["global_id"], sup["global_id"]))

    # direct beam end -> column
    for b in beams:
        for end in _ends(b):
            for c in cols:
                gap = _pt_gap(end, boxes[c["global_id"]])
                if gap <= TOL and (b["global_id"], c["global_id"]) not in plated:
                    add(b["global_id"], c["global_id"], f"beam end bears on {c['cat'].lower()} (no connection element)", gap)

    # column bottom -> footing directly (only when no base plate between them)
    has_down = {s for (s, _d) in edges}
    for c in by_cat.get("Column", []):
        if c["global_id"] in has_down:
            continue
        a, b2 = _ends(c)
        bottom = a if a[2] < b2[2] else b2
        for f in ftgs:
            gap = _pt_gap(bottom, boxes[f["global_id"]])
            if gap <= 0.1:
                add(c["global_id"], f["global_id"], "column bears on footing", gap)

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
    return sorted(edges.values(), key=lambda e: (e["src"], e["dst"]))
