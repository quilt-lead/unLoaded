"""Synthetic building v2: a 3-storey steel office, as a LAYOUT -> TOPOLOGY function.

The layout is the engineer's input (grid, column positions, removed columns, load areas);
the topology (which member frames into what, spans, tributary strips, frame lines,
grade beam segments) is derived from it. A column move is therefore just a different
layout: the design re-runs on the derived topology. Units: ft, kip, psf.

Framing scheme (typical composite-deck office):
- grid 1..5 (x, 4 bays of 30 ft) x A..D (y, bays 30 / 25 / 30 ft); corridor bay B-C
- girders along Y on every number line, column to column
- infill beams along X at third points of each bay (deck span 8'-4" to 10'-0"), framing
  into the girders; grid beams along X on every letter line, column to column
- 2 special moment frame (SMF) lines along X: lines A and D, bays 2-3 and 3-4 (RBS)
- 1 special concentrically braced frame (SCBF) line along Y: line 3, bays A-B and C-D
  (chevron); girder 3 B-C is the collector between them
- collectors: grid beams A 1-2 / 4-5, D 1-2 / 4-5 (drag into the SMF), girder 3 B-C
- spread footing + pier under every column; grade beams on lines A, D, 1, 5 (perimeter
  wall, SMF base moments) and line 3 (ties the braced-frame footings)

Move semantics (recorded in the notes file): a moved column keeps its grid identity and
its members; members re-frame to its new position (skew), infill beams keep their y and
re-span to the girder line. A removed column's two girders merge into one girder spanning
both bays, and the grid beams that framed into the column frame into that girder instead.
"""
from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field

GX = [("1", 0.0), ("2", 30.0), ("3", 60.0), ("4", 90.0), ("5", 120.0)]
GY = [("A", 0.0), ("B", 30.0), ("C", 55.0), ("D", 85.0)]
LEVELS = [("L2", "Level 2", 14.0), ("L3", "Level 3", 27.0), ("RF", "Roof", 40.0)]
STOREY_H = {"L2": 14.0, "L3": 13.0, "RF": 13.0}
FTG_TOP = -3.0          # top of footing (ft); pier from -3.0 to -0.5, base plate at 0.0 (slab on grade)
PIER_TOP = -0.5

MF_LINES = {"A": ("2", "3", "4"), "D": ("2", "3", "4")}     # SMF along X: columns on these number lines
BF_LINE = ("3", [("A", "B"), ("C", "D")])                    # SCBF along Y on line 3, braced bays
COLLECTORS_X = {"A": [("1", "2"), ("4", "5")], "D": [("1", "2"), ("4", "5")]}
COLLECTORS_Y = {"3": [("B", "C")]}
GRADE_BEAM_LINES = {"x": ["A", "D"], "y": ["1", "5", "3"]}   # x: along X on letter line; y: along Y on number line

WALL_PSF = 15.0
PARAPET_FT = 3.0
DECK_T_IN = {"L2": 6.25, "L3": 6.25, "RF": 1.5}   # total deck + topping depth (in), floors / roof


def column_depth_axis(roles) -> str:
    """Plan axis ("x" | "y") a column's web / depth runs along, i.e. the direction its STRONG
    axis resists bending in. The one orientation rule the calcs (gravity.column_demands
    eccentricities, SMF / SCBF checks), the IFC, the drawings and the ETABS export all read.

    Every column has its depth along X:
    - SMF columns (lines A and D, frames along X): strong axis in the moment frame - the AISC 358
      prequalified RBS connection is a beam-flange-to-column-flange connection (Issy, 2026-11-14,
      for 3A / 3D, which are also in the line-3 braced frame).
    - SCBF columns (line 3, frame along Y): the line-3 braces and collector girders gusset to the
      column web, as at 3A / 3D; braced-frame columns are axial members (pinned beams, braces).
    - gravity columns: girders (along Y) frame into the web (e = 3 in), beams along X into the
      flanges (e = d/2 + 3 in), the eccentricities the column calc has always used."""
    return "x"


def wall_trib_h(level: str) -> float:
    """Height of perimeter wall carried at `level` (ft): half the storey below + half the storey
    above, or the parapet at the roof. The one definition gravity line loads, the seismic weight
    and the ETABS export all use."""
    order = [l for l, _, _ in LEVELS]
    i = order.index(level)
    return STOREY_H[level] / 2 + (STOREY_H[order[i + 1]] / 2 if i + 1 < len(order) else PARAPET_FT)


def wall_klf(level: str) -> float:
    """Perimeter wall line load (kip/ft of wall) at `level`."""
    return WALL_PSF * wall_trib_h(level) / 1000


@dataclass
class Area:
    name: str
    kind: str            # office | corridor | roof | mech
    level: str           # L2 | L3 | RF
    x0: float
    y0: float
    x1: float
    y1: float
    d_psf: float         # superimposed + slab/deck dead (steel self-weight is added per member)
    l_psf: float = 0.0   # floor live (incl. 15 psf partitions where LL <= 80)
    lr_psf: float = 0.0  # roof live
    seis_extra_psf: float = 0.0  # partition allowance for seismic weight (ASCE 7 12.7.2)

    def contains(self, x: float, y: float) -> bool:
        return self.x0 - 1e-6 <= x <= self.x1 + 1e-6 and self.y0 - 1e-6 <= y <= self.y1 + 1e-6


def default_areas() -> list[Area]:
    a = []
    for lv in ("L2", "L3"):
        a.append(Area(f"Office {lv}", "office", lv, 0, 0, 120, 30, 61.0, 65.0, seis_extra_psf=10.0))
        a.append(Area(f"Corridor {lv}", "corridor", lv, 0, 30, 120, 55, 61.0, 80.0, seis_extra_psf=10.0))
        a.append(Area(f"Office {lv} north", "office", lv, 0, 55, 120, 85, 61.0, 65.0, seis_extra_psf=10.0))
    a.append(Area("Mech (RTU zone)", "mech", "RF", 60, 0, 90, 30, 90.0, 0.0, 20.0))
    a.append(Area("Roof", "roof", "RF", 0, 0, 120, 85, 25.0, 0.0, 20.0))  # last = fallback
    return a


def area_record_id(ar: Area) -> str:
    """Calc record id (calc A2) of a load area."""
    return f"A2-{ar.name.replace(' ', '_').replace('(', '').replace(')', '')}"


def area_at(areas: list[Area], level: str, x: float, y: float) -> Area | None:
    for ar in areas:
        if ar.level == level and ar.contains(x, y):
            return ar
    return None


@dataclass
class Layout:
    cols: dict[str, tuple[float, float]]          # "2B" -> (x, y)
    removed: set[str] = field(default_factory=set)
    areas: list[Area] = field(default_factory=default_areas)
    label: str = "Base design"

    def copy(self) -> "Layout":
        return copy.deepcopy(self)


def base_layout() -> Layout:
    return Layout({f"{xl}{yl}": (x, y) for xl, x in GX for yl, y in GY})


def gx(label: str) -> float:
    return dict(GX)[label]


def gy(label: str) -> float:
    return dict(GY)[label]


def infill_ys() -> list[tuple[str, float, float]]:
    """(bay 'AB', y, spacing) for infill beams at third points of each Y bay."""
    out = []
    for (la, ya), (lb, yb) in zip(GY, GY[1:]):
        s = (yb - ya) / 3
        for k in (1, 2):
            out.append((la + lb, ya + k * s, s))
    return out


# --------------------------------------------------------------------------- topology
@dataclass
class Member:
    id: str
    kind: str              # girder | beam (grid beam) | infill
    level: str
    line: str              # gridline it sits on ('2' for a girder, 'B' for a grid beam, '' for infill)
    i: dict                # support: {"col": "2B"} | {"member": id, "a": dist along it}
    j: dict
    p1: tuple[float, float]
    p2: tuple[float, float]
    trib: list[tuple[float, float, float]]   # strips (width ft, sample x, sample y) for area loads
    wall: bool = False      # perimeter wall line load
    roles: list[str] = field(default_factory=list)   # gravity | smf_beam | sbf_beam | collector
    frame: str = ""

    @property
    def span(self) -> float:
        return math.dist(self.p1, self.p2)


@dataclass
class Topology:
    layout: Layout
    members: dict[str, Member]
    columns: dict[str, dict]             # "2B" -> {x, y, roles, frame}
    braces: dict[str, dict]
    grade_beams: dict[str, dict]


def _col_role(c: str) -> tuple[list[str], list[str]]:
    xl, yl = c[:-1], c[-1]
    roles, frames = [], []
    if yl in MF_LINES and xl in MF_LINES[yl]:
        roles.append("smf_column")
        frames.append(f"SMF-{yl}")
    if xl == BF_LINE[0] and any(yl in bay for bay in BF_LINE[1]):
        roles.append("scbf_column")
        frames.append(f"SCBF-{xl}")
    return roles or ["gravity"], frames


def build(layout: Layout) -> Topology:
    cols = {c: p for c, p in layout.cols.items() if c not in layout.removed}
    columns = {}
    for c, (x, y) in cols.items():
        roles, frames = _col_role(c)
        columns[c] = {"x": x, "y": y, "roles": roles, "frames": frames, "grid": f"{c[:-1]}/{c[-1]}"}
    members: dict[str, Member] = {}
    xlabels = [l for l, _ in GX]
    ylabels = [l for l, _ in GY]
    for lv, _, _ in LEVELS:
        # girders along each number line: consecutive present columns
        girders_on: dict[str, list[Member]] = {}
        for xl in xlabels:
            present = [yl for yl in ylabels if f"{xl}{yl}" in cols]
            gl = []
            for ya, yb in zip(present, present[1:]):
                ca, cb = f"{xl}{ya}", f"{xl}{yb}"
                mid = f"G-{lv}-{xl}-{ya}{yb}"
                m = Member(mid, "girder", lv, xl, {"col": ca}, {"col": cb}, cols[ca], cols[cb], [],
                           wall=xl in ("1", "5"), roles=["gravity"])
                if xl == BF_LINE[0] and (ya, yb) in BF_LINE[1]:
                    m.roles = ["scbf_beam"]
                    m.frame = f"SCBF-{xl}"
                if xl in COLLECTORS_Y and (ya, yb) in COLLECTORS_Y[xl]:
                    m.roles = ["gravity", "collector"]
                    m.frame = f"SCBF-{xl}"
                members[mid] = m
                gl.append(m)
            girders_on[xl] = gl

        def girder_at(xl: str, y: float) -> tuple[Member, float] | None:
            for g in girders_on.get(xl, []):
                y0, y1 = g.p1[1], g.p2[1]
                if y0 - 1e-6 <= y <= y1 + 1e-6:
                    t = (y - y0) / (y1 - y0)
                    x = g.p1[0] + t * (g.p2[0] - g.p1[0])
                    return g, math.dist(g.p1, (x, y))
            return None

        def point_on(g: Member, a: float) -> tuple[float, float]:
            t = a / g.span
            return (g.p1[0] + t * (g.p2[0] - g.p1[0]), g.p1[1] + t * (g.p2[1] - g.p1[1]))

        # infill beams in each bay between number lines
        iys = infill_ys()
        for xa, xb in zip(xlabels, xlabels[1:]):
            for n, (bay, y, s) in enumerate(iys):
                ga, gb = girder_at(xa, y), girder_at(xb, y)
                if not ga or not gb:
                    continue
                mid = f"B-{lv}-{xa}{xb}-{bay}{1 + n % 2}"
                pa, pb = point_on(*ga), point_on(*gb)
                members[mid] = Member(mid, "infill", lv, "", {"member": ga[0].id, "a": ga[1]},
                                      {"member": gb[0].id, "a": gb[1]}, pa, pb,
                                      [(s / 2, 0, y - s / 4), (s / 2, 0, y + s / 4)], roles=["gravity"])
        # grid beams along each letter line between consecutive number lines
        for yl in ylabels:
            y_line = gy(yl)
            for xa, xb in zip(xlabels, xlabels[1:]):
                sups, pts = [], []
                for xl in (xa, xb):
                    c = f"{xl}{yl}"
                    if c in cols:
                        sups.append({"col": c})
                        pts.append(cols[c])
                    else:
                        g = girder_at(xl, y_line)
                        if not g:
                            break
                        sups.append({"member": g[0].id, "a": g[1]})
                        pts.append(point_on(*g))
                if len(sups) < 2:
                    continue
                # tributary strips: half the distance to the neighbouring infill on each side
                strips = []
                below = [y for _, y, _ in iys if y < y_line - 1e-6]
                above = [y for _, y, _ in iys if y > y_line + 1e-6]
                if below:
                    w = (y_line - max(below)) / 2
                    strips.append((w, 0, y_line - w / 2))
                if above:
                    w = (min(above) - y_line) / 2
                    strips.append((w, 0, y_line + w / 2))
                mid = f"B-{lv}-{yl}-{xa}{xb}"
                m = Member(mid, "beam", lv, yl, sups[0], sups[1], pts[0], pts[1], strips,
                           wall=yl in ("A", "D"), roles=["gravity"])
                if yl in MF_LINES and xa in MF_LINES[yl] and xb in MF_LINES[yl] \
                        and f"{xa}{yl}" in cols and f"{xb}{yl}" in cols:
                    m.roles = ["smf_beam"]
                    m.frame = f"SMF-{yl}"
                if yl in COLLECTORS_X and (xa, xb) in COLLECTORS_X[yl]:
                    m.roles = ["gravity", "collector"]
                    m.frame = f"SMF-{yl}"
                members[mid] = m
        # sample x of strips = member midpoint x (areas are bay-aligned)
    for m in members.values():
        xm = (m.p1[0] + m.p2[0]) / 2
        if m.kind == "infill":
            m.trib = [(w, xm, y) for w, _, y in m.trib]
        elif m.kind == "beam":
            m.trib = [(w, xm, y) for w, _, y in m.trib]

    # braces: chevron in each braced bay, every storey, from the column bases to beam mid-span above
    braces = {}
    xl = BF_LINE[0]
    zs = [0.0] + [z for _, _, z in LEVELS]
    lvs = ["L1"] + [l for l, _, _ in LEVELS]
    for ya, yb in BF_LINE[1]:
        ca, cb = f"{xl}{ya}", f"{xl}{yb}"
        if ca not in cols or cb not in cols:
            continue
        for s in range(3):
            for side, c in (("S", ca), ("N", cb)):
                bid = f"BR-{lvs[s]}-{xl}-{ya}{yb}-{side}"
                pa, pb = cols[ca], cols[cb]
                mid_pt = ((pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2)
                braces[bid] = {"id": bid, "storey": s, "level_top": lvs[s + 1], "base": c, "bay": f"{ya}{yb}",
                               "p1": (*cols[c], zs[s]), "p2": (*mid_pt, zs[s + 1]), "frame": f"SCBF-{xl}",
                               "beam": f"G-{lvs[s + 1]}-{xl}-{ya}{yb}"}

    # grade beams: segments between consecutive present columns on the grade-beam lines
    gbs = {}
    for yl in GRADE_BEAM_LINES["x"]:
        present = [x for x, _ in GX if f"{x}{yl}" in cols]
        for a, b in zip(present, present[1:]):
            gid = f"GB-{yl}-{a}{b}"
            gbs[gid] = {"id": gid, "line": yl, "a": f"{a}{yl}", "b": f"{b}{yl}", "p1": cols[f"{a}{yl}"],
                        "p2": cols[f"{b}{yl}"], "smf": yl in MF_LINES, "wall": True}
    for xl_ in GRADE_BEAM_LINES["y"]:
        present = [y for y, _ in GY if f"{xl_}{y}" in cols]
        for a, b in zip(present, present[1:]):
            gid = f"GB-{xl_}-{a}{b}"
            gbs[gid] = {"id": gid, "line": xl_, "a": f"{xl_}{a}", "b": f"{xl_}{b}", "p1": cols[f"{xl_}{a}"],
                        "p2": cols[f"{xl_}{b}"], "smf": False, "wall": xl_ in ("1", "5")}
    return Topology(layout, members, columns, braces, gbs)
