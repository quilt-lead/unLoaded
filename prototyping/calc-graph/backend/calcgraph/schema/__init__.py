"""calc-graph schema: one Pydantic model set for every output, mandatory provenance,
units on every quantity, explicit coordinate frames. Adapters in `schema.adapters` convert
the existing outputs into it; `scripts/schema_audit.py` runs them and reports gaps;
`scripts/gen_ts_types.py` writes frontend/src/types/schema.ts from these models."""
from .frames import (BBox, BuildingFt, CalcModelFt, FrameMismatch, ModelM, ModelRegistration, NoRegistration, Point2,
                     Point3, SheetCalibration, SheetPt)
from .models import (SCHEMA_VERSION, Bundle, CalcRecord, CalcSheet, ConnectionInstance, ConnectionType, DocKind,
                     Document, Element, ElementType, Fact, Finding, Link, Method, ModelEvidence, Occurrence,
                     OccurrenceKind, PdfEvidence, Provenance, RecordEvidence, Relation, RelationKind, Revision,
                     Severity, TranscriptEvidence, Unitless)
from .units import Quantity, UnitMismatch, UnknownUnit, convert, q, unit_from_key

__all__ = [n for n in dir() if not n.startswith("_")]
