"""Parity gate between two IFC files of the SAME model (e.g. before / after a writer refactor).

    uv run python scripts/check_ifc_parity.py BEFORE.ifc AFTER.ifc [--tol-mm 1.0] [--json]

Compares, per physical element (IfcElement, keyed by GlobalId): class, Name, ObjectType,
PredefinedType, containing storey, every property set and value, and the world-coordinate
bounding box of its body geometry (each of the 6 bounds within --tol-mm). Also compares the
spatial tree (project / site / building names, storey names + elevations). Exit 1 on any
difference. Entities the AFTER file adds that are not IfcElements (materials, an analytical
model, extra units) are reported as counts, not failures.
"""
from __future__ import annotations

import argparse
import json
import multiprocessing
import sys
from collections import Counter

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.element as uel
import ifcopenshell.util.placement
import numpy as np


def _bboxes(f) -> dict[str, list[float]]:
    s = ifcopenshell.geom.settings()
    s.set("use-world-coords", True)
    out: dict[str, list[float]] = {}
    it = ifcopenshell.geom.iterator(s, f, multiprocessing.cpu_count() // 2 or 1, include=f.by_type("IfcElement"))
    if it.initialize():
        while True:
            sh = it.get()
            v = np.array(sh.geometry.verts, float).reshape(-1, 3)
            if len(v):
                out[sh.guid] = [*v.min(0).round(6).tolist(), *v.max(0).round(6).tolist()]
            if not it.next():
                break
    return out


def extract(path: str) -> dict:
    f = ifcopenshell.open(path)
    bb = _bboxes(f)
    els = {}
    for e in f.by_type("IfcElement"):
        c = uel.get_container(e)
        psets = {k: {pk: pv for pk, pv in v.items() if pk != "id"} for k, v in uel.get_psets(e).items()}
        els[e.GlobalId] = {"class": e.is_a(), "name": e.Name, "object_type": e.ObjectType,
                           "predefined": getattr(e, "PredefinedType", None), "storey": c.Name if c else None,
                           "psets": psets, "bbox": bb.get(e.GlobalId)}
    proj = f.by_type("IfcProject")[0]
    storeys = {}
    for s in f.by_type("IfcBuildingStorey"):
        m = ifcopenshell.util.placement.get_local_placement(s.ObjectPlacement) if s.ObjectPlacement else None
        storeys[s.Name] = {"elevation": round(float(s.Elevation or 0.0), 6), "world_z": round(float(m[2, 3]), 6) if m is not None else None}
    return {"project": proj.Name, "phase": proj.Phase, "site": [s.Name for s in f.by_type("IfcSite")],
            "building": [b.Name for b in f.by_type("IfcBuilding")], "storeys": storeys, "elements": els,
            "entity_counts": Counter(x.is_a() for x in f)}


def compare(a: dict, b: dict, tol_mm: float = 1.0) -> dict:
    tol = tol_mm / 1000.0
    probs: list[str] = []
    for k in ("project", "phase", "site", "building", "storeys"):
        if a[k] != b[k]:
            probs.append(f"{k}: {a[k]!r} != {b[k]!r}")
    ga, gb = set(a["elements"]), set(b["elements"])
    if ga - gb:
        probs.append(f"{len(ga - gb)} GlobalIds missing after: {sorted(ga - gb)[:5]}")
    if gb - ga:
        probs.append(f"{len(gb - ga)} GlobalIds new after: {sorted(gb - ga)[:5]}")
    worst = 0.0
    field_diffs: Counter = Counter()
    for g in sorted(ga & gb):
        ea, eb = a["elements"][g], b["elements"][g]
        for k in ("class", "name", "object_type", "predefined", "storey", "psets"):
            if ea[k] != eb[k]:
                field_diffs[k] += 1
                if field_diffs[k] <= 3:
                    probs.append(f"{g} {k}: {ea[k]!r} != {eb[k]!r}")
        if (ea["bbox"] is None) != (eb["bbox"] is None):
            probs.append(f"{g}: geometry present before={ea['bbox'] is not None} after={eb['bbox'] is not None}")
        elif ea["bbox"] is not None:
            d = float(np.max(np.abs(np.array(ea["bbox"]) - np.array(eb["bbox"]))))
            worst = max(worst, d)
            if d > tol:
                field_diffs["bbox"] += 1
                if field_diffs["bbox"] <= 3:
                    probs.append(f"{g} bbox off by {d * 1000:.3f} mm")
    added = {k: v - a["entity_counts"].get(k, 0) for k, v in b["entity_counts"].items() if v > a["entity_counts"].get(k, 0)}
    removed = {k: a["entity_counts"][k] - b["entity_counts"].get(k, 0) for k in a["entity_counts"]
               if a["entity_counts"][k] > b["entity_counts"].get(k, 0)}
    return {"ok": not probs, "elements_before": len(ga), "elements_after": len(gb), "common": len(ga & gb),
            "psets_compared": sum(len(a["elements"][g]["psets"]) for g in ga & gb),
            "props_compared": sum(len(p) for g in ga & gb for p in a["elements"][g]["psets"].values()),
            "with_geometry": sum(1 for g in ga & gb if a["elements"][g]["bbox"]),
            "worst_bbox_mm": round(worst * 1000, 4), "field_diffs": dict(field_diffs), "problems": probs,
            "entities_added": added, "entities_removed": removed}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("before")
    ap.add_argument("after")
    ap.add_argument("--tol-mm", type=float, default=1.0)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    r = compare(extract(a.before), extract(a.after), a.tol_mm)
    if a.json:
        print(json.dumps(r, indent=1, default=str))
    else:
        print(("PARITY OK" if r["ok"] else "PARITY FAILED") + f": {r['common']}/{r['elements_before']} elements, "
              f"{r['psets_compared']} psets / {r['props_compared']} props, {r['with_geometry']} with geometry, "
              f"worst bbox {r['worst_bbox_mm']} mm")
        for p in r["problems"]:
            print("  -", p)
        print("  entities added:", json.dumps(r["entities_added"], sort_keys=True))
        print("  entities removed:", json.dumps(r["entities_removed"], sort_keys=True))
    sys.exit(0 if r["ok"] else 1)


if __name__ == "__main__":
    main()
