"""Write the logical building to IFC4 with IfcOpenShell.

Byte-stable: GlobalIds are uuid5 of each element's logical key (so they are also
stable across model revisions), the header timestamp is fixed, and entities are
created in a fixed order.
"""
from __future__ import annotations

import uuid

import ifcopenshell
import ifcopenshell.guid
import numpy as np

from . import shapes
from .building import LEVELS, Building, El

NS = uuid.UUID("8d016bdf-53b1-411f-8536-d9c9f73e8546")
STOREYS = [("Foundation", -1.5), ("Level 1", 0.0)] + [(n, z) for n, z, _ in LEVELS]


def guid_for(key: str) -> str:
    return ifcopenshell.guid.compress(uuid.uuid5(NS, key).hex)


def write(b: Building, path: str, timestamp: str = "2026-11-14T09:00:00") -> dict[str, str]:
    """Returns {element key: GlobalId}."""
    f = ifcopenshell.file(schema="IFC4")
    f.header.file_name.name = path.rsplit("/", 1)[-1]
    f.header.file_name.time_stamp = timestamp
    f.header.file_name.author = ("calc-graph synth",)
    f.header.file_name.organization = ("calc-graph",)
    f.header.file_name.preprocessor_version = "IfcOpenShell"
    f.header.file_name.originating_system = "calc-graph synth generator"
    f.header.file_name.authorization = "none"
    f.header.file_description.description = ("ViewDefinition [ReferenceView]",)

    def pt(*c):
        return f.createIfcCartesianPoint(tuple(float(v) for v in c))

    def dirn(*c):
        return f.createIfcDirection(tuple(float(v) for v in c))

    def ax(loc, z=(0, 0, 1), x=(1, 0, 0)):
        return f.createIfcAxis2Placement3D(pt(*loc), dirn(*z), dirn(*x))

    units = f.createIfcUnitAssignment([
        f.createIfcSIUnit(None, "LENGTHUNIT", None, "METRE"),
        f.createIfcSIUnit(None, "AREAUNIT", None, "SQUARE_METRE"),
        f.createIfcSIUnit(None, "VOLUMEUNIT", None, "CUBIC_METRE"),
        f.createIfcSIUnit(None, "PLANEANGLEUNIT", None, "RADIAN"),
    ])
    ctx = f.createIfcGeometricRepresentationContext(None, "Model", 3, 1e-5, ax((0, 0, 0)), None)
    body = f.createIfcGeometricRepresentationSubContext("Body", "Model", None, None, None, None, ctx, None, "MODEL_VIEW", None)
    project = f.createIfcProject(guid_for("project"), None, "Sample Office Building", "Synthetic steel frame - calc-graph",
                                 None, None, b.label, [ctx], units)
    site_pl = f.createIfcLocalPlacement(None, ax((0, 0, 0)))
    site = f.createIfcSite(guid_for("site"), None, "Site", None, None, site_pl, None, None, "ELEMENT", None, None, None, None, None)
    bldg_pl = f.createIfcLocalPlacement(site_pl, ax((0, 0, 0)))
    bldg = f.createIfcBuilding(guid_for("building"), None, "Sample Office Building", None, None, bldg_pl, None, None, "ELEMENT",
                               None, None, None)
    f.createIfcRelAggregates(guid_for("rel:project-site"), None, None, None, project, [site])
    f.createIfcRelAggregates(guid_for("rel:site-building"), None, None, None, site, [bldg])
    storeys = {}
    for name, z in STOREYS:
        pl = f.createIfcLocalPlacement(bldg_pl, ax((0, 0, z)))
        storeys[name] = f.createIfcBuildingStorey(guid_for(f"storey:{name}"), None, name, None, None, pl, None, None, "ELEMENT", z)
    f.createIfcRelAggregates(guid_for("rel:building-storeys"), None, None, None, bldg, list(storeys.values()))

    profiles: dict[str, object] = {}

    def i_profile(name: str):
        if name not in profiles:
            s = shapes.w_si(name)
            profiles[name] = f.createIfcIShapeProfileDef("AREA", name, None, s["bf"], s["d"], s["tw"], s["tf"], None, None, None)
        return profiles[name]

    def hss_profile(name: str):
        if name not in profiles:
            s = shapes.hss_si(name)
            profiles[name] = f.createIfcRectangleHollowProfileDef("AREA", name, None, s["b"], s["b"], s["t"], None, None)
        return profiles[name]

    def solid(profile, depth: float):
        return f.createIfcExtrudedAreaSolid(profile, None, dirn(0, 0, 1), float(depth))

    def shape_of(e: El):
        g = e.geom
        if g["kind"] == "box":
            mn, mx = np.array(g["min"]), np.array(g["max"])
            size = mx - mn
            prof = f.createIfcRectangleProfileDef("AREA", None, None, float(size[0]), float(size[1]))
            centre = (mn + mx) / 2
            return ax((centre[0], centre[1], mn[2])), solid(prof, size[2])
        if g["kind"] == "column":
            x, y, z0 = g["base"]
            # depth along global X: profile x -> RefDirection (0,1,0), profile y -> Z x X = (-1,0,0)
            return ax((x, y, z0), (0, 0, 1), (0, 1, 0)), solid(i_profile(g["section"]), g["top"] - z0)
        if g["kind"] in ("member", "brace"):
            p1, p2 = np.array(g["p1"], float), np.array(g["p2"], float)
            d = p2 - p1
            length = float(np.linalg.norm(d))
            zdir = d / length
            up = np.array([0.0, 0.0, 1.0])
            xdir = np.cross(up, zdir)
            xdir /= np.linalg.norm(xdir)
            if g["kind"] == "member":
                depth = shapes.w_si(g["section"])["d"]
                origin = p1 - up * depth / 2  # top of steel on the level line
                prof = i_profile(g["section"])
            else:
                origin = p1
                prof = hss_profile(g["section"])
            return ax(tuple(origin), tuple(zdir), tuple(xdir)), solid(prof, length)
        raise ValueError(g["kind"])

    by_storey: dict[str, list] = {}
    gids: dict[str, str] = {}
    for e in b.elements:
        placement_ax, sol = shape_of(e)
        rep = f.createIfcShapeRepresentation(body, "Body", "SweptSolid", [sol])
        pds = f.createIfcProductDefinitionShape(None, None, [rep])
        lp = f.createIfcLocalPlacement(None, placement_ax)
        gid = guid_for(e.key)
        gids[e.key] = gid
        cls = e.ifc_class
        if cls == "IfcBeam":
            inst = f.createIfcBeam(gid, None, e.name, None, e.object_type, lp, pds, None, "BEAM")
        elif cls == "IfcColumn":
            inst = f.createIfcColumn(gid, None, e.name, None, e.object_type, lp, pds, None, "COLUMN")
        elif cls == "IfcSlab":
            inst = f.createIfcSlab(gid, None, e.name, None, e.object_type, lp, pds, None, "ROOF" if e.storey == "Roof" else "FLOOR")
        elif cls == "IfcFooting":
            inst = f.createIfcFooting(gid, None, e.name, None, e.object_type, lp, pds, None, "PAD_FOOTING")
        elif cls == "IfcPlate":
            inst = f.createIfcPlate(gid, None, e.name, None, e.object_type, lp, pds, None, "NOTDEFINED")
        elif cls == "IfcMember":
            inst = f.createIfcMember(gid, None, e.name, None, e.object_type, lp, pds, None, "BRACE")
        elif cls == "IfcWall":
            inst = f.createIfcWall(gid, None, e.name, None, e.object_type, lp, pds, None, "SOLIDWALL")
        else:
            raise ValueError(cls)
        by_storey.setdefault(e.storey, []).append(inst)
        for pname, props in e.psets.items():
            vals = [f.createIfcPropertySingleValue(k, None, f.createIfcLabel(str(v)), None) for k, v in props.items()]
            ps = f.createIfcPropertySet(guid_for(f"pset:{e.key}:{pname}"), None, pname, None, vals)
            f.createIfcRelDefinesByProperties(guid_for(f"rel:pset:{e.key}:{pname}"), None, None, None, [inst], ps)
    for name, items in by_storey.items():
        f.createIfcRelContainedInSpatialStructure(guid_for(f"rel:contain:{name}"), None, None, None, items, storeys[name])
    f.write(path)
    return gids
