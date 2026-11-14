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

- authored connectivity (rule ``ifc_rel_connects``): an IfcRelConnectsElements / ...PathElements /
  ...WithRealizingElements between two of the elements above (``connections`` from
  ifc_ingest.read_ifc). The IFC relation is undirected; direction comes from the same gravity
  ordering the contact rules use (see _gravity_order). A pair the contact rules already joined, in
  either direction, keeps the geometry edge and its direction and lists both rules in ``rules``;
  only a pair no contact rule found becomes a new edge.

Edge kinds: frames-into / bears-on are the load path proper; connected-by edges record the
connection node on that path (scorers that model plates as path nodes read those).

Every edge carries the rule and the gap measured, so a reviewer can see why it exists.
"""
from __future__ import annotations

import numpy as np

TOL = 0.025  # m; contact tolerance
RANK = {"Footing": 0, "Pile": 0, "Column": 1, "Wall": 1, "Beam": 2, "Brace": 3}
REL_RULE = "ifc_rel_connects"
# gravity order for an authored relation: lower = supporting. Slabs sit on beams (slab bears on beam
# top), so they rank above every member.
GRAVITY = RANK | {"Slab": 4}


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


def _gravity_order(a: dict, b: dict, boxes: dict) -> tuple[dict, dict]:
    """(supported, supporting) for two elements an IFC relation joins, by the contact rules' ordering:
    the higher GRAVITY rank carries its load to the lower (brace > beam > column/wall > footing; slab
    on top). Same rank: two beams - the one with an end nearer the other is supported (it frames into
    the one running through); anything else - the higher one is supported (column on the pier below)."""
    ra, rb = GRAVITY.get(a["cat"], 5), GRAVITY.get(b["cat"], 5)
    if ra != rb:
        return (a, b) if ra > rb else (b, a)
    if a["cat"] == "Beam":
        ga = min(_pt_gap(p, boxes[b["global_id"]]) for p in _ends(a))
        gb = min(_pt_gap(p, boxes[a["global_id"]]) for p in _ends(b))
        if ga != gb:
            return (a, b) if ga < gb else (b, a)
    za, zb = boxes[a["global_id"]][0][2], boxes[b["global_id"]][0][2]
    if za != zb:
        return (a, b) if za > zb else (b, a)
    return (a, b) if a["global_id"] < b["global_id"] else (b, a)


def _plate_order(p: dict, m: dict, boxes: dict) -> tuple[dict, dict]:
    """(src, dst) for an authored relation between a Connection (plate) and another element, as the
    contact rules orient a plate: supported member -> plate -> supporting member. Beams, braces and
    slabs are supported by their plates; footings / piles support theirs; for a column or wall, a
    plate above its mid-height is a cap / shear tab it supports (plate -> column), one below is its
    base plate (column -> plate)."""
    if m["cat"] in ("Beam", "Brace", "Slab"):
        return m, p
    if m["cat"] in ("Footing", "Pile"):
        return p, m
    pmn, pmx = boxes[p["global_id"]]
    mmn, mmx = boxes[m["global_id"]]
    return (p, m) if (pmn[2] + pmx[2]) / 2 >= (mmn[2] + mmx[2]) / 2 else (m, p)


def _authored(connections: list[dict], by_id: dict, boxes: dict, edges: dict) -> None:
    """Edges for the IFC file's own connectivity relations (rule REL_RULE), deduped against the
    geometry edges already in `edges` (keyed (src, dst))."""
    pair = {}
    for (s, d), e in edges.items():
        pair.setdefault(frozenset((s, d)), e)  # geometry edges by unordered pair
    for c in connections:
        a, b = by_id.get(c["a"]), by_id.get(c["b"])
        if a is None or b is None or a is b:
            continue  # not an element the contact rules consider (no geometry, or a category they skip)
        if a["cat"] == b["cat"] == "Connection":
            continue  # plate to plate is not a step of the load path
        g = pair.get(frozenset((a["global_id"], b["global_id"])))
        if g is not None:  # found both ways: geometry's direction and rule stay; record both rules
            g.setdefault("rules", [g["rule"]])
            if REL_RULE not in g["rules"]:
                g["rules"].append(REL_RULE)
            g.setdefault("ifc_rels", [])
            if c["rel"] not in g["ifc_rels"]:
                g["ifc_rels"].append(c["rel"])
            continue
        if "Connection" in (a["cat"], b["cat"]):
            p, m = (a, b) if a["cat"] == "Connection" else (b, a)
            src, dst = _plate_order(p, m, boxes)
            kind = "connected-by"
        else:
            src, dst = _gravity_order(a, b, boxes)
            kind = "bears-on" if src["cat"] in ("Column", "Wall", "Slab") else "frames-into"
        e = {"src": src["global_id"], "dst": dst["global_id"], "kind": kind, "rule": REL_RULE,
             "gap_m": round(_box_gap(boxes[src["global_id"]], boxes[dst["global_id"]]), 4),
             "rules": [REL_RULE], "ifc_rels": [c["rel"]]}
        edges[(e["src"], e["dst"])] = e
        pair[frozenset((e["src"], e["dst"]))] = e


def infer(elements: list[dict], connections: list[dict] | None = None) -> list[dict]:
    """Load-path edges from geometry contact, plus (when given) the IFC file's authored connectivity
    relations between the same elements - see the module docstring."""
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

    if connections:
        considered = {e["global_id"]: e for e in els if e["cat"] in GRAVITY or e["cat"] == "Connection"}
        _authored(connections, considered, boxes, edges)
    return sorted(edges.values(), key=lambda e: (e["src"], e["dst"]))
