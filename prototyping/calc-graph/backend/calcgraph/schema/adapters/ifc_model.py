"""An IFC model's elements + property sets -> schema Bundle.

An Element per GlobalId with its psets as attrs (strings like "7.0 m" become Quantities; a bare
number with no unit stays Unitless) and an `ifc` Occurrence. A drawing set's model.ifc is the
building's authored IFC; its drawing tags are tied to these elements in graph.json (element.model,
set_pipeline.link_model), not here.
Geometry is not read here (ifc_ingest does that); positions would be ModelM.
"""
from __future__ import annotations

import os
import re
from collections import Counter

import ifcopenshell
import ifcopenshell.util.element as ue

from ..models import Bundle, DocKind, Element, ModelEvidence, Occurrence, OccurrenceKind
from ..units import Quantity, UnknownUnit, canonical
from ._common import DocRegistry, Rule, Tally, build, prov
from ..models import Unitless

_QTY = re.compile(r"^\s*([+-]?\d+(?:\.\d+)?)\s*([A-Za-z][A-Za-z0-9*/^'\"-]*)\s*$")
_BARE = re.compile(r"^\s*[+-]?\d+(?:\.\d+)?\s*$")
# pset fields whose text is a label even if numeric-looking
LABEL_PROPS = {"Mark", "Grid", "Section", "Size", "Grade", "Class", "Tag", "Sheet", "ElementId", "Level", "Base Level",
               "Top Level", "Bolts", "Plate", "Anchor Rods", "f'c", "Deck"}


def _value(prop: str, v, uc: Counter):
    if isinstance(v, bool):
        return v
    s = str(v)
    if prop.split(".")[-1] in LABEL_PROPS:
        return s
    m = _QTY.match(s)
    if m:
        try:
            uc["explicit_in_text"] += 1
            return Quantity(value=float(m.group(1)), unit=canonical(m.group(2)))
        except UnknownUnit:
            uc["explicit_in_text"] -= 1
            return s
    if isinstance(v, (int, float)) or _BARE.match(s):
        uc["unitless"] += 1
        return Unitless(raw=s)
    return s


def convert(path: str, set_id: str, strict: bool = False) -> tuple[Bundle, Tally]:
    t = Tally(source=f"{set_id}/{os.path.basename(path)}")
    reg = DocRegistry()
    f = ifcopenshell.open(path)
    fn = f.header.file_name
    engine = f"{fn.originating_system} / {fn.preprocessor_version}".strip(" /") or None
    reg.add("model", path, DocKind.ifc, os.path.basename(path), None, "IFC model")
    b = Bundle(source=t.source, documents=list(reg.docs.values()))
    sha = reg.sha("model")
    rule_declared = Rule(engine=engine or "ifc reader", confidence=1.0)

    for el in f.by_type("IfcElement"):
        psets = ue.get_psets(el)

        def make_el(el=el, psets=psets):
            uc = Counter()
            attrs = {}
            for ps, props in psets.items():
                for k, v in props.items():
                    if k == "id" or v is None or v == "":
                        continue
                    attrs[f"{ps}.{k}"] = _value(f"{ps}.{k}", v, uc)
            flat = {k.split(".", 1)[1]: v for k, v in attrs.items()}
            ev = ModelEvidence(doc_sha=sha, global_id=el.GlobalId, entity=el.is_a(), text=el.Name or "")
            return {"_units": uc, "id": f"el:{set_id}:ifc:{el.GlobalId}", "category": el.is_a(),
                    "mark": str(flat.get("Mark", "")), "designation": str(flat.get("Section") or flat.get("Size") or ""),
                    "grid": str(flat.get("Grid", "")), "attrs": attrs,
                    "provenance": prov([ev], None, rule_declared, declared_rule_id="ifc.element_psets", engine=engine,
                                       at=fn.time_stamp)}
        e = build(t, b, "elements", Element, el.GlobalId, make_el, strict)
        if e:
            build(t, b, "occurrences", Occurrence, el.GlobalId, lambda e=e: {
                "id": f"occ:{set_id}:ifc:{e.provenance.evidence[0].global_id}", "kind": OccurrenceKind.ifc,
                "subject_id": e.id, "at": e.provenance.evidence[0], "label": e.category, "provenance": e.provenance},
                  strict)
    if not engine:
        t.notes.append("IFC header names no originating system")
    t.notes.append(f"IFC header: originating system {fn.originating_system!r}, no version of the writing engine")
    return b, t
