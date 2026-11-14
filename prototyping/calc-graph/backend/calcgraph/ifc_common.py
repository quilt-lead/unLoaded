"""Shared IFC4 writing helpers (IfcOpenShell), used by the synthetic generator
(synth/ifc_writer.py) and by the plans-to-IFC builder (plans_to_ifc.py).

Entities are created in a fixed order so a writer that calls these helpers in a
fixed order produces byte-stable files (the synth generator's --check relies on it).
GlobalIds are uuid5 of a caller-chosen key, so they are stable across re-runs.
"""
from __future__ import annotations

import uuid

import ifcopenshell
import ifcopenshell.guid


class IfcBuilder:
    def __init__(self, path: str, *, namespace: uuid.UUID, project_name: str, project_description: str,
                 project_phase: str | None, building_name: str, storeys: list[tuple[str, float]],
                 author: str, originating_system: str, timestamp: str = "2026-11-14T09:00:00"):
        self.ns = namespace
        f = self.f = ifcopenshell.file(schema="IFC4")
        f.header.file_name.name = path.rsplit("/", 1)[-1]
        f.header.file_name.time_stamp = timestamp
        f.header.file_name.author = (author,)
        f.header.file_name.organization = ("calc-graph",)
        f.header.file_name.preprocessor_version = "IfcOpenShell"
        f.header.file_name.originating_system = originating_system
        f.header.file_name.authorization = "none"
        f.header.file_description.description = ("ViewDefinition [ReferenceView]",)
        units = f.createIfcUnitAssignment([
            f.createIfcSIUnit(None, "LENGTHUNIT", None, "METRE"),
            f.createIfcSIUnit(None, "AREAUNIT", None, "SQUARE_METRE"),
            f.createIfcSIUnit(None, "VOLUMEUNIT", None, "CUBIC_METRE"),
            f.createIfcSIUnit(None, "PLANEANGLEUNIT", None, "RADIAN"),
        ])
        ctx = f.createIfcGeometricRepresentationContext(None, "Model", 3, 1e-5, self.ax((0, 0, 0)), None)
        self.body = f.createIfcGeometricRepresentationSubContext("Body", "Model", None, None, None, None, ctx, None,
                                                                 "MODEL_VIEW", None)
        self.project = f.createIfcProject(self.guid("project"), None, project_name, project_description, None, None,
                                          project_phase, [ctx], units)
        site_pl = f.createIfcLocalPlacement(None, self.ax((0, 0, 0)))
        site = f.createIfcSite(self.guid("site"), None, "Site", None, None, site_pl, None, None, "ELEMENT", None, None,
                               None, None, None)
        bldg_pl = f.createIfcLocalPlacement(site_pl, self.ax((0, 0, 0)))
        bldg = f.createIfcBuilding(self.guid("building"), None, building_name, None, None, bldg_pl, None, None,
                                   "ELEMENT", None, None, None)
        f.createIfcRelAggregates(self.guid("rel:project-site"), None, None, None, self.project, [site])
        f.createIfcRelAggregates(self.guid("rel:site-building"), None, None, None, site, [bldg])
        self.storeys = {}
        for name, z in storeys:
            pl = f.createIfcLocalPlacement(bldg_pl, self.ax((0, 0, z)))
            self.storeys[name] = f.createIfcBuildingStorey(self.guid(f"storey:{name}"), None, name, None, None, pl,
                                                           None, None, "ELEMENT", z)
        f.createIfcRelAggregates(self.guid("rel:building-storeys"), None, None, None, bldg, list(self.storeys.values()))
        self.profiles: dict[str, object] = {}
        self.by_storey: dict[str, list] = {}

    # -- primitives
    def guid(self, key: str) -> str:
        return ifcopenshell.guid.compress(uuid.uuid5(self.ns, key).hex)

    def pt(self, *c):
        return self.f.createIfcCartesianPoint(tuple(float(v) for v in c))

    def dirn(self, *c):
        return self.f.createIfcDirection(tuple(float(v) for v in c))

    def ax(self, loc, z=(0, 0, 1), x=(1, 0, 0)):
        return self.f.createIfcAxis2Placement3D(self.pt(*loc), self.dirn(*z), self.dirn(*x))

    # -- profiles (cached by name; SI metres)
    def i_profile(self, name: str, bf: float, d: float, tw: float, tf: float):
        if name not in self.profiles:
            self.profiles[name] = self.f.createIfcIShapeProfileDef("AREA", name, None, bf, d, tw, tf, None, None, None)
        return self.profiles[name]

    def rect_hollow_profile(self, name: str, b: float, h: float, t: float):
        if name not in self.profiles:
            self.profiles[name] = self.f.createIfcRectangleHollowProfileDef("AREA", name, None, b, h, t, None, None)
        return self.profiles[name]

    def channel_profile(self, name: str, d: float, bf: float, tw: float, tf: float):
        if name not in self.profiles:
            self.profiles[name] = self.f.createIfcUShapeProfileDef("AREA", name, None, d, bf, tw, tf, None, None, None)
        return self.profiles[name]

    def rect_profile(self, x: float, y: float, name: str | None = None):
        return self.f.createIfcRectangleProfileDef("AREA", name, None, float(x), float(y))

    def solid(self, profile, depth: float):
        return self.f.createIfcExtrudedAreaSolid(profile, None, self.dirn(0, 0, 1), float(depth))

    # -- products
    def product(self, cls: str, key: str, name: str, object_type: str, placement_ax, solid, storey: str,
                predefined: str):
        f = self.f
        rep = f.createIfcShapeRepresentation(self.body, "Body", "SweptSolid", [solid])
        pds = f.createIfcProductDefinitionShape(None, None, [rep])
        lp = f.createIfcLocalPlacement(None, placement_ax)
        gid = self.guid(key)
        inst = getattr(f, f"create{cls}")(gid, None, name, None, object_type, lp, pds, None, predefined)
        self.by_storey.setdefault(storey, []).append(inst)
        return inst, gid

    def psets(self, inst, key: str, psets: dict[str, dict]):
        f = self.f
        for pname, props in psets.items():
            vals = [f.createIfcPropertySingleValue(k, None, f.createIfcLabel(str(v)), None) for k, v in props.items()]
            ps = f.createIfcPropertySet(self.guid(f"pset:{key}:{pname}"), None, pname, None, vals)
            f.createIfcRelDefinesByProperties(self.guid(f"rel:pset:{key}:{pname}"), None, None, None, [inst], ps)

    def write(self, path: str):
        for name, items in self.by_storey.items():
            self.f.createIfcRelContainedInSpatialStructure(self.guid(f"rel:contain:{name}"), None, None, None, items,
                                                           self.storeys[name])
        self.f.write(path)
