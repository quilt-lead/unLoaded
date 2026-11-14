"""ETABS adapter: the designed synthetic building as CSI ETABS would expose it through its
OAPI, mapped to registry ids, plus a MOCK send-change / pull-results round trip.

MOCK, NOT ETABS. No ETABS instance is contacted and no ETABS analysis runs. Model objects are
built from data/synthetic_v2/design.json; "results" are calc-graph's own design re-run
(synth.v2.design.run, PyNite frame analyses in synth.v2.lateral) reshaped into the OAPI result
layouts, every value tagged ``{"method": METHOD}``.

How the design maps to ETABS objects
------------------------------------
- Stories: Base (0 ft) + Story1..Story3 = registry levels L2 / L3 / RF (14 / 27 / 40 ft).
- Grid lines: system "G1"; number lines 1..5 are DIR "X" (they sit at X coordinates), letter
  lines A..D are DIR "Y" (the convention seen in ETABS-exported .e2k files).
- Point objects: ETABS points are PLAN locations ("1", "2", ...) that exist at one or more
  stories. Column points come first (in registry order) and keep their label when a column
  moves; other points (infill ends on girders, chevron work points) are labelled by location.
  A point at a story maps to COL-<grid> (BP-<grid> at Base) when it is a column point.
- Frame objects: ETABS labels are per plan location and repeat on every story; (label, story)
  is unique. Columns C1.. (one per column, three story objects each -> COL-<grid>), beams and
  girders B1.. (plan key = registry id without its level -> one label for G-L2-1-AB,
  G-L3-1-AB, G-RF-1-AB), chevron braces D1.. (BR-L1-3-AB-S, BR-L2-3-AB-S, ... share D1). ETABS
  numbers labels in drawing order; here the order is the registry order, deterministic. A
  re-labelled model (a change) is seeded from the base map, so B12 stays B12.
- Unique names (ETABS "Name"): sequential strings, separate namespaces for points and frames.
- Frame sections: AISC16 library shapes by name, materials A992Fy50 (W) / A500GrC (HSS).
- Load patterns Dead, SDL, Live, Lr, EQX, EQY, WX, WY; one linear static case per pattern +
  Modal; the ASCE 7-16 2.3 combinations the design uses (gravity LC1-LC3, seismic with
  (1.2+0.2SDS)D / (0.9-0.2SDS)D and rho, wind 1.2D+W+0.5L, overstrength Omega0 E).
- Story drifts: from the calc records C-SMF:A, C-SMF:D (EQX) and C-SCBF:3 (EQY), shaped like
  SapModel.Results.StoryDrifts rows. Drift = Cd*delta_xe/Ie / h (the amplified design drift
  the records carry), Label = the frame's first column point at that story.
- Frame design: D/C ratios from the calc records' ``uc`` (B-BM, C-MFB, C-COLL, B-COL, C-MFC,
  C-BFC, C-BR), shaped like DesignSteel.GetSummaryResults rows. A column record carries one
  governing storey, so it lands on that storey's column object only.

OAPI names used in ``raw`` (CSI ETABS API reference, docs.csiamerica.com):
- Story.GetStories; PointObj.GetCoordCartesian / GetRestraint; FrameObj.GetLabelNameList
  https://docs.csiamerica.com/help-files/etabs-api-2016/html/427e3068-586b-116d-ec1e-23a67d22627b.htm
  FrameObj.GetSection
  https://docs.csiamerica.com/help-files/etabs-api-2016/html/b75bfab1-bd97-8eff-f9ab-b986ba107d23.htm
  FrameObj.GetPoints / GetReleases / GetDesignOrientation; PropFrame.ImportProp;
  PropMaterial.GetMPIsotropic / GetOSteel; LoadPatterns.GetLoadType; LoadCases.StaticLinear.GetLoads;
  RespCombo.GetCaseList.
- Results.StoryDrifts
  https://docs.csiamerica.com/help-files/etabs-api-2016/html/e55e16e2-b7b0-2864-f3dc-b781f4062325.htm
- Results.BaseReact
  https://docs.csiamerica.com/help-files/etabs-api-2015/html/9dd65ba7-c726-4550-127f-3f37f67d51c4.htm
- DesignSteel.GetSummaryResults (FrameName, Ratio, RatioType, Location, ComboName, ...)
  https://docs.csiamerica.com/help-files/etabs-api-2016/html/d6b77ede-8b2a-23fe-186c-14683f147a7f.htm
Field names follow those pages; enum values (eLoadPatternType, eFrameDesignOrientation) are
from memory of the API and are not verified against a running ETABS.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
from zoneinfo import ZoneInfo

from . import e2k
from .base import (DATA_DIR, AnalysisAdapter, AnalysisObject, apply_change, layout_from_design, load_design,
                   validate_change)

METHOD = "calc-graph PyNite re-run (mock ETABS - ETABS did not run)"
SOURCE = "calc-graph design.json mapped to ETABS-style objects (ETABS did not run)"
JOBS_DIR = os.path.join(DATA_DIR, "etabs_jobs")
TOL = 1e-4

MATERIALS = {
    # ETABS name: registry id, grade, E ksi, Fy, Fu, Fye, Fue (ksi), weight kcf
    "A992Fy50": ("MAT:A992", "Grade 50", 29000.0, 50.0, 65.0, 55.0, 71.5, 0.49),
    "A500GrC": ("MAT:A500C", "Grade C", 29000.0, 50.0, 62.0, 65.0, 74.4, 0.49),
}
PATTERNS = [
    # name, e2k TYPE, eLoadPatternType, self weight multiplier, description
    ("Dead", "Dead", 1, 1.0, "steel self weight (SELFWEIGHT 1); the design's area D is in SDL"),
    ("SDL", "Super Dead", 2, 0.0, "area D on the floor / roof areas (slab, deck and superimposed - the design "
                                   "does not split them) + perimeter wall line loads"),
    ("Live", "Live", 3, 0.0, "floor live incl. partitions, on the floor areas"),
    ("Lr", "Roof Live", 11, 0.0, "roof live, on the roof areas"),
    ("EQX", "Seismic", 5, 0.0, "ELF, X (SMF); +/-5% accidental eccentricity"),
    ("EQY", "Seismic", 5, 0.0, "ELF, Y (SCBF); +/-5% accidental eccentricity"),
    ("WX", "Wind", 6, 0.0, "MWFRS story forces (calc C2), X, as point loads on the windward-face columns"),
    ("WY", "Wind", 6, 0.0, "MWFRS story forces (calc C2), Y, as point loads on the windward-face columns"),
]
DIAPHRAGM = "D1"
# Mass-only load pattern: the design's seismic weight (lateral.seismic_weights) = area D + walls (SDL)
# + partition allowance + a steel framing allowance in psf. SDL carries the first two; this pattern
# carries the two allowances as area loads. It is in the mass source only - no load case uses it.
MASS_PATTERN = "SeisWt"
MASS_SOURCE = "MsSrc1"
# Deck shell material: zero weight, because the design's area D already includes slab + deck. f'c
# 3 ksi LW topping (calc A1 criteria); E = 57000 sqrt(f'c) psi. Membrane + rigid diaphragm, so E
# and thickness carry no analysis stiffness.
DECK_MATERIAL = {"name": "Deck3000NoWt", "type": "Concrete", "grade": "f'c 3000 psi (zero weight)", "fc_ksi": 3.0,
                 "E_ksi": 57.0 * 3000 ** 0.5, "nu": 0.2, "alpha_per_F": 5.5e-6, "weight_kcf": 0.0}


def _now_et() -> str:
    return _dt.datetime.now(ZoneInfo("America/New_York")).isoformat(timespec="seconds")


def stories() -> list[tuple[str, str, float, float]]:
    """[(story name, registry level, elevation ft, height ft)] bottom-up, Base first."""
    from synth.v2.model import LEVELS
    out = [("Base", "L1", 0.0, 0.0)]
    prev = 0.0
    for i, (lv, _, z) in enumerate(LEVELS):
        out.append((f"Story{i + 1}", lv, z, z - prev))
        prev = z
    return out


def _story_of_z(z: float) -> str:
    for name, _, elev, _ in stories():
        if abs(elev - z) < 1e-6:
            return name
    raise ValueError(f"no story at elevation {z}")


def _plan_key(eid: str) -> str:
    """Registry member id without its level: G-L2-1-AB -> G-1-AB, BR-L1-3-AB-S -> BR-3-AB-S."""
    parts = eid.split("-")
    return "-".join(parts[:1] + parts[2:])


# ------------------------------------------------------------------ frame input
def frame_input_from_design(exp: dict) -> dict:
    """{columns, members, braces} from design.json elements (sizes as designed)."""
    cols, mems, brs = [], [], []
    for e in exp["elements"]:
        t = e["type"]
        if t == "column":
            cols.append({"id": e["id"], "grid": e["id"][4:], "x": e["x"], "y": e["y"], "size": e["size"],
                         "roles": e.get("roles", [])})
        elif t in ("beam", "girder"):
            mems.append({"id": e["id"], "kind": e.get("kind", t), "level": e["level"], "z": e["p1"][2],
                         "p1": tuple(e["p1"][:2]), "p2": tuple(e["p2"][:2]), "size": e["size"],
                         "roles": e.get("roles", []), "frame": e.get("frame", "")})
        elif t == "brace":
            brs.append({"id": e["id"], "p1": tuple(e["p1"]), "p2": tuple(e["p2"]), "size": e["size"],
                        "frame": e.get("frame", "")})
    return {"columns": cols, "members": mems, "braces": brs, "sizes": "as designed"}


def frame_input_from_layout(layout, exp: dict) -> dict:
    """Geometry of `layout` (synth.v2.model.build, no re-design) with sizes CARRIED from the
    design by registry id. A member the base design does not have (e.g. the merged girder when
    a column is removed) takes the heaviest size of the same element type on the same level and
    line, and is flagged size_source='carried (heaviest on line)'."""
    from synth.v2 import aisc
    from synth.v2.model import LEVELS, build
    topo = build(layout)
    lvz = {l: z for l, _, z in LEVELS}
    by_id = {e["id"]: e for e in exp["elements"]}

    def carried(eid, etype, level=None, line=None):
        if eid in by_id:
            return by_id[eid]["size"], "carried"
        cand = [e["size"] for e in exp["elements"] if e["type"] == etype
                and (level is None or e.get("level") == level) and (line is None or e.get("line") == line)]
        cand = cand or [e["size"] for e in exp["elements"] if e["type"] == etype]
        return max(cand, key=lambda s: aisc.get(s)["W"]), "carried (heaviest on line)"

    cols, mems, brs = [], [], []
    for c, info in topo.columns.items():
        size, src = carried(f"COL-{c}", "column")
        cols.append({"id": f"COL-{c}", "grid": c, "x": round(info["x"], 3), "y": round(info["y"], 3), "size": size,
                     "roles": info["roles"], "size_source": src})
    for k, m in topo.members.items():
        etype = "girder" if m.kind == "girder" else "beam"
        size, src = carried(k, etype, m.level, m.line or None)
        mems.append({"id": k, "kind": m.kind, "level": m.level, "z": lvz[m.level],
                     "p1": (round(m.p1[0], 3), round(m.p1[1], 3)), "p2": (round(m.p2[0], 3), round(m.p2[1], 3)),
                     "size": size, "roles": m.roles, "frame": m.frame, "size_source": src})
    for bid, b in topo.braces.items():
        size, src = carried(bid, "brace")
        brs.append({"id": bid, "p1": tuple(round(v, 3) for v in b["p1"]), "p2": tuple(round(v, 3) for v in b["p2"]),
                    "size": size, "frame": b["frame"], "size_source": src})
    return {"columns": cols, "members": mems, "braces": brs, "sizes": "carried (geometry-only change)"}


# ------------------------------------------------------------------ model build
def _restraint(roles) -> list[bool]:
    fixed = "smf_column" in roles      # SMF bases fixed, all others pinned (synth.v2.lateral)
    return [True, True, True, fixed, fixed, fixed]


def build_objects(exp: dict, frames: dict | None = None, seed: dict | None = None,
                  layout=None) -> tuple[list[AnalysisObject], dict]:
    """ETABS-style objects for the design (or for `frames`, a frame input with a change applied).

    seed: label map from a previous build ({"points": {key: label}, "frames": {plan key: label}})
    so labels stay stable across a change. layout: the synth.v2.model.Layout `frames` comes from
    (default: the design's own, layout_from_design(exp)) - its load areas and perimeter walls
    are the loads. Returns (objects, label map).

    Loads come from the design's own definitions, never re-typed: floor / roof area loads from
    the layout's load areas (calc A2), perimeter walls from synth.v2.model.wall_klf on the members
    the topology marks `wall`, wind story forces from the C-WIND records, ELF Cs / k from the
    C-ELF records, the seismic mass from the same areas + allowances lateral.seismic_weights uses."""
    from synth.v2 import lateral as LAT
    from synth.v2.model import DECK_T_IN, GX, GY, area_at, area_record_id, column_depth_axis, wall_klf
    from synth.v2.model import build as build_topology
    frames = frames or frame_input_from_design(exp)
    layout = layout or layout_from_design(exp)
    topo = build_topology(layout)
    seed = seed or {}
    st = stories()
    st_name = {lv: n for n, lv, _, _ in st}
    st_elev = {n: z for n, _, z, _ in st}
    objs: list[AnalysisObject] = []
    records = {r["id"]: r for r in exp.get("records", [])}
    with_results = bool(records) and frames.get("sizes") == "as designed"

    # stories
    top = st[-1][0]
    for name, lv, z, h in st:
        raw = {"Story.GetStories": {"StoryName": name, "StoryElevation": z, "StoryHeight": h,
                                    "IsMasterStory": name == top, "SimilarToStory": "" if name in (top, "Base") else top,
                                    "SpliceAbove": False, "SpliceHeight": 0.0}}
        objs.append(AnalysisObject("story", name, f"LEVEL:{lv}", [], {"elevation_ft": z, "height_ft": h, "level": lv}, raw))
    # grids
    for lab, x in GX:
        objs.append(AnalysisObject("grid", lab, f"GRID:{lab}", [], {"dir": "X", "coord_ft": x, "system": "G1"},
                                   {"GridSys": "G1", "GridLineID": lab, "Dir": "X", "Ordinate": x}))
    for lab, y in GY:
        objs.append(AnalysisObject("grid", lab, f"GRID:{lab}", [], {"dir": "Y", "coord_ft": y, "system": "G1"},
                                   {"GridSys": "G1", "GridLineID": lab, "Dir": "Y", "Ordinate": y}))
    # materials + sections
    sizes = sorted({c["size"] for c in frames["columns"]} | {m["size"] for m in frames["members"]}
                   | {b["size"] for b in frames["braces"]})
    used_mats = sorted({"A500GrC" if s.startswith("HSS") else "A992Fy50" for s in sizes})
    for mname in used_mats:
        reg, grade, E, fy, fu, fye, fue, wt = MATERIALS[mname]
        props = {"type": "Steel", "grade": grade, "E_ksi": E, "Fy_ksi": fy, "Fu_ksi": fu, "Fye_ksi": fye, "Fue_ksi": fue,
                 "weight_kcf": wt, "nu": 0.3, "alpha_per_F": 6.5e-6}
        raw = {"PropMaterial.GetMPIsotropic": {"E": E * 144, "U": 0.3, "A": 6.5e-6, "units": "kip, ft, F"},
               "PropMaterial.GetOSteel": {"Fy": fy * 144, "Fu": fu * 144, "EFy": fye * 144, "EFu": fue * 144}}
        objs.append(AnalysisObject("material", mname, reg, [], props, raw))
    for s in sizes:
        mat = "A500GrC" if s.startswith("HSS") else "A992Fy50"
        objs.append(AnalysisObject("section", s, f"TYPE:{s}", [], {"material": mat, "shape": s, "library": "AISC16"},
                                   {"PropFrame.ImportProp": {"Name": s, "MatProp": mat, "FileName": "AISC16.xml", "PropName": s}}))

    # points: plan locations
    pt_seed = dict(seed.get("points", {}))
    pt_label: dict[str, str] = {}
    pt_xy: dict[str, tuple[float, float]] = {}
    used = set(pt_seed.values())
    nxt = [max([int(v) for v in used] or [0]) + 1]

    def ckey(x, y):
        return f"xy:{round(x, 4):.4f},{round(y, 4):.4f}"

    loc_to_label: dict[str, str] = {}

    def point(key: str, x: float, y: float) -> str:
        if key in pt_label:
            return pt_label[key]
        ck = ckey(x, y)
        if not key.startswith("col:") and ck in loc_to_label:   # coincides with an existing point
            return loc_to_label[ck]
        lab = pt_seed.get(key)
        if lab is None or lab in pt_xy:
            lab = str(nxt[0])
            nxt[0] += 1
        pt_label[key] = lab
        pt_xy[lab] = (x, y)
        loc_to_label[ck] = lab
        return lab

    col_of_pt = {}
    for c in frames["columns"]:
        lab = point(f"col:{c['grid']}", c["x"], c["y"])
        col_of_pt[lab] = c
    girders = [m for m in frames["members"] if m["kind"] == "girder"]

    def skey(x: float, y: float) -> str:
        """Structural key of a non-column point: the girder (plan key) it sits on + its y, so a
        point that slides along a skewed girder keeps its label, as an ETABS point would."""
        for g in girders:
            (x1, y1), (x2, y2) = g["p1"], g["p2"]
            L2 = (x2 - x1) ** 2 + (y2 - y1) ** 2
            t = ((x - x1) * (x2 - x1) + (y - y1) * (y2 - y1)) / L2 if L2 else 0.0
            if -1e-9 <= t <= 1 + 1e-9 and (x1 + t * (x2 - x1) - x) ** 2 + (y1 + t * (y2 - y1) - y) ** 2 < 4e-6:   # 2e-3 ft (coords at 3 dp)
                return f"on:{_plan_key(g['id'])}:{y:.3f}"
        return ckey(x, y)

    for m in frames["members"]:
        for p in (m["p1"], m["p2"]):
            point(skey(*p), *p)
    for b in frames["braces"]:
        for p in (b["p1"], b["p2"]):
            point(skey(p[0], p[1]), p[0], p[1])

    # frame objects
    fr_seed = dict(seed.get("frames", {}))
    fr_label: dict[str, str] = {}
    counters = {"C": 0, "B": 0, "D": 0}
    for v in fr_seed.values():
        counters[v[0]] = max(counters[v[0]], int(v[1:]))

    def flabel(prefix: str, key: str) -> str:
        if key not in fr_label:
            lab = fr_seed.get(key)
            if lab is None or lab in fr_label.values():
                counters[prefix] += 1
                lab = f"{prefix}{counters[prefix]}"
            fr_label[key] = lab
        return fr_label[key]

    point_use: dict[tuple[str, str], set] = {}
    frame_objs: list[AnalysisObject] = []
    uname = [0]

    def add_frame(label, story, etype, eid, pi, pj, zi, zj, size, release, props, n_below):
        uname[0] += 1
        name = str(uname[0])
        si = _story_of_z(zi)
        point_use.setdefault((pi, si), set()).add(eid)
        point_use.setdefault((pj, story), set()).add(eid)
        xi, yi = pt_xy[pi]
        xj, yj = pt_xy[pj]
        rel = [False, False, False, False, True, True] if release else [False] * 6
        orient = {"COLUMN": 1, "BEAM": 2, "BRACE": 3}[etype]
        mat = "A500GrC" if size.startswith("HSS") else "A992Fy50"
        raw = {"FrameObj.GetLabelNameList": {"Name": name, "Label": label, "Story": story},
               "FrameObj.GetPoints": {"Point1": f"{pi}@{si}", "Point2": f"{pj}@{story}"},
               "FrameObj.GetSection": {"PropName": size, "SAuto": ""},
               "FrameObj.GetReleases": {"II": rel, "JJ": rel},
               "FrameObj.GetDesignOrientation": {"DesignOrientation": orient}}
        p = {"etabs_type": etype, "unique_name": name, "section": size, "material": mat, "point_i": pi, "point_j": pj,
             "xyz_i": [xi, yi, zi], "xyz_j": [xj, yj, zj], "release": "PINNED" if release else "",
             "stories_below_i": n_below, **props}
        ob = AnalysisObject("frame", label, eid, [], p, raw, story)
        frame_objs.append(ob)
        return ob

    order = [s[0] for s in st]
    for c in frames["columns"]:
        lab = flabel("C", f"COL-{c['grid']}")
        pl = pt_label[f"col:{c['grid']}"]
        for k in range(1, len(st)):
            add_frame(lab, st[k][0], "COLUMN", c["id"], pl, pl, st[k - 1][2], st[k][2], c["size"], False,
                      {"roles": c["roles"], "angle_deg": 0.0 if column_depth_axis(c["roles"]) == "x" else 90.0,
                       "size_source": c.get("size_source", "design")}, 1)
    for m in frames["members"]:
        lab = flabel("B", _plan_key(m["id"]))
        pi, pj = loc_to_label[ckey(*m["p1"])], loc_to_label[ckey(*m["p2"])]
        pinned = "smf_beam" not in m["roles"]       # SMF beams are moment connected (RBS)
        add_frame(lab, st_name[m["level"]], "BEAM", m["id"], pi, pj, m["z"], m["z"], m["size"], pinned,
                  {"roles": m["roles"], "frame": m["frame"], "member_kind": m["kind"],
                   "size_source": m.get("size_source", "design")}, 0)
    for b in frames["braces"]:
        lab = flabel("D", _plan_key(b["id"]))
        pi = loc_to_label[ckey(b["p1"][0], b["p1"][1])]
        pj = loc_to_label[ckey(b["p2"][0], b["p2"][1])]
        story = _story_of_z(b["p2"][2])
        n = order.index(story) - order.index(_story_of_z(b["p1"][2]))
        add_frame(lab, story, "BRACE", b["id"], pi, pj, b["p1"][2], b["p2"][2], b["size"], True,
                  {"roles": ["scbf_brace"], "frame": b["frame"], "size_source": b.get("size_source", "design")}, n)

    # perimeter wall line loads (SDL) on the members the topology marks `wall` (gravity.line_loads
    # applies the same wall_klf on the same members)
    for f in frame_objs:
        m = topo.members.get(f.element_id)
        if m is not None and m.wall:
            f.props["line_loads"] = {"SDL": wall_klf(m.level)}

    # floor / roof area objects: one per plan cell between grid lines (and load-area edges), corner
    # points on the columns (a moved column takes its panel corners with it), membrane deck with
    # zero self weight, the load area's D / L / Lr and the seismic allowances as uniform loads
    gx_, gy_ = [x for _, x in GX], [y for _, y in GY]
    # a panel corner follows its column (connectivity) unless that would pull the slab edge in:
    # on the footprint boundary the corner stays on the boundary (the design loads the whole
    # footprint whatever the column positions), as a corner point that frames nothing
    grid_col = {}
    for c in frames["columns"]:
        g = c["grid"]
        gxy = (dict(GX)[g[:-1]], dict(GY)[g[-1]])
        on_x_edge, on_y_edge = gxy[0] in (gx_[0], gx_[-1]), gxy[1] in (gy_[0], gy_[-1])
        if (on_x_edge and abs(c["x"] - gxy[0]) > 1e-9) or (on_y_edge and abs(c["y"] - gxy[1]) > 1e-9):
            continue
        grid_col[gxy] = pt_label[f"col:{g}"]
    deck_ids = {e["level"]: e["id"] for e in exp.get("elements", []) if e.get("type") == "deck"}
    area_objs, shell_objs, area_label = [], [], {}
    for name, lv, z, _ in st[1:]:
        zones = [a for a in layout.areas if a.level == lv]
        xb = sorted({*gx_, *(v for a in zones for v in (a.x0, a.x1) if gx_[0] < v < gx_[-1])})
        yb = sorted({*gy_, *(v for a in zones for v in (a.y0, a.y1) if gy_[0] < v < gy_[-1])})
        prop = f"DK-{lv}"
        shell_objs.append(AnalysisObject("shell_prop", prop, deck_ids.get(lv), [], {
            "prop_type": "Slab", "modeling": "Membrane", "slab_type": "Slab", "thickness_ft": DECK_T_IN[lv] / 12,
            "material": DECK_MATERIAL["name"], "material_props": DECK_MATERIAL, "level": lv,
            "note": "zero-weight membrane: the area D load carries slab + deck; rigid diaphragm"},
            {"PropArea.GetSlab": {"Name": prop, "SlabType": "Slab", "ShellType": "Membrane",
                                  "MatProp": DECK_MATERIAL["name"], "Thickness": DECK_T_IN[lv] / 12}}))
        for x0, x1 in zip(xb, xb[1:]):
            for y0, y1 in zip(yb, yb[1:]):
                corners = []
                for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
                    lab = grid_col.get((x, y)) or point(ckey(x, y), x, y)
                    corners.append(lab)
                key = tuple(corners)
                if key not in area_label:
                    area_label[key] = f"F{len(area_label) + 1}"
                lab = area_label[key]
                xy = [pt_xy[c] for c in corners]
                a_ft2 = abs(sum(xa * yb_ - xb_ * ya for (xa, ya), (xb_, yb_) in zip(xy, xy[1:] + xy[:1]))) / 2
                ar = area_at(layout.areas, lv, (x0 + x1) / 2, (y0 + y1) / 2)
                loads = {}
                if ar is not None:
                    loads = {"SDL": ar.d_psf / 1000, "Live": ar.l_psf / 1000, "Lr": ar.lr_psf / 1000,
                             MASS_PATTERN: (ar.seis_extra_psf + LAT.STEEL_ALLOW_PSF[lv]) / 1000}
                    loads = {k: v for k, v in loads.items() if v}
                rids = [area_record_id(ar)] if ar is not None else []
                raw = {"AreaObj.GetLabelNameList": {"Label": lab, "Story": name},
                       "AreaObj.GetPoints": {"Point": [f"{c}@{name}" for c in corners]},
                       "AreaObj.GetProperty": {"PropName": prop}, "AreaObj.GetDiaphragm": {"DiaphragmName": DIAPHRAGM},
                       "AreaObj.GetLoadUniform": {"LoadPat": list(loads), "Value": [v for v in loads.values()],
                                                  "Dir": [10] * len(loads), "units": "kip, ft"}}
                area_objs.append(AnalysisObject("area", lab, deck_ids.get(lv), rids, {
                    "points": corners, "xy": [list(p) for p in xy], "area_ft2": a_ft2, "section": prop,
                    "diaphragm": DIAPHRAGM, "zone": ar.name if ar else None, "loads_ksf": loads,
                    "mesh": "DEFAULT"}, raw, name))

    # wind: the C-WIND story forces on the windward face, split over the face columns by
    # tributary width so the resultant sits at the face centroid (rigid diaphragm carries it)
    wind_loads: dict[tuple[str, str], dict[str, list[float]]] = {}
    cxy = [(pt_label[f"col:{c['grid']}"], c["x"], c["y"]) for c in frames["columns"]]
    for pat, k in (("WX", 0), ("WY", 1)):
        rec = records.get(f"C-WIND:{pat[-1]}")
        if not rec or not cxy:
            continue
        face = min(p[1 + k] for p in cxy)
        on = sorted((p for p in cxy if abs(p[1 + k] - face) < 1e-6), key=lambda p: p[2 - k])
        along = [p[2 - k] for p in on]
        lo, hi = min(p[2 - k] for p in cxy), max(p[2 - k] for p in cxy)
        edges = [lo] + [(a + b) / 2 for a, b in zip(along, along[1:])] + [hi]
        tribs = [b - a for a, b in zip(edges, edges[1:])]
        for lv, F in rec["values"]["Fx_k"].items():
            for p, t in zip(on, tribs):
                f = [0.0, 0.0, 0.0]
                f[k] = F * t / (hi - lo)
                wind_loads.setdefault((p[0], st_name[lv]), {})[pat] = f

    # point objects (one per label x story in use)
    pn = 0
    for lab in sorted(pt_xy, key=int):
        x, y = pt_xy[lab]
        for sname in order:
            if (lab, sname) not in point_use:
                continue
            pn += 1
            c = col_of_pt.get(lab)
            eid = None
            if c:
                eid = f"BP-{c['grid']}" if sname == "Base" else c["id"]
            restr = _restraint(c["roles"]) if (c and sname == "Base") else [False] * 6
            raw = {"PointObj.GetLabelNameList": {"Name": f"{lab}@{sname}", "Label": lab, "Story": sname},
                   "PointObj.GetCoordCartesian": {"X": x, "Y": y, "Z": st_elev[sname]},
                   "PointObj.GetRestraint": {"Value": restr}}
            props = {"x_ft": x, "y_ft": y, "z_ft": st_elev[sname], "restraint": restr,
                     "framing": sorted(point_use[(lab, sname)])}
            if sname != "Base":
                props["diaphragm"] = DIAPHRAGM
                raw["PointObj.GetDiaphragm"] = {"DiaphragmName": DIAPHRAGM}
            pl = wind_loads.get((lab, sname))
            rids = []
            if pl:
                props["point_loads"] = pl
                raw["PointObj.GetLoadForce"] = {"LoadPat": list(pl), "F1": [v[0] for v in pl.values()],
                                                "F2": [v[1] for v in pl.values()], "units": "kip"}
                rids = [f"C-WIND:{p[-1]}" for p in pl]
            objs.append(AnalysisObject("point", lab, eid, rids, props, raw, sname))
    objs.extend(frame_objs)
    objs.append(AnalysisObject("diaphragm", DIAPHRAGM, None, [], {
        "type": "RIGID", "reason": "the design distributes story forces by a rigid (composite deck) diaphragm "
                                   "with 5% accidental torsion (synth.v2.lateral.distribute); the roof is "
                                   "taken rigid too, as the design does"},
        {"Diaphragm.GetDiaphragm": {"Name": DIAPHRAGM, "SemiRigid": False}}))
    objs.extend(shell_objs)
    objs.extend(area_objs)

    # load patterns / cases / combos
    area_d = [r for r in records.values() if r["kind"] == "area_load" and r["values"].get("D_psf")]
    area_l = [r["id"] for r in records.values() if r["kind"] == "area_load" and r["values"].get("L_psf")]
    area_lr = [r["id"] for r in records.values() if r["kind"] == "area_load" and r["values"].get("Lr_psf")]
    pat_recs = {"Dead": [r["id"] for r in area_d], "SDL": [r["id"] for r in area_d], "Live": area_l, "Lr": area_lr,
                "EQX": ["C-ELF:X"], "EQY": ["C-ELF:Y"], "WX": ["C-WIND:X"], "WY": ["C-WIND:Y"]}
    for name, etype, enum, sw, desc in PATTERNS:
        rids = [r for r in pat_recs[name] if r in records]
        props = {"type": etype, "self_weight": sw, "description": desc}
        if name in ("EQX", "EQY") and f"C-ELF:{name[-1]}" in records:
            v = records[f"C-ELF:{name[-1]}"]["values"]
            props.update(method="User Coefficient", dir=name[-1], ecc=0.05, shear_coeff=v["Cs"], height_exponent=v["k"],
                         V_k=v["V_k"], Fx_k=v["Fx_k"])
        if name in ("WX", "WY") and f"C-WIND:{name[-1]}" in records:
            v = records[f"C-WIND:{name[-1]}"]["values"]
            props.update(dir=name[-1], V_k=v["V_k"], Fx_k=v["Fx_k"], psf=v["psf"])
        objs.append(AnalysisObject("load_pattern", name, None, rids, props,
                                   {"LoadPatterns.GetLoadType": {"MyType": enum}, "LoadPatterns.GetSelfWTMultiplier": {"SelfWTMultiplier": sw}}))
    elf = [r for r in ("C-ELF:X", "C-ELF:Y") if r in records]
    objs.append(AnalysisObject("mass_source", MASS_SOURCE, None, elf, {
        "include_elements": False, "include_added_mass": False, "include_loads": True, "lateral_only": True,
        "lump_at_stories": True, "loads": [["SDL", 1.0], [MASS_PATTERN, 1.0]],
        "extra_patterns": [{"name": MASS_PATTERN, "type": "Other", "self_weight": 0.0,
                            "description": "mass only: partition allowance + steel framing allowance (psf) of "
                                           "the design's seismic weight; in no load case"}],
        "note": "W = SDL (area D + walls) + allowances = lateral.seismic_weights; element self mass excluded "
                "because the design's W uses a psf steel allowance, not the as-designed tonnage"},
        {"SourceMass.GetMassSource": {"Name": MASS_SOURCE, "MassFromElements": False, "MassFromMasses": False,
                                      "MassFromLoads": True, "IsDefault": True, "LoadPat": ["SDL", MASS_PATTERN],
                                      "SF": [1.0, 1.0]}}))
    objs.append(AnalysisObject("load_case", "Modal", None, [], {"type": "Modal - Eigen", "max_modes": 12}, {"LoadCases.GetNameList": "Modal"}))
    for name, _, _, _, _ in PATTERNS:
        objs.append(AnalysisObject("load_case", name, None, list(pat_recs[name] and [r for r in pat_recs[name] if r in records]),
                                   {"type": "Linear Static", "loads": [[name, 1.0]]},
                                   {"LoadCases.StaticLinear.GetLoads": {"NumberLoads": 1, "LoadType": ["Load"], "LoadName": [name], "SF": [1.0]}}))
    sds = LAT.SDS
    rx, ry = LAT.SYS["x"]["rho"], LAT.SYS["y"]["rho"]
    o0x, o0y = LAT.SYS["x"]["O0"], LAT.SYS["y"]["O0"]
    dq, dq2 = round(1.2 + 0.2 * sds, 4), round(0.9 - 0.2 * sds, 4)
    D = lambda f: [["Dead", f], ["SDL", f]]   # noqa: E731
    combos = [
        ("1.4D", D(1.4), "gravity", ["A1-CRIT"]),
        ("1.2D+1.6L+0.5Lr", D(1.2) + [["Live", 1.6], ["Lr", 0.5]], "gravity", ["A1-CRIT"]),
        ("1.2D+1.6Lr+0.5L", D(1.2) + [["Lr", 1.6], ["Live", 0.5]], "gravity", ["A1-CRIT"]),
    ]
    for d_, rho, o0 in (("X", rx, o0x), ("Y", ry, o0y)):
        for sg, s_ in ((1, "+"), (-1, "-")):
            combos.append((f"{dq:g}D+0.5L{s_}{rho:g}EQ{d_}", D(dq) + [["Live", 0.5], [f"EQ{d_}", sg * rho]], "seismic", [f"C-ELF:{d_}"]))
            combos.append((f"{dq2:g}D{s_}{rho:g}EQ{d_}", D(dq2) + [[f"EQ{d_}", sg * rho]], "seismic", [f"C-ELF:{d_}"]))
        combos.append((f"1.2D+0.5L+1.0W{d_}", D(1.2) + [["Live", 0.5], [f"W{d_}", 1.0]], "wind", [f"C-WIND:{d_}"]))
        combos.append((f"{dq:g}D+0.5L+{o0:g}EQ{d_} (Omega0)", D(dq) + [["Live", 0.5], [f"EQ{d_}", o0]], "overstrength",
                       [f"C-ELF:{d_}"]))
    for name, terms, group, rids in combos:
        objs.append(AnalysisObject("combo", name, None, [r for r in rids if r in records],
                                   {"type": "Linear Add", "design": "Steel", "combo_type": "Strength", "group": group,
                                    "terms": terms, "code": "ASCE 7-16 2.3 / 12.4"},
                                   {"RespCombo.GetCaseList": {"NumberItems": len(terms), "CType": [0] * len(terms),
                                                              "CName": [t[0] for t in terms], "SF": [t[1] for t in terms]},
                                    "RespCombo.GetTypeOAPI": {"ComboType": 0}}))

    if with_results:
        objs.extend(_drift_objects(records, frames, pt_label, st))
        objs.extend(_design_objects(records, frame_objs))
    return objs, {"points": pt_label, "frames": fr_label}


def _drift_objects(records: dict, frames: dict, pt_label: dict, st) -> list[AnalysisObject]:
    out = []
    src = [("C-SMF:A", "EQX", "X", "A"), ("C-SMF:D", "EQX", "X", "D"), ("C-SCBF:3", "EQY", "Y", "3")]
    elev = {lv: z for _, lv, z, _ in st}
    sname = {lv: n for n, lv, _, _ in st}
    for rid, case, d, line in src:
        r = records.get(rid)
        if not r:
            continue
        cols = [c for c in frames["columns"] if (c["grid"][-1] == line if d == "X" else c["grid"][:-1] == line)
                and any(x in c["roles"] for x in ("smf_column", "scbf_column"))]
        c0 = cols[0] if cols else None
        frame_id = r["elements"][0] if r["elements"] else None
        for row in r["values"]["drifts"]:
            story = sname[row["level"]]
            drift = row["delta_in"] / (row["h"] * 12.0)
            raw = {"Results.StoryDrifts": {"Story": story, "LoadCase": case, "StepType": "", "StepNum": 0.0,
                                           "Direction": d, "Drift": round(drift, 6),
                                           "Label": pt_label[f"col:{c0['grid']}"] if c0 else "",
                                           "X": c0["x"] if c0 else None, "Y": c0["y"] if c0 else None,
                                           "Z": elev[row["level"]]}}
            props = {"line": line, "direction": d, "load_case": case, "drift_ratio": round(drift, 6),
                     "limit_ratio": 0.020, "dc": row["ratio"], "delta_in": row["delta_in"], "allow_in": row["allow_in"],
                     "h_ft": row["h"], "amplified": "Cd*delta_xe/Ie (ASCE 7-16 12.8-15)", "source": SOURCE}
            out.append(AnalysisObject("story_drift", f"{story} {case} {d} line {line}", frame_id, [rid], props, raw, story))
    return out


def _design_objects(records: dict, frame_objs: list[AnalysisObject]) -> list[AnalysisObject]:
    by_el: dict[str, list[AnalysisObject]] = {}
    for f in frame_objs:
        by_el.setdefault(f.element_id, []).append(f)
    per_frame: dict[tuple[str, str], list[dict]] = {}
    for r in records.values():
        if r["kind"] not in ("beam_design", "smf_beam", "collector", "column_design", "brace") or r.get("uc") is None:
            continue
        for eid in r["elements"]:
            fos = by_el.get(eid, [])
            if not fos:
                continue
            if r["kind"] == "column_design":
                stn = f"Story{r['values'].get('storey') or 1}"
                fos = [f for f in fos if f.story == stn] or fos[:1]
            for f in fos:
                per_frame.setdefault((f.label, f.story), []).append({"r": r, "f": f})
    out = []
    for (lab, story), items in per_frame.items():
        gov = max(items, key=lambda i: i["r"]["uc"])
        r, f = gov["r"], gov["f"]
        shear = "shear" in (r.get("check") or "").lower() or str(r["values"].get("governs", "")).startswith("shear")
        raw = {"DesignSteel.GetSummaryResults": {"FrameName": f.props["unique_name"], "Ratio": r["uc"],
                                                 "RatioType": 2 if shear else 1, "Location": None,
                                                 "ComboName": r.get("lc") or "", "ErrorSummary": "",
                                                 "WarningSummary": "" if r["uc"] <= 1.0 else "D/C > 1.0"}}
        props = {"ratio": r["uc"], "governing_record": r["id"], "check": r.get("check"), "combo": r.get("lc"),
                 "section": f.props["section"], "etabs_type": f.props["etabs_type"], "source": SOURCE,
                 "ratio_type": "major shear" if shear else "PMM / flexure"}
        out.append(AnalysisObject("frame_design", lab, f.element_id, sorted({i["r"]["id"] for i in items}), props, raw, story))
    return out


OBJECT_TYPE = {"story": "Story", "grid": "GridLine", "point": "Point", "frame": "Frame", "area": "Area",
               "shell_prop": "AreaProperty", "diaphragm": "Diaphragm", "mass_source": "MassSource",
               "section": "FrameSection", "material": "Material", "load_pattern": "LoadPattern",
               "load_case": "LoadCase", "combo": "Combo", "story_drift": "StoryDrift", "frame_design": "SteelDesign"}


def occurrences_of(objs: list[AnalysisObject], doc: str = "etabs") -> list[dict]:
    out = []
    for o in objs:
        refs = ([o.element_id] if o.element_id else []) + list(o.record_ids)
        for ref in dict.fromkeys(refs):
            out.append({"ref": ref, "doc": doc, "kind": f"{doc}-object", "object_type": OBJECT_TYPE[o.kind],
                        "label": o.label, "story": o.story, "how": f"{doc}-object"})
    return out


# ------------------------------------------------------------------ adapter
class EtabsAdapter(AnalysisAdapter):
    """ETABS adapter over design.json. All results are MOCK (see module docstring)."""

    name = "ETABS"
    doc = "etabs"

    def __init__(self, design: dict | str | None = None):
        self._design_src = design
        self._exp = None
        self._objs = None
        self._labels = None

    @property
    def design(self) -> dict:
        if self._exp is None:
            self._exp = load_design(self._design_src)
        return self._exp

    def _build(self):
        if self._objs is None:
            self._objs, self._labels = build_objects(self.design)
        return self._objs

    def model_objects(self) -> list[AnalysisObject]:
        return list(self._build())

    def label_map(self) -> dict:
        """{"frames": {registry plan key: label}, "points": {point key: label},
        "by_element": {element id: [{label, story}]}}"""
        objs = self._build()
        by_el: dict[str, list] = {}
        for o in objs:
            if o.kind == "frame":
                by_el.setdefault(o.element_id, []).append({"label": o.label, "story": o.story})
        return {**self._labels, "by_element": by_el}

    def occurrences(self) -> list[dict]:
        return occurrences_of(self._build(), self.doc)

    def counts(self) -> dict:
        out: dict[str, int] = {}
        for o in self._build():
            out[o.kind] = out.get(o.kind, 0) + 1
        return out

    # ---- text model
    def _objects_for(self, exp: dict, change: dict | None, redesign: bool):
        if not change:
            return (self._build() if exp is self.design else build_objects(exp)[0]), "as designed", None
        layout = apply_change(layout_from_design(exp), change)
        self._build()
        if redesign:
            from synth.v2 import design as DSN, records
            d = DSN.run(layout)
            exp2 = records.export(d)
            objs, _ = build_objects(exp2, seed=self._labels, layout=layout)
            return objs, "re-designed (calc-graph synth.v2.design.run)", (d, exp2)
        objs, _ = build_objects(exp, frame_input_from_layout(layout, exp), seed=self._labels, layout=layout)
        return objs, "carried from the base design (geometry-only change)", None

    def export_model(self, path: str, design: dict | None = None, change: dict | None = None,
                     redesign: bool = False) -> dict:
        """Write an ETABS .e2k text model. change=None: the design as designed. With a change:
        geometry re-derived by synth.v2.model.build; sizes carried from the design by registry id
        (redesign=False, fast) or re-designed by synth.v2.design.run (redesign=True, ~25 s)."""
        exp = load_design(design) if design is not None else self.design
        objs, sizes, _ = self._objects_for(exp, change, redesign)
        title = (exp.get("building") or {}).get("name", "calc-graph synthetic building")
        info = e2k.write_e2k(objs, path, title=title, note=f"sizes: {sizes}" + (f"; change: {json.dumps(change, sort_keys=True)}" if change else ""))
        return {"path": path, "sizes": sizes, "change": change, **info}

    def roundtrip(self, path: str) -> dict:
        """Read `path` back with e2k.read_e2k and compare to the design: object counts, every
        frame segment (3D end coordinates + section) and the label -> registry id map."""
        parsed = e2k.read_e2k(path)
        segs = e2k.frame_segments(parsed)
        objs = self._build()
        cnt = self.counts()
        names = e2k.etabs_load_names(objs)
        exp_counts = {"stories": sum(1 for o in objs if o.kind == "story"), "grids": cnt.get("grid", 0),
                      "points (plan)": len({o.label for o in objs if o.kind == "point"}),
                      "frames (label x story)": cnt.get("frame", 0), "sections": cnt.get("section", 0),
                      "materials": cnt.get("material", 0) + len({o.props["material"] for o in objs if o.kind == "shell_prop"}),
                      "load patterns": len(names["patterns"]),
                      "load cases": len(names["cases"]), "combos": len(names["combos"]),
                      "areas (label x story)": cnt.get("area", 0), "diaphragms": cnt.get("diaphragm", 0),
                      "mass sources": cnt.get("mass_source", 0)}
        got_counts = {"stories": len(parsed["stories"]), "grids": len(parsed["grids"]),
                      "points (plan)": len(parsed["points"]), "frames (label x story)": len(segs),
                      "sections": len(parsed["sections"]), "materials": len(parsed["materials"]),
                      "load patterns": len(parsed["load_patterns"]), "load cases": len(parsed["load_cases"]),
                      "combos": len(parsed["combos"]), "areas (label x story)": len(parsed["area_assigns"]),
                      "diaphragms": len(parsed["diaphragms"]), "mass sources": len(parsed["mass_sources"])}
        # design segments straight from design.json (independent of the label map)
        des = []
        lv_z = [z for _, _, z, _ in stories()]
        for e in self.design["elements"]:
            if e["type"] == "column":
                for z0, z1 in zip(lv_z, lv_z[1:]):
                    des.append(((e["x"], e["y"], z0), (e["x"], e["y"], z1), e["size"], e["id"]))
            elif e["type"] in ("beam", "girder", "brace"):
                des.append((tuple(e["p1"]), tuple(e["p2"]), e["size"], e["id"]))

        def key(a, b):
            ka = tuple(round(v, 3) for v in a)
            kb = tuple(round(v, 3) for v in b)
            return min(ka, kb), max(ka, kb)
        got = {key(s["i"], s["j"]): s for s in segs}
        missing, sec_bad, max_err = [], [], 0.0
        for a, b, size, eid in des:
            s = got.get(key(a, b))
            if not s:
                missing.append(eid)
                continue
            if s["section"] != size:
                sec_bad.append(eid)
            for p, q in ((a, s["i"]), (b, s["j"])) if key(a, a) == key(s["i"], s["i"]) else ((a, s["j"]), (b, s["i"])):
                max_err = max(max_err, max(abs(u - v) for u, v in zip(p, q)))
        extra = len(segs) - (len(des) - len(missing))
        # label map: (label, story) in the file -> registry element via the adapter map -> same geometry
        fobj = {(o.label, o.story): o for o in objs if o.kind == "frame"}
        des_by_id: dict[str, list] = {}
        for a, b, size, eid in des:
            des_by_id.setdefault(eid, []).append(key(a, b))
        map_bad = [f"{s['label']}@{s['story']}" for s in segs
                   if (s["label"], s["story"]) not in fobj
                   or key(s["i"], s["j"]) not in des_by_id.get(fobj[(s["label"], s["story"])].element_id, [])]
        return {"path": path, "counts_model": exp_counts, "counts_read": got_counts,
                "counts_match": exp_counts == got_counts, "design_segments": len(des), "matched": len(des) - len(missing),
                "missing": missing[:20], "missing_n": len(missing), "extra_n": extra, "section_mismatch": sec_bad[:20],
                "section_mismatch_n": len(sec_bad), "max_coord_err_ft": max_err, "label_map_mismatch": map_bad[:20],
                "label_map_mismatch_n": len(map_bad),
                "ok": exp_counts == got_counts and not missing and not sec_bad and extra == 0 and not map_bad and max_err < 1e-3}

    # ---- mock round trip
    def send_change(self, design: dict | None, change: dict) -> dict:
        """MOCK send: writes <JOBS_DIR>/<job_id>/{change.json, model.e2k, job.json} and returns
        the job record. model.e2k = the changed geometry with sizes carried (what would be sent to
        ETABS for analysis); nothing is sent anywhere."""
        exp = load_design(design) if design is not None else self.design
        base_layout = layout_from_design(exp)
        change = validate_change(change, base_layout)
        stamp = _dt.datetime.now(ZoneInfo("America/New_York"))
        h = hashlib.sha1(json.dumps(change, sort_keys=True).encode()).hexdigest()[:8]
        job_id = f"etabs-{stamp:%Y%m%d-%H%M%S}-{h}"
        jdir = os.path.join(JOBS_DIR, job_id)
        os.makedirs(jdir, exist_ok=True)
        base_objs = self._build() if exp is self.design else build_objects(exp)[0]
        new_objs, sizes, _ = self._objects_for(exp, change, False)
        diff = diff_objects(base_objs, new_objs)
        items = []
        for c, (dx, dy) in change["moved"].items():
            x, y = base_layout.cols[c]
            items.append({"op": "move", "column": c, "element_id": f"COL-{c}", "from_ft": [x, y], "to_ft": [x + dx, y + dy],
                          "etabs": self.label_map()["by_element"].get(f"COL-{c}", [])})
        for c in change["removed"]:
            items.append({"op": "remove", "column": c, "element_id": f"COL-{c}", "at_ft": list(base_layout.cols[c]),
                          "etabs": self.label_map()["by_element"].get(f"COL-{c}", [])})
        e2k_path = os.path.join(jdir, "model.e2k")
        title = (exp.get("building") or {}).get("name", "calc-graph synthetic building")
        e2k.write_e2k(new_objs, e2k_path, title=title, note=f"proposed change {job_id}; sizes: {sizes}")
        change_doc = {"job_id": job_id, "change": change, "items": items, "etabs_diff": diff, "sizes": sizes}
        with open(os.path.join(jdir, "change.json"), "w") as fh:
            json.dump(change_doc, fh, indent=1, sort_keys=True)
        job = {"job_id": job_id, "adapter": "etabs", "status": "sent", "created_at": stamp.isoformat(timespec="seconds"),
               "change": change, "dir": jdir,
               "files": {"e2k": e2k_path, "change": os.path.join(jdir, "change.json"), "job": os.path.join(jdir, "job.json")},
               "diff_summary": {k: len(v) for k, v in diff.items()},
               "note": "MOCK: files written locally; nothing was sent to ETABS and ETABS did not run"}
        with open(job["files"]["job"], "w") as fh:
            json.dump(job, fh, indent=1, sort_keys=True)
        return job

    def pull_results(self, job: dict | str, force: bool = False) -> dict:
        """MOCK pull: re-runs calc-graph's design on the changed layout (synth.v2.design.run,
        PyNite frames inside, ~25 s) and returns results in ETABS result shapes; cached in
        <job dir>/results.json. Every row carries {"method": METHOD}."""
        job_id = job if isinstance(job, str) else job["job_id"]
        jdir = os.path.join(JOBS_DIR, job_id)
        rpath = os.path.join(jdir, "results.json")
        if os.path.exists(rpath) and not force:
            with open(rpath) as fh:
                return json.load(fh)
        with open(os.path.join(jdir, "change.json")) as fh:
            change = json.load(fh)["change"]
        objs, sizes, (d, exp2) = self._objects_for(self.design, change, True)
        base = {(o.kind, o.label, o.story): o for o in self._build() if o.kind in ("story_drift", "frame_design")}

        def tag(row):
            return {**row, "method": METHOD}
        drifts = []
        for o in objs:
            if o.kind != "story_drift":
                continue
            b = base.get(("story_drift", o.label, o.story))
            drifts.append(tag({**o.raw["Results.StoryDrifts"], "line": o.props["line"], "dc": o.props["dc"],
                               "record_id": o.record_ids[0], "element_id": o.element_id,
                               "base_Drift": b.raw["Results.StoryDrifts"]["Drift"] if b else None,
                               "base_dc": b.props["dc"] if b else None}))
        design_rows = []
        for o in objs:
            if o.kind != "frame_design":
                continue
            b = base.get(("frame_design", o.label, o.story))
            r = o.raw["DesignSteel.GetSummaryResults"]
            design_rows.append(tag({**r, "Label": o.label, "Story": o.story, "element_id": o.element_id,
                                    "section": o.props["section"], "record_ids": o.record_ids,
                                    "base_Ratio": b.raw["DesignSteel.GetSummaryResults"]["Ratio"] if b else None,
                                    "base_section": b.props["section"] if b else None}))
        reactions = [tag(r) for r in base_reactions(exp2)]
        base_react = {r["LoadCase"]: r for r in base_reactions(self.design)}
        for r in reactions:
            br = base_react.get(r["LoadCase"])
            r["base_FX"], r["base_FY"], r["base_FZ"] = (br["FX"], br["FY"], br["FZ"]) if br else (None, None, None)
        changed = [r for r in design_rows if r["base_section"] and r["section"] != r["base_section"]]
        summary = {
            "max_drift_dc": {ln: max((x["dc"] for x in drifts if x["line"] == ln), default=None) for ln in ("A", "D", "3")},
            "base_max_drift_dc": {ln: max((x["base_dc"] for x in drifts if x["line"] == ln and x["base_dc"] is not None), default=None)
                                  for ln in ("A", "D", "3")},
            "max_ratio": max((r["Ratio"] for r in design_rows), default=None),
            "frames_over_1": sorted(f"{r['Label']}@{r['Story']}" for r in design_rows if r["Ratio"] > 1.0),
            "sections_changed": len(changed),
            "sections_changed_list": [{"label": r["Label"], "story": r["Story"], "element_id": r["element_id"],
                                       "from": r["base_section"], "to": r["section"]} for r in changed],
            "infeasible": exp2.get("infeasible", []), "clashes": len(exp2.get("clashes", [])),
            "method": METHOD,
        }
        e2k_path = os.path.join(jdir, "model_redesigned.e2k")
        e2k.write_e2k(objs, e2k_path, title="calc-graph re-run of proposed change",
                      note=f"job {job_id}; sizes: {sizes}")
        res = {"job_id": job_id, "adapter": "etabs", "status": "complete", "completed_at": _now_et(),
               "change": change, "method": METHOD,
               "note": "MOCK: ETABS did not run. Values are calc-graph's own design re-run (PyNite) in ETABS result shapes.",
               "story_drifts": drifts, "frame_design": design_rows, "base_reactions": reactions, "summary": summary,
               "files": {"results": rpath, "e2k_redesigned": e2k_path}}
        with open(rpath, "w") as fh:
            json.dump(res, fh, indent=1, sort_keys=True, default=str)
        return res


def base_reactions(exp: dict) -> list[dict]:
    """Results.BaseReact-shaped rows per load case from calc records: gravity = sum of column
    base axial components (D incl. superimposed, L, Lr), lateral = ELF / MWFRS base shear.
    MX/MY/MZ are not computed by calc-graph and are None."""
    recs = {r["id"]: r for r in exp["records"]}
    cols = [r for r in exp["records"] if r["kind"] == "column_design"]
    pd = sum(r["values"].get("P_base_D") or 0 for r in cols)
    pl = sum(r["values"].get("P_base_L") or 0 for r in cols)
    plr = sum(r["values"].get("P_base_Lr") or 0 for r in cols)
    rows = [("Dead", 0.0, 0.0, pd, [r["id"] for r in cols]), ("SDL", 0.0, 0.0, 0.0, []),
            ("Live", 0.0, 0.0, pl, [r["id"] for r in cols]), ("Lr", 0.0, 0.0, plr, [r["id"] for r in cols])]
    for case, rid, d in (("EQX", "C-ELF:X", "x"), ("EQY", "C-ELF:Y", "y"), ("WX", "C-WIND:X", "x"), ("WY", "C-WIND:Y", "y")):
        v = recs.get(rid, {}).get("values", {}).get("V_k")
        if v is None:
            continue
        rows.append((case, -v if d == "x" else 0.0, -v if d == "y" else 0.0, 0.0, [rid]))
    return [{"LoadCase": c, "StepType": "", "StepNum": 0.0, "FX": round(fx, 1), "FY": round(fy, 1), "FZ": round(fz, 1),
             "MX": None, "ParamMy": None, "MZ": None, "gx": 0.0, "gy": 0.0, "gz": 0.0, "record_ids": rids,
             "note": ("the design does not split D: this Dead row is all of D (steel + area D + walls); the .e2k "
                      "puts steel self weight in Dead and area D + walls in SDL, so compare Dead + SDL")
             if c in ("Dead", "SDL") else ""}
            for c, fx, fy, fz, rids in rows]


def _design_area_totals(exp: dict) -> dict[str, dict[str, float]]:
    """{level: {"D": kip, "L": kip, "Lr": kip}} from the calc A2 area_load records alone (extents
    and psf; where extents overlap the first record wins, as synth.v2.model.area_at does)."""
    recs = [r["values"] for r in exp["records"] if r["kind"] == "area_load"]
    out: dict[str, dict[str, float]] = {}
    for lv in sorted({v["level"] for v in recs}):
        zs = [v for v in recs if v["level"] == lv]
        xb = sorted({v["extent_ft"][i] for v in zs for i in (0, 2)})
        yb = sorted({v["extent_ft"][i] for v in zs for i in (1, 3)})
        tot = {"D": 0.0, "L": 0.0, "Lr": 0.0}
        for x0, x1 in zip(xb, xb[1:]):
            for y0, y1 in zip(yb, yb[1:]):
                cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
                v = next((v for v in zs if v["extent_ft"][0] <= cx <= v["extent_ft"][2]
                          and v["extent_ft"][1] <= cy <= v["extent_ft"][3]), None)
                if v:
                    a = (x1 - x0) * (y1 - y0)
                    tot["D"] += a * v["D_psf"] / 1000
                    tot["L"] += a * v["L_psf"] / 1000
                    tot["Lr"] += a * v["Lr_psf"] / 1000
        out[lv] = tot
    return out


def _columns_oriented(parsed: dict, exp: dict) -> bool:
    """Every column LINEASSIGN's ANG is what synth.v2.model.column_depth_axis gives the design
    element (0 = depth along X, 90 = along Y): the e2k cannot drift from the IFC / drawings / calcs."""
    from synth.v2.model import column_depth_axis
    by_el = EtabsAdapter(exp).label_map()["by_element"]
    ang = {(a["label"], a["story"]): float(a.get("ang") or 0.0) for a in parsed["line_assigns"]}
    cols = [e for e in exp["elements"] if e["type"] == "column"]
    for e in cols:
        want = 0.0 if column_depth_axis(e.get("roles", [])) == "x" else 90.0
        for seg in by_el.get(e["id"], []):
            got = ang.get((seg["label"], seg["story"]))
            if got is None or abs(got - want) > 1e-6:
                return False
    return bool(cols)


def e2k_load_check(path: str, exp: dict, tol: float = 0.01) -> dict:
    """Read an .e2k back (e2k.read_e2k + e2k.load_summary) and compare what ETABS will be given
    with design.json: total D (self weight + SDL), L and Lr against the column base reactions;
    L and Lr per level against the calc A2 area records; the mass-source weight per level against
    C-ELF W_by_level; the implied ELF V and story forces against C-ELF; wind story forces against
    C-WIND. rows: [{quantity, level, e2k, design, rel_err, ok}]; ok = every |rel_err| <= tol and
    the model has areas + diaphragm points on every story above Base and a mass source."""
    from synth.v2 import aisc
    parsed = e2k.read_e2k(path)
    sm = e2k.load_summary(parsed, lambda shape: aisc.get(shape)["A"] / 144.0)
    recs = {r["id"]: r for r in exp["records"]}
    cols = [r["values"] for r in exp["records"] if r["kind"] == "column_design"]
    lv_story = {lv: n for n, lv, _, _ in stories()}
    above = [n for n, lv, _, _ in stories() if lv != "L1"]
    V = sm["vertical"]
    rows = []

    def row(q, level, got, want):
        err = (got - want) / want if want else (0.0 if abs(got) < 1e-9 else float("inf"))
        rows.append({"quantity": q, "level": level, "e2k": round(got, 2), "design": round(want, 2),
                     "rel_err": round(err, 5), "ok": abs(err) <= tol})

    tot = lambda pats: sum(V[s].get(p, 0.0) for s in V for p in pats)   # noqa: E731
    row("Dead + SDL (base vertical)", "all", tot(["Dead", "SDL"]), sum(c.get("P_base_D") or 0 for c in cols))
    row("Live (base vertical)", "all", tot(["Live"]), sum(c.get("P_base_L") or 0 for c in cols))
    row("Roof live (base vertical)", "all", tot(["Lr"]), sum(c.get("P_base_Lr") or 0 for c in cols))
    area = _design_area_totals(exp)
    for lv, t in area.items():
        s = lv_story[lv]
        for pat, k in (("Live", "L"), ("Lr", "Lr")):
            if t[k]:
                row(pat, lv, V[s].get(pat, 0.0), t[k])
    elf = {d: recs[f"C-ELF:{d}"]["values"] for d in ("X", "Y") if f"C-ELF:{d}" in recs}
    if elf:
        wl = next(iter(elf.values()))["W_by_level_k"]
        for lv, w in wl.items():
            row("Seismic weight (mass source)", lv, sm["mass_weight"][lv_story[lv]], w)
        row("Seismic weight (mass source)", "all", sum(sm["mass_weight"][s] for s in above), next(iter(elf.values()))["W_k"])
    for d, v in elf.items():
        for name, sp in sm["seismic"].items():
            if name.startswith(f"EQ{d}"):
                row(f"{name} base shear", "all", sp["V"], v["V_k"])
                for lv, f in v["Fx_k"].items():
                    row(f"{name} story force", lv, sp["Fx"][lv_story[lv]], f)
    for d, k in (("X", 0), ("Y", 1)):
        w = recs.get(f"C-WIND:{d}")
        if w:
            for lv, f in w["values"]["Fx_k"].items():
                row(f"W{d} story force", lv, sm["lateral"].get(f"W{d}", {}).get(lv_story[lv], [0, 0])[k], f)
    struct = {"areas_on_every_story": all(sm["areas_by_story"].get(s) for s in above),
              "diaphragm_points_on_every_story": all(sm["diaphragm_points"].get(s) for s in above),
              "rigid_diaphragm": any(str(v.get("TYPE", "")).upper() == "RIGID" for v in parsed["diaphragms"].values()),
              "mass_source_loads_only": any(str(m.get("INCLUDEELEMENTS")).lower() == "no" and m["loads"]
                                            for m in parsed["mass_sources"].values()),
              "sdl_type_super_dead": parsed["load_patterns"].get("SDL", {}).get("TYPE") == "Super Dead",
              "units_kip_ft": parsed["units"] == ["KIP", "FT", "F"],
              "one_eccentricity_per_seismic_pattern": all(" " not in str(v.get("DIR", "")) for v in parsed["seismic"].values()),
              "combos_15_design": sum(1 for c in parsed["combos"].values() if c.get("TYPE") == "Linear Add") == 15,
              "column_orientation_matches_design": _columns_oriented(parsed, exp)}
    ok = all(r["ok"] for r in rows) and all(struct.values())
    return {"path": path, "rows": rows, "structure": struct, "max_abs_rel_err": max(abs(r["rel_err"]) for r in rows),
            "summary": sm, "ok": ok}


def diff_objects(a: list[AnalysisObject], b: list[AnalysisObject]) -> dict:
    """Frame / point differences between two builds keyed by (label, story)."""
    fa = {(o.label, o.story): o for o in a if o.kind == "frame"}
    fb = {(o.label, o.story): o for o in b if o.kind == "frame"}
    pa = {(o.label, o.story): o for o in a if o.kind == "point"}
    pb = {(o.label, o.story): o for o in b if o.kind == "point"}

    def row(o):
        return {"label": o.label, "story": o.story, "element_id": o.element_id}

    def moved(x, y):
        return any(abs(u - v) > TOL for p, q in (("xyz_i", "xyz_i"), ("xyz_j", "xyz_j")) for u, v in zip(x.props[p], y.props[q]))
    return {
        "frames_removed": [row(fa[k]) for k in fa if k not in fb],
        "frames_added": [row(fb[k]) for k in fb if k not in fa],
        "frames_moved": [row(fb[k]) for k in fb if k in fa and moved(fa[k], fb[k])],
        "frames_resized": [{**row(fb[k]), "from": fa[k].props["section"], "to": fb[k].props["section"]}
                           for k in fb if k in fa and fa[k].props["section"] != fb[k].props["section"]],
        "points_moved": [row(pb[k]) for k in pb if k in pa and (abs(pa[k].props["x_ft"] - pb[k].props["x_ft"]) > TOL
                                                                  or abs(pa[k].props["y_ft"] - pb[k].props["y_ft"]) > TOL)],
        "points_added": [row(pb[k]) for k in pb if k not in pa],
        "points_removed": [row(pa[k]) for k in pa if k not in pb],
    }
