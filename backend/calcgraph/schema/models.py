"""The one schema every calc-graph output converts into (Pydantic v2).

Every DERIVED fact (an element read off a sheet, a calc record parsed from a table row, a
link, a relation, a finding ...) subclasses `Fact` and therefore must carry a `Provenance`:
the evidence that produced it (where in which document, in a named frame), the rule and
rule/engine version that read it, the method (deterministic / ai / human) and a confidence.
A fact without one does not validate. Source documents and revisions are not derived and
carry no provenance.

Numbers are never bare: an attribute or calc value is a `Quantity` (value + unit), an
explicit `Unitless` (a number whose source declares no unit, kept as its raw text so the
gap stays visible), a string, a bool or a list of strings. A float in `attrs` / `values`
fails validation.
"""
from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictStr, field_validator, model_validator

from .frames import BBox, CalcModelFt, ModelM, BuildingFt, Point2, Point3, SheetCalibration, SheetPt, \
    ModelRegistration  # noqa: F401  (re-exported for the bundle)
from .units import Quantity

SCHEMA_VERSION = "calcgraph-schema/1.0"
SHA256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------- enums ----------------
class DocKind(str, Enum):
    drawing = "drawing"
    calc = "calc"
    spec = "spec"
    ifc = "ifc"
    platform = "platform"
    meeting = "meeting"
    analysis_export = "analysis_export"  # a BHoM / ETABS / Speckle payload: evidence cites its sha256


class Method(str, Enum):
    deterministic = "deterministic"
    ai = "ai"
    human = "human"


class OccurrenceKind(str, Enum):
    plan_tag = "plan-tag"
    plan_symbol = "plan-symbol"
    elevation = "elevation"
    schedule_row = "schedule-row"
    detail_callout = "detail-callout"
    text_ref = "text-ref"
    ifc = "ifc"
    calc_row = "calc-row"
    spec_article = "spec-article"
    platform_record = "platform-record"
    meeting_span = "meeting-span"


class RelationKind(str, Enum):
    supports = "supports"
    bears_on = "bears-on"
    frames_into = "frames-into"
    connected_by = "connected-by"
    instance_of = "instance-of"
    specified_by = "specified-by"
    designed_by = "designed-by"
    detailed_by = "detailed-by"
    member_of = "member-of"
    feeds = "feeds"
    discussed_in = "discussed-in"


class Severity(str, Enum):
    info = "info"
    low = "low"
    medium = "medium"
    high = "high"


# ---------------- values ----------------
class Unitless(_M):
    """A number whose source declares no unit. Kept as raw text; never silently a float."""
    kind: Literal["unitless"] = "unitless"
    raw: StrictStr
    note: str = "source declares no unit"


Value = Union[Quantity, Unitless, StrictBool, StrictStr, list[StrictStr], None]


# ---------------- documents ----------------
class Document(_M):
    sha256: SHA256
    kind: DocKind
    name: str = Field(min_length=1)
    pages: int | None = Field(default=None, ge=1)
    role: str = ""


# ---------------- evidence ----------------
class PdfEvidence(_M):
    """A place on a PDF page. bbox and rects must be in that page's SheetPt frame."""
    locator: Literal["pdf"] = "pdf"
    doc_sha: SHA256
    page: int = Field(ge=1)
    bbox: BBox
    rects: list[BBox] = Field(default_factory=list)
    text: str = ""
    char_span: tuple[int, int] | None = None
    note: str = ""

    @model_validator(mode="after")
    def _frame(self):
        want = SheetPt(doc_sha=self.doc_sha, page=self.page)
        for b in [self.bbox, *self.rects]:
            if not isinstance(b.frame, SheetPt) or b.frame.key() != want.key():
                raise ValueError(f"pdf evidence box must be in SheetPt(doc {self.doc_sha[:10]}.., page {self.page}),"
                                 f" got {b.frame}")
        return self


class ModelEvidence(_M):
    """An entity in a model file (IFC GlobalId), optionally one property of it."""
    locator: Literal["model"] = "model"
    doc_sha: SHA256
    global_id: str = Field(min_length=1)
    entity: str = ""
    pset_path: str = ""
    text: str = ""


class RecordEvidence(_M):
    """A record on a construction platform (RFI, submittal, change event ...)."""
    locator: Literal["record"] = "record"
    doc_sha: SHA256
    platform: str
    record_type: str
    record_id: str
    field: str = ""
    text: str = ""


class TranscriptEvidence(_M):
    """A span of a meeting transcript."""
    locator: Literal["transcript"] = "transcript"
    doc_sha: SHA256
    start_s: float = Field(ge=0)
    end_s: float = Field(ge=0)
    speaker: str = ""
    char_span: tuple[int, int] | None = None
    text: str = ""


Evidence = Annotated[Union[PdfEvidence, ModelEvidence, RecordEvidence, TranscriptEvidence],
                     Field(discriminator="locator")]

ProvField = Literal["rule_id", "rule_version", "engine", "confidence", "evidence"]


class Provenance(_M):
    """Why a fact exists. Required on every derived fact.

    `adapter_supplied` lists the provenance fields that the source output did not carry and
    that a schema adapter filled from the producing module's declared rule (see
    schema/adapters). Empty = the source carried full provenance itself.
    """
    evidence: list[Evidence]
    rule_id: str = Field(min_length=1)
    rule_text: str = Field(default="", description="the source's own wording of the rule, if any")
    rule_version: str = Field(min_length=1)
    engine: str = Field(min_length=1, description="producing module / engine and its version")
    method: Method
    confidence: float = Field(ge=0.0, le=1.0)
    model_id: str | None = Field(default=None, description="required when method == ai")
    actor: str | None = Field(default=None, description="required when method == human")
    at: str | None = Field(default=None, description="ISO time the fact was produced or decided (US Eastern)")
    adapter_supplied: list[ProvField] = Field(default_factory=list)

    @model_validator(mode="after")
    def _method_needs(self):
        if self.method in (Method.deterministic, Method.ai) and not self.evidence:
            raise ValueError(f"{self.method.value} provenance needs at least one evidence item")
        if self.method == Method.ai and not self.model_id:
            raise ValueError("ai provenance needs model_id")
        if self.method == Method.human and not self.actor:
            raise ValueError("human provenance needs actor")
        return self


class Fact(_M):
    id: str = Field(min_length=1)
    provenance: Provenance


# ---------------- entities ----------------
class ElementType(Fact):
    """A type: a section designation or schedule mark shared by instances."""
    category: str
    designation: str = Field(description="normalised size (W16X26) or schedule mark (F5)")
    name: str = ""
    material: str = ""


class Element(Fact):
    """One element instance. position is optional and always framed."""
    category: str
    type_id: str | None = None
    mark: str = ""
    designation: str = ""
    level: str = ""
    grid: str = ""
    position: Point2 | Point3 | None = None
    attrs: dict[str, Value] = Field(default_factory=dict)


class Occurrence(Fact):
    """Where a subject (element, type, connection) appears in a document."""
    kind: OccurrenceKind
    subject_id: str
    at: Evidence
    label: str = ""


class Relation(Fact):
    kind: RelationKind
    src: str
    dst: str
    attrs: dict[str, Value] = Field(default_factory=dict)


class CalcSheet(Fact):
    """One calc sheet / page of a calc package (the unit page-level links point at)."""
    doc_sha: SHA256
    page: int = Field(ge=1)
    sheet_id: str
    section: str = ""
    title: str = ""
    software: str = ""
    role: str = ""
    level: str = ""


class CalcRecord(Fact):
    """One design record: a table row group of one analysis run (member, column stack, footing ...)."""
    doc_sha: SHA256
    run: str
    record_type: str
    section: str = ""
    label: str = ""
    level: str = ""
    tables: list[str] = Field(default_factory=list)
    values: dict[str, Value] = Field(default_factory=dict)
    uc: Quantity | None = None
    governing_lc: str | None = None
    geometry: list[Point2 | Point3] = Field(default_factory=list)

    @field_validator("uc")
    @classmethod
    def _uc_dimensionless(cls, v):
        if v is not None and v.unit != "1":
            raise ValueError(f"UC must be dimensionless, got unit {v.unit}")
        return v


class ConnectionType(Fact):
    detail: str
    sheet: str
    title: str = ""
    category: str = ""
    is_connection: bool = True
    designations: list[str] = Field(default_factory=list)
    scale: str = ""


class ConnectionInstance(Fact):
    type_id: str | None = None
    via: str
    symbol: str = ""
    attached: list[str] = Field(default_factory=list, description="element ids")
    grid: str = ""


class Link(Fact):
    """Element <-> calc evidence link. provenance.confidence is the link score."""
    src: str
    dst: str
    tier: str
    system: str = ""
    status: Literal["auto", "confirmed", "rejected", "manual"] = "auto"


class Finding(Fact):
    kind: str
    severity: Severity
    text: str
    subjects: list[str] = Field(default_factory=list)


class Revision(_M):
    """An ingest or an edit. Not derived, so no provenance; who/what made it is recorded."""
    id: str
    kind: str
    seq: int = Field(ge=1)
    parent_id: str | None = None
    doc_sha: SHA256 | None = None
    label: str = ""
    source_name: str = ""
    created_at: str
    created_by: str = ""
    decision_source: str | None = Field(default=None, description="e.g. a meeting-span occurrence id")


class Bundle(_M):
    """Everything one adapter run produced, validated."""
    schema_version: Literal["calcgraph-schema/1.0"] = SCHEMA_VERSION
    source: str
    documents: list[Document] = Field(default_factory=list)
    revisions: list[Revision] = Field(default_factory=list)
    calibrations: list[SheetCalibration] = Field(default_factory=list)
    registrations: list[ModelRegistration] = Field(default_factory=list)
    element_types: list[ElementType] = Field(default_factory=list)
    elements: list[Element] = Field(default_factory=list)
    occurrences: list[Occurrence] = Field(default_factory=list)
    relations: list[Relation] = Field(default_factory=list)
    calc_sheets: list[CalcSheet] = Field(default_factory=list)
    calc_records: list[CalcRecord] = Field(default_factory=list)
    connection_types: list[ConnectionType] = Field(default_factory=list)
    connection_instances: list[ConnectionInstance] = Field(default_factory=list)
    links: list[Link] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)


# models exported to TypeScript (scripts/gen_ts_types.py); schema/structural.py adds STRUCTURAL_TS_MODELS
TS_MODELS = [Bundle, Document, Revision, Provenance, PdfEvidence, ModelEvidence, RecordEvidence, TranscriptEvidence,
             ElementType, Element, Occurrence, Relation, CalcSheet, CalcRecord, ConnectionType, ConnectionInstance,
             Link, Finding, Quantity, Unitless, BBox, Point2, Point3, SheetPt, BuildingFt, ModelM, CalcModelFt,
             SheetCalibration, ModelRegistration]
