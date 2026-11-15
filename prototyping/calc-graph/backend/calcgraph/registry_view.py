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

Two rules hold for every id, so no caller has to remember them:
- an element is governed by the spec articles of what it IS (its type, the type's material, the
  frames it belongs to, its own specified-by links): `governing_specs()` walks those relations, and
  `occurrences()` lists each governing article's spec page with `via` (which link brought it in). The
  change-order estimator reads the same `governing_specs()`.
- each distinct place appears once: occurrences are merged on (doc, page, bbox, IFC GlobalId, analysis
  object); distinct boxes on one page stay distinct and carry a `label` read from the document (a
  schedule row's row header, e.g. "L3 - ROOF"), so three rows of one schedule do not read alike.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Callable

# collection in design.json -> entity kind reported by resolve()
COLLECTIONS = (("elements", "element"), ("types", "type"), ("records", "record"),
               ("spec_articles", "spec_article"), ("details", "detail"))
# relations whose target's spec articles govern the source too (an element IS an instance of its type,
# a member of its frame); member-of GRID / LEVEL carry no specification and are not followed
GOVERNED_THROUGH = {"instance-of": None, "member-of": ("FRAME:",)}

# (doc, page) -> [(x0, y0, x1, y1, word)] in PDF points: the document text a label is read from
WordsFn = Callable[[str, int], list[tuple[float, float, float, float, str]]]


def occurrence_key(o: dict) -> tuple:
    """What makes two occurrences the same place: document, page, box, IFC GlobalId, analysis object."""
    bb = tuple(round(v, 1) for v in o.get("bbox") or ())
    return (o.get("doc"), o.get("page"), bb, o.get("global_id"), o.get("object_type"), o.get("label") if o.get("doc") == "etabs" else None,
            o.get("story"), o.get("id") if o.get("doc") == "platforms" else None, o.get("record_type"), o.get("platform"))


def dedupe(occ: list[dict]) -> list[dict]:
    """Each distinct place once, first occurrence wins; a later duplicate's `via` is merged into it."""
    seen: dict[tuple, dict] = {}
    out = []
    for o in occ:
        k = occurrence_key(o)
        if k in seen:
            if o.get("via"):
                first = seen[k]
                first["via"] = sorted(set(first.get("via") or []) | set(o["via"]))
            continue
        o = dict(o)
        seen[k] = o
        out.append(o)
    return out


def row_label(words: list[tuple[float, float, float, float, str]], bbox: list[float], gap: float = 14.0) -> str | None:
    """The row header of a table cell: the leftmost run of words on the cell's line (vertical centre
    inside the cell's box), left of the cell. None when nothing is there."""
    y0, y1, x0 = bbox[1], bbox[3], bbox[0]
    line = sorted((w for w in words if y0 <= (w[1] + w[3]) / 2 <= y1 and w[2] <= x0 - 1), key=lambda w: w[0])
    if not line:
        return None
    run = [line[0]]
    for w in line[1:]:
        if w[0] - run[-1][2] > gap:
            break
        run.append(w)
    return " ".join(w[4] for w in run).strip() or None


class RegistryView:
    def __init__(self, design: dict, words: WordsFn | None = None):
        """words(doc, page): the document's words, for occurrence labels (None = no labels)."""
        self.design = design
        self.words = words
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

    def governing_specs(self, eid: str) -> dict[str, list[str]]:
        """{spec article id: [what brought it in]} for every article that governs `eid`: its own
        specified-by links, and those of its type (instance-of), the type's material and the frames it
        is a member of. A SPEC id governs itself."""
        out: dict[str, set] = defaultdict(set)
        hit = self.resolve(eid)
        if hit and hit[0] == "spec_article":
            out[eid].add(eid)
        todo, seen = [eid], set()
        while todo:
            x = todo.pop()
            if x in seen:
                continue
            seen.add(x)
            for r in self.rels_out.get(x, []):
                if r["kind"] == "specified-by":
                    out[r["dst"]].add(x)
                elif r["kind"] in GOVERNED_THROUGH and (GOVERNED_THROUGH[r["kind"]] is None
                                                       or r["dst"].startswith(GOVERNED_THROUGH[r["kind"]])):
                    todo.append(r["dst"])
            ent = (self.resolve(x) or (None, {}))[1]
            if ent.get("material"):
                todo.append(ent["material"])
        return {k: sorted(v) for k, v in sorted(out.items())}

    def spec_occurrences(self, eid: str) -> list[dict]:
        """The spec page box of every article governing `eid` (not `eid`'s own), with `via`."""
        out = []
        for art, via in self.governing_specs(eid).items():
            if art == eid:
                continue
            locs = [o for o in self.doc_occ.get(art, []) if o.get("doc") == "specs"] or self.own_location(art)
            for o in locs:
                out.append({**o, "ref": eid, "article": art, "via": via, "how": "governing-spec"})
        return out

    def _label(self, o: dict) -> dict:
        if self.words and o.get("how") == "schedule_row" and o.get("bbox") and o.get("page") and not o.get("label"):
            try:
                lab = row_label(self.words(o["doc"], o["page"]), o["bbox"])
            except Exception as e:   # a label is a convenience: say why it is missing, never fail the page
                lab = None
                o = {**o, "label_error": f"{type(e).__name__}: {e}"}
            if lab:
                o = {**o, "label": lab}
        return o

    def occurrences(self, eid: str, analysis: list[dict] | None = None, platforms: dict[str, list[dict]] | None = None) -> list[dict]:
        """Every occurrence of `eid`, each distinct place once: own location first, then documents
        (incl. the governing spec articles), analysis model, platforms.
        `analysis` = an analysis adapter's occurrences() rows; `platforms` = platform_occurrences()."""
        out = self.own_location(eid) + list(self.doc_occ.get(eid, [])) + self.spec_occurrences(eid)
        out += [o for o in analysis or [] if o.get("ref") == eid]
        out += (platforms or {}).get(eid, [])
        return [self._label(o) for o in dedupe(out)]

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
