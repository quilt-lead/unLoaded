"""F1 schema contract: wrong frames / units / missing provenance fail loudly; bundles round-trip.
(Not run on the dev Mac - CI only. The same contract is exercised by scripts/schema_audit.py.)"""
import importlib.util
import os

import pytest

from calcgraph.schema import Bundle, Element, PdfEvidence, Provenance, frames, q
from calcgraph.schema.units import UnitMismatch

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SHA = "c" * 64


def _audit():
    spec = importlib.util.spec_from_file_location("schema_audit", os.path.join(ROOT, "scripts", "schema_audit.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_contract_checks_all_raise():
    assert _audit().contract_checks() == []


def test_units_convert_and_refuse():
    assert q(1, "ft").to("in").value == pytest.approx(12)
    assert q(1, "ksf").to("psf").value == pytest.approx(1000)
    with pytest.raises(UnitMismatch):
        q(1, "kip").to("ft")


def test_bundle_round_trip():
    ev = PdfEvidence(doc_sha=SHA, page=3, bbox=frames.sheet_bbox(SHA, 3, [1, 2, 3, 4]), text="W16x26")
    p = Provenance(evidence=[ev], rule_id="test.rule", rule_version="1", engine="test", method="deterministic",
                   confidence=1.0)
    el = Element(id="el:x:1", category="Beam", designation="W16X26", attrs={"length": q(20, "ft")}, provenance=p,
                 position=frames.Point2(frame=frames.BuildingFt(building="x"), x=1, y=2))
    b = Bundle(source="test", elements=[el])
    again = Bundle.model_validate_json(b.model_dump_json())
    assert again == b
    assert again.elements[0].attrs["length"].to("in").value == pytest.approx(240)
