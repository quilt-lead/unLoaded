"""Write the synthetic BHoM-JSON fixtures the BHoM converter and the bhom_etabs adapter are
developed against: data/fixtures/bhom/portal_model.json (+ portal_results.json).

SYNTHETIC, OURS. Hand-built in the shape BHoM's Serialiser writes (see
schema/adapters/bhom_json.py for the wire rules) and the shape BHoM's ETABS adapter is
expected to return (ETABSId fragments, SI units). No BHoM or ETABS produced these files;
the result numbers are invented placeholders for plumbing, NOT an analysis of the frame.
When the Windows bridge returns real BHoM JSON, capture one into this folder beside these
and run scripts/bhom_roundtrip.py on it.

Model: a two-storey, two-bay steel frame on grid A-C (2 x 9 m), storeys 4 m. Columns
W14X48 (fixed bases on A, pinned elsewhere), beams W18X40 (bay A-B moment connected,
bay B-C pinned), ASTM A992 Gr 50. Section properties are AISC v16 values (synth/v2/aisc.py
subset) converted to SI here.

    uv run python scripts/make_bhom_fixtures.py
"""
from __future__ import annotations

import json
import os
import sys
import uuid

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path[:0] = [os.path.join(ROOT, "backend"), ROOT]

from calcgraph.schema.units import convert  # noqa: E402
from synth.v2 import aisc  # noqa: E402

OUT = os.path.join(ROOT, "data", "fixtures", "bhom")
NS = uuid.UUID("0b6f5d0e-31f4-4c62-8f9a-0c1f7f3a9e21")
S = "BH.oM.Structure."


def guid(key: str) -> str:
    return str(uuid.uuid5(NS, key))


def vec(x=0.0, y=0.0, z=0.0, t="BH.oM.Geometry.Vector"):
    return {"_t": t, "X": float(x), "Y": float(y), "Z": float(z)}


def etabs_id(uid, label, story):
    return [{"_t": "BH.oM.Adapters.ETABS.ETABSId", "Id": uid, "Label": label, "Story": story, "PersistentId": None}]


def c6(name, flags, ks=None):
    """flags: 6 x 'Fixed'/'Free'/'Spring'; ks: optional stiffnesses (N/m, N*m/rad)."""
    ks = ks or [0.0] * 6
    keys = ["TranslationX", "TranslationY", "TranslationZ", "RotationX", "RotationY", "RotationZ"]
    kkeys = ["TranslationalStiffnessX", "TranslationalStiffnessY", "TranslationalStiffnessZ", "RotationalStiffnessX",
             "RotationalStiffnessY", "RotationalStiffnessZ"]
    d = {"_t": S + "Constraints.Constraint6DOF", "BHoM_Guid": guid("c6:" + name + str(flags) + str(ks)), "Name": name}
    for k, kk, f, kv in zip(keys, kkeys, flags, ks):
        d[kk] = kv
        d[k] = f
    return d


STEEL = {"_t": S + "MaterialFragments.Steel", "BHoM_Guid": guid("mat:A992"), "Name": "A992Fy50",
         "Density": 7849.05, "DampingRatio": 0.0, "PoissonsRatio": 0.3, "ThermalExpansionCoeff": 1.17e-5,
         "YoungsModulus": convert(29000, "ksi", "Pa"), "YieldStress": convert(50, "ksi", "Pa"),
         "UltimateStress": convert(65, "ksi", "Pa")}


def section(name):
    a = aisc.get(name)
    si = lambda v, u_in, u_si: convert(v, u_in, u_si) if v is not None else 0.0  # noqa: E731
    return {"_t": S + "SectionProperties.SteelSection", "BHoM_Guid": guid("sec:" + name), "Name": name,
            "Fabrication": "HotRolled", "PlateRestraint": "NoRestraint", "Material": STEEL,
            "SectionProfile": {"_t": "BH.oM.Spatial.ShapeProfiles.ISectionProfile", "Shape": "ISection",
                               "Height": si(a["d"], "in", "m"), "Width": si(a["bf"], "in", "m"),
                               "WebThickness": si(a["tw"], "in", "m"), "FlangeThickness": si(a["tf"], "in", "m"),
                               "RootRadius": 0.0, "ToeRadius": 0.0, "Edges": []},
            "Area": si(a["A"], "in2", "m2"), "Rgy": si(a["rx"], "in", "m"), "Rgz": si(a["ry"], "in", "m"),
            "J": si(a["J"], "in4", "m4"), "Iy": si(a["Ix"], "in4", "m4"), "Iz": si(a["Iy"], "in4", "m4"),
            "Iw": si(a["Cw"], "in6", "m6"), "Wely": si(a["Sx"], "in3", "m3"), "Welz": si(a["Sy"], "in3", "m3"),
            "Wply": si(a["Zx"], "in3", "m3"), "Wplz": si(a["Zy"], "in3", "m3"),
            # geometric constants BHoM derives from the profile; values here are placeholders
            "CentreZ": 0.0, "CentreY": 0.0, "Vz": 0.0, "Vpz": 0.0, "Vy": 0.0, "Vpy": 0.0,
            "Asy": 0.0, "Asz": si(a["d"] * a["tw"], "in2", "m2")}


GRID = {"A": 0.0, "B": 9.0, "C": 18.0}
STORIES = [("Base", 0.0), ("Story1", 4.0), ("Story2", 8.0)]
FIXED_BASE = {"A"}


def build():
    nodes = {}
    n = 0
    for g, x in GRID.items():
        n += 1
        for st, z in STORIES:
            sup = None
            if st == "Base":
                sup = c6("Fixed" if g in FIXED_BASE else "Pin",
                         ["Fixed"] * 6 if g in FIXED_BASE else ["Fixed"] * 3 + ["Free"] * 3)
            nodes[(g, st)] = {"_t": S + "Elements.Node", "BHoM_Guid": guid(f"node:{g}:{st}"), "Name": "",
                              "Fragments": etabs_id(f"{n}@{st}", str(n), st),
                              "Position": vec(x, 0.0, z, "BH.oM.Geometry.Point"), "Orientation": None, "Support": sup}
    col, beam = section("W14X48"), section("W18X40")
    fixfix = None  # BHoM: Release null = full fixity
    pinpin = {"_t": S + "Constraints.BarRelease", "BHoM_Guid": guid("rel:pinpin"), "Name": "PinPin",
              "StartRelease": c6("Pin", ["Fixed"] * 4 + ["Free"] * 2),
              "EndRelease": c6("Pin", ["Fixed"] * 4 + ["Free"] * 2)}
    bars = []
    u = 0
    for i, g in enumerate(GRID):
        for k in range(1, len(STORIES)):
            u += 1
            st = STORIES[k][0]
            bars.append({"_t": S + "Elements.Bar", "BHoM_Guid": guid(f"col:{g}:{st}"), "Name": "",
                         "Fragments": etabs_id(str(u), f"C{i + 1}", st),
                         "Start": nodes[(g, STORIES[k - 1][0])], "End": nodes[(g, st)], "SectionProperty": col,
                         "OrientationAngle": 0.0, "Release": None, "FEAType": "Flexural", "Support": None,
                         "Offset": None})
    gl = list(GRID)
    for j in range(len(gl) - 1):
        for st, _ in STORIES[1:]:
            u += 1
            off = None
            if j == 0:
                off = {"_t": S + "Offsets.Offset", "BHoM_Guid": guid(f"off:{j}:{st}"), "Name": "",
                       "Start": vec(0.178, 0, 0), "End": vec(-0.178, 0, 0)}
            bars.append({"_t": S + "Elements.Bar", "BHoM_Guid": guid(f"beam:{j}:{st}"), "Name": "",
                         "Fragments": etabs_id(str(u), f"B{j + 1}", st),
                         "Start": nodes[(gl[j], st)], "End": nodes[(gl[j + 1], st)], "SectionProperty": beam,
                         "OrientationAngle": 0.0, "Release": fixfix if j == 0 else pinpin, "FEAType": "Flexural",
                         "Support": None, "Offset": off})
    cases = {name: {"_t": S + "Loads.Loadcase", "BHoM_Guid": guid("case:" + name), "Name": name, "Nature": nat,
                    "Number": i + 1}
             for i, (name, nat) in enumerate([("Dead", "Dead"), ("SDL", "SuperDead"), ("Live", "Live"),
                                              ("EQX", "Seismic"), ("WX", "Wind")])}
    combos = [
        {"_t": S + "Loads.LoadCombination", "BHoM_Guid": guid("combo:1"), "Name": "1.2D+1.6L", "Number": 101,
         "LoadCases": [[1.2, cases["Dead"]], [1.2, cases["SDL"]], [1.6, cases["Live"]]]},
        {"_t": S + "Loads.LoadCombination", "BHoM_Guid": guid("combo:2"), "Name": "1.4D+0.5L+1.0EQX", "Number": 102,
         "LoadCases": [[1.4, cases["Dead"]], [1.4, cases["SDL"]], [0.5, cases["Live"]], [1.0, cases["EQX"]]]},
    ]
    beams = [b for b in bars if b["Fragments"][0]["Label"].startswith("B")]
    roof = [b for b in beams if b["Fragments"][0]["Story"] == "Story2"]
    grp = lambda items, t: {"_t": f"BH.oM.Base.BHoMGroup<{t}>", "BHoM_Guid": guid("grp:" + ",".join(  # noqa: E731
        i["BHoM_Guid"] for i in items)), "Name": "", "Elements": items}
    loads = [
        {"_t": S + "Loads.GravityLoad", "BHoM_Guid": guid("load:sw"), "Name": "self weight",
         "GravityDirection": vec(0, 0, -1), "Loadcase": cases["Dead"], "Objects": grp(bars, S + "Elements.Bar"),
         "Axis": "Global", "Projected": False},
        {"_t": S + "Loads.BarUniformlyDistributedLoad", "BHoM_Guid": guid("load:sdl"), "Name": "SDL beams",
         "Force": vec(0, 0, -12000.0), "Moment": vec(), "Loadcase": cases["SDL"],
         "Objects": grp(beams, S + "Elements.Bar"), "Axis": "Global", "Projected": False},
        {"_t": S + "Loads.BarVaryingDistributedLoad", "BHoM_Guid": guid("load:live-tri"), "Name": "live triangle",
         "StartPosition": 0.0, "ForceAtStart": vec(0, 0, 0.0), "MomentAtStart": vec(), "EndPosition": 1.0,
         "ForceAtEnd": vec(0, 0, -18000.0), "MomentAtEnd": vec(), "Loadcase": cases["Live"],
         "Objects": grp(roof[:1], S + "Elements.Bar"), "Axis": "Global", "Projected": False, "RelativePositions": True},
        {"_t": S + "Loads.BarPointLoad", "BHoM_Guid": guid("load:live-pt"), "Name": "live point",
         "DistanceFromA": 4.5, "Force": vec(0, 0, -40000.0), "Moment": vec(), "Loadcase": cases["Live"],
         "Objects": grp(roof[1:2], S + "Elements.Bar"), "Axis": "Global", "Projected": False},
        {"_t": S + "Loads.PointLoad", "BHoM_Guid": guid("load:eqx"), "Name": "EQX roof",
         "Force": vec(60000.0, 0, 0), "Moment": vec(), "Loadcase": cases["EQX"],
         "Objects": grp([nodes[("A", "Story2")]], S + "Elements.Node"), "Axis": "Global", "Projected": False},
        {"_t": S + "Loads.PointLoad", "BHoM_Guid": guid("load:wx"), "Name": "WX roof",
         "Force": vec(35000.0, 0, 0), "Moment": vec(0, 0, 0), "Loadcase": cases["WX"],
         "Objects": grp([nodes[("A", "Story2")], nodes[("A", "Story1")]], S + "Elements.Node"), "Axis": "Global",
         "Projected": False},
    ]
    requests = [
        {"_t": S + "Requests.BarResultRequest", "ResultType": "BarForce", "DivisionType": "EvenlyDistributed",
         "Divisions": 3, "Cases": [combos[0], combos[1]], "Modes": [], "ObjectIds": []},
        {"_t": S + "Requests.NodeResultRequest", "ResultType": "NodeReaction", "Axis": "Global",
         "Cases": [combos[0]], "Modes": [], "ObjectIds": []},
        {"_t": S + "Requests.GlobalResultRequest", "ResultType": "StoreyDrifts", "Cases": [cases["EQX"]], "Modes": [],
         "ObjectIds": []},
    ]
    model = [STEEL, col, beam, *nodes.values(), *bars, *cases.values(), *combos, *loads, *requests]

    # ---- results: PLACEHOLDER numbers (no analysis), shaped like BHoM result objects
    results = []
    for b in beams:
        uid = b["Fragments"][0]["Id"]
        for pos, m in ((0.0, -150000.0), (0.5, 110000.0), (1.0, -150000.0)):
            results.append({"_t": S + "Results.BarForce", "ObjectId": uid, "ResultCase": "1.2D+1.6L", "ModeNumber": 0,
                            "TimeStep": 0.0, "Position": pos, "Divisions": 3, "FX": 0.0, "FY": 0.0,
                            "FZ": 80000.0 * (1 - 2 * pos), "MX": 0.0, "MY": m, "MZ": 0.0})
    for g in GRID:
        results.append({"_t": S + "Results.NodeReaction", "ObjectId": f"{list(GRID).index(g) + 1}@Base",
                        "ResultCase": "1.2D+1.6L", "ModeNumber": 0, "TimeStep": 0.0,
                        "Orientation": None, "FX": 0.0, "FY": 0.0, "FZ": 250000.0, "MX": 0.0,
                        "MY": 30000.0 if g in FIXED_BASE else 0.0, "MZ": 0.0})
    results.append({"_t": S + "Results.GlobalReactions", "ObjectId": "", "ResultCase": "EQX", "ModeNumber": 0,
                    "TimeStep": 0.0, "FX": -60000.0, "FY": 0.0, "FZ": 0.0, "MX": 0.0, "MY": 0.0, "MZ": 0.0})
    for st, r in (("Story1", 0.0042), ("Story2", 0.0061)):
        results.append({"_t": S + "Results.StoreyDrift", "ObjectId": "", "ResultCase": "EQX", "ModeNumber": 0,
                        "TimeStep": 0.0, "Storey": st, "Direction": vec(1, 0, 0), "Ratio": r})
    for b in beams[:2]:
        results.append({"_t": S + "Results.SteelUtilisation", "ObjectId": b["Fragments"][0]["Id"],
                        "ResultCase": "1.2D+1.6L", "ModeNumber": 0, "TimeStep": 0.0, "Position": 0.5, "Divisions": 0,
                        "MajorEffectiveLength": "", "MinorEffectiveLength": "", "SteelClass": 0,
                        "TensionCompressionRatio": 0.02, "MajorShearRatio": 0.31, "MinorShearRatio": 0.0,
                        "MajorBendingRatio": 0.74, "MinorBendingRatio": 0.0, "BiaxialBendingAxialRatio": 0.76})
    return model, results


def main():
    os.makedirs(OUT, exist_ok=True)
    model, results = build()
    for name, objs in (("portal_model.json", model), ("portal_results.json", results)):
        path = os.path.join(OUT, name)
        with open(path, "w") as fh:
            json.dump(objs, fh, indent=1)
        print(f"wrote {os.path.relpath(path, ROOT)}: {len(objs)} top-level objects")


if __name__ == "__main__":
    main()
