"""Revision diff of two IFC files with ifcdiff (IfcOpenShell), shaped like Store.compare_models.

    diff_ifc(old_path, new_path)      -> {"added", "removed", "changed", "counts", ...}
    diff_revisions(store, a, b)       -> the same for two model revisions of the revision store
                                         (their IFC blobs), plus "store": Store.compare_models(a, b)

ifcdiff matches elements by GlobalId and reports, per common element, which kinds of change it
found: attributes (Name, ObjectType, PredefinedType, ...), properties (every pset value, with old ->
new), container (storey), type, and geometry (the body shapes re-tessellated and compared, so a
moved or resized element is caught whatever its placement chain). With structural=True the
analysis model's items (IfcStructuralItem: analytical members and nodes) are diffed too; their
topology is NOT geometry-compared by ifcdiff (it only tessellates Body representations), so a
moved node shows up only through the attributes / properties it changes.

The store's own diff is a key join over what ifc_ingest extracted (params, mark, profile, storey,
an ingest-side geometry summary); ifcdiff reads the IFC itself. scripts/compare_revision_diffs.py
runs both on the same pair and reports where they agree and differ.
"""
from __future__ import annotations

import contextlib
import io
import re

import ifcopenshell
from ifcdiff import IfcDiff

# ifcdiff checks the non-attribute, non-geometry relationships in this order and stops at the first
# one that changed, so "property" goes last: its pset diff also flags the psets' own entity ids
# (ifcdiff's exclude r".*id$" never matches a DeepDiff path, which ends in "']"), and a spurious
# property hit first would hide a real container / type change.
RELATIONSHIPS = ["attributes", "container", "type", "property", "geometry"]
_KEY = re.compile(r"\['([^']*)'\]")


def _fields(dd) -> dict[str, list]:
    """DeepDiff of two get_psets() dicts -> {"Pset.Prop": [old, new]}."""
    out: dict[str, list] = {}
    if not hasattr(dd, "get"):
        return {"(psets)": ["", "changed"]}
    for path, v in (dd.get("values_changed") or {}).items():
        out[".".join(_KEY.findall(path))] = [v.get("old_value"), v.get("new_value")]
    # ifcdiff leaves each pset's own STEP id ("Pset.id") in the comparison: not a property
    out = {k: v for k, v in out.items() if not k.endswith(".id")}
    for kind, side in (("dictionary_item_added", 1), ("dictionary_item_removed", 0)):
        for path in dd.get(kind) or []:
            pair = [None, None]
            pair[side] = "(present)"
            out[".".join(_KEY.findall(str(path)))] = pair
    for path, v in (dd.get("type_changes") or {}).items():
        out[".".join(_KEY.findall(path))] = [v.get("old_value"), v.get("new_value")]
    return {k: v for k, v in out.items() if not k.endswith(".id")}


def diff_ifc(old_path: str, new_path: str, structural: bool = True) -> dict:
    old, new = ifcopenshell.open(old_path), ifcopenshell.open(new_path)
    query = "IfcElement, IfcSpatialElement" + (", IfcStructuralItem" if structural else "")
    d = IfcDiff(old, new, relationships=RELATIONSHIPS, is_shallow=False, filter_elements=query)
    with contextlib.redirect_stdout(io.StringIO()):
        d.diff()

    def row(f, g):
        e = f.by_guid(g)
        return {"global_id": g, "class": e.is_a(), "name": e.Name}

    changed = []
    for g, reg in sorted(d.change_register.items()):
        kinds = {k.replace("_changed", "") for k in reg}
        fields = _fields(reg["properties_changed"]) if "properties_changed" in reg else {}
        if "properties" in kinds and not fields:
            kinds.discard("properties")       # only the pset entity ids differed
        if not kinds:
            continue
        r = row(new, g) | {"kinds": sorted(kinds)}
        if fields:
            r["fields"] = fields
        changed.append(r)
    added = [row(new, g) for g in sorted(d.added_elements)]
    removed = [row(old, g) for g in sorted(d.deleted_elements)]

    def by_class(rows):
        c: dict[str, int] = {}
        for r in rows:
            c[r["class"]] = c.get(r["class"], 0) + 1
        return dict(sorted(c.items()))

    return {"engine": "ifcdiff", "relationships": RELATIONSHIPS, "query": query,
            "added": added, "removed": removed, "changed": changed,
            "counts": {"added": by_class(added), "removed": by_class(removed), "changed": by_class(changed)}}


def diff_revisions(st, a: int, b: int, structural: bool = True) -> dict:
    """ifcdiff of two model revisions of `st` (calcgraph.store.Store), with the store's key-join
    diff of the same pair alongside."""
    for rid in (a, b):
        if st.revision(rid)["kind"] != "model":
            raise ValueError(f"revision {rid} is not a model revision")
    out = diff_ifc(st.blob_path(a), st.blob_path(b), structural=structural)
    return out | {"a": a, "b": b, "store": st.compare_models(a, b)}
