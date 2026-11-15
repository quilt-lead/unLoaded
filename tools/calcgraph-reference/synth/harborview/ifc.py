"""Write a Harborview model revision to IFC4 (the shared IfcBuilder: byte-stable, uuid5 GlobalIds).

GlobalId = uuid5(NS, element id), so an element keeps its GlobalId across rev 1 and rev 2 (the diff keys on it).
Geometry comes from the bundle (metres, Z up): steel members are I / HSS profiles swept along their axis,
caissons are circles, everything else (pile caps, slabs, walls, base plates, joints) is its bounding box.
Every element carries "Identity Data".Mark (the space-free mark the calcs use) and a "Structural" pset.
"""
from __future__ import annotations

import uuid

import numpy as np

from .. import shapes
from ..ifc_common import IfcBuilder
from .model import Element, Model, norm_size

NS = uuid.UUID("5f0b8f3e-2a8e-4d55-9a37-3c1b6a0e7d21")
PREDEFINED = {"IfcBeam": "BEAM", "IfcColumn": "COLUMN", "IfcMember": "BRACE", "IfcSlab": "FLOOR", "IfcWall": "SHEAR",
              "IfcFooting": "PILE_CAP", "IfcPile": "BORED", "IfcPlate": "NOTDEFINED"}
ROLE = {"beam": "girder", "column": "column", "brace": "brace", "slab": "floor slab", "wall": "core shear wall",
        "footing": "pile cap", "pile": "caisson", "connection": "connection"}


def guid_for(element_id: str) -> str:
    import ifcopenshell.guid
    return ifcopenshell.guid.compress(uuid.uuid5(NS, element_id).hex)


def write(m: Model, path: str, timestamp: str = "2026-11-15T09:00:00") -> dict[str, str]:
    """Returns {element id: GlobalId}."""
    B = IfcBuilder(path, namespace=NS, project_name=m.project,
                   project_description="Synthetic steel / composite tower matching the Harborview demo - calc-graph",
                   project_phase=m.label, building_name=m.project, storeys=m.levels, author="calc-graph synth",
                   originating_system="calc-graph synth generator (harborview)", timestamp=timestamp)

    def i_profile(name: str):
        s = shapes.w_si(name)
        return B.i_profile(name, s["bf"], s["d"], s["tw"], s["tf"])

    def hss_profile(name: str):
        s = shapes.hss_si(name)
        return B.rect_hollow_profile(name, s["b"], s["b"], s["t"])

    def swept(p1, p2, prof):
        p1, p2 = np.array(p1, float), np.array(p2, float)
        d = p2 - p1
        length = float(np.linalg.norm(d))
        zdir = d / length
        up = np.array([0.0, 0.0, 1.0])
        xdir = np.cross(up, zdir) if abs(zdir[2]) < 0.99 else np.array([0.0, 1.0, 0.0])
        xdir /= np.linalg.norm(xdir)
        return B.ax(tuple(p1), tuple(zdir), tuple(xdir)), B.solid(prof, length)

    def shape_of(e: Element):
        g = e.geom
        mn, mx = np.array(g["bbox"]["min"], float), np.array(g["bbox"]["max"], float)
        size = norm_size(e.profile)
        if e.kind in ("beam", "column") and size in shapes.W:
            a = g["axis"]
            return swept(a["start"], a["end"], i_profile(size))
        if e.kind == "brace" and size in shapes.HSS:
            # the bbox is the braced panel: the brace runs corner to corner in its long horizontal direction
            h = 0 if (mx[0] - mn[0]) >= (mx[1] - mn[1]) else 1
            p1, p2 = mn.copy(), mx.copy()
            other = 1 - h
            p1[other] = p2[other] = (mn[other] + mx[other]) / 2
            return swept(p1, p2, hss_profile(size))
        if e.kind == "pile":
            r = min(mx[0] - mn[0], mx[1] - mn[1]) / 2
            prof = B._profile("IfcCircleProfileDef", None, Radius=r)
            c = (mn + mx) / 2
            return B.ax((c[0], c[1], mn[2])), B.solid(prof, mx[2] - mn[2])
        ext = mx - mn
        c = (mn + mx) / 2
        return B.ax((c[0], c[1], mn[2])), B.solid(B.rect_profile(ext[0], ext[1]), ext[2])

    gids: dict[str, str] = {}
    for e in m.elements:
        placement, solid = shape_of(e)
        cls = e.ifc_class
        inst, gid = B.product(cls, e.id, e.label, e.profile or ROLE[e.kind], placement, solid, e.storey, PREDEFINED[cls])
        gids[e.id] = gid
        structural = {"Section": e.profile, "Grade": e.material, "Role": "infill beam" if e.role == "InfillBeam" else ROLE[e.kind]}
        if e.grid:
            structural["Grid"] = e.grid
        B.psets(inst, e.id, {"Identity Data": {"Mark": e.mark}, "Structural": structural})
    B.write(path)
    return gids
