"""Run every schema adapter over the existing outputs and report what lacks provenance or units.

    uv run python scripts/schema_audit.py            # report + converted bundles
    uv run python scripts/schema_audit.py --strict   # fail on the first fact whose provenance
                                                     # is not fully carried by its source

Sources: data/sets/*/{graph,calc_records,connections}.json, data/sets/*/model.ifc,
data/synthetic/model_rev1.ifc, the IFC-path store (data/store, read from a copy) as
both the /export view and the full state view, and the revision store's own stored facts
(store/<project>: the head snapshots of every project, both paths, as served by
GET /api/store/projects/{pid}/bundle - read from a copy, which migrates / backfills itself).

Writes (gitignored - derived from the inputs, may include drawing text):
    data/eval/schema/<source>.bundle.json   validated bundles
    data/eval/schema/report.json            the tally per source
Also checks (and exits non-zero if broken) the frame/unit contract: a value in the wrong
frame or unit must raise, and cross-source references must resolve.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from calcgraph.schema import frames, units  # noqa: E402
from calcgraph.schema.adapters import calc_records, connections, drawing_set, ifc_model, ifc_store  # noqa: E402
from calcgraph.schema.models import Bundle  # noqa: E402

OUT = os.path.join(ROOT, "data", "eval", "schema")


def contract_checks() -> list[str]:
    """Each must raise. Returns failures (empty = contract holds)."""
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
    from calcgraph.schema.models import CalcRecord, Element, PdfEvidence, Provenance
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


def integrity(bundles: list[Bundle]) -> dict:
    """Cross-source references: every relation / link / occurrence end must exist somewhere."""
    ids = set()
    for b in bundles:
        for coll in ("elements", "element_types", "calc_sheets", "calc_records", "connection_types",
                     "connection_instances"):
            ids |= {x.id for x in getattr(b, coll)}
    out = {}
    for b in bundles:
        dangling = {}
        for r in b.relations:
            for end in ("src", "dst"):
                if getattr(r, end) not in ids:
                    dangling.setdefault(f"relation {r.kind.value} {end}", []).append(getattr(r, end))
        for l in b.links:
            for end in ("src", "dst"):
                if getattr(l, end) not in ids:
                    dangling.setdefault(f"link {end}", []).append(getattr(l, end))
        for o in b.occurrences:
            if o.subject_id not in ids:
                dangling.setdefault(f"occurrence {o.kind.value} subject", []).append(o.subject_id)
        for c in b.connection_instances:
            for a in c.attached:
                if a not in ids:
                    dangling.setdefault("connection instance attached element", []).append(a)
            if c.type_id and c.type_id not in ids:
                dangling.setdefault("connection instance type", []).append(c.type_id)
        out[b.source] = {k: {"count": len(v), "examples": sorted(set(v))[:3]} for k, v in dangling.items()}
    return out


def store_sources(store_dir: str, scratch: str, strict: bool) -> list[tuple[str, tuple[Bundle, object]]]:
    """Every project's head bundle as the revision store serves it (from a copy of the store)."""
    import shutil
    from collections import Counter
    from calcgraph import revstore
    from calcgraph.schema.adapters._common import Reject, Tally
    os.makedirs(scratch, exist_ok=True)
    shutil.copyfile(os.path.join(store_dir, "calcgraph.sqlite"), os.path.join(scratch, "calcgraph.sqlite"))
    os.symlink(os.path.join(store_dir, "blobs"), os.path.join(scratch, "blobs"))
    st = revstore.open_store(scratch)
    st.db.commit()
    out = []
    for p in st.all_projects():
        name = p["slug"] or f"project-{p['id']}"
        t = Tally(source=f"store/{name}")
        b = revstore.project_bundle(st, p["id"])
        for coll in ("element_types", "elements", "occurrences", "relations", "calc_sheets", "calc_records",
                     "connection_types", "connection_instances", "links", "findings"):
            for f in getattr(b, coll):
                t.attempted[coll] += 1
                t.converted[coll] += 1
                for x in f.provenance.adapter_supplied:
                    t.supplied[coll][x] += 1
                if strict and f.provenance.adapter_supplied:
                    raise Reject(f"store/{name} {coll} {f.id}: provenance incomplete in source: "
                                 f"{f.provenance.adapter_supplied}")
        t.notes.append(f"heads {p['heads']}")
        out.append((f"store:{name}", (b, t)))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true", help="raise on the first fact without full own provenance")
    ap.add_argument("--no-write", action="store_true")
    a = ap.parse_args()

    failures = contract_checks()
    print("frame / unit contract:", "OK (16 wrong-frame / wrong-unit cases raise)" if not failures else failures)

    results = []
    for set_dir in sorted(glob.glob(os.path.join(ROOT, "data", "sets", "*"))):
        sid = os.path.basename(set_dir)
        if os.path.exists(os.path.join(set_dir, "graph.json")):
            results.append((sid, drawing_set.convert(set_dir, a.strict)))
        if os.path.exists(os.path.join(set_dir, "calc_records.json")):
            results.append((sid, calc_records.convert(set_dir, a.strict)))
        if os.path.exists(os.path.join(set_dir, "connections.json")):
            results.append((sid, connections.convert(set_dir, a.strict)))
        if os.path.exists(os.path.join(set_dir, "model.ifc")):
            results.append((sid, ifc_model.convert(os.path.join(set_dir, "model.ifc"), sid, a.strict)))
    syn = os.path.join(ROOT, "data", "synthetic", "model_rev1.ifc")
    if os.path.exists(syn):
        results.append(("synthetic", ifc_model.convert(syn, "synthetic", a.strict)))
    store = os.environ.get("CALCGRAPH_STORE", os.path.join(ROOT, "data", "store"))
    if os.path.exists(os.path.join(store, "calcgraph.sqlite")):
        with tempfile.TemporaryDirectory() as tmp:
            for view in ("export", "state"):
                results.append(("ifc-store", ifc_store.convert(store, os.path.join(tmp, view), view, strict=a.strict)))
            results += store_sources(store, os.path.join(tmp, "facts"), a.strict)

    report = {"contract_failures": failures, "sources": [t.summary() for _, (_, t) in results]}
    by_set: dict[str, list[Bundle]] = {}
    for sid, (b, _) in results:
        if b.source == "ifc-store/export":
            continue  # the export is a lossy view of the same store as ifc-store/state
        by_set.setdefault(sid, []).append(b)
    report["dangling_references"] = {sid: integrity(bs) for sid, bs in by_set.items()}

    print(f"\n{'source':44} {'entity':22} {'tried':>6} {'ok':>6} {'rej':>5}  own-prov  unitless-facts")
    for _, (b, t) in results:
        for ent, n in t.attempted.items():
            ok = t.converted.get(ent, 0)
            sup = t.supplied.get(ent, {})
            own = ok - max(sup.values()) if sup else ok
            print(f"{t.source:44} {ent:22} {n:6} {ok:6} {n - ok:5}  {own:8}  {t.facts_without_own_units.get(ent, 0):6}")
    print("\nrejections:")
    for _, (b, t) in results:
        for ent, reasons in t.rejected.items():
            for r, n in sorted(reasons.items(), key=lambda kv: -kv[1]):
                print(f"  {t.source} {ent}: {n} x {r}")
    print("\nadapter-supplied provenance fields (source did not carry them):")
    for _, (b, t) in results:
        for ent, f in t.supplied.items():
            print(f"  {t.source} {ent}: {dict(f)}")
    print("\nunits (numbers by how their unit is known):")
    for _, (b, t) in results:
        for ent, u in t.units.items():
            print(f"  {t.source} {ent}: {dict(u)}")
    print("\ndangling references:")
    for sid, per in report["dangling_references"].items():
        for src, d in per.items():
            for k, v in d.items():
                print(f"  {src} {k}: {v['count']} (e.g. {v['examples'][:2]})")

    if not a.no_write:
        os.makedirs(OUT, exist_ok=True)
        for _, (b, t) in results:
            fn = t.source.replace("/", "__") + ".bundle.json"
            with open(os.path.join(OUT, fn), "w") as fh:
                fh.write(b.model_dump_json())
        with open(os.path.join(OUT, "report.json"), "w") as fh:
            json.dump(report, fh, indent=1, default=str)
        # round trip: every written bundle re-validates
        for fn in glob.glob(os.path.join(OUT, "*.bundle.json")):
            Bundle.model_validate_json(open(fn).read())
        print(f"\nwrote {len(results)} bundles + report.json to {os.path.relpath(OUT, ROOT)}/ (re-validated)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
