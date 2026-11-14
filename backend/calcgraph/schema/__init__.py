"""calc-graph schema: one Pydantic model set for every output, mandatory provenance,
units on every quantity, explicit coordinate frames. Adapters in `schema.adapters` convert
the IFC-path store rows into it; `scripts/gen_ts_types.py` writes src/types/schema.ts (repo root) from these models."""
from .frames import (BBox, BuildingFt, CalcModelFt, FrameMismatch, ModelM, ModelRegistration, NoRegistration, Point2,
                     Point3, SheetCalibration, SheetPt)
from .models import (SCHEMA_VERSION, Bundle, CalcRecord, CalcSheet, ConnectionInstance, ConnectionType, DocKind,
                     Document, Element, ElementType, Fact, Finding, Link, Method, ModelEvidence, Occurrence,
                     OccurrenceKind, PdfEvidence, Provenance, RecordEvidence, Relation, RelationKind, Revision,
                     Severity, TranscriptEvidence, Unitless)
from .structural import (
    AnalyticalBar, AnalyticalNode, AnalyticalPanel, AreaLoad, AxisSystem, BarDistributedLoad, BarFEAType,
    BarForceResult, BarPointLoad, CombinationKind, CombinationTerm, DOFType, DivisionType, Dof, EndReleases,
    ExternalRef, Fixity6, GlobalReactionResult, GravityLoad, LoadCase, LoadCombination, LoadNature, MaterialGrade,
    MaterialKind, NodeDisplacementResult, NodeReactionResult, Offset, PointLoad, QVector, ResultKind,
    ResultRequest, ResultSource, SectionPropertySet, SectionShape, StoreyDriftResult, StructuralBundle,
    StructuralFact, StructuralUsage, Support, SurfacePropertySet, UtilisationResult, STRUCTURAL_SCHEMA_VERSION,
    STRUCTURAL_TS_MODELS)
from .units import Quantity, UnitMismatch, UnknownUnit, convert, q, unit_from_key

__all__ = [n for n in dir() if not n.startswith("_")]
