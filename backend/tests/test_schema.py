"""F1 schema contract: wrong frames / units / missing provenance fail loudly; bundles round-trip.
(Not run on the dev Mac - CI only.)"""
import pytest

from calcgraph.schema import Bundle, Element, PdfEvidence, Provenance, frames, q, units
from calcgraph.schema.models import CalcRecord
from calcgraph.schema.units import UnitMismatch

SHA = "c" * 64


def contract_checks() -> list[str]:
    """Each case must raise. Returns failures (empty = contract holds). Moved here verbatim from the
    hackathon's scripts/schema_audit.py, which was not ported (it ran the drawing-set adapters)."""
    sha_a, sha_b = "a" * 64, "b" * 64
    p1 = frames.Point2(frame=frames.SheetPt(doc_sha=sha_a, page=1), x=0, y=0)
    p2 = frames.Point2(frame=frames.SheetPt(doc_sha=sha_a, page=2), x=0, y=0)
    pb = frames.Point2(frame=frames.BuildingFt(building="x"), x=0, y=0)
    cal = frames.SheetCalibration(
        sheet=frames.SheetPt(doc_sha=sha_a, page=1), building=frames.BuildingFt(building="x"),
        cols=[frames.GridAnchor(label="1", pt=0, ft=0), frames.GridAnchor(label="2", pt=90, ft=10)],
        rows=[frames.GridAnchor(label="A", pt=0, ft=0), frames.GridAnchor(label="B", pt=90, ft=10)],
        kx_ft_per_pt=1 / 9, ky_ft_per_pt=1 / 9, depth_ft=10)
    reg = frames.ModelRegistration(building=frames.BuildingFt(building="x"), model=frames.ModelM(doc_sha=sha_b))
    good_ev = PdfEvidence(doc_sha=sha_a, page=1, bbox=frames.sheet_bbox(sha_a, 1, [0, 0, 1, 1]))
    good_prov = Provenance(evidence=[good_ev], rule_id="r", rule_version="1", engine="e", method="deterministic",
                           confidence=1)
    cases = {
        "distance across two pages": lambda: p1.dist(p2),
        "distance sheet vs building": lambda: p1.dist(pb),
        "calibration fed a point from another page": lambda: cal.to_building(p2),
        "model registration fed a sheet point": lambda: reg.to_model(frames.Point3(frame=p1.frame, x=0, y=0, z=0)),
        "calc model -> building registration": lambda: frames.register(frames.CalcModelFt(model="m"), pb.frame),
        "pdf evidence box on another page": lambda: PdfEvidence(doc_sha=sha_a, page=1,
                                                                bbox=frames.sheet_bbox(sha_a, 2, [0, 0, 1, 1])),
        "pdf evidence box on another document": lambda: PdfEvidence(doc_sha=sha_a, page=1,
                                                                    bbox=frames.sheet_bbox(sha_b, 1, [0, 0, 1, 1])),
        "kip converted to ft": lambda: units.q(1, "kip").to("ft"),
        "ft + kip": lambda: units.q(1, "ft") + units.q(1, "kip"),
        "Quantity + bare float": lambda: units.q(1, "ft") + 1.0,
        "unknown unit": lambda: units.q(1, "furlongs"),
        "bare float in element attrs": lambda: Element(id="e", category="c", attrs={"length": 3.0}, provenance=good_prov),
        "UC with a unit": lambda: CalcRecord(id="r", doc_sha=sha_a, run="x", record_type="m", uc=units.q(0.5, "ksi"),
                                             provenance=good_prov),
        "element without provenance": lambda: Element(id="e", category="c"),
        "deterministic provenance without evidence": lambda: Provenance(evidence=[], rule_id="r", rule_version="1",
                                                                        engine="e", method="deterministic",
                                                                        confidence=1),
        "ai provenance without model id": lambda: Provenance(evidence=[good_ev], rule_id="r", rule_version="1",
                                                             engine="e", method="ai", confidence=0.5),
    }
    failures = []
    for name, fn in cases.items():
        try:
            fn()
        except Exception:  # noqa: BLE001 - any loud failure satisfies the contract
            continue
        failures.append(f"did not raise: {name}")
    # and the happy paths stay exact
    if abs(units.q(12, "in").to("ft").value - 1.0) > 1e-12 or abs(units.q(1, "kip*ft").to("kN*m").value - 1.3558179483314) > 1e-9:
        failures.append("unit conversion values wrong")
    bp = cal.to_building(frames.Point2(frame=frames.SheetPt(doc_sha=sha_a, page=1), x=45, y=45))
    if (round(bp.x, 9), round(bp.y, 9)) != (5.0, 5.0):
        failures.append(f"calibration interpolation wrong: {bp}")
    return failures


def test_contract_checks_all_raise():
    assert contract_checks() == []


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
