"""Structural analysis types: the analytical model, its properties, loads and results.

Modelled on the class shapes of BHoM Structure_oM (github.com/BHoM/BHoM, Structure_oM:
Constraints, Elements, Offsets, SectionProperties, MaterialFragments, Loads, Requests,
Results) - read for their SHAPE only, no BHoM source is copied here. Field-by-field mapping
to BHoM and to Speckle's structural kits: docs/schema-bhom-mapping.md.

Same contract as schema/models.py:
- every type here is a `Fact` (mandatory `Provenance`); nothing structural is "just data"
- every number is a `Quantity` with a unit from the closed vocabulary in schema/units.py, and
  each field checks the DIMENSION it needs (a section area given in in4 fails, a pressure
  given as a line load fails)
- every position is a framed `Point3`; a vector is a `QVector` in a named axis system
- every RESULT says which program produced it (`source`): real ETABS via BHoM, real CSI OAPI,
  calc-graph's PyNite, or the mock. A result with no source does not validate.

Analytical vs physical: `Element` (schema/models.py) is the PHYSICAL member a drawing,
schedule or IFC shows. `AnalyticalBar` / `AnalyticalNode` / `AnalyticalPanel` are the
analysis idealisation; `physical_id` points from the idealisation to the physical element
(many analytical bars may idealise one physical column - one per storey in ETABS).
"""
from __future__ import annotations

from enum import Enum
from typing import Annotated, ClassVar, Literal, Union

from pydantic import Field, field_validator, model_validator

from .frames import Point3, same_frame
from .models import Fact, _M
from .units import (ANGLE, AREA, FORCE, LENGTH, LINE_LOAD, MOMENT, NONE, PRESSURE, Quantity, UnitMismatch,
                    dim)

STRUCTURAL_SCHEMA_VERSION = "calcgraph-structural/1.0"

L4 = (4, 0, 0)
L6 = (6, 0, 0)
VOLUME_ = (3, 0, 0)
FORCE_PER_VOLUME = (-3, 1, 0)
ROT_STIFFNESS = (1, 1, -1)
TRANS_STIFFNESS = LINE_LOAD  # force / length


def _need(qty: Quantity | None, want: tuple, what: str) -> Quantity | None:
    if qty is not None and dim(qty.unit) != want:
        raise UnitMismatch(f"{what} must have dimension {want} (length, force, angle), got {qty.unit}")
    return qty


# ------------------------------------------------------------------ external identity
class ExternalRef(_M):
    """The identity an object has in another system (kept so a round trip is lossless)."""
    system: str = Field(description="bhom | etabs | speckle | ifc | risa ...")
    type: str = Field(default="", description="the system's type name, e.g. BH.oM.Structure.Elements.Bar")
    guid: str = ""
    name: str = ""
    ids: dict[str, str] = Field(default_factory=dict, description="adapter ids, e.g. {'etabs': '12', 'etabs_label': 'B12'}")


class StructuralFact(Fact):
    name: str = ""
    refs: list[ExternalRef] = Field(default_factory=list)


# ------------------------------------------------------------------ vectors
class AxisSystem(str, Enum):
    global_ = "global"
    local = "local"


class QVector(_M):
    """A vector with a unit on each component, in a named axis system.

    `frame` names the global frame the components are measured in when axis == global (e.g.
    ModelM of a BHoM/ETABS model, BuildingFt of a drawing set); for axis == local the
    components are along the element's own local axes (x along the member)."""
    axis: AxisSystem = AxisSystem.global_
    x: Quantity
    y: Quantity
    z: Quantity

    @model_validator(mode="after")
    def _one_dimension(self):
        d = {dim(c.unit) for c in (self.x, self.y, self.z)}
        if len(d) != 1:
            raise UnitMismatch(f"vector components disagree in dimension: {self.x.unit}, {self.y.unit}, {self.z.unit}")
        return self

    @property
    def dimension(self):
        return dim(self.x.unit)

    def need(self, want: tuple, what: str) -> "QVector":
        if self.dimension != want:
            raise UnitMismatch(f"{what} must have dimension {want}, got {self.x.unit}")
        return self

    def is_zero(self) -> bool:
        return self.x.value == 0 and self.y.value == 0 and self.z.value == 0


def qvec(x: float, y: float, z: float, unit: str, axis: AxisSystem = AxisSystem.global_) -> QVector:
    return QVector(axis=axis, x=Quantity(value=x, unit=unit), y=Quantity(value=y, unit=unit),
                   z=Quantity(value=z, unit=unit))


# ------------------------------------------------------------------ fixity: supports and end releases
class DOFType(str, Enum):
    """Fixity of one degree of freedom (BHoM DOFType values, as names)."""
    free = "free"
    fixed = "fixed"
    fixed_negative = "fixed-negative"
    fixed_positive = "fixed-positive"
    spring = "spring"
    spring_negative = "spring-negative"
    spring_positive = "spring-positive"
    spring_relative = "spring-relative"
    spring_relative_negative = "spring-relative-negative"
    spring_relative_positive = "spring-relative-positive"
    nonlinear = "nonlinear"
    friction = "friction"
    damped = "damped"
    gap = "gap"


class Dof(_M):
    """One DOF: its type and, for the spring kinds, a stiffness with a unit."""
    type: DOFType = DOFType.free
    stiffness: Quantity | None = None

    @model_validator(mode="after")
    def _spring_needs_stiffness(self):
        if self.type.value.startswith("spring") and self.stiffness is None:
            raise ValueError(f"DOF type {self.type.value} needs a stiffness")
        return self


_T, _R = ("tx", "ty", "tz"), ("rx", "ry", "rz")


class Fixity6(_M):
    """Six DOFs (BHoM Constraint6DOF). Translational stiffness is force/length, rotational
    stiffness is moment/angle; a stiffness in the wrong dimension fails."""
    name: str = ""
    tx: Dof = Field(default_factory=Dof)
    ty: Dof = Field(default_factory=Dof)
    tz: Dof = Field(default_factory=Dof)
    rx: Dof = Field(default_factory=Dof)
    ry: Dof = Field(default_factory=Dof)
    rz: Dof = Field(default_factory=Dof)

    @model_validator(mode="after")
    def _stiffness_dims(self):
        for k in _T:
            _need(getattr(self, k).stiffness, TRANS_STIFFNESS, f"{k} spring stiffness")
        for k in _R:
            _need(getattr(self, k).stiffness, ROT_STIFFNESS, f"{k} spring stiffness")
        return self

    def code(self) -> str:
        """Speckle-style 6-letter code: F fixed, R released/free, K spring, X anything else."""
        m = {DOFType.fixed: "F", DOFType.free: "R"}
        return "".join(m.get(getattr(self, k).type, "K" if getattr(self, k).type.value.startswith("spring") else "X")
                       for k in (*_T, *_R))

    @classmethod
    def from_flags(cls, fixed: list[bool], name: str = "") -> "Fixity6":
        """[tx, ty, tz, rx, ry, rz] booleans (True = fixed) as in ETABS PointObj.GetRestraint."""
        if len(fixed) != 6:
            raise ValueError("need six flags")
        return cls(name=name, **{k: Dof(type=DOFType.fixed if f else DOFType.free) for k, f in zip((*_T, *_R), fixed)})


class EndReleases(_M):
    """Member end fixity (BHoM BarRelease). Convention as BHoM: `fixed` = the DOF is
    CONNECTED to the node (moment/force transferred), `free` = RELEASED. A pin-pin beam is
    rotations ry/rz free at both ends. (ETABS GetReleases uses the inverse: True = released.)"""
    name: str = ""
    start: Fixity6
    end: Fixity6

    @classmethod
    def from_etabs_released(cls, ii: list[bool], jj: list[bool], name: str = "") -> "EndReleases":
        return cls(name=name, start=Fixity6.from_flags([not r for r in ii]), end=Fixity6.from_flags([not r for r in jj]))

    def etabs_released(self) -> tuple[list[bool], list[bool]]:
        def flags(f: Fixity6):
            out = []
            for k in (*_T, *_R):
                t = getattr(f, k).type
                if t not in (DOFType.fixed, DOFType.free):
                    raise ValueError(f"ETABS boolean releases cannot carry DOF type {t.value}")
                out.append(t == DOFType.free)
            return out
        return flags(self.start), flags(self.end)


class Offset(_M):
    """Rigid end offsets (BHoM Offset: start / end vectors). Lengths with units."""
    start: QVector
    end: QVector

    @model_validator(mode="after")
    def _lengths(self):
        self.start.need(LENGTH, "start offset")
        self.end.need(LENGTH, "end offset")
        return self


# ------------------------------------------------------------------ materials and sections
class MaterialKind(str, Enum):
    steel = "steel"
    concrete = "concrete"
    aluminium = "aluminium"
    timber = "timber"
    rebar = "rebar"
    generic_isotropic = "generic-isotropic"
    generic_orthotropic = "generic-orthotropic"


class MaterialGrade(StructuralFact):
    """A material grade: standard + grade + the mechanical properties analysis needs.

    `unit_weight` is a WEIGHT density (force/volume: pcf, kN/m3). A source that gives mass
    density (BHoM: kg/m3) is converted with standard gravity g0 = 9.80665 m/s2, which the
    converter states in the provenance rule text."""
    kind: MaterialKind
    standard: str = Field(default="", description="e.g. ASTM A992, ASTM A500, ACI 318 NW")
    grade: str = Field(default="", description="e.g. Grade 50, Gr C, f'c 4000 psi")
    E: Quantity | None = Field(default=None, description="Young's modulus")
    G: Quantity | None = Field(default=None, description="shear modulus")
    nu: Quantity | None = Field(default=None, description="Poisson's ratio (unit 1)")
    unit_weight: Quantity | None = None
    damping_ratio: Quantity | None = None
    thermal_expansion_per_degC: float | None = Field(
        default=None, description="1/degC; temperature is outside the unit vocabulary, so the unit is in the field name")
    fy: Quantity | None = Field(default=None, description="yield stress (steel, rebar)")
    fu: Quantity | None = Field(default=None, description="ultimate stress (steel, rebar)")
    fy_expected: Quantity | None = Field(default=None, description="expected yield Ry*Fy (AISC 341), if declared")
    fu_expected: Quantity | None = Field(default=None, description="expected tensile Rt*Fu, if declared")
    fc: Quantity | None = Field(default=None, description="concrete cylinder strength")
    fcu: Quantity | None = Field(default=None, description="concrete cube strength")

    @model_validator(mode="after")
    def _dims(self):
        for k in ("E", "G", "fy", "fu", "fy_expected", "fu_expected", "fc", "fcu"):
            _need(getattr(self, k), PRESSURE, k)
        for k in ("nu", "damping_ratio"):
            _need(getattr(self, k), NONE, k)
        _need(self.unit_weight, FORCE_PER_VOLUME, "unit_weight")
        return self


class SectionShape(str, Enum):
    i = "I"          # W, S, M, HP, welded I
    rect_hollow = "rect-hollow"
    circ_hollow = "circ-hollow"
    pipe = "pipe"
    channel = "channel"
    angle = "angle"
    double_angle = "double-angle"
    tee = "tee"
    rect = "rect"
    circle = "circle"
    explicit = "explicit"   # properties only, no profile
    other = "other"


class SectionPropertySet(StructuralFact):
    """A frame section and its properties (BHoM ISectionProperty: SteelSection, ConcreteSection,
    ExplicitSection ...). Axis names follow US practice: x = MAJOR (strong) axis, y = MINOR.
    (BHoM names them y = major, z = minor: Iy -> Ix here, Iz -> Iy; see the mapping doc.)"""
    designation: str = Field(description="e.g. W18X40, HSS6X6X3/8")
    shape: SectionShape
    material_id: str | None = None
    catalogue: str = Field(default="", description="e.g. 'AISC Shapes Database v16.0'")
    fabrication: str = Field(default="", description="hot-rolled / welded / cold-formed")
    # profile dimensions
    d: Quantity | None = None
    bf: Quantity | None = None
    tw: Quantity | None = None
    tf: Quantity | None = None
    t_design: Quantity | None = None
    # properties
    A: Quantity | None = None
    Ix: Quantity | None = None
    Iy: Quantity | None = None
    J: Quantity | None = None
    Cw: Quantity | None = None
    Sx: Quantity | None = None
    Sy: Quantity | None = None
    Zx: Quantity | None = None
    Zy: Quantity | None = None
    rx: Quantity | None = None
    ry: Quantity | None = None
    Avx: Quantity | None = Field(default=None, description="shear area parallel to the major axis web direction")
    Avy: Quantity | None = None
    weight_per_length: Quantity | None = None

    @model_validator(mode="after")
    def _dims(self):
        for k in ("d", "bf", "tw", "tf", "t_design", "rx", "ry"):
            _need(getattr(self, k), LENGTH, k)
        for k in ("A", "Avx", "Avy"):
            _need(getattr(self, k), AREA, k)
        for k in ("Ix", "Iy", "J"):
            _need(getattr(self, k), L4, k)
        for k in ("Sx", "Sy", "Zx", "Zy"):
            _need(getattr(self, k), VOLUME_, k)
        _need(self.Cw, L6, "Cw")
        _need(self.weight_per_length, LINE_LOAD, "weight_per_length")
        return self


class SurfacePropertySet(StructuralFact):
    """A panel property (BHoM ISurfaceProperty: ConstantThickness, SlabOnDeck ...), minimal."""
    kind: str = Field(description="constant-thickness | slab-on-deck | ribbed | layered | other")
    material_id: str | None = None
    thickness: Quantity | None = None

    @field_validator("thickness")
    @classmethod
    def _t(cls, v):
        return _need(v, LENGTH, "thickness")


# ------------------------------------------------------------------ analytical elements
class BarFEAType(str, Enum):
    flexural = "flexural"
    axial = "axial"
    compression_only = "compression-only"
    tension_only = "tension-only"


class StructuralUsage(str, Enum):
    undefined = "undefined"
    beam = "beam"
    column = "column"
    brace = "brace"
    cable = "cable"
    pile = "pile"


class Support(StructuralFact):
    """A support: fixity applied at an analytical node (BHoM Node.Support)."""
    node_id: str
    fixity: Fixity6


class AnalyticalNode(StructuralFact):
    position: Point3
    support_id: str | None = None
    physical_id: str | None = Field(default=None, description="physical element / connection this node idealises")
    story: str = ""


class AnalyticalBar(StructuralFact):
    """A 1D analytical member between two nodes (BHoM Bar)."""
    start_node: str
    end_node: str
    section_id: str | None = None
    orientation_angle: Quantity = Field(default_factory=lambda: Quantity(value=0.0, unit="deg"))
    releases: EndReleases | None = None
    offset: Offset | None = None
    fea_type: BarFEAType = BarFEAType.flexural
    usage: StructuralUsage = StructuralUsage.undefined
    physical_id: str | None = Field(default=None, description="the physical Element this bar idealises")
    story: str = ""

    @field_validator("orientation_angle")
    @classmethod
    def _angle(cls, v):
        return _need(v, ANGLE, "orientation_angle")

    @model_validator(mode="after")
    def _two_nodes(self):
        if self.start_node == self.end_node:
            raise ValueError(f"bar {self.id}: start and end node are the same ({self.start_node})")
        return self


class AnalyticalPanel(StructuralFact):
    """A 2D analytical element (BHoM Panel), boundary as node ids in order."""
    boundary_nodes: list[str] = Field(min_length=3)
    property_id: str | None = None
    orientation_angle: Quantity = Field(default_factory=lambda: Quantity(value=0.0, unit="deg"))
    physical_id: str | None = None

    @field_validator("orientation_angle")
    @classmethod
    def _angle(cls, v):
        return _need(v, ANGLE, "orientation_angle")


# ------------------------------------------------------------------ loading
class LoadNature(str, Enum):
    dead = "dead"
    superimposed_dead = "superimposed-dead"
    live = "live"
    roof_live = "roof-live"
    snow = "snow"
    wind = "wind"
    seismic = "seismic"
    temperature = "temperature"
    accidental = "accidental"
    prestress = "prestress"
    notional = "notional"
    other = "other"


class LoadCase(StructuralFact):
    """A load case / load pattern (BHoM Loadcase; ETABS load pattern + its linear static case)."""
    nature: LoadNature
    number: int = 0
    self_weight_multiplier: Quantity = Field(default_factory=lambda: Quantity(value=0.0, unit="1"))
    description: str = ""

    @field_validator("self_weight_multiplier")
    @classmethod
    def _sw(cls, v):
        return _need(v, NONE, "self_weight_multiplier")


class CombinationKind(str, Enum):
    linear_add = "linear-add"
    envelope = "envelope"
    absolute_add = "absolute-add"
    srss = "srss"


class CombinationTerm(_M):
    case_id: str = Field(description="a LoadCase id or another LoadCombination id")
    factor: Quantity

    @field_validator("factor")
    @classmethod
    def _f(cls, v):
        return _need(v, NONE, "combination factor")


class LoadCombination(StructuralFact):
    """A load combination (BHoM LoadCombination: [(factor, case)])."""
    terms: list[CombinationTerm] = Field(min_length=1)
    kind: CombinationKind = CombinationKind.linear_add
    number: int = 0
    code_ref: str = Field(default="", description="e.g. ASCE 7-16 2.3.6 (5)")
    group: str = Field(default="", description="gravity | seismic | wind | overstrength | service ...")


class _LoadBase(StructuralFact):
    case_id: str
    axis: AxisSystem = AxisSystem.global_
    projected: bool = False


class PointLoad(_LoadBase):
    """Force/moment at nodes (BHoM PointLoad)."""
    kind: Literal["point"] = "point"
    node_ids: list[str] = Field(min_length=1)
    force: QVector | None = None
    moment: QVector | None = None

    @model_validator(mode="after")
    def _dims(self):
        if self.force is None and self.moment is None:
            raise ValueError("point load needs a force or a moment")
        self.force and self.force.need(FORCE, "point load force")
        self.moment and self.moment.need(MOMENT, "point load moment")
        return self


class BarPointLoad(_LoadBase):
    """Concentrated force/moment on bars at a distance from the start (BHoM BarPointLoad)."""
    kind: Literal["bar-point"] = "bar-point"
    bar_ids: list[str] = Field(min_length=1)
    distance_from_start: Quantity
    force: QVector | None = None
    moment: QVector | None = None

    @model_validator(mode="after")
    def _dims(self):
        if self.force is None and self.moment is None:
            raise ValueError("bar point load needs a force or a moment")
        _need(self.distance_from_start, LENGTH, "distance_from_start")
        self.force and self.force.need(FORCE, "bar point load force")
        self.moment and self.moment.need(MOMENT, "bar point load moment")
        return self


class BarDistributedLoad(_LoadBase):
    """Uniform or linearly varying load along bars (BHoM BarUniformlyDistributedLoad /
    BarVaryingDistributedLoad). Positions are lengths from the start, or fractions of the
    length (unit 1) when `relative_positions`."""
    kind: Literal["bar-distributed"] = "bar-distributed"
    bar_ids: list[str] = Field(min_length=1)
    force_start: QVector
    force_end: QVector | None = Field(default=None, description="None = uniform (force_start along the whole span)")
    moment_start: QVector | None = None
    moment_end: QVector | None = None
    start_position: Quantity | None = None
    end_position: Quantity | None = None
    relative_positions: bool = True

    @model_validator(mode="after")
    def _dims(self):
        self.force_start.need(LINE_LOAD, "distributed force")
        self.force_end and self.force_end.need(LINE_LOAD, "distributed force at end")
        for m in (self.moment_start, self.moment_end):
            m and m.need(FORCE, "distributed moment (moment per length = force)")
        want = NONE if self.relative_positions else LENGTH
        for k in ("start_position", "end_position"):
            _need(getattr(self, k), want, k)
        return self

    @property
    def uniform(self) -> bool:
        return self.force_end is None


class AreaLoad(_LoadBase):
    """Uniform pressure on panels (BHoM AreaUniformlyDistributedLoad)."""
    kind: Literal["area"] = "area"
    panel_ids: list[str] = Field(min_length=1)
    pressure: QVector

    @model_validator(mode="after")
    def _dims(self):
        self.pressure.need(PRESSURE, "area load pressure")
        return self


class GravityLoad(_LoadBase):
    """Self weight of the listed objects (BHoM GravityLoad), direction as unit-1 factors."""
    kind: Literal["gravity"] = "gravity"
    object_ids: list[str] = Field(default_factory=list, description="empty = every object")
    direction: QVector

    @model_validator(mode="after")
    def _dims(self):
        self.direction.need(NONE, "gravity direction factors")
        return self


Load = Annotated[Union[PointLoad, BarPointLoad, BarDistributedLoad, AreaLoad, GravityLoad], Field(discriminator="kind")]


# ------------------------------------------------------------------ result requests and results
class ResultKind(str, Enum):
    bar_force = "bar-force"
    bar_displacement = "bar-displacement"
    node_reaction = "node-reaction"
    node_displacement = "node-displacement"
    global_reactions = "global-reactions"
    storey_drift = "storey-drift"
    steel_utilisation = "steel-utilisation"
    modal = "modal"


class DivisionType(str, Enum):
    evenly_distributed = "evenly-distributed"
    extreme_values = "extreme-values"


class ResultRequest(StructuralFact):
    """What to pull from an analysis (BHoM BarResultRequest / NodeResultRequest /
    GlobalResultRequest). Provenance says who or what asked (e.g. a move-a-column job)."""
    kind: ResultKind
    case_ids: list[str] = Field(default_factory=list, description="empty = all cases")
    object_ids: list[str] = Field(default_factory=list, description="empty = all objects")
    modes: list[str] = Field(default_factory=list)
    divisions: int = Field(default=5, ge=1)
    division_type: DivisionType = DivisionType.evenly_distributed
    axis: AxisSystem = AxisSystem.global_


class ResultSource(str, Enum):
    """Which program produced a value. Shown next to every number in the UI."""
    etabs_via_bhom = "etabs-via-bhom"        # real ETABS, pulled through BHoM's ETABS_Toolkit
    csi_oapi = "csi-oapi"                     # real ETABS, read directly through CSI's OAPI
    calcgraph_pynite = "calcgraph-pynite"     # calc-graph's own re-analysis (PyNite)
    mock = "mock"                             # mock adapter: calc-graph values in vendor shapes
    imported_file = "imported-file"           # a BHoM / Speckle JSON file someone handed us

    @property
    def real_vendor_run(self) -> bool:
        return self in (ResultSource.etabs_via_bhom, ResultSource.csi_oapi)


class _ResultBase(StructuralFact):
    source: ResultSource
    object_id: str = Field(description="analytical object id (bar / node), or '' for a global result")
    case_id: str = Field(description="LoadCase or LoadCombination id")
    mode_number: int = 0
    time_step: float = 0.0
    request_id: str | None = None


class BarForceResult(_ResultBase):
    """Internal forces at one station along a bar (BHoM BarForce). position is the fraction
    of the length (0 = start, 1 = end), unit 1. Local axes: x along the bar, y/z per the
    member's orientation (BHoM: FY/MY minor/major as in its convention; see mapping doc)."""
    kind: Literal["bar-force"] = "bar-force"
    position: Quantity
    divisions: int = 0
    fx: Quantity
    fy: Quantity
    fz: Quantity
    mx: Quantity
    my: Quantity
    mz: Quantity

    @model_validator(mode="after")
    def _dims(self):
        _need(self.position, NONE, "position")
        if not 0.0 <= self.position.value <= 1.0:
            raise ValueError(f"bar result position {self.position.value} outside [0, 1]")
        for k in ("fx", "fy", "fz"):
            _need(getattr(self, k), FORCE, k)
        for k in ("mx", "my", "mz"):
            _need(getattr(self, k), MOMENT, k)
        return self


class NodeReactionResult(_ResultBase):
    kind: Literal["node-reaction"] = "node-reaction"
    fx: Quantity
    fy: Quantity
    fz: Quantity
    mx: Quantity | None = None
    my: Quantity | None = None
    mz: Quantity | None = None

    @model_validator(mode="after")
    def _dims(self):
        for k in ("fx", "fy", "fz"):
            _need(getattr(self, k), FORCE, k)
        for k in ("mx", "my", "mz"):
            _need(getattr(self, k), MOMENT, k)
        return self


class NodeDisplacementResult(_ResultBase):
    kind: Literal["node-displacement"] = "node-displacement"
    ux: Quantity
    uy: Quantity
    uz: Quantity
    rx: Quantity | None = None
    ry: Quantity | None = None
    rz: Quantity | None = None

    @model_validator(mode="after")
    def _dims(self):
        for k in ("ux", "uy", "uz"):
            _need(getattr(self, k), LENGTH, k)
        for k in ("rx", "ry", "rz"):
            _need(getattr(self, k), ANGLE, k)
        return self


class GlobalReactionResult(_ResultBase):
    """Sum of reactions for a case (BHoM GlobalReactions; ETABS Results.BaseReact)."""
    kind: Literal["global-reactions"] = "global-reactions"
    fx: Quantity
    fy: Quantity
    fz: Quantity
    mx: Quantity | None = None
    my: Quantity | None = None
    mz: Quantity | None = None

    @model_validator(mode="after")
    def _dims(self):
        for k in ("fx", "fy", "fz"):
            _need(getattr(self, k), FORCE, k)
        for k in ("mx", "my", "mz"):
            _need(getattr(self, k), MOMENT, k)
        return self


class StoreyDriftResult(_ResultBase):
    """Inter-storey drift ratio (BHoM StoreyDrift; ETABS Results.StoryDrifts)."""
    kind: Literal["storey-drift"] = "storey-drift"
    storey: str
    direction: Literal["x", "y"]
    ratio: Quantity
    limit: Quantity | None = None

    @model_validator(mode="after")
    def _dims(self):
        _need(self.ratio, NONE, "drift ratio")
        _need(self.limit, NONE, "drift limit")
        return self


class UtilisationResult(_ResultBase):
    """Design demand/capacity of a member (BHoM SteelUtilisation, reduced to the governing
    ratio + its type; ETABS DesignSteel.GetSummaryResults)."""
    kind: Literal["steel-utilisation"] = "steel-utilisation"
    ratio: Quantity
    ratio_type: str = Field(default="", description="PMM, shear major, ... as the program names it")
    position: Quantity | None = None
    components: dict[str, Quantity] = Field(default_factory=dict, description="named sub-ratios, unit 1")

    @model_validator(mode="after")
    def _dims(self):
        _need(self.ratio, NONE, "utilisation ratio")
        for k, v in self.components.items():
            _need(v, NONE, f"utilisation component {k}")
        return self


Result = Annotated[Union[BarForceResult, NodeReactionResult, NodeDisplacementResult, GlobalReactionResult,
                         StoreyDriftResult, UtilisationResult], Field(discriminator="kind")]


# ------------------------------------------------------------------ the bundle
class StructuralBundle(_M):
    """One analysis model (and optionally its results), validated. Ids are unique across the
    bundle and every reference resolves."""
    schema_version: Literal["calcgraph-structural/1.0"] = STRUCTURAL_SCHEMA_VERSION
    source: str
    model_frame: str = Field(default="", description="the global frame node positions are in, e.g. ModelM(<sha>)")
    materials: list[MaterialGrade] = Field(default_factory=list)
    sections: list[SectionPropertySet] = Field(default_factory=list)
    surface_properties: list[SurfacePropertySet] = Field(default_factory=list)
    nodes: list[AnalyticalNode] = Field(default_factory=list)
    supports: list[Support] = Field(default_factory=list)
    bars: list[AnalyticalBar] = Field(default_factory=list)
    panels: list[AnalyticalPanel] = Field(default_factory=list)
    load_cases: list[LoadCase] = Field(default_factory=list)
    combinations: list[LoadCombination] = Field(default_factory=list)
    loads: list[Load] = Field(default_factory=list)
    requests: list[ResultRequest] = Field(default_factory=list)
    results: list[Result] = Field(default_factory=list)

    COLLECTIONS: ClassVar[tuple[str, ...]] = ("materials", "sections", "surface_properties", "nodes", "supports", "bars", "panels", "load_cases",
                   "combinations", "loads", "requests", "results")

    @model_validator(mode="after")
    def _integrity(self):
        ids: dict[str, str] = {}
        for coll in self.COLLECTIONS:
            for o in getattr(self, coll):
                if o.id in ids:
                    raise ValueError(f"duplicate id {o.id!r} ({ids[o.id]} and {coll})")
                ids[o.id] = coll

        def need(ref, colls, what):
            if ref is not None and ids.get(ref) not in colls:
                raise ValueError(f"{what} -> {ref!r} does not resolve to {'/'.join(colls)}")

        frame = None
        for n in self.nodes:
            need(n.support_id, ("supports",), f"node {n.id} support")
            if frame is None:
                frame = n.position.frame
            elif not same_frame(frame, n.position.frame):
                raise ValueError(f"node {n.id} is in a different frame from the other nodes")
        for s in self.supports:
            need(s.node_id, ("nodes",), f"support {s.id} node")
        for s in self.sections:
            need(s.material_id, ("materials",), f"section {s.id} material")
        for s in self.surface_properties:
            need(s.material_id, ("materials",), f"surface property {s.id} material")
        for b in self.bars:
            need(b.start_node, ("nodes",), f"bar {b.id} start")
            need(b.end_node, ("nodes",), f"bar {b.id} end")
            need(b.section_id, ("sections",), f"bar {b.id} section")
        for p in self.panels:
            for n in p.boundary_nodes:
                need(n, ("nodes",), f"panel {p.id} boundary")
            need(p.property_id, ("surface_properties",), f"panel {p.id} property")
        cases = ("load_cases", "combinations")
        for c in self.combinations:
            for t in c.terms:
                need(t.case_id, cases, f"combination {c.id} term")
        for ld in self.loads:
            need(ld.case_id, ("load_cases",), f"load {ld.id} case")
            targets = {"point": ("node_ids", ("nodes",)), "bar-point": ("bar_ids", ("bars",)),
                       "bar-distributed": ("bar_ids", ("bars",)), "area": ("panel_ids", ("panels",)),
                       "gravity": ("object_ids", ("bars", "panels", "nodes"))}[ld.kind]
            for t in getattr(ld, targets[0]):
                need(t, targets[1], f"load {ld.id} target")
        for r in self.requests:
            for c in r.case_ids:
                need(c, cases, f"request {r.id} case")
        for r in self.results:
            need(r.case_id, cases, f"result {r.id} case")
            need(r.request_id, ("requests",), f"result {r.id} request")
            if r.object_id:
                need(r.object_id, ("bars",) if r.kind in ("bar-force", "steel-utilisation") else ("nodes", "bars"),
                     f"result {r.id} object")
        return self

    def counts(self) -> dict[str, int]:
        return {c: len(getattr(self, c)) for c in self.COLLECTIONS}


STRUCTURAL_TS_MODELS = [StructuralBundle, MaterialGrade, SectionPropertySet, SurfacePropertySet, AnalyticalNode,
                        AnalyticalBar, AnalyticalPanel, Support, Fixity6, Dof, EndReleases, Offset, QVector, LoadCase,
                        LoadCombination, CombinationTerm, PointLoad, BarPointLoad, BarDistributedLoad, AreaLoad,
                        GravityLoad, ResultRequest, BarForceResult, NodeReactionResult, NodeDisplacementResult,
                        GlobalReactionResult, StoreyDriftResult, UtilisationResult, ExternalRef]
