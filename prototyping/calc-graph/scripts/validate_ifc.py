"""Validate every IFC calc-graph produces against our IDS contracts (ifctester) and the checks IDS
cannot express.

    uv run python scripts/validate_ifc.py                 # fresh v2 base + a move revision, and every IFC on disk
    uv run python scripts/validate_ifc.py --fresh-only    # just the freshly written v2 pair (CI / evaluate_all)
    uv run python scripts/validate_ifc.py --include-store # + the revision store's IFC blobs (history)
    uv run python scripts/validate_ifc.py FILE.ifc ...    # these files only
    [--json-out PATH]

Which contract applies is read from the file header (originating system), never guessed from the path:
  calc-graph synth v2 generator -> backend/calcgraph/ids/calc-graph-v2.ids
  anything else                 -> skipped (not ours)
Besides the IDS, every one of our files gets IfcOpenShell schema validation, and v2 files get:
  - GlobalId stability by construction: GlobalId == uuid5(v2 namespace, Pset_CalcGraph.ElementId)
    for every element, and (fresh pair) the same GlobalId for every element both revisions keep;
  - profile consistency: the IfcMaterialProfileSet profile names the member's Structural.Section;
  - analytical model: every linear steel element is idealized by >= 1 IfcStructuralCurveMember
    (IfcRelAssignsToProduct) naming the same ElementId; every member has 2 node connections whose
    vertex coordinates are the member's edge ends.
Exit 1 if any file we produce fails.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import tempfile
import uuid
from collections import Counter

import ifcopenshell
import ifcopenshell.guid
import ifcopenshell.util.element as ue
import ifcopenshell.validate
from ifctester import ids

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path[:0] = [ROOT, os.path.join(ROOT, "backend")]
IDS_DIR = os.path.join(ROOT, "backend", "calcgraph", "ids")
CONTRACTS = {"calc-graph synth v2 generator": "calc-graph-v2.ids"}
LINEAR = ("IfcBeam", "IfcColumn", "IfcMember")


def _contract(f) -> tuple[bool, str | None]:
    sysname = f.header.file_name.originating_system
    return (sysname in CONTRACTS), CONTRACTS.get(sysname)


def _schema_errors(f) -> list[str]:
    log = ifcopenshell.validate.json_logger()
    ifcopenshell.validate.validate(f, log)
    return [str(s.get("message"))[:200] for s in log.statements]


def _v2_checks(f) -> list[str]:
    from synth.v2.ifc_v2 import NS
    probs: list[str] = []
    for e in f.by_type("IfcElement"):
        eid = ue.get_psets(e).get("Pset_CalcGraph", {}).get("ElementId")
        if e.GlobalId != ifcopenshell.guid.compress(uuid.uuid5(NS, eid or "").hex):
            probs.append(f"{e.GlobalId} ({eid}): GlobalId is not uuid5(NS, ElementId) - not stable across revisions")
    idealized: dict[str, list] = {}
    for rel in f.by_type("IfcRelAssignsToProduct"):
        for o in rel.RelatedObjects:
            if o.is_a("IfcStructuralCurveMember"):
                idealized.setdefault(rel.RelatingProduct.GlobalId, []).append(o)
    for e in f.by_type("IfcElement"):
        ps = ue.get_psets(e)
        sec = ps.get("Structural", {}).get("Section")
        if not (e.is_a() in LINEAR and sec):
            continue
        mat = ue.get_material(e, should_skip_usage=True)
        names = sorted({p.Profile.ProfileName for p in (mat.MaterialProfiles if mat and mat.is_a("IfcMaterialProfileSet") else [])})
        if names != [sec]:
            probs.append(f"{ps['Pset_CalcGraph']['ElementId']}: material profile {names} != Structural.Section {sec}")
        mems = idealized.get(e.GlobalId, [])
        if not mems:
            probs.append(f"{ps['Pset_CalcGraph']['ElementId']}: no analytical member idealizes it")
        for m in mems:
            if ue.get_psets(m).get("CalcGraph_Analytical", {}).get("ElementId") != ps["Pset_CalcGraph"]["ElementId"]:
                probs.append(f"{m.GlobalId}: analytical ElementId does not match its physical element")
    for m in f.by_type("IfcStructuralCurveMember"):
        conns = [r.RelatedStructuralConnection for r in m.ConnectedBy]
        edge = m.Representation.Representations[0].Items[0]
        ends = {tuple(round(c, 6) for c in v.VertexGeometry.Coordinates) for v in (edge.EdgeStart, edge.EdgeEnd)}
        at = {tuple(round(c, 6) for c in n.Representation.Representations[0].Items[0].VertexGeometry.Coordinates) for n in conns}
        if len(conns) != 2 or at != ends:
            probs.append(f"{m.Name} {m.Description}: {len(conns)} node connections, ends {sorted(ends)} vs nodes {sorted(at)}")
    return probs


def validate(path: str) -> dict:
    f = ifcopenshell.open(path)
    ours, contract = _contract(f)
    r = {"file": os.path.relpath(path, ROOT) if path.startswith(ROOT) else os.path.basename(path),
         "originating_system": f.header.file_name.originating_system, "ours": ours, "contract": contract}
    if not ours:
        return r | {"skipped": "not written by calc-graph"}
    r["schema_errors"] = _schema_errors(f)
    if contract:
        spec = ids.open(os.path.join(IDS_DIR, contract), validate=True)
        spec.validate(f)
        r["ids"] = [{"id": s.identifier or f"#{i + 1}", "name": s.name, "pass": bool(s.status), "applicable": len(s.applicable_entities),
                     "failed": len(s.failed_entities)} for i, s in enumerate(spec.specifications)]
    r["checks"] = _v2_checks(f) if contract == "calc-graph-v2.ids" else []
    r["ok"] = not r["schema_errors"] and all(s["pass"] for s in r.get("ids", [])) and not r["checks"]
    return r


def fresh_pair(tmp: str) -> tuple[list[str], list[str]]:
    """Write the v2 base design and one move revision (as /api/v2/apply does); return the paths and
    the cross-revision GlobalId problems."""
    from calcgraph import recalc
    from synth.v2 import ifc_v2
    from synth.v2.generate import build
    d, exp = build()
    a = os.path.join(tmp, "v2_base.ifc")
    ifc_v2.write(exp, a, d)
    lay = recalc.layout_from_change({"moved": {"2B": [5, 0]}, "label": "Move 2B (+5, +0) ft"})
    d2, exp2 = build(lay, keep={e["id"]: e for e in exp["elements"]})
    b = os.path.join(tmp, "v2_move_2B.ifc")
    ifc_v2.write(exp2, b, d2, label="Move 2B (+5, +0) ft")
    probs = []
    fa, fb = ifcopenshell.open(a), ifcopenshell.open(b)   # keep the files alive while their entities are read
    ga = {ue.get_psets(e)["Pset_CalcGraph"]["ElementId"]: e.GlobalId for e in fa.by_type("IfcElement")}
    gb = {ue.get_psets(e)["Pset_CalcGraph"]["ElementId"]: e.GlobalId for e in fb.by_type("IfcElement")}
    for k in sorted(set(ga) & set(gb)):
        if ga[k] != gb[k]:
            probs.append(f"{k}: GlobalId {ga[k]} -> {gb[k]} across the move")
    dj = os.path.join(ROOT, "data", "synthetic_v2", "design.json")   # what the registry / UI key on
    if os.path.exists(dj):
        for e in json.load(open(dj))["elements"]:
            if e.get("global_id") and e["id"] in ga and e["global_id"] != ga[e["id"]]:
                probs.append(f"{e['id']}: design.json global_id {e['global_id']} != freshly written IFC {ga[e['id']]}")
    return [a, b], probs


def on_disk(include_store: bool) -> list[str]:
    """The current working outputs. Revision-store blobs are immutable history (an old revision was
    written by the writer of its day), so they are only checked on request."""
    pats = ["data/synthetic_v2/model.ifc", "data/sets/*/model.ifc"]
    pats += ["data/store/blobs/*.ifc"] if include_store else []
    return sorted({p for pat in pats for p in glob.glob(os.path.join(ROOT, pat), recursive=True)})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*")
    ap.add_argument("--fresh-only", action="store_true")
    ap.add_argument("--include-store", action="store_true", help="also the revision store's IFC blobs (history)")
    ap.add_argument("--json-out")
    a = ap.parse_args()
    results, cross = [], []
    with tempfile.TemporaryDirectory() as tmp:
        paths = list(a.files)
        if not a.files:
            fresh, cross = fresh_pair(tmp)
            paths = fresh + ([] if a.fresh_only else on_disk(a.include_store))
        for p in paths:
            results.append(validate(p))
    ours = [r for r in results if r["ours"]]
    ok = all(r["ok"] for r in ours) and not cross
    for r in results:
        if not r["ours"]:
            print(f"SKIP {r['file']} ({r['originating_system'] or 'no originating system'})")
            continue
        ids_s = ", ".join(f"{s['id']} {'pass' if s['pass'] else 'FAIL'} {s['applicable'] - s['failed']}/{s['applicable']}"
                          for s in r.get("ids", [])) or "no IDS (deprecated v1)"
        print(f"{'OK  ' if r['ok'] else 'FAIL'} {r['file']}: schema errors {len(r['schema_errors'])}; {ids_s}; "
              f"extra checks {len(r['checks'])} problems")
        for m in (r["schema_errors"] + r["checks"])[:8]:
            print("     -", m)
    if not a.files:
        print(f"{'OK  ' if not cross else 'FAIL'} GlobalId stability across the fresh base -> move revision: "
              f"{len(cross)} problems")
        for m in cross[:8]:
            print("     -", m)
    print(f"{'PASS' if ok else 'FAIL'}: {sum(r['ok'] for r in ours)}/{len(ours)} calc-graph IFC files pass "
          f"({Counter(r['contract'] or 'v1-schema-only' for r in ours)})")
    if a.json_out:
        with open(a.json_out, "w") as fh:
            json.dump({"ok": ok, "results": results, "cross_revision": cross,
                       "metrics": {"ifc_files_pass_rate": (sum(r["ok"] for r in ours) / len(ours)) if ours else 1.0},
                       "gated": ["ifc_files_pass_rate"]}, fh, indent=1)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
