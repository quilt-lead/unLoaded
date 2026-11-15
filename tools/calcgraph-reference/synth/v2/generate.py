"""Generate the v2 synthetic dataset (one designed building -> its model and calc package).

    cd tools/calcgraph-reference
    uv run python -m synth.v2.generate [--out data/synthetic_v2] [--check]

Writes design.json (elements, types, relations, calc records, verification of the AISC
table), model.ifc, calc_package.pdf, drawings.pdf (the structural drawing set) and
registry_truth.json (every element / type / detail / record and where it occurs in the IFC, the
drawings and the calcs). --check generates twice into temp dirs and compares sha256 of every file
(byte-stable).

Standalone copy of the hackathon's synth/v2 (calc-graph prototype, 2026-11-14) for the move-impact
gate (packages/move-impact). Left out on purpose: the spec book, the
platform writers, the ETABS adapter (so the registry truth has no etabs occurrences), and the
structural analysis model inside the IFC. Outside synth/v2 it imports only synth/ifc_common.py (the shared IFC builder the v1 generator
also uses).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import time

from . import aisc, calc_pdf_v2, design, drawings_v2, ifc_v2, model, records, registry_truth

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(ROOT, "data", "synthetic_v2")


def _clean(o):
    """JSON-safe, deterministic (numpy scalars -> float, tuples -> lists, floats rounded)."""
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if hasattr(o, "item") and not isinstance(o, (str, bytes)):
        o = o.item()
    if isinstance(o, float):
        return round(o, 6)
    return o


def write_json_atomic(path: str, obj, **kw) -> None:
    """json.dump to a temp file beside `path`, then os.replace: readers see the old or the new
    file, never a partial one. Used for every JSON artefact under data/synthetic_v2."""
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", suffix=".json", dir=d)
    try:
        with os.fdopen(fd, "w") as fh:
            json.dump(obj, fh, **kw)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def build(layout: model.Layout | None = None, keep: dict | None = None) -> tuple[dict, dict]:
    layout = layout or model.base_layout()
    d = design.run(layout, keep=keep)
    exp = records.export(d)
    exp["building"] = {"name": "Harbor View Office (synthetic)", "grids": {"x": model.GX, "y": model.GY},
                       "levels": [{"key": k, "name": n, "elev_ft": z} for k, n, z in model.LEVELS],
                       "areas": [a.__dict__ for a in layout.areas], "layout_label": layout.label,
                       "columns": {c: list(p) for c, p in layout.cols.items()}, "removed": sorted(layout.removed),
                       "lateral": layout.lateral.to_dict()}
    exp["aisc_verification"] = aisc.verify()
    return d, _clean(exp)


def generate(out: str = OUT) -> dict:
    """Every artefact is written into a staging directory inside `out` and then moved into place
    with os.replace (atomic on one filesystem), so a reader of `out` never sees a half-written
    file - other sessions read drawings.pdf / model.ifc / calc_package.pdf while this runs."""
    os.makedirs(out, exist_ok=True)
    t = time.time()
    stage = tempfile.mkdtemp(prefix=".generate-", dir=out)
    try:
        written, summary = _generate_into(stage)
        for name in written:
            os.replace(os.path.join(stage, name), os.path.join(out, name))
    finally:
        for name in os.listdir(stage):
            os.remove(os.path.join(stage, name))
        os.rmdir(stage)
    return {"seconds": round(time.time() - t, 1), **summary, "files": sorted(f for f in os.listdir(out) if not f.startswith("."))}


def _generate_into(out: str) -> tuple[list[str], dict]:
    """Write every artefact into `out` (a fresh staging directory); returns (file names, summary)."""
    d, exp = build()
    gids = ifc_v2.write(exp, os.path.join(out, "model.ifc"), d)
    for e in exp["elements"]:
        if e["id"] in gids:
            e["global_id"] = gids[e["id"]]
    # document writers record their occurrences (page / bbox / sheet) into exp in place, in the
    # hackathon's order (calc package, then drawing set), then the registry truth reads them
    calc_pdf_v2.write(exp, d, os.path.join(out, "calc_package.pdf"))
    drawings_v2.write(exp, d, os.path.join(out, "drawings.pdf"))
    registry_truth.write(exp, os.path.join(out, "registry_truth.json"))
    with open(os.path.join(out, "design.json"), "w") as fh:
        json.dump(exp, fh, indent=1, sort_keys=True)
    return (sorted(f for f in os.listdir(out) if os.path.isfile(os.path.join(out, f))),
            {"elements": len(exp["elements"]), "records": len(exp["records"]), "relations": len(exp["relations"])})


def _sha(dirpath: str) -> dict:
    return {f: hashlib.sha256(open(os.path.join(dirpath, f), "rb").read()).hexdigest() for f in sorted(os.listdir(dirpath))
            if os.path.isfile(os.path.join(dirpath, f))}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if a.check:
        with tempfile.TemporaryDirectory() as t1, tempfile.TemporaryDirectory() as t2:
            generate(t1)
            generate(t2)
            h1, h2 = _sha(t1), _sha(t2)
            bad = [f for f in h1 if h1[f] != h2.get(f)]
            print("byte-stable" if not bad else f"NOT byte-stable: {bad}", {f: h[:12] for f, h in h1.items()})
            raise SystemExit(1 if bad else 0)
    print(json.dumps(generate(a.out), indent=1))


if __name__ == "__main__":
    main()
