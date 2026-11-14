"""Round trip BHoM JSON -> calc-graph structural schema -> BHoM JSON -> schema, and report.

    uv run python scripts/bhom_roundtrip.py                       # the synthetic fixtures
    uv run python scripts/bhom_roundtrip.py a.json [b.json ...]   # any BHoM JSON (e.g. a bridge capture)

Checks, exits non-zero on any failure:
  1. every input object converts (Report.unsupported / unmapped printed; must be empty for
     the fixtures - a real capture may legitimately show unmapped fields, which are listed)
  2. schema -> BHoM -> schema is the identity on the schema (canonical JSON, provenance aside)
  3. BHoM -> schema -> BHoM keeps every field the converter maps, value for value (floats to
     1e-9 relative), for every BHoMObject matched by BHoM_Guid and every result object
  4. dimension guards fire: a section Ix given in in3 and a load in the wrong axis unit fail
"""
from __future__ import annotations

import json
import math
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path[:0] = [os.path.join(ROOT, "backend"), ROOT]

from calcgraph.schema.adapters.bhom_json import (BASE_KEYS, SECTION_DERIVED, bhom_to_schema, canonical,  # noqa: E402
                                                 load_bhom_json, schema_to_bhom)
from calcgraph.schema.structural import ResultSource, SectionPropertySet  # noqa: E402

FIXTURES = [os.path.join(ROOT, "data", "fixtures", "bhom", f) for f in ("portal_model.json", "portal_results.json")]


def close(a, b) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12)
    return a == b


def diff(a, b, path="", out=None, skip=frozenset()):
    """Fields of `a` that `b` lacks or disagrees on (b may carry extra fields)."""
    out = [] if out is None else out
    if isinstance(a, dict) and isinstance(b, dict):
        for k, v in a.items():
            if k in skip:
                continue
            if k not in b:
                if v not in (None, "", [], {}, 0, 0.0, False):
                    out.append(f"{path}.{k}: missing in round trip (was {str(v)[:60]})")
                continue
            diff(v, b[k], f"{path}.{k}", out, skip)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append(f"{path}: list length {len(a)} -> {len(b)}")
        for i, (x, y) in enumerate(zip(a, b)):
            diff(x, y, f"{path}[{i}]", out, skip)
    elif not close(a, b):
        out.append(f"{path}: {str(a)[:60]} -> {str(b)[:60]}")
    return out


def guard_checks() -> list[str]:
    fails = []
    from calcgraph.schema.structural import qvec
    try:
        SectionPropertySet.model_validate({"id": "s", "designation": "x", "shape": "I", "Ix": {"value": 1, "unit": "in3"},
                                           "provenance": {"evidence": [], "rule_id": "t", "rule_version": "1",
                                                          "engine": "t", "method": "human", "confidence": 1,
                                                          "actor": "test"}})
        fails.append("section Ix in in3 was accepted")
    except Exception:
        pass
    try:
        qvec(1, 0, 0, "kN").need((-1, 1, 0), "distributed force")
        fails.append("a force vector passed as a line load")
    except Exception:
        pass
    return fails


def main(paths: list[str]) -> int:
    objs, shas = [], []
    for p in paths:
        o, sha = load_bhom_json(p)
        objs += o
        shas.append(sha)
    doc_sha = shas[0]
    b1, rep = bhom_to_schema(objs, doc_sha=doc_sha, source=ResultSource.imported_file, source_name=os.path.basename(paths[0]))
    print(f"input: {len(objs)} top-level objects from {', '.join(os.path.relpath(p, ROOT) for p in paths)}")
    print(f"schema: {b1.counts()}")
    print(f"converted BHoM types: {dict(rep.converted)}")
    print(f"unsupported: {dict(rep.unsupported) or 'none'}; unmapped: {rep.to_dict()['unmapped'] or 'none'}")
    fails = []
    fixtures = paths == FIXTURES
    if fixtures and not rep.lossless():
        fails.append("fixtures did not convert losslessly")

    out = schema_to_bhom(b1)
    # same doc identity on the second pass so framed positions compare equal
    b2, rep2 = bhom_to_schema(json.loads(json.dumps(out)), doc_sha=doc_sha, source=ResultSource.imported_file,
                              source_name="roundtrip")
    c1, c2 = canonical(b1), canonical(b2)
    same = c1 == c2
    print(f"schema -> BHoM -> schema identical: {same} ({len(c1)} canonical bytes)")
    if not same:
        a, b = json.loads(c1), json.loads(c2)
        for line in diff(a, b)[:20] + diff(b, a)[:20]:
            print("   ", line)
        fails.append("schema round trip not identical")
    if not rep2.lossless():
        fails.append(f"re-emitted BHoM not lossless: {rep2.to_dict()}")

    # BHoM-level: every mapped field of every input object survives
    def walk(o, acc):
        if isinstance(o, dict):
            if o.get("BHoM_Guid"):
                acc.setdefault(o["BHoM_Guid"], o)
            for v in o.values():
                walk(v, acc)
        elif isinstance(o, list):
            for v in o:
                walk(v, acc)
        return acc
    src, dst = walk(objs, {}), walk(out, {})
    unmapped_keys = {k for ks in rep.unmapped.values() for k in ks}
    skip = frozenset(SECTION_DERIVED | {"Edges", "Shape", "RootRadius", "ToeRadius", "PlateRestraint", "Orientation",
                                        "Tags", "BHoM_Guid"} | unmapped_keys)
    field_diffs, missing = [], 0
    for g, o in src.items():
        if g not in dst:
            # constraint / release / offset / group guids are minted on the way out; their fields are compared via the parent
            if o.get("_t", "").endswith(("Constraint6DOF", "BarRelease", "Offset")) or "BHoMGroup" in o.get("_t", ""):
                continue
            missing += 1
            field_diffs.append(f"{o.get('_t')} {g}: not re-emitted")
            continue
        field_diffs += [f"{o['_t'].rsplit('.', 1)[-1]}{d}" for d in diff(o, dst[g], skip=skip | {"BHoM_Guid"})
                        if not any(f".{k}" in d for k in ("StartRelease.BHoM_Guid", "EndRelease.BHoM_Guid"))]
    res_in = [o for o in objs if ".Results." in o.get("_t", "")]
    res_out = [o for o in out if ".Results." in o.get("_t", "")]
    if len(res_in) != len(res_out):
        field_diffs.append(f"results: {len(res_in)} in, {len(res_out)} out")
    for a, b in zip(res_in, res_out):
        field_diffs += [f"{a['_t'].rsplit('.', 1)[-1]}{d}" for d in diff(a, b, skip=skip)]
    checked = len([g for g in src if g in dst]) + len(res_in)
    print(f"BHoM -> schema -> BHoM: {checked} objects compared field by field, {len(field_diffs)} differences")
    for line in field_diffs[:25]:
        print("   ", line)
    if field_diffs:
        fails.append(f"{len(field_diffs)} BHoM field differences")

    g = guard_checks()
    print(f"dimension guards: {'ok' if not g else g}")
    fails += g
    print("RESULT:", "PASS" if not fails else "FAIL - " + "; ".join(fails))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or FIXTURES))
