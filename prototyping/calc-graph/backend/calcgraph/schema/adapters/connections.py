"""data/sets/<set>/connections.json (connections.py output) -> schema Bundle.

types      -> ConnectionType (evidence: the detail number + title words on its sheet)
instances  -> ConnectionInstance + Occurrence (callout bubble -> detail-callout, plan symbol ->
              plan-symbol, text reference -> text-ref) + Relation instance-of (instance -> type)
              + Relation connected-by (attached drawn element -> instance)
views, legends, other_callouts, note_refs, detail_refs and calc hits are not converted
(no entity for them in F1, or no target entity): counted under `skipped`.
"""
from __future__ import annotations

import json
import os
import re
from collections import Counter

from ..models import Bundle, ConnectionInstance, ConnectionType, Occurrence, OccurrenceKind, Relation, RelationKind
from ._common import Rule, Tally, build, pdf_ev, produced_by, prov, to_values
from .drawing_set import registry_for

R_CONN = Rule(engine="connections (connections.json carries no engine version)", confidence=1.0)
VIA_OCC = {"callout bubble": OccurrenceKind.detail_callout, "plan symbol": OccurrenceKind.plan_symbol,
           "text reference": OccurrenceKind.text_ref}


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (s or "").lower()).strip("_")


def convert(set_dir: str, strict: bool = False) -> tuple[Bundle, Tally]:
    c = json.load(open(os.path.join(set_dir, "connections.json")))
    graph = json.load(open(os.path.join(set_dir, "graph.json")))
    sid = c.get("id") or graph["id"]
    t = Tally(source=f"{sid}/connections.json")
    reg = registry_for(set_dir, graph)
    b = Bundle(source=t.source, documents=list(reg.docs.values()))
    built = c.get("built_at")
    P = produced_by(c, "connections")

    def tid(x):
        return f"conn-type:{sid}:{x}"

    def iid(x):
        return f"conn:{sid}:{x}"

    for x in c.get("types", []):
        build(t, b, "connection_types", ConnectionType, x["id"], lambda x=x: {
            "id": tid(x["id"]), "detail": str(x["detail"]), "sheet": x["sheet"], "title": x.get("title") or "",
            "category": x.get("category") or "", "is_connection": bool(x.get("is_connection")),
            "designations": [str(s) for s in x.get("sizes") or []], "scale": x.get("scale") or "",
            "provenance": prov([pdf_ev(reg, x["doc"], x["page"], [x.get("number_rect"), *(x.get("title_rects") or [])],
                                       f"{x['detail']} {x.get('title', '')}", note="detail number + title",
                                       sheet=x["sheet"])],
                               f"connections.detail_type.{_slug(x.get('category'))}", R_CONN,
                               rule_text=x.get("rule", ""), confidence=x.get("confidence"), at=built, **P)}, strict)

    known = {ct.id for ct in b.connection_types}
    for x in c.get("instances", []):
        def ev(x=x):
            return pdf_ev(reg, x["doc"], x["page"], x.get("rects") or [x.get("bbox")], x.get("ref", ""),
                          note=x.get("via", ""), sheet=x["sheet"])

        inst = build(t, b, "connection_instances", ConnectionInstance, x["id"], lambda x=x: {
            "id": iid(x["id"]), "type_id": tid(x["type_id"]) if x.get("type_id") else None, "via": x["via"],
            "symbol": x.get("symbol") or "", "attached": [f"el:{sid}:{a['id']}" for a in x.get("attached") or []],
            "grid": x.get("grid") or "",
            "provenance": prov([ev()], f"connections.instance.{_slug(x['via'])}", R_CONN,
                               rule_text=x.get("attach_rule", ""), confidence=x.get("confidence"), at=built, **P)}, strict)
        if not inst:
            continue
        build(t, b, "occurrences", Occurrence, x["id"], lambda x=x, inst=inst: {
            "id": f"occ:{sid}:{x['id']}", "kind": VIA_OCC[x["via"]], "subject_id": inst.id,
            "at": inst.provenance.evidence[0], "label": f"{x.get('ref')} on {x['sheet']}", "provenance": inst.provenance},
              strict)
        if inst.type_id:
            build(t, b, "relations", Relation, x["id"], lambda inst=inst: {
                "id": f"rel:instance-of:{inst.id}->{inst.type_id}", "kind": RelationKind.instance_of,
                "src": inst.id, "dst": inst.type_id,
                "attrs": {"type_known": inst.type_id in known},
                "provenance": prov(inst.provenance.evidence, "connections.instance_type_by_ref", R_CONN,
                                   rule_text="callout / legend reference names the detail",
                                   confidence=inst.provenance.confidence if x.get("confidence") is not None else None,
                                   at=built, **P)}, strict)
        for a in x.get("attached") or []:
            def make(a=a, inst=inst, x=x):
                uc = Counter()
                attrs = to_values(uc, {k: v for k, v in a.items() if k not in ("id", "cat", "type", "size")})
                return {"_units": uc, "id": f"rel:connected-by:el:{sid}:{a['id']}->{inst.id}",
                        "kind": RelationKind.connected_by, "src": f"el:{sid}:{a['id']}", "dst": inst.id, "attrs": attrs,
                        "provenance": prov(inst.provenance.evidence, "connections.attach_nearest", R_CONN,
                                           rule_text=x.get("attach_rule", ""),
                                           confidence=inst.provenance.confidence if x.get("confidence") is not None else None,
                                           at=built, **P)}
            build(t, b, "relations", Relation, f"{x['id']}<-{a['id']}", make, strict)

    for k in ("views", "other_callouts", "note_refs", "detail_refs"):
        t.skipped[f"{k} (no F1 entity)"] = len(c.get(k) or [])
    t.skipped["calc hits (name no connection type / instance to attach to)"] = len((c.get("calc") or {}).get("hits") or [])
    t.notes.append("attachment distances ('dist', 'end_dist') carry no unit in the output (the rule text says pt)")
    return b, t
