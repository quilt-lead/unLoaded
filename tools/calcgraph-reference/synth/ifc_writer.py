"""Write the logical building to IFC4 with IfcOpenShell.

Byte-stable: GlobalIds are uuid5 of each element's logical key (so they are also
stable across model revisions), the header timestamp is fixed, and entities are
created in a fixed order. The IFC plumbing is shared with the plans-to-IFC builder
(synth.ifc_common).
"""
from __future__ import annotations

import uuid

import numpy as np

from .ifc_common import IfcBuilder

from . import shapes
from .building import LEVELS, Building, El

NS = uuid.UUID("8d016bdf-53b1-411f-8536-d9c9f73e8546")
STOREYS = [("Foundation", -1.5), ("Level 1", 0.0)] + [(n, z) for n, z, _ in LEVELS]
PREDEFINED = {"IfcBeam": "BEAM", "IfcColumn": "COLUMN", "IfcFooting": "PAD_FOOTING", "IfcPlate": "NOTDEFINED",
              "IfcMember": "BRACE", "IfcWall": "SOLIDWALL"}


def guid_for(key: str) -> str:
    import ifcopenshell.guid
    return ifcopenshell.guid.compress(uuid.uuid5(NS, key).hex)


def write(b: Building, path: str, timestamp: str = "2026-11-14T09:00:00") -> dict[str, str]:
    """Returns {element key: GlobalId}."""
    B = IfcBuilder(path, namespace=NS, project_name="Sample Office Building",
                   project_description="Synthetic steel frame - calc-graph", project_phase=b.label,
                   building_name="Sample Office Building", storeys=STOREYS, author="calc-graph synth",
                   originating_system="calc-graph synth generator", timestamp=timestamp)

    def i_profile(name: str):
        s = shapes.w_si(name)
        return B.i_profile(name, s["bf"], s["d"], s["tw"], s["tf"])

    def hss_profile(name: str):
        s = shapes.hss_si(name)
        return B.rect_hollow_profile(name, s["b"], s["b"], s["t"])

    def shape_of(e: El):
        g = e.geom
        if g["kind"] == "box":
            mn, mx = np.array(g["min"]), np.array(g["max"])
            size = mx - mn
            prof = B.rect_profile(size[0], size[1])
            centre = (mn + mx) / 2
            return B.ax((centre[0], centre[1], mn[2])), B.solid(prof, size[2])
        if g["kind"] == "column":
            x, y, z0 = g["base"]
            # depth along global X: profile x -> RefDirection (0,1,0), profile y -> Z x X = (-1,0,0)
            return B.ax((x, y, z0), (0, 0, 1), (0, 1, 0)), B.solid(i_profile(g["section"]), g["top"] - z0)
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
            return B.ax(tuple(origin), tuple(zdir), tuple(xdir)), B.solid(prof, length)
        raise ValueError(g["kind"])

    gids: dict[str, str] = {}
    for e in b.elements:
        placement_ax, sol = shape_of(e)
        cls = e.ifc_class
        if cls == "IfcSlab":
            pre = "ROOF" if e.storey == "Roof" else "FLOOR"
        elif cls in PREDEFINED:
            pre = PREDEFINED[cls]
        else:
            raise ValueError(cls)
        inst, gid = B.product(cls, e.key, e.name, e.object_type, placement_ax, sol, e.storey, pre)
        gids[e.key] = gid
        B.psets(inst, e.key, e.psets)
    B.write(path)
    return gids
