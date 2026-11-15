"""IFC -> element records with IfcOpenShell.

Each element keeps an OPEN parameter set (every property set flattened into
``params`` as {"Pset.Prop": value}), so new connection types or new psets add
fields without a schema change. Geometry is reduced to what the graph needs: a
world-space axis-aligned box and a principal axis (two end points) from PCA of
the tessellated vertices.
"""
from __future__ import annotations

import multiprocessing
import re

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.element as ue
import numpy as np

TYPES = ["IfcBeam", "IfcColumn", "IfcSlab", "IfcFooting", "IfcPile", "IfcWall", "IfcMember", "IfcPlate",
         "IfcMechanicalFastener", "IfcRoof", "IfcBuildingElementProxy", "IfcStairFlight", "IfcRampFlight"]
MARK_KEYS = ["Mark", "Type Mark", "Reference Mark", "Piece Mark"]
PROFILE_KEYS = ["MemberSection", "Section", "Profile", "Section Name"]

# One section dimension: 6, 6.625, 1/4, 1-1/2, .25 (HSS / angle walls are fractions of an inch:
# "HSS6X6X1/4" must not read as "HSS6X6X1"). Shared with matcher._PROF so the two cannot drift.
PROFILE_DIM = r"(?:\d+(?:\.\d+)?(?:-\d+/\d+|/\d+)?|\.\d+)"
_PROFILE_RE = re.compile(
    rf"\b(?:W|HSS|WT|MC|C|L|UB|UC|PFC|SHS|RHS|CHS|IPE|HEA|HEB)\s?{PROFILE_DIM}X{PROFILE_DIM}(?:X{PROFILE_DIM})?(?![\d/])"
    r"|\b\d{3,4}X\d{3,4}\b")


def norm_profile(s: str) -> str:
    return s.upper().replace(" ", "").replace("×", "X") if s else ""


def profile_from(*strs: str | None) -> str:
    """Port of the mockup's profileFrom()."""
    for s in strs:
        if not s:
            continue
        m = _PROFILE_RE.search(str(s).upper().replace("×", "X"))
        if m:
            return norm_profile(m.group(0))
    return ""


def cat_of(ifc_type: str, name: str = "") -> str:
    """Port of the mockup's catOf()."""
    t, n = ifc_type.upper(), name.lower()
    if "BEAM" in t:
        return "Beam"
    if "COLUMN" in t:
        return "Column"
    if "SLAB" in t or "ROOF" in t:
        return "Slab"
    if "FOOTING" in t:
        return "Footing"
    if "PILE" in t:
        return "Pile"
    if "WALL" in t:
        return "Wall"
    if "MEMBER" in t:
        return "Brace"
    if "PLATE" in t or "FASTENER" in t or re.search(r"connection|shear tab|fin plate|base plate", n):
        return "Connection"
    return "Other"


def _storey_of(el) -> str:
    c = ue.get_container(el)
    while c is not None and not c.is_a("IfcBuildingStorey"):
        c = ue.get_aggregate(c)
    return (c.Name or c.LongName or "") if c is not None else ""


def read_ifc(path: str) -> dict:
    f = ifcopenshell.open(path)
    els: dict[str, dict] = {}
    for t in TYPES:
        try:
            items = f.by_type(t, include_subtypes=True)
        except RuntimeError:
            continue
        for el in items:
            if el.GlobalId in els:
                continue
            params: dict[str, str] = {}
            for pset, props in ue.get_psets(el).items():
                for k, v in props.items():
                    if k == "id" or v is None or v == "":
                        continue
                    params[f"{pset}.{k}"] = str(v)
            flat = {k.split(".", 1)[1]: v for k, v in params.items()}
            mark = next((flat[k] for k in MARK_KEYS if flat.get(k)), "")
            if re.fullmatch(r"(n\.?a\.?|-|none)", mark, re.I):
                mark = ""
            name, typ = el.Name or "", getattr(el, "ObjectType", None) or ""
            prof = profile_from(*(flat.get(k) for k in PROFILE_KEYS), typ, name)
            els[el.GlobalId] = {
                "global_id": el.GlobalId, "express_id": el.id(), "ifc_type": el.is_a(), "cat": cat_of(el.is_a(), f"{name} {typ}"),
                "mark": mark, "name": name, "type_name": typ, "profile": "" if prof == "N.A" else prof,
                "storey": _storey_of(el), "params": params, "geom": None,
            }
    _geometry(f, els)
    meta = {"schema": f.schema, "project": (f.by_type("IfcProject") or [None])[0].Name if f.by_type("IfcProject") else ""}
    return {"elements": list(els.values()), "meta": meta}


def _geometry(f, els: dict[str, dict]) -> None:
    s = ifcopenshell.geom.settings()
    s.set("use-world-coords", True)
    targets = [f.by_guid(g) for g in els]
    if not targets:
        return
    it = ifcopenshell.geom.iterator(s, f, max(1, min(8, multiprocessing.cpu_count())), include=targets)
    if not it.initialize():
        return
    while True:
        sh = it.get()
        v = np.asarray(sh.geometry.verts, dtype=float).reshape(-1, 3)
        if len(v) and sh.guid in els:
            mn, mx = v.min(0), v.max(0)
            c = v.mean(0)
            # principal axis by PCA; end points = centroid +- half extent along it
            if len(v) >= 2:
                _, _, vt = np.linalg.svd(v - c, full_matrices=False)
                ax = vt[0]
                proj = (v - c) @ ax
                p1, p2 = c + ax * proj.min(), c + ax * proj.max()
            else:
                p1 = p2 = c
            els[sh.guid]["geom"] = {"min": [round(float(x), 4) for x in mn], "max": [round(float(x), 4) for x in mx],
                                    "p1": [round(float(x), 4) for x in p1], "p2": [round(float(x), 4) for x in p2]}
        if not it.next():
            break
