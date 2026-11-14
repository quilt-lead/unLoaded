"""BHoM JSON <-> calc-graph structural schema (schema/structural.py).

BHoM itself is C#/LGPL and is never run or copied here. This module only reads and writes
the JSON its Serialiser produces, from the wire behaviour of BHoM_Engine/Serialiser_Engine
(read 2026-11-14, develop branch):

- an object is {"_t": "<full type name>", <every public property by name>}; a BHoMObject
  also carries "BHoM_Guid" and "Name", and "Fragments" / "Tags" / "CustomData" only when
  non-empty. Nested objects are written in full every time (a Node inside each Bar it ends;
  the Loadcase inside each load) - there are no references, so this module de-duplicates
  by BHoM_Guid.
- an enum property is its NAME as a string ("Fixed", "Dead"); an enum held in an object-typed
  slot is {"_t": "System.Enum", "TypeName": ..., "Value": name}.
- a Tuple<double, ICase> (LoadCombination.LoadCases items) is a 2-element array
  [factor, {case}]; when the declared type differs it is {"_t": ..., "_v": [...]}.
- a Fragments set is an array of objects; BHoM's ETABS adapter puts an ETABSId fragment
  {"_t": "BH.oM.Adapters.ETABS.ETABSId", "Id", "Label", "Story", "PersistentId"} there.
- quantities are SI (BHoM declares SI quantity attributes): m, N, N*m, Pa, rad, kg/m3.

Every fact this produces carries provenance: ModelEvidence on the BHoM JSON document
(global_id = BHoM_Guid, or a composite key for results, which have no guid), method
deterministic, confidence 1.0 (a format conversion), rule `bhom-json/<Type>`. A BHoM field
this module does not map is never dropped silently: a non-default value lands in
`Report.unmapped`, a BHoM type it does not convert in `Report.unsupported`.

    bundle, report = bhom_to_schema(objs, doc_sha=sha, source=ResultSource.etabs_via_bhom)
    objs2 = schema_to_bhom(bundle)
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import math
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo

from ..frames import BuildingFt, ModelM, Point3
from ..models import Method, ModelEvidence, Provenance
from ..structural import (AnalyticalBar, AnalyticalNode, AreaLoad, AxisSystem, BarDistributedLoad, BarFEAType,
                          BarForceResult, BarPointLoad, CombinationTerm, DivisionType, Dof, DOFType, EndReleases,
                          ExternalRef, Fixity6, GlobalReactionResult, GravityLoad, LoadCase, LoadCombination,
                          LoadNature, MaterialGrade, MaterialKind, NodeDisplacementResult, NodeReactionResult, Offset,
                          PointLoad, QVector, ResultKind, ResultRequest, ResultSource, SectionPropertySet,
                          SectionShape, StoreyDriftResult, StructuralBundle, StructuralUsage, Support,
                          UtilisationResult)
from ..units import FT, Quantity, convert

CONVERTER = "calcgraph.schema.adapters.bhom_json"
CONVERTER_VERSION = "bhom-json/1.0"
G0 = 9.80665  # standard gravity, m/s2 (exact by definition) - kg/m3 -> N/m3
NS = "BH.oM.Structure."
BASE_KEYS = {"_t", "BHoM_Guid", "Name", "Fragments", "Tags", "CustomData"}
ETABS_ID = "BH.oM.Adapters.ETABS.ETABSId"
_GUID_NS = uuid.UUID("6f1d1c2e-6a52-4b8e-9a4f-3b8a43c7a0b5")  # calc-graph's namespace for minted BHoM guids

# BHoM enum names <-> ours
DOF = {"Free": DOFType.free, "Fixed": DOFType.fixed, "FixedNegative": DOFType.fixed_negative,
       "FixedPositive": DOFType.fixed_positive, "Spring": DOFType.spring, "SpringNegative": DOFType.spring_negative,
       "SpringPositive": DOFType.spring_positive, "SpringRelative": DOFType.spring_relative,
       "SpringRelativeNegative": DOFType.spring_relative_negative,
       "SpringRelativePositive": DOFType.spring_relative_positive, "NonLinear": DOFType.nonlinear,
       "Friction": DOFType.friction, "Damped": DOFType.damped, "Gap": DOFType.gap}
NATURE = {"Dead": LoadNature.dead, "SuperDead": LoadNature.superimposed_dead, "Live": LoadNature.live,
          "Wind": LoadNature.wind, "Seismic": LoadNature.seismic, "Temperature": LoadNature.temperature,
          "Snow": LoadNature.snow, "Accidental": LoadNature.accidental, "Prestress": LoadNature.prestress,
          "Notional": LoadNature.notional, "Other": LoadNature.other}
# BHoM has no roof-live nature; ours maps to Live and keeps the distinction in Tags.
NATURE_OUT = {v: k for k, v in NATURE.items()} | {LoadNature.roof_live: "Live"}
FEA = {"Flexural": BarFEAType.flexural, "Axial": BarFEAType.axial, "CompressionOnly": BarFEAType.compression_only,
       "TensionOnly": BarFEAType.tension_only}
DIVISION = {"EvenlyDistributed": DivisionType.evenly_distributed, "ExtremeValues": DivisionType.extreme_values}
AXIS = {"Global": AxisSystem.global_, "Local": AxisSystem.local}
REQ_BAR = {"BarForce": ResultKind.bar_force, "BarDisplacement": ResultKind.bar_displacement}
REQ_NODE = {"NodeReaction": ResultKind.node_reaction, "NodeDisplacement": ResultKind.node_displacement}
REQ_GLOBAL = {"Reactions": ResultKind.global_reactions, "StoreyDrifts": ResultKind.storey_drift,
              "ModalDynamics": ResultKind.modal}
MATERIAL_T = {"MaterialFragments.Steel": MaterialKind.steel, "MaterialFragments.Concrete": MaterialKind.concrete,
              "MaterialFragments.Aluminium": MaterialKind.aluminium,
              "MaterialFragments.GenericIsotropicMaterial": MaterialKind.generic_isotropic}
SECTION_T = ("SectionProperties.SteelSection", "SectionProperties.ConcreteSection", "SectionProperties.ExplicitSection",
             "SectionProperties.GenericSection", "SectionProperties.AluminiumSection", "SectionProperties.TimberSection")
PROFILE_SHAPE = {"ISectionProfile": SectionShape.i, "BoxProfile": SectionShape.rect_hollow,
                 "TubeProfile": SectionShape.circ_hollow, "ChannelProfile": SectionShape.channel,
                 "AngleProfile": SectionShape.angle, "TSectionProfile": SectionShape.tee,
                 "RectangleProfile": SectionShape.rect, "CircleProfile": SectionShape.circle}
# BHoM section property (SI) -> ours (x = major). BHoM: y = major, z = minor.
SECTION_PROPS = [("Area", "A", "m2"), ("Iy", "Ix", "m4"), ("Iz", "Iy", "m4"), ("J", "J", "m4"), ("Iw", "Cw", "m6"),
                 ("Wely", "Sx", "m3"), ("Welz", "Sy", "m3"), ("Wply", "Zx", "m3"), ("Wplz", "Zy", "m3"),
                 ("Rgy", "rx", "m"), ("Rgz", "ry", "m"), ("Asz", "Avx", "m2"), ("Asy", "Avy", "m2")]
SECTION_DERIVED = {"CentreY", "CentreZ", "Vy", "Vpy", "Vz", "Vpz"}  # geometric, recomputed by BHoM from the profile


class BhomConversionError(ValueError):
    pass


@dataclass
class Report:
    """What a conversion saw and could not carry. Empty unmapped/unsupported = lossless."""
    converted: Counter = field(default_factory=Counter)
    unsupported: Counter = field(default_factory=Counter)
    unmapped: dict[str, set] = field(default_factory=lambda: defaultdict(set))
    notes: list[str] = field(default_factory=list)

    def lossless(self) -> bool:
        return not self.unsupported and not self.unmapped

    def to_dict(self) -> dict:
        return {"converted": dict(self.converted), "unsupported": dict(self.unsupported),
                "unmapped": {k: sorted(v) for k, v in self.unmapped.items()}, "notes": self.notes,
                "lossless": self.lossless()}


def _now_et() -> str:
    return _dt.datetime.now(ZoneInfo("America/New_York")).isoformat(timespec="seconds")


def short_type(t: str) -> str:
    """'BH.oM.Structure.Elements.Bar' -> 'Elements.Bar'; generics keep their outer name."""
    t = (t or "").split("<")[0].split("`")[0]
    return t[len(NS):] if t.startswith(NS) else t


def _enum(v, table: dict, what: str):
    if isinstance(v, dict) and v.get("_t") == "System.Enum":
        v = v.get("Value")
    if isinstance(v, int) and not isinstance(v, bool):
        names = list(table)
        if 0 <= v < len(names):
            return table[names[v]]
    if v in table:
        return table[v]
    raise BhomConversionError(f"unknown BHoM {what} value {v!r}")


def _num(v, what: str) -> float:
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    if isinstance(v, str) and v in ("NaN", "Infinity", "-Infinity"):
        return float(v.replace("Infinity", "inf"))
    raise BhomConversionError(f"{what}: expected a number, got {v!r}")


def _tuple(v):
    if isinstance(v, dict) and "_v" in v:
        v = v["_v"]
    if isinstance(v, dict) and "Item1" in v:
        return v["Item1"], v["Item2"]
    if isinstance(v, (list, tuple)) and len(v) == 2:
        return v[0], v[1]
    raise BhomConversionError(f"expected a 2-tuple, got {v!r}")


def _group(v) -> list:
    """BHoMGroup<T> -> its Elements list."""
    if v is None:
        return []
    if isinstance(v, dict):
        return list(v.get("Elements") or [])
    if isinstance(v, list):
        return v
    raise BhomConversionError(f"expected a BHoMGroup, got {v!r}")


# ======================================================================== BHoM -> schema
class _In:
    def __init__(self, doc_sha: str, source: ResultSource, at: str | None, report: Report):
        self.doc_sha, self.source, self.at, self.r = doc_sha, source, at or _now_et(), report
        self.frame = ModelM(doc_sha=doc_sha)
        self.by_guid: dict[str, str] = {}
        self.adapter_id: dict[str, str] = {}   # ETABSId.Id -> our id (results refer to these)
        self.case_by: dict[str, str] = {}      # case Name / Number -> our id
        self.out: dict[str, dict] = defaultdict(dict)  # collection -> id -> fact
        self.used_ids: set[str] = set()

    # ---- provenance / identity
    def prov(self, t: str, key: str, text: str = "") -> Provenance:
        return Provenance(evidence=[ModelEvidence(doc_sha=self.doc_sha, global_id=key or "(no id)", entity=t,
                                                  text=text[:200])],
                          rule_id=f"bhom-json/{short_type(t)}", rule_version=CONVERTER_VERSION,
                          engine=f"{CONVERTER} ({CONVERTER_VERSION})", method=Method.deterministic, confidence=1.0,
                          at=self.at)

    def refs(self, o: dict) -> list[ExternalRef]:
        ids = {}
        for fr in o.get("Fragments") or []:
            if isinstance(fr, dict) and fr.get("_t") == ETABS_ID:
                for k, ours in (("Id", "etabs"), ("Label", "etabs_label"), ("Story", "etabs_story"),
                                ("PersistentId", "etabs_guid")):
                    if fr.get(k) not in (None, ""):
                        ids[ours] = str(fr[k])
        return [ExternalRef(system="bhom", type=o.get("_t", ""), guid=str(o.get("BHoM_Guid") or ""),
                            name=o.get("Name") or "", ids=ids)]

    def new_id(self, prefix: str, o: dict, *candidates) -> str:
        for c in candidates:
            if c not in (None, ""):
                cid = f"{prefix}:{c}"
                if cid not in self.used_ids:
                    self.used_ids.add(cid)
                    return cid
        cid = f"{prefix}:{o.get('BHoM_Guid') or len(self.used_ids)}"
        self.used_ids.add(cid)
        return cid

    def check_fields(self, o: dict, handled: set, defaults: dict | None = None):
        t = short_type(o.get("_t", ""))
        defaults = defaults or {}
        for k, v in o.items():
            if k in BASE_KEYS or k in handled:
                continue
            if v in (None, "", [], {}, 0, 0.0, False) or defaults.get(k) == v:
                continue
            self.r.unmapped[t].add(k)
        for fr in o.get("Fragments") or []:
            if not (isinstance(fr, dict) and fr.get("_t") == ETABS_ID):
                self.r.unmapped[t].add(f"Fragments[{short_type(fr.get('_t', '?')) if isinstance(fr, dict) else '?'}]")
        if o.get("CustomData"):
            self.r.unmapped[t].add("CustomData")

    def cached(self, o: dict):
        g = o.get("BHoM_Guid")
        return self.by_guid.get(g) if g else None

    def remember(self, o: dict, oid: str):
        if o.get("BHoM_Guid"):
            self.by_guid[o["BHoM_Guid"]] = oid
        for ref in self.refs(o):
            if "etabs" in ref.ids:
                self.adapter_id[ref.ids["etabs"]] = oid

    def vec(self, v, unit: str, axis: AxisSystem = AxisSystem.global_) -> QVector:
        if v is None:
            v = {}
        return QVector(axis=axis, **{k.lower(): Quantity(value=_num(v.get(k, 0.0), f"vector {k}"), unit=unit)
                                     for k in ("X", "Y", "Z")})

    def q(self, o: dict, key: str, unit: str) -> Quantity | None:
        v = o.get(key)
        if v is None:
            return None
        x = _num(v, key)
        return None if math.isnan(x) else Quantity(value=x, unit=unit)

    # ---- dispatch
    def any(self, o: dict):
        if not isinstance(o, dict) or "_t" not in o:
            raise BhomConversionError(f"not a BHoM object: {str(o)[:80]}")
        t = short_type(o["_t"])
        fn = {
            "Elements.Node": self.node, "Elements.Bar": self.bar, "Loads.Loadcase": self.loadcase,
            "Loads.LoadCombination": self.combination, "Loads.PointLoad": self.point_load,
            "Loads.BarUniformlyDistributedLoad": self.bar_udl, "Loads.BarVaryingDistributedLoad": self.bar_vdl,
            "Loads.BarPointLoad": self.bar_point_load, "Loads.GravityLoad": self.gravity_load,
            "Requests.BarResultRequest": self.request, "Requests.NodeResultRequest": self.request,
            "Requests.GlobalResultRequest": self.request,
            "Results.BarForce": self.bar_force, "Results.NodeReaction": self.node_reaction,
            "Results.NodeDisplacement": self.node_displacement, "Results.GlobalReactions": self.global_reactions,
            "Results.StoreyDrift": self.storey_drift, "Results.SteelUtilisation": self.utilisation,
        }.get(t)
        if fn is None and t in MATERIAL_T:
            fn = self.material
        if fn is None and t in SECTION_T:
            fn = self.section
        if fn is None:
            self.r.unsupported[t] += 1
            return None
        return fn(o)

    # ---- properties
    def material(self, o: dict) -> str:
        if (hit := self.cached(o)):
            return hit
        t = short_type(o["_t"])
        oid = self.new_id("mat", o, o.get("Name"))
        rho = o.get("Density")
        uw = None
        if rho not in (None, 0, 0.0):
            uw = Quantity(value=_num(rho, "Density") * G0 / 1000.0, unit="kN/m3")
        nu = self.q(o, "PoissonsRatio", "1")
        E = self.q(o, "YoungsModulus", "Pa")
        kind = MATERIAL_T[t]
        m = MaterialGrade(
            id=oid, name=o.get("Name") or "", refs=self.refs(o),
            provenance=self.prov(o["_t"], o.get("BHoM_Guid", ""), o.get("Name") or ""),
            kind=kind, E=E, nu=nu, unit_weight=uw, damping_ratio=self.q(o, "DampingRatio", "1"),
            thermal_expansion_per_degC=(_num(o["ThermalExpansionCoeff"], "ThermalExpansionCoeff")
                                        if o.get("ThermalExpansionCoeff") is not None else None),
            fy=self.q(o, "YieldStress", "Pa"), fu=self.q(o, "UltimateStress", "Pa"),
            fc=self.q(o, "CylinderStrength", "Pa"), fcu=self.q(o, "CubeStrength", "Pa"))
        if uw is not None:
            m.provenance.rule_text = "BHoM Density (kg/m3) x g0 9.80665 m/s2 -> unit weight"
        self.check_fields(o, {"Density", "PoissonsRatio", "YoungsModulus", "DampingRatio", "ThermalExpansionCoeff",
                              "YieldStress", "UltimateStress", "CylinderStrength", "CubeStrength"})
        self.out["materials"][oid] = m
        self.remember(o, oid)
        self.r.converted[t] += 1
        return oid

    def section(self, o: dict) -> str:
        if (hit := self.cached(o)):
            return hit
        t = short_type(o["_t"])
        oid = self.new_id("sec", o, o.get("Name"))
        mat_id = self.material(o["Material"]) if isinstance(o.get("Material"), dict) else None
        prof = o.get("SectionProfile") if isinstance(o.get("SectionProfile"), dict) else None
        shape = SectionShape.explicit
        dims = {}
        if prof:
            pt = prof.get("_t", "").rsplit(".", 1)[-1]
            shape = PROFILE_SHAPE.get(pt, SectionShape.other)
            if shape == SectionShape.other:
                self.r.unmapped[t].add(f"SectionProfile[{pt}]")
            for bk, ours in (("Height", "d"), ("Width", "bf"), ("WebThickness", "tw"), ("FlangeThickness", "tf"),
                             ("Thickness", "t_design")):
                if prof.get(bk) not in (None, 0, 0.0):
                    dims[ours] = Quantity(value=_num(prof[bk], bk), unit="m")
            for k in ("RootRadius", "ToeRadius", "OuterRadius", "InnerRadius"):
                if prof.get(k):
                    self.r.unmapped[t].add(f"SectionProfile.{k}")
        props = {ours: self.q(o, bk, u) for bk, ours, u in SECTION_PROPS}
        s = SectionPropertySet(
            id=oid, name=o.get("Name") or "", refs=self.refs(o),
            provenance=self.prov(o["_t"], o.get("BHoM_Guid", ""), o.get("Name") or ""),
            designation=o.get("Name") or oid, shape=shape, material_id=mat_id,
            fabrication=str(o.get("Fabrication") or ""), **dims, **{k: v for k, v in props.items() if v is not None})
        self.check_fields(o, {"Material", "SectionProfile", "Fabrication", "PlateRestraint", *SECTION_DERIVED,
                              *[bk for bk, _, _ in SECTION_PROPS]},
                          defaults={"PlateRestraint": "NoRestraint"})
        self.out["sections"][oid] = s
        self.remember(o, oid)
        self.r.converted[t] += 1
        return oid

    def fixity(self, c: dict | None) -> Fixity6 | None:
        if not c:
            return None
        out = {}
        for ours, dk, kk, unit in (("tx", "TranslationX", "TranslationalStiffnessX", "N/m"),
                                   ("ty", "TranslationY", "TranslationalStiffnessY", "N/m"),
                                   ("tz", "TranslationZ", "TranslationalStiffnessZ", "N/m"),
                                   ("rx", "RotationX", "RotationalStiffnessX", "N*m/rad"),
                                   ("ry", "RotationY", "RotationalStiffnessY", "N*m/rad"),
                                   ("rz", "RotationZ", "RotationalStiffnessZ", "N*m/rad")):
            typ = _enum(c.get(dk, "Free"), DOF, "DOFType")
            k = c.get(kk)
            stiff = Quantity(value=_num(k, kk), unit=unit) if (k not in (None, 0, 0.0) or typ.value.startswith("spring")) \
                else None
            out[ours] = Dof(type=typ, stiffness=stiff)
        return Fixity6(name=c.get("Name") or "", **out)

    # ---- elements
    def node(self, o: dict) -> str:
        if (hit := self.cached(o)):
            return hit
        refs = self.refs(o)
        ids = refs[0].ids
        oid = self.new_id("node", o, ids.get("etabs"), o.get("Name"))
        p = o.get("Position") or {}
        pos = Point3(frame=self.frame, x=_num(p.get("X", 0), "X"), y=_num(p.get("Y", 0), "Y"), z=_num(p.get("Z", 0), "Z"))
        sup_id = None
        fx = self.fixity(o.get("Support"))
        if fx is not None:
            sup_id = f"sup:{oid.split(':', 1)[1]}"
            self.out["supports"][sup_id] = Support(id=sup_id, name=fx.name, node_id=oid, fixity=fx,
                                                    provenance=self.prov(o["_t"], o.get("BHoM_Guid", ""), "Support"))
            self.r.converted["Constraints.Constraint6DOF"] += 1
        if o.get("Orientation") not in (None, {}):
            self.r.unmapped["Elements.Node"].add("Orientation")
        n = AnalyticalNode(id=oid, name=o.get("Name") or "", refs=refs, position=pos, support_id=sup_id,
                           story=ids.get("etabs_story", ""),
                           provenance=self.prov(o["_t"], o.get("BHoM_Guid", ""), o.get("Name") or ""))
        self.check_fields(o, {"Position", "Support", "Orientation"})
        self.out["nodes"][oid] = n
        self.remember(o, oid)
        self.r.converted["Elements.Node"] += 1
        return oid

    def bar(self, o: dict) -> str:
        if (hit := self.cached(o)):
            return hit
        refs = self.refs(o)
        ids = refs[0].ids
        oid = self.new_id("bar", o, ids.get("etabs"), o.get("Name"))
        start, end = self.node(o["Start"]), self.node(o["End"])
        sec = self.section(o["SectionProperty"]) if isinstance(o.get("SectionProperty"), dict) else None
        rel = None
        if isinstance(o.get("Release"), dict):
            r = o["Release"]
            rel = EndReleases(name=r.get("Name") or "", start=self.fixity(r.get("StartRelease")) or Fixity6(),
                              end=self.fixity(r.get("EndRelease")) or Fixity6())
            self.r.converted["Constraints.BarRelease"] += 1
        off = None
        if isinstance(o.get("Offset"), dict):
            ov = o["Offset"]
            off = Offset(start=self.vec(ov.get("Start"), "m", AxisSystem.local), end=self.vec(ov.get("End"), "m", AxisSystem.local))
            if off.start.is_zero() and off.end.is_zero():
                off = None
        if o.get("Support"):
            self.r.unmapped["Elements.Bar"].add("Support")
        b = AnalyticalBar(
            id=oid, name=o.get("Name") or "", refs=refs, start_node=start, end_node=end, section_id=sec,
            orientation_angle=Quantity(value=_num(o.get("OrientationAngle", 0.0), "OrientationAngle"), unit="rad"),
            releases=rel, offset=off, fea_type=_enum(o.get("FEAType", "Flexural"), FEA, "BarFEAType"),
            story=ids.get("etabs_story", ""),
            provenance=self.prov(o["_t"], o.get("BHoM_Guid", ""), o.get("Name") or ""))
        self.check_fields(o, {"Start", "End", "SectionProperty", "OrientationAngle", "Release", "FEAType", "Support",
                              "Offset"}, defaults={"FEAType": "Flexural"})
        self.out["bars"][oid] = b
        self.remember(o, oid)
        self.r.converted["Elements.Bar"] += 1
        return oid

    # ---- loading
    def loadcase(self, o: dict) -> str:
        if (hit := self.cached(o)):
            return hit
        oid = self.new_id("case", o, o.get("Name"), o.get("Number"))
        nature = _enum(o.get("Nature", "Other"), NATURE, "LoadNature")
        tags = o.get("Tags") or []
        if nature == LoadNature.live and "calcgraph:roof-live" in tags:
            nature = LoadNature.roof_live
        c = LoadCase(id=oid, name=o.get("Name") or "", refs=self.refs(o), nature=nature, number=int(o.get("Number") or 0),
                     provenance=self.prov(o["_t"], o.get("BHoM_Guid", ""), o.get("Name") or ""))
        self.check_fields(o, {"Nature", "Number"})
        if [t for t in tags if t != "calcgraph:roof-live"]:
            self.r.unmapped["Loads.Loadcase"].add("Tags")
        self.out["load_cases"][oid] = c
        self.remember(o, oid)
        self._case_keys(o, oid)
        self.r.converted["Loads.Loadcase"] += 1
        return oid

    def _case_keys(self, o, oid):
        if o.get("Name"):
            self.case_by[str(o["Name"])] = oid
        if o.get("Number"):
            self.case_by.setdefault(str(o["Number"]), oid)

    def case(self, o) -> str:
        t = short_type(o.get("_t", "")) if isinstance(o, dict) else ""
        if t == "Loads.Loadcase":
            return self.loadcase(o)
        if t == "Loads.LoadCombination":
            return self.combination(o)
        raise BhomConversionError(f"expected a load case or combination, got {str(o)[:80]}")

    def combination(self, o: dict) -> str:
        if (hit := self.cached(o)):
            return hit
        oid = self.new_id("combo", o, o.get("Name"), o.get("Number"))
        self.by_guid[o.get("BHoM_Guid") or oid] = oid   # guard recursion on self-reference
        terms = []
        for item in o.get("LoadCases") or []:
            f, c = _tuple(item)
            terms.append(CombinationTerm(case_id=self.case(c), factor=Quantity(value=_num(f, "factor"), unit="1")))
        lc = LoadCombination(id=oid, name=o.get("Name") or "", refs=self.refs(o), terms=terms,
                             number=int(o.get("Number") or 0),
                             provenance=self.prov(o["_t"], o.get("BHoM_Guid", ""), o.get("Name") or ""))
        self.check_fields(o, {"LoadCases", "Number"})
        self.out["combinations"][oid] = lc
        self.remember(o, oid)
        self._case_keys(o, oid)
        self.r.converted["Loads.LoadCombination"] += 1
        return oid

    def _load_common(self, o, prefix):
        oid = self.new_id(prefix, o, o.get("Name"))
        return dict(id=oid, name=o.get("Name") or "", refs=self.refs(o), case_id=self.loadcase(o["Loadcase"]),
                    axis=_enum(o.get("Axis", "Global"), AXIS, "LoadAxis"), projected=bool(o.get("Projected", False)),
                    provenance=self.prov(o["_t"], o.get("BHoM_Guid", ""), o.get("Name") or ""))

    def _vec_or_none(self, v, unit, axis):
        if v is None:
            return None
        q = self.vec(v, unit, axis)
        return None if q.is_zero() else q

    def point_load(self, o):
        c = self._load_common(o, "load")
        ld = PointLoad(**c, node_ids=[self.node(n) for n in _group(o.get("Objects"))],
                       force=self._vec_or_none(o.get("Force"), "N", c["axis"]),
                       moment=self._vec_or_none(o.get("Moment"), "N*m", c["axis"]))
        return self._load_done(o, ld, {"Loadcase", "Objects", "Axis", "Projected", "Force", "Moment"})

    def bar_point_load(self, o):
        c = self._load_common(o, "load")
        ld = BarPointLoad(**c, bar_ids=[self.bar(b) for b in _group(o.get("Objects"))],
                          distance_from_start=Quantity(value=_num(o.get("DistanceFromA", 0.0), "DistanceFromA"), unit="m"),
                          force=self._vec_or_none(o.get("Force"), "N", c["axis"]),
                          moment=self._vec_or_none(o.get("Moment"), "N*m", c["axis"]))
        return self._load_done(o, ld, {"Loadcase", "Objects", "Axis", "Projected", "Force", "Moment", "DistanceFromA"})

    def bar_udl(self, o):
        c = self._load_common(o, "load")
        ld = BarDistributedLoad(**c, bar_ids=[self.bar(b) for b in _group(o.get("Objects"))],
                                force_start=self.vec(o.get("Force"), "N/m", c["axis"]),
                                moment_start=self._vec_or_none(o.get("Moment"), "N", c["axis"]))
        return self._load_done(o, ld, {"Loadcase", "Objects", "Axis", "Projected", "Force", "Moment"})

    def bar_vdl(self, o):
        c = self._load_common(o, "load")
        rel = bool(o.get("RelativePositions", True))
        pu = "1" if rel else "m"
        ld = BarDistributedLoad(**c, bar_ids=[self.bar(b) for b in _group(o.get("Objects"))],
                                force_start=self.vec(o.get("ForceAtStart"), "N/m", c["axis"]),
                                force_end=self.vec(o.get("ForceAtEnd"), "N/m", c["axis"]),
                                moment_start=self._vec_or_none(o.get("MomentAtStart"), "N", c["axis"]),
                                moment_end=self._vec_or_none(o.get("MomentAtEnd"), "N", c["axis"]),
                                start_position=Quantity(value=_num(o.get("StartPosition", 0.0), "StartPosition"), unit=pu),
                                end_position=Quantity(value=_num(o.get("EndPosition", 0.0), "EndPosition"), unit=pu),
                                relative_positions=rel)
        return self._load_done(o, ld, {"Loadcase", "Objects", "Axis", "Projected", "ForceAtStart", "ForceAtEnd",
                                       "MomentAtStart", "MomentAtEnd", "StartPosition", "EndPosition",
                                       "RelativePositions"})

    def gravity_load(self, o):
        c = self._load_common(o, "load")
        objs = []
        for x in _group(o.get("Objects")):
            st = short_type(x.get("_t", ""))
            objs.append(self.bar(x) if st == "Elements.Bar" else self.node(x) if st == "Elements.Node" else None)
            if objs[-1] is None:
                raise BhomConversionError(f"gravity load on unsupported object type {st}")
        ld = GravityLoad(**c, object_ids=objs, direction=self.vec(o.get("GravityDirection") or {"Z": -1}, "1"))
        return self._load_done(o, ld, {"Loadcase", "Objects", "Axis", "Projected", "GravityDirection"})

    def _load_done(self, o, ld, handled):
        self.check_fields(o, handled, defaults={"Axis": "Global"})
        self.out["loads"][ld.id] = ld
        self.remember(o, ld.id)
        self.r.converted[short_type(o["_t"])] += 1
        return ld.id

    # ---- requests
    def request(self, o):
        t = short_type(o["_t"])
        table = {"Requests.BarResultRequest": REQ_BAR, "Requests.NodeResultRequest": REQ_NODE,
                 "Requests.GlobalResultRequest": REQ_GLOBAL}[t]
        kind = _enum(o.get("ResultType"), table, f"{t}.ResultType")
        cases = []
        for c in o.get("Cases") or []:
            cases.append(self.case(c) if isinstance(c, dict) else self.case_by.get(str(c)) or self._missing_case(c))
        ident = [kind.value, cases, [str(x) for x in (o.get("ObjectIds") or [])], o.get("Modes") or [],
                 o.get("Divisions"), o.get("DivisionType"), o.get("Axis")]
        key = hashlib.sha1(json.dumps(ident, sort_keys=True, default=str).encode()).hexdigest()[:10]
        oid = self.new_id("req", o, f"{kind.value}:{key}")
        rq = ResultRequest(id=oid, kind=kind, case_ids=cases,
                           object_ids=[str(x) for x in (o.get("ObjectIds") or [])], modes=[str(m) for m in o.get("Modes") or []],
                           divisions=int(o.get("Divisions") or 5),
                           division_type=_enum(o.get("DivisionType", "EvenlyDistributed"), DIVISION, "DivisionType"),
                           axis=_enum(o.get("Axis", "Global"), AXIS, "LoadAxis"),
                           refs=[ExternalRef(system="bhom", type=o["_t"])],
                           provenance=self.prov(o["_t"], key))
        self.check_fields(o, {"ResultType", "Cases", "ObjectIds", "Modes", "Divisions", "DivisionType", "Axis"})
        self.out["requests"][oid] = rq
        self.r.converted[t] += 1
        return oid

    def _missing_case(self, c):
        raise BhomConversionError(f"result/request refers to case {c!r} that is not in the payload")

    # ---- results
    def _res_common(self, o, kind, obj_required=True):
        t = o["_t"]
        obj = o.get("ObjectId")
        oid_obj = ""
        if obj not in (None, ""):
            oid_obj = self.adapter_id.get(str(obj)) or self.by_guid.get(str(obj)) or ""
            if not oid_obj:
                for coll in ("bars", "nodes"):
                    for prefix in ("bar", "node"):
                        if f"{prefix}:{obj}" in self.out[coll]:
                            oid_obj = f"{prefix}:{obj}"
            if not oid_obj and obj_required:
                raise BhomConversionError(f"{short_type(t)} refers to object {obj!r} that is not in the payload")
        case = o.get("ResultCase")
        cid = self.case_by.get(str(case))
        if cid is None:
            self._missing_case(case)
        key = f"{obj}|{case}|{o.get('ModeNumber', 0)}|{o.get('TimeStep', 0)}|{o.get('Position', '')}|{o.get('Storey', '')}"
        rid = self.new_id(f"res:{kind}", o, key)
        return dict(id=rid, source=self.source, object_id=oid_obj, case_id=cid, mode_number=int(o.get("ModeNumber") or 0),
                    time_step=float(o.get("TimeStep") or 0.0), refs=[ExternalRef(system="bhom", type=t, name=str(obj or ""))],
                    provenance=self.prov(t, key))

    def _res_done(self, o, res, handled):
        self.check_fields(o, {"ObjectId", "ResultCase", "ModeNumber", "TimeStep", *handled})
        self.out["results"][res.id] = res
        self.r.converted[short_type(o["_t"])] += 1
        return res.id

    def _six(self, o, keys, units):
        return {k.lower(): (Quantity(value=_num(o[k], k), unit=u) if o.get(k) is not None else None)
                for k, u in zip(keys, units)}

    def bar_force(self, o):
        c = self._res_common(o, "bar-force")
        six = self._six(o, ("FX", "FY", "FZ", "MX", "MY", "MZ"), ("N",) * 3 + ("N*m",) * 3)
        res = BarForceResult(**c, position=Quantity(value=_num(o.get("Position", 0.0), "Position"), unit="1"),
                             divisions=int(o.get("Divisions") or 0), **six)
        return self._res_done(o, res, {"Position", "Divisions", "FX", "FY", "FZ", "MX", "MY", "MZ"})

    def node_reaction(self, o):
        c = self._res_common(o, "node-reaction")
        res = NodeReactionResult(**c, **self._six(o, ("FX", "FY", "FZ", "MX", "MY", "MZ"), ("N",) * 3 + ("N*m",) * 3))
        return self._res_done(o, res, {"FX", "FY", "FZ", "MX", "MY", "MZ", "Orientation"})

    def node_displacement(self, o):
        c = self._res_common(o, "node-displacement")
        res = NodeDisplacementResult(**c, **self._six(o, ("UX", "UY", "UZ", "RX", "RY", "RZ"), ("m",) * 3 + ("rad",) * 3))
        return self._res_done(o, res, {"UX", "UY", "UZ", "RX", "RY", "RZ", "Orientation"})

    def global_reactions(self, o):
        c = self._res_common(o, "global-reactions", obj_required=False)
        c["object_id"] = ""
        res = GlobalReactionResult(**c, **self._six(o, ("FX", "FY", "FZ", "MX", "MY", "MZ"), ("N",) * 3 + ("N*m",) * 3))
        return self._res_done(o, res, {"FX", "FY", "FZ", "MX", "MY", "MZ"})

    def storey_drift(self, o):
        c = self._res_common(o, "storey-drift", obj_required=False)
        c["object_id"] = c["object_id"] if c["object_id"] else ""
        d = o.get("Direction") or {}
        dx, dy = abs(_num(d.get("X", 0), "Direction.X")), abs(_num(d.get("Y", 0), "Direction.Y"))
        if dx == dy:
            raise BhomConversionError(f"storey drift direction {d} is neither X nor Y")
        res = StoreyDriftResult(**c, storey=str(o.get("Storey") or ""), direction="x" if dx > dy else "y",
                                ratio=Quantity(value=_num(o.get("Ratio"), "Ratio"), unit="1"))
        return self._res_done(o, res, {"Storey", "Direction", "Ratio"})

    UTIL = ("TensionCompressionRatio", "MajorShearRatio", "MinorShearRatio", "TorsionRatio", "MajorTorsionShearRatio",
            "MinorTorsionShearRatio", "MajorBendingRatio", "MinorBendingRatio", "MajorBendingAxialRatio",
            "MinorBendingAxialRatio", "BiaxialBendingAxialRatio", "MajorUniformCompressionRatio",
            "MinorUniformCompressionRatio", "UniformBendingRatio", "MajorUniformBendingCompressionRatio",
            "MinorUniformBendingCompressionRatio")

    def utilisation(self, o):
        c = self._res_common(o, "steel-utilisation")
        comps = {k: Quantity(value=_num(o[k], k), unit="1") for k in self.UTIL if o.get(k) is not None}
        if not comps:
            raise BhomConversionError("SteelUtilisation with no ratios")
        gov = max(comps, key=lambda k: comps[k].value)
        res = UtilisationResult(**c, ratio=comps[gov], ratio_type=gov, components=comps,
                                position=Quantity(value=_num(o.get("Position", 0.0), "Position"), unit="1"))
        # MajorEffectiveLength / MinorEffectiveLength / SteelClass are not mapped: reported when set
        return self._res_done(o, res, {*self.UTIL, "Position", "Divisions"})


def _order(objs: list[dict]) -> list[dict]:
    """Definitions before the results that refer to them by id."""
    def rank(o):
        t = short_type(o.get("_t", "")) if isinstance(o, dict) else ""
        return 2 if t.startswith("Results.") else 1 if t.startswith("Requests.") else 0
    return sorted(objs, key=rank)


def bhom_to_schema(objs: list[dict], *, doc_sha: str, source: ResultSource, source_name: str = "bhom-json",
                   at: str | None = None) -> tuple[StructuralBundle, Report]:
    """A list of BHoM-serialised objects (top level; nesting is followed) -> a validated bundle."""
    rep = Report()
    cv = _In(doc_sha, source, at, rep)
    for o in _order(objs):
        cv.any(o)
    o = cv.out
    bundle = StructuralBundle(source=f"{source_name} ({source.value})", model_frame=f"ModelM({doc_sha[:12]})",
                              **{c: list(o[c].values()) for c in StructuralBundle.COLLECTIONS})
    return bundle, rep


def load_bhom_json(path: str) -> tuple[list[dict], str]:
    """(objects, sha256) of a BHoM JSON file: a JSON array, {"objects": [...]}, or one object per line."""
    raw = open(path, "rb").read()
    sha = hashlib.sha256(raw).hexdigest()
    text = raw.decode("utf-8").strip()
    if text.startswith("["):
        return json.loads(text), sha
    if text.startswith("{") and "\n" not in text.split("}", 1)[0] and '"objects"' in text[:200]:
        return json.loads(text)["objects"], sha
    try:
        d = json.loads(text)
        return (d["objects"] if isinstance(d, dict) and "objects" in d else [d]), sha
    except json.JSONDecodeError:
        return [json.loads(line) for line in text.splitlines() if line.strip()], sha


# ======================================================================== schema -> BHoM
def _guid(fact, kind: str) -> str:
    for r in getattr(fact, "refs", []):
        if r.system == "bhom" and r.guid:
            return r.guid
    return str(uuid.uuid5(_GUID_NS, f"{kind}:{fact.id}"))


def _bname(fact) -> str:
    for r in getattr(fact, "refs", []):
        if r.system == "bhom" and r.guid:   # came from BHoM: keep its Name, even an empty one
            return r.name
    return fact.name or fact.id.split(":", 1)[-1]


def _btype(fact, default: str) -> str:
    for r in getattr(fact, "refs", []):
        if r.system == "bhom" and r.type:
            return r.type
    return default


def _si(qty: Quantity | None, unit: str, default=0.0):
    return default if qty is None else convert(qty.value, qty.unit, unit)


def _fragments(fact) -> list:
    for r in getattr(fact, "refs", []):
        if r.ids.get("etabs") or r.ids.get("etabs_label"):
            fr = {"_t": ETABS_ID, "Id": r.ids.get("etabs"), "Label": r.ids.get("etabs_label", ""),
                  "Story": r.ids.get("etabs_story", "")}
            fr["PersistentId"] = r.ids.get("etabs_guid")
            return [fr]
    return []


class _Out:
    def __init__(self, b: StructuralBundle):
        self.b = b
        self.idx = {o.id: o for c in StructuralBundle.COLLECTIONS for o in getattr(b, c)}

    def base(self, fact, t: str, kind: str, name: bool = True) -> dict:
        d = {"_t": _btype(fact, t), "BHoM_Guid": _guid(fact, kind)}
        if name:
            d["Name"] = _bname(fact)
        fr = _fragments(fact)
        if fr:
            d["Fragments"] = fr
        return d

    def vec(self, v: QVector | None, unit: str) -> dict:
        if v is None:
            return {"_t": "BH.oM.Geometry.Vector", "X": 0.0, "Y": 0.0, "Z": 0.0}
        return {"_t": "BH.oM.Geometry.Vector", "X": _si(v.x, unit), "Y": _si(v.y, unit), "Z": _si(v.z, unit)}

    def fixity(self, f: Fixity6 | None, t="BH.oM.Structure.Constraints.Constraint6DOF") -> dict | None:
        if f is None:
            return None
        inv = {v: k for k, v in DOF.items()}
        d = {"_t": t, "BHoM_Guid": str(uuid.uuid5(_GUID_NS, f"fix:{f.model_dump_json()}")), "Name": f.name}
        for ours, dk, kk, unit in (("tx", "TranslationX", "TranslationalStiffnessX", "N/m"),
                                   ("ty", "TranslationY", "TranslationalStiffnessY", "N/m"),
                                   ("tz", "TranslationZ", "TranslationalStiffnessZ", "N/m"),
                                   ("rx", "RotationX", "RotationalStiffnessX", "N*m/rad"),
                                   ("ry", "RotationY", "RotationalStiffnessY", "N*m/rad"),
                                   ("rz", "RotationZ", "RotationalStiffnessZ", "N*m/rad")):
            dof = getattr(f, ours)
            d[dk] = inv[dof.type]
            d[kk] = _si(dof.stiffness, unit)
        return d

    def material(self, m: MaterialGrade) -> dict:
        t = {MaterialKind.steel: "MaterialFragments.Steel", MaterialKind.concrete: "MaterialFragments.Concrete",
             MaterialKind.aluminium: "MaterialFragments.Aluminium"}.get(m.kind, "MaterialFragments.GenericIsotropicMaterial")
        d = self.base(m, NS + t, "mat")
        d["Density"] = _si(m.unit_weight, "kN/m3") * 1000.0 / G0
        d["DampingRatio"] = _si(m.damping_ratio, "1")
        d["PoissonsRatio"] = _si(m.nu, "1")
        d["ThermalExpansionCoeff"] = m.thermal_expansion_per_degC or 0.0
        d["YoungsModulus"] = _si(m.E, "Pa")
        if m.kind == MaterialKind.steel:
            d["YieldStress"], d["UltimateStress"] = _si(m.fy, "Pa"), _si(m.fu, "Pa")
        if m.kind == MaterialKind.concrete:
            d["CylinderStrength"], d["CubeStrength"] = _si(m.fc, "Pa"), _si(m.fcu, "Pa")
        return d

    def section(self, s: SectionPropertySet) -> dict:
        default = NS + ("SectionProperties.ExplicitSection" if s.shape == SectionShape.explicit
                        else "SectionProperties.SteelSection")
        d = self.base(s, default, "sec")
        d["Material"] = self.material(self.idx[s.material_id]) if s.material_id else None
        if s.shape != SectionShape.explicit:
            pname = {v: k for k, v in PROFILE_SHAPE.items()}.get(s.shape)
            if pname:
                prof = {"_t": f"BH.oM.Spatial.ShapeProfiles.{pname}"}
                for ours, bk in (("d", "Height"), ("bf", "Width"), ("tw", "WebThickness"), ("tf", "FlangeThickness"),
                                 ("t_design", "Thickness")):
                    if getattr(s, ours) is not None:
                        prof[bk] = _si(getattr(s, ours), "m")
                d["SectionProfile"] = prof
        if s.fabrication:
            d["Fabrication"] = s.fabrication
        for bk, ours, u in SECTION_PROPS:
            d[bk] = _si(getattr(s, ours), u)
        return d

    def node(self, n: AnalyticalNode) -> dict:
        d = self.base(n, NS + "Elements.Node", "node")
        p = n.position
        if isinstance(p.frame, ModelM):
            xyz = (p.x, p.y, p.z)
        elif isinstance(p.frame, BuildingFt):
            xyz = (p.x * FT, p.y * FT, p.z * FT)
        else:
            raise BhomConversionError(f"node {n.id}: cannot write a {p.frame.kind} position to BHoM (needs metres)")
        d["Position"] = {"_t": "BH.oM.Geometry.Point", "X": xyz[0], "Y": xyz[1], "Z": xyz[2]}
        d["Orientation"] = None
        d["Support"] = self.fixity(self.idx[n.support_id].fixity) if n.support_id else None
        return d

    def bar(self, b: AnalyticalBar) -> dict:
        d = self.base(b, NS + "Elements.Bar", "bar")
        d["Start"] = self.node(self.idx[b.start_node])
        d["End"] = self.node(self.idx[b.end_node])
        d["SectionProperty"] = self.section(self.idx[b.section_id]) if b.section_id else None
        d["OrientationAngle"] = _si(b.orientation_angle, "rad")
        if b.releases is not None:
            d["Release"] = {"_t": NS + "Constraints.BarRelease",
                            "BHoM_Guid": str(uuid.uuid5(_GUID_NS, f"rel:{b.releases.model_dump_json()}")),
                            "Name": b.releases.name, "StartRelease": self.fixity(b.releases.start),
                            "EndRelease": self.fixity(b.releases.end)}
        else:
            d["Release"] = None
        d["FEAType"] = {v: k for k, v in FEA.items()}[b.fea_type]
        d["Support"] = None
        d["Offset"] = None if b.offset is None else {
            "_t": NS + "Offsets.Offset", "BHoM_Guid": str(uuid.uuid5(_GUID_NS, f"off:{b.id}")), "Name": "",
            "Start": self.vec(b.offset.start, "m"), "End": self.vec(b.offset.end, "m")}
        return d

    def case(self, c) -> dict:
        if isinstance(c, LoadCase):
            d = self.base(c, NS + "Loads.Loadcase", "case")
            d["Nature"] = NATURE_OUT[c.nature]
            d["Number"] = c.number
            if c.nature == LoadNature.roof_live:
                d["Tags"] = ["calcgraph:roof-live"]
            return d
        d = self.base(c, NS + "Loads.LoadCombination", "combo")
        d["LoadCases"] = [[_si(t.factor, "1"), self.case(self.idx[t.case_id])] for t in c.terms]
        d["Number"] = c.number
        return d

    def group(self, items: list[dict], t: str) -> dict:
        return {"_t": f"BH.oM.Base.BHoMGroup<{t}>", "BHoM_Guid": str(uuid.uuid5(_GUID_NS, "grp:" + ",".join(
            i["BHoM_Guid"] for i in items))), "Name": "", "Elements": items}

    def load(self, ld) -> dict:
        common = lambda d: d.update(Loadcase=self.case(self.idx[ld.case_id]),  # noqa: E731
                                    Axis="Local" if ld.axis == AxisSystem.local else "Global", Projected=ld.projected)
        if isinstance(ld, PointLoad):
            d = self.base(ld, NS + "Loads.PointLoad", "load")
            d.update(Force=self.vec(ld.force, "N"), Moment=self.vec(ld.moment, "N*m"),
                     Objects=self.group([self.node(self.idx[i]) for i in ld.node_ids], NS + "Elements.Node"))
        elif isinstance(ld, BarPointLoad):
            d = self.base(ld, NS + "Loads.BarPointLoad", "load")
            d.update(DistanceFromA=_si(ld.distance_from_start, "m"), Force=self.vec(ld.force, "N"),
                     Moment=self.vec(ld.moment, "N*m"),
                     Objects=self.group([self.bar(self.idx[i]) for i in ld.bar_ids], NS + "Elements.Bar"))
        elif isinstance(ld, BarDistributedLoad) and ld.uniform:
            d = self.base(ld, NS + "Loads.BarUniformlyDistributedLoad", "load")
            d.update(Force=self.vec(ld.force_start, "N/m"), Moment=self.vec(ld.moment_start, "N"),
                     Objects=self.group([self.bar(self.idx[i]) for i in ld.bar_ids], NS + "Elements.Bar"))
        elif isinstance(ld, BarDistributedLoad):
            pu = "1" if ld.relative_positions else "m"
            d = self.base(ld, NS + "Loads.BarVaryingDistributedLoad", "load")
            d.update(StartPosition=_si(ld.start_position, pu), ForceAtStart=self.vec(ld.force_start, "N/m"),
                     MomentAtStart=self.vec(ld.moment_start, "N"), EndPosition=_si(ld.end_position, pu),
                     ForceAtEnd=self.vec(ld.force_end, "N/m"), MomentAtEnd=self.vec(ld.moment_end, "N"),
                     RelativePositions=ld.relative_positions,
                     Objects=self.group([self.bar(self.idx[i]) for i in ld.bar_ids], NS + "Elements.Bar"))
        elif isinstance(ld, GravityLoad):
            d = self.base(ld, NS + "Loads.GravityLoad", "load")
            objs = [self.bar(self.idx[i]) if i in {b.id for b in self.b.bars} else self.node(self.idx[i])
                    for i in ld.object_ids]
            kinds = {x["_t"] for x in objs}
            gt = kinds.pop() if len(kinds) == 1 else "BH.oM.Base.BHoMObject"
            d.update(GravityDirection=self.vec(ld.direction, "1"), Objects=self.group(objs, gt))
        elif isinstance(ld, AreaLoad):
            raise BhomConversionError("area loads need panels, which this converter does not write yet")
        else:
            raise BhomConversionError(f"unknown load {type(ld).__name__}")
        common(d)
        return d

    def request(self, r: ResultRequest) -> dict:
        inv_b, inv_n, inv_g = ({v: k for k, v in t.items()} for t in (REQ_BAR, REQ_NODE, REQ_GLOBAL))
        if r.kind in inv_b:
            d = {"_t": NS + "Requests.BarResultRequest", "ResultType": inv_b[r.kind],
                 "DivisionType": {v: k for k, v in DIVISION.items()}[r.division_type], "Divisions": r.divisions}
        elif r.kind in inv_n:
            d = {"_t": NS + "Requests.NodeResultRequest", "ResultType": inv_n[r.kind],
                 "Axis": "Local" if r.axis == AxisSystem.local else "Global"}
        elif r.kind in inv_g:
            d = {"_t": NS + "Requests.GlobalResultRequest", "ResultType": inv_g[r.kind]}
        else:
            raise BhomConversionError(f"no BHoM request type for {r.kind.value}")
        d["Cases"] = [self.case(self.idx[c]) for c in r.case_ids]
        d["Modes"] = list(r.modes)
        d["ObjectIds"] = list(r.object_ids)
        return d

    def _obj_ref(self, oid: str):
        """The id BHoM results use for an object: its adapter id when it has one, else its name."""
        if not oid:
            return ""
        o = self.idx[oid]
        for r in o.refs:
            if r.ids.get("etabs"):
                return r.ids["etabs"]
        return oid.split(":", 1)[1]

    def _case_ref(self, cid: str):
        return _bname(self.idx[cid])

    def result(self, r) -> dict:
        d = {"ObjectId": self._obj_ref(r.object_id), "ResultCase": self._case_ref(r.case_id),
             "ModeNumber": r.mode_number, "TimeStep": r.time_step}
        six = lambda keys, ours, units: {k: (None if getattr(r, o) is None else _si(getattr(r, o), u))  # noqa: E731
                                         for k, o, u in zip(keys, ours, units)}
        F, M = ("FX", "FY", "FZ"), ("MX", "MY", "MZ")
        if isinstance(r, BarForceResult):
            d = {"_t": NS + "Results.BarForce", **d, "Position": _si(r.position, "1"), "Divisions": r.divisions,
                 **six(F + M, ("fx", "fy", "fz", "mx", "my", "mz"), ("N",) * 3 + ("N*m",) * 3)}
        elif isinstance(r, NodeReactionResult):
            d = {"_t": NS + "Results.NodeReaction", **d,
                 **six(F + M, ("fx", "fy", "fz", "mx", "my", "mz"), ("N",) * 3 + ("N*m",) * 3)}
        elif isinstance(r, NodeDisplacementResult):
            d = {"_t": NS + "Results.NodeDisplacement", **d,
                 **six(("UX", "UY", "UZ", "RX", "RY", "RZ"), ("ux", "uy", "uz", "rx", "ry", "rz"), ("m",) * 3 + ("rad",) * 3)}
        elif isinstance(r, GlobalReactionResult):
            d = {"_t": NS + "Results.GlobalReactions", **d,
                 **six(F + M, ("fx", "fy", "fz", "mx", "my", "mz"), ("N",) * 3 + ("N*m",) * 3)}
        elif isinstance(r, StoreyDriftResult):
            d = {"_t": NS + "Results.StoreyDrift", **d, "Storey": r.storey,
                 "Direction": {"_t": "BH.oM.Geometry.Vector", "X": 1.0 if r.direction == "x" else 0.0,
                               "Y": 1.0 if r.direction == "y" else 0.0, "Z": 0.0},
                 "Ratio": _si(r.ratio, "1")}
        elif isinstance(r, UtilisationResult):
            d = {"_t": NS + "Results.SteelUtilisation", **d, "Position": _si(r.position, "1", 0.0),
                 **{k: _si(v, "1") for k, v in r.components.items()}}
        else:
            raise BhomConversionError(f"unknown result {type(r).__name__}")
        return d


def schema_to_bhom(bundle: StructuralBundle, *, include_results: bool = True) -> list[dict]:
    """A bundle -> top-level BHoM-serialised objects, in BHoM's own nesting (full nested
    objects, SI units). Order: materials, sections, nodes, bars, cases, combos, loads,
    requests, results."""
    o = _Out(bundle)
    out = [o.material(m) for m in bundle.materials] + [o.section(s) for s in bundle.sections]
    out += [o.node(n) for n in bundle.nodes] + [o.bar(b) for b in bundle.bars]
    out += [o.case(c) for c in bundle.load_cases] + [o.case(c) for c in bundle.combinations]
    out += [o.load(ld) for ld in bundle.loads] + [o.request(r) for r in bundle.requests]
    if include_results:
        out += [o.result(r) for r in bundle.results]
    if bundle.panels or bundle.surface_properties:
        raise BhomConversionError("panels / surface properties are not written to BHoM yet")
    return out


def canonical(bundle: StructuralBundle, strip_provenance: bool = True) -> str:
    """Canonical JSON of a bundle for diffing (provenance optional: it names the source doc)."""
    d = bundle.model_dump(mode="json")
    if strip_provenance:
        def strip(x):
            if isinstance(x, dict):
                return {k: strip(v) for k, v in x.items() if k not in ("provenance", "model_frame", "source")}
            if isinstance(x, list):
                return [strip(v) for v in x]
            return x
        d = strip(d)

    def rnd(x):
        if isinstance(x, float):
            return float(f"{x:.12g}")
        if isinstance(x, dict):
            return {k: rnd(v) for k, v in x.items()}
        if isinstance(x, list):
            return [rnd(v) for v in x]
        return x
    return json.dumps(rnd(d), sort_keys=True, separators=(",", ":"))
