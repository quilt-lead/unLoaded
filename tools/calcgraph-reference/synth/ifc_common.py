"""Shared IFC4 writing helpers on the IfcOpenShell API (ifcopenshell.api), used by every IFC
calc-graph writes (today: the synthetic generator, synth/ifc_writer.py).

Every entity is made through ifcopenshell.api (root / project / unit / context / aggregate /
spatial / geometry / profile / material / pset / structural) - nothing here hand-assembles
IFC entity attribute lists, so the schema rules the api knows (placements relative to their
spatial parent, rel bookkeeping, unit / context setup) hold in every file we write.

Stability: the api mints random GlobalIds, so every rooted entity this module creates is
re-keyed to uuid5(namespace, caller key) straight after - an element keeps its GlobalId across
re-runs and model revisions (what the revision store keys on). Calls happen in a
fixed order, so a writer that calls these helpers in a fixed order produces byte-stable files
(synth.generate --check relies on it).
"""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass

import ifcopenshell
import ifcopenshell.api
import ifcopenshell.api.aggregate
import ifcopenshell.api.context
import ifcopenshell.api.geometry
import ifcopenshell.api.material
import ifcopenshell.api.profile
import ifcopenshell.api.project
import ifcopenshell.api.pset
import ifcopenshell.api.root
import ifcopenshell.api.spatial
import ifcopenshell.api.unit
import ifcopenshell.guid
import ifcopenshell.ifcopenshell_wrapper
import numpy as np

api = ifcopenshell.api


def _canonical_sets(f) -> None:
    """Every SET-typed attribute (unordered in IFC) stored in entity id order. Some api use cases
    fill them through Python sets (assign_unit, assign_container, assign_material, ...), whose order
    varies run to run - without this the file is not byte-stable even though nothing changed."""
    schema = ifcopenshell.ifcopenshell_wrapper.schema_by_name(f.schema)
    cache: dict[str, list[str]] = {}
    for ent in f:
        cls = ent.is_a()
        if cls not in cache:
            cache[cls] = [a.name() for a in schema.declaration_by_name(cls).all_attributes()
                          if isinstance(t := a.type_of_attribute(), ifcopenshell.ifcopenshell_wrapper.aggregation_type)
                          and t.type_of_aggregation_string() == "set"]
        for name in cache[cls]:
            v = getattr(ent, name)
            if v and len(v) > 1 and all(isinstance(x, ifcopenshell.entity_instance) and x.id() for x in v):
                setattr(ent, name, sorted(v, key=lambda e: e.id()))


@dataclass(frozen=True)
class Extrusion:
    """A profile swept along the local Z of the product placement (what `IfcBuilder.solid` returns)."""
    profile: object
    depth: float


class IfcBuilder:
    def __init__(self, path: str, *, namespace: uuid.UUID, project_name: str, project_description: str,
                 project_phase: str | None, building_name: str, storeys: list[tuple[str, float]],
                 author: str, originating_system: str, timestamp: str = "2026-11-14T09:00:00"):
        self.ns = namespace
        self._keyed: set[str] = set()
        f = self.f = api.project.create_file(version="IFC4")
        # basename, not rsplit("/"): a Windows path would put its directory in the header (not byte-stable)
        f.header.file_name.name = os.path.basename(path)
        f.header.file_name.time_stamp = timestamp
        f.header.file_name.author = (author,)
        f.header.file_name.organization = ("calc-graph",)
        f.header.file_name.preprocessor_version = "IfcOpenShell"
        f.header.file_name.originating_system = originating_system
        f.header.file_name.authorization = "none"
        f.header.file_description.description = ("ViewDefinition [ReferenceView]",)

        self.project = self.rooted("IfcProject", "project", name=project_name)
        self.project.Description = project_description
        self.project.Phase = project_phase
        si = [api.unit.add_si_unit(f, unit_type=t) for t in
              ("LENGTHUNIT", "AREAUNIT", "VOLUMEUNIT", "PLANEANGLEUNIT", "FORCEUNIT")]
        for u, name in zip(si, ("METRE", "SQUARE_METRE", "CUBIC_METRE", "RADIAN", "NEWTON")):
            u.Name = name
        length, force = si[0], si[4]
        lin_force = api.unit.add_derived_unit(f, "LINEARFORCEUNIT", None, {force: 1, length: -1})
        api.unit.assign_unit(f, units=si + [lin_force])
        self.model_ctx = api.context.add_context(f, context_type="Model")
        self.body = api.context.add_context(f, context_type="Model", context_identifier="Body",
                                            target_view="MODEL_VIEW", parent=self.model_ctx)
        self._reference_ctx = None

        site = self.rooted("IfcSite", "site", name="Site")
        bldg = self.rooted("IfcBuilding", "building", name=building_name)
        self.building = bldg
        for p in (site, bldg):
            p.CompositionType = "ELEMENT"
        self.keyed(api.aggregate.assign_object(f, products=[site], relating_object=self.project), "rel:project-site")
        api.geometry.edit_object_placement(f, product=site, matrix=np.eye(4))
        self.keyed(api.aggregate.assign_object(f, products=[bldg], relating_object=site), "rel:site-building")
        api.geometry.edit_object_placement(f, product=bldg, matrix=np.eye(4))
        self.storeys = {}
        for name, z in storeys:
            st = self.rooted("IfcBuildingStorey", f"storey:{name}", name=name)
            st.CompositionType = "ELEMENT"
            st.Elevation = float(z)
            self.storeys[name] = st
        self.keyed(api.aggregate.assign_object(f, products=list(self.storeys.values()), relating_object=bldg),
                   "rel:building-storeys")
        for (_, z), st in zip(storeys, self.storeys.values()):
            api.geometry.edit_object_placement(f, product=st, matrix=self.ax((0, 0, z)))
        self.profiles: dict[str, object] = {}
        self.materials: dict[str, object] = {}
        self.profile_sets: dict[tuple[str, str], object] = {}

    # -- identity
    def guid(self, key: str) -> str:
        return ifcopenshell.guid.compress(uuid.uuid5(self.ns, key).hex)

    def keyed(self, ent, key: str):
        """Give an api-made rooted entity (or rel) its stable GlobalId."""
        if ent is not None:
            ent.GlobalId = self.guid(key)
            self._keyed.add(ent.GlobalId)
        return ent

    def rooted(self, cls: str, key: str, name: str | None = None, predefined: str | None = None):
        return self.keyed(api.root.create_entity(self.f, ifc_class=cls, name=name, predefined_type=predefined), key)

    @property
    def reference_ctx(self):
        """Model/Reference/GRAPH_VIEW sub-context for structural topology (made on first use)."""
        if self._reference_ctx is None:
            self._reference_ctx = api.context.add_context(self.f, context_type="Model", context_identifier="Reference",
                                                          target_view="GRAPH_VIEW", parent=self.model_ctx)
        return self._reference_ctx

    # -- placements: a 4x4 matrix (SI metres); the api writes the IfcLocalPlacement
    @staticmethod
    def ax(loc, z=(0, 0, 1), x=(1, 0, 0)) -> np.ndarray:
        zv = np.array(z, float)
        zv /= np.linalg.norm(zv)
        xv = np.array(x, float)
        xv = xv - zv * float(xv @ zv)          # RefDirection projected normal to Axis (IFC rule)
        xv /= np.linalg.norm(xv)
        m = np.eye(4)
        m[:3, 0], m[:3, 1], m[:3, 2], m[:3, 3] = xv, np.cross(zv, xv), zv, np.array(loc, float)
        return m

    # -- profiles (cached by name; SI metres) via api.profile
    def _profile(self, cls: str, name: str | None, **attrs):
        p = api.profile.add_parameterized_profile(self.f, ifc_class=cls)
        p.ProfileName = name
        for k, v in attrs.items():
            setattr(p, k, float(v))
        return p

    def i_profile(self, name: str, bf: float, d: float, tw: float, tf: float):
        if name not in self.profiles:
            self.profiles[name] = self._profile("IfcIShapeProfileDef", name, OverallWidth=bf, OverallDepth=d,
                                                WebThickness=tw, FlangeThickness=tf)
        return self.profiles[name]

    def rect_hollow_profile(self, name: str, b: float, h: float, t: float):
        if name not in self.profiles:
            self.profiles[name] = self._profile("IfcRectangleHollowProfileDef", name, XDim=b, YDim=h, WallThickness=t)
        return self.profiles[name]

    def channel_profile(self, name: str, d: float, bf: float, tw: float, tf: float):
        if name not in self.profiles:
            self.profiles[name] = self._profile("IfcUShapeProfileDef", name, Depth=d, FlangeWidth=bf, WebThickness=tw,
                                                FlangeThickness=tf)
        return self.profiles[name]

    def rect_profile(self, x: float, y: float, name: str | None = None):
        return self._profile("IfcRectangleProfileDef", name, XDim=x, YDim=y)

    def solid(self, profile, depth: float) -> Extrusion:
        return Extrusion(profile, float(depth))

    # -- materials (api.material): one IfcMaterial per grade, one IfcMaterialProfileSet per (profile, grade)
    def material(self, name: str, category: str = "steel"):
        if name not in self.materials:
            self.materials[name] = api.material.add_material(self.f, name=name, category=category)
        return self.materials[name]

    def assign_profile_material(self, inst, profile, grade: str, category: str = "steel"):
        """IfcMaterialProfileSetUsage on a linear member: its section profile in its material grade."""
        key = (profile.ProfileName or f"#{profile.id()}", grade)
        if key not in self.profile_sets:
            ps = api.material.add_material_set(self.f, name=f"{key[0]} {grade}", set_type="IfcMaterialProfileSet")
            api.material.add_profile(self.f, profile_set=ps, material=self.material(grade, category), profile=profile,
                                     name=key[0])
            self.profile_sets[key] = ps
        self._key_material_rel(api.material.assign_material(self.f, products=[inst], type="IfcMaterialProfileSetUsage",
                                                            material=self.profile_sets[key]))

    def assign_material(self, inst, grade: str, category: str):
        self._key_material_rel(api.material.assign_material(self.f, products=[inst], type="IfcMaterial",
                                                            material=self.material(grade, category)))

    def _key_material_rel(self, rels):
        """IfcRelAssociatesMaterial: keyed by the first product it was made for (the api may add
        later products to the same rel; its GlobalId stays the first product's)."""
        for rel in rels if isinstance(rels, (list, tuple)) else [rels]:
            if rel is not None and rel.is_a("IfcRelAssociatesMaterial") and rel.GlobalId not in self._keyed:
                self.keyed(rel, f"rel:material:{rel.RelatedObjects[0].GlobalId}")

    # -- products
    def product(self, cls: str, key: str, name: str, object_type: str, placement_ax, solid: Extrusion, storey: str,
                predefined: str):
        f = self.f
        inst = self.rooted(cls, key, name=name, predefined=predefined)
        inst.ObjectType = object_type
        # contain first, then place: the placement is written once, relative to the storey (placing
        # first makes assign_container re-localize placements in an unordered pass - not byte-stable)
        self.keyed(api.spatial.assign_container(f, products=[inst], relating_structure=self.storeys[storey]),
                   f"rel:contain:{storey}")
        api.geometry.edit_object_placement(f, product=inst, matrix=placement_ax)
        rep = api.geometry.add_profile_representation(f, context=self.body, profile=solid.profile, depth=solid.depth,
                                                      cardinal_point=None)
        api.geometry.assign_representation(f, product=inst, representation=rep)
        return inst, inst.GlobalId

    def psets(self, inst, key: str, psets: dict[str, dict]):
        """Every value is written as IfcLabel text (str(v)), as calc-graph's readers expect."""
        for pname, props in psets.items():
            ps = self.keyed(api.pset.add_pset(self.f, product=inst, name=pname), f"pset:{key}:{pname}")
            api.pset.edit_pset(self.f, pset=ps, properties={k: self.f.createIfcLabel(str(v)) for k, v in props.items()})
            self.keyed(ps.DefinesOccurrence[0], f"rel:pset:{key}:{pname}")

    def write(self, path: str):
        _canonical_sets(self.f)
        # an api call that minted a rooted entity nobody re-keyed would leave a random GlobalId:
        # the file would not be byte-stable and ifcdiff / the store would see churn - refuse to write it
        stray = [e for e in self.f.by_type("IfcRoot") if e.GlobalId not in self._keyed]
        if stray:
            raise RuntimeError(f"{len(stray)} IFC entities without a stable GlobalId (not re-keyed after the api "
                               f"call): {sorted({e.is_a() for e in stray})}")
        self.f.write(path)
