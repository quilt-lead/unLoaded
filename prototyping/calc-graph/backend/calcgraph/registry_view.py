"""The v2 registry read path: one id -> its entity and EVERY place it occurs.

design.json holds registry entities in several collections, all addressed by id from relations and
occurrences: elements (COL-2B, CX-..), types (TYPE:/DETAIL:/MAT:), calc records, spec articles
(SPEC:05 12 00/1.3.B) and drawing details (DET:4/S-502). `RegistryView.resolve()` looks an id up in all
of them, so any id a relation or occurrence names can be opened.

`RegistryView.occurrences()` is the one list of where an id occurs, merged from every source the
prototype knows: the document occurrences in design.json (drawings, specs, calcs), the IFC element, an
entity's own located box (a detail's sheet/page/bbox, a spec article's page/bbox), the analysis model
(ETABS objects) and the construction platforms (records whose element_ids name it, with the platform,
record type, source live/mock and a link). Callers pass the adapter lists; the view only indexes them.
"""
from __future__ import annotations

from collections import defaultdict

# collection in design.json -> entity kind reported by resolve()
COLLECTIONS = (("elements", "element"), ("types", "type"), ("records", "record"),
               ("spec_articles", "spec_article"), ("details", "detail"))


class RegistryView:
    def __init__(self, design: dict):
        self.design = design
        self.by_id: dict[str, tuple[str, dict]] = {}
        for coll, kind in COLLECTIONS:
            for x in design.get(coll) or []:
                self.by_id.setdefault(x["id"], (kind, x))
        self.rels_out: dict[str, list[dict]] = defaultdict(list)
        self.rels_in: dict[str, list[dict]] = defaultdict(list)
        for r in design.get("relations", []):
            self.rels_out[r["src"]].append(r)
            self.rels_in[r["dst"]].append(r)
        self.doc_occ: dict[str, list[dict]] = defaultdict(list)
        for o in design.get("occurrences", []):
            self.doc_occ[o["ref"]].append(o)
        self.designed_by: dict[str, list[dict]] = defaultdict(list)
        for r in design.get("records", []):
            for e in r.get("elements", []):
                self.designed_by[e].append(r)

    # ------------------------------------------------------------------ entities
    def resolve(self, eid: str) -> tuple[str, dict] | None:
        """(kind, entity) for any registry id, or None. kind: element | type | record | spec_article | detail."""
        return self.by_id.get(eid)

    # ------------------------------------------------------------------ occurrences
    def own_location(self, eid: str) -> list[dict]:
        """The located box an entity carries itself (IFC GlobalId; a detail's or spec article's page box)."""
        hit = self.resolve(eid)
        if not hit:
            return []
        kind, x = hit
        if x.get("global_id"):
            return [{"ref": eid, "doc": "ifc", "global_id": x["global_id"], "how": "ifc-element"}]
        if kind == "detail" and x.get("page"):
            return [{"ref": eid, "doc": "drawings", "how": "detail", "page": x["page"], "bbox": x.get("bbox"),
                     "sheet": x.get("sheet"), "text": x.get("title")}]
        if kind == "spec_article" and x.get("page") and not any(o.get("doc") == "specs" for o in self.doc_occ.get(eid, [])):
            return [{"ref": eid, "doc": "specs", "how": "spec_article", "page": x["page"], "bbox": x.get("bbox"),
                     "sheet": x.get("section"), "text": x.get("text")}]
        return []

    def occurrences(self, eid: str, analysis: list[dict] | None = None, platforms: dict[str, list[dict]] | None = None) -> list[dict]:
        """Every occurrence of `eid`: own location first, then documents, analysis model, platforms.
        `analysis` = an analysis adapter's occurrences() rows; `platforms` = platform_occurrences()."""
        out = self.own_location(eid) + list(self.doc_occ.get(eid, []))
        out += [o for o in analysis or [] if o.get("ref") == eid]
        out += (platforms or {}).get(eid, [])
        return out

    def view(self, eid: str, analysis: list[dict] | None = None, platforms: dict[str, list[dict]] | None = None) -> dict | None:
        """The registry element page payload, or None when the id is unknown."""
        hit = self.resolve(eid)
        if not hit:
            return None
        kind, x = hit
        return {"id": eid, "kind": kind,
                "element": x if kind in ("element", "type") else None,
                "record": x if kind == "record" else None,
                "entity": x,
                "relations_out": self.rels_out.get(eid, []), "relations_in": self.rels_in.get(eid, []),
                "designed_by": self.designed_by.get(eid, []),
                "occurrences": self.occurrences(eid, analysis, platforms),
                "occurrence_kinds_reserved": ["discussed-in (meeting id, time range, speaker, transcript span) - not built yet"]}


def platform_occurrences(adapters) -> dict[str, list[dict]]:
    """{registry id: [occurrence]} for every platform record that names a registry element. One row per
    (record, element): doc "platforms", the platform, record type, number, title, status, the record's
    link, source live|mock and source_label (from live.SourcedAdapter)."""
    out: dict[str, list[dict]] = defaultdict(list)
    for a in adapters:
        for rt in sorted(a.capabilities):
            for r in a.list(rt):
                for e in dict.fromkeys(r.element_ids):
                    out[e].append({"ref": e, "doc": "platforms", "how": "platform-record", "platform": a.name,
                                   "platform_label": a.label, "record_type": rt, "id": r.id, "record_ref": r.ref,
                                   "number": r.number, "title": r.title, "status": r.status, "link": r.links.get("self"),
                                   "source": r.fields.get("source", "mock"), "source_label": r.fields.get("source_label")})
    return dict(out)
