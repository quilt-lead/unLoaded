"""The IFC-path revision store -> schema Bundle.

Two views of the same store, so the gap between them is measurable:
- "export": pipeline.export() - what GET /api/projects/{pid}/export returns. It drops the
  evidence boxes the store holds (link rects / spans, calc-edge evidence), so most of its
  links and calc edges are rejected here.
- "state":  pipeline.state() - the store's head revisions with full link + calc-edge evidence
  and the carried-forward human decisions applied to link status.
Revisions -> Revision; elements -> Element (evidence: the IFC entity in the head model
revision); load-path edges -> Relation (evidence: both IFC entities; gap_m with its unit);
calcs -> CalcSheet (rejected: neither view stores a title box); links -> Link; calc edges ->
Relation feeds. Reads a COPY of the sqlite file, never the live one.
"""
from __future__ import annotations

import os
import shutil
from collections import Counter

from ..models import Bundle, CalcSheet, DocKind, Document, Element, Link, ModelEvidence, Relation, RelationKind, Revision
from ._common import Reject, Rule, Tally, build, evidence_list, prov, to_values

# loadpath.py stores kind "load_path" for every edge; the relation type is in its rule text
LOADPATH_RULE = [("framed to connection", RelationKind.connected_by), ("bears on", RelationKind.bears_on),
                 ("end on", RelationKind.bears_on)]


def _rel_kind(kind: str, rule: str) -> RelationKind:
    r = (rule or "").lower()
    for key, rk in LOADPATH_RULE:
        if key in r:
            return rk
    raise Reject(f"unmapped load-path edge rule {rule!r} (kind {kind!r})")


def open_copy(store_dir: str, scratch: str):
    from ...store import Store
    os.makedirs(scratch, exist_ok=True)
    shutil.copyfile(os.path.join(store_dir, "calcgraph.sqlite"), os.path.join(scratch, "calcgraph.sqlite"))
    return Store(scratch)


def convert(store_dir: str, scratch: str, view: str = "state", pid: int | None = None,
            strict: bool = False) -> tuple[Bundle, Tally]:
    from ... import ENGINE_VERSION, pipeline
    st = open_copy(store_dir, scratch)
    pid = pid or st.ensure_project()
    t = Tally(source=f"ifc-store/{view}")
    s = pipeline.state(st, pid)
    exp = pipeline.export(st, pid) if view == "export" else None
    revs = st.revisions(pid)
    b = Bundle(source=t.source)
    seen = set()
    for r in revs:
        if r["sha256"] not in seen:
            seen.add(r["sha256"])
            b.documents.append(Document(sha256=r["sha256"], kind=DocKind.ifc if r["kind"] == "model" else DocKind.calc,
                                        name=r["source_name"] or r["blob"]))
        b.revisions.append(Revision(id=f"rev:{pid}:{r['id']}", kind=r["kind"], seq=r["seq"],
                                    parent_id=f"rev:{pid}:{r['parent_id']}" if r["parent_id"] else None,
                                    doc_sha=r["sha256"], label=r["label"] or "", source_name=r["source_name"] or "",
                                    created_at=r["created_at"], created_by="ingest"))
    msha = s["model_rev"]["sha256"]
    csha = s["calc_rev"]["sha256"]
    at = s["run"]["created_at"] if s["run"] else None
    R_IFC = Rule(engine="ifc_ingest (store keeps no reader version)", confidence=1.0)
    R_LP = Rule(engine="loadpath (store keeps no engine version)", confidence=1.0)
    # the mapping run records its engine version, so links / calc edges carry it from the source
    run_engine = s["run"]["engine_version"] if s["run"] else None
    R_MAP = Rule(engine=ENGINE_VERSION, version=ENGINE_VERSION, confidence=1.0)

    def eid(g):
        return f"el:ifc-store:{g}"

    def cid(k):
        return f"calc:ifc-store:{k}"

    # ---- elements ----
    src_elements = exp["elements"] if exp else s["elements"]
    for e in src_elements:
        def make(e=e):
            uc = Counter()
            ev = ModelEvidence(doc_sha=msha, global_id=e["global_id"], entity=e["ifc_type"], text=e.get("mark") or "")
            params = {} if exp else (e.get("params") or {})
            return {"_units": uc, "id": eid(e["global_id"]), "category": e.get("cat") or e["ifc_type"],
                    "mark": e.get("mark") or "", "designation": e.get("size") or e.get("profile") or "",
                    "level": e.get("storey") or "", "attrs": to_values(uc, {"status": e.get("status"), **params}),
                    "provenance": prov([ev], None, R_IFC, declared_rule_id="ifc_ingest.read_ifc", at=at)}
        build(t, b, "elements", Element, e["global_id"], make, strict)

    # ---- load path ----
    edges = exp["load_path"] if exp else s["edges"]
    kinds = {(x["src"], x["dst"]): x.get("kind", "") for x in s["edges"]}
    for x in edges:
        def make(x=x):
            uc = Counter()
            kind = x.get("kind") or kinds.get((x["src"], x["dst"]), "")
            evs = [ModelEvidence(doc_sha=msha, global_id=x["src"], text="source element"),
                   ModelEvidence(doc_sha=msha, global_id=x["dst"], text="target element")]
            return {"_units": uc, "id": f"rel:{kind}:{eid(x['src'])}->{eid(x['dst'])}", "kind": _rel_kind(kind, x["rule"]),
                    "src": eid(x["src"]), "dst": eid(x["dst"]),
                    "attrs": to_values(uc, {"source_kind": kind, "gap_m": x.get("gap_m")}),
                    "provenance": prov(evs, f"loadpath.{_slug(x.get('rule'))}", R_LP, rule_text=x.get("rule") or "", at=at)}
        build(t, b, "relations", Relation, f"{x['src']}->{x['dst']}", make, strict)

    # ---- calcs ----
    calcs = exp["calcs"] if exp else s["calcs"]
    for c in calcs:
        build(t, b, "calc_sheets", CalcSheet, c["key"], lambda c=c: {
            "id": cid(c["key"]), "doc_sha": csha, "page": (c.get("pages") or [None])[0], "sheet_id": c["key"],
            "title": c.get("title") or "", "software": c.get("software") or "",
            "provenance": _raise("the store keeps no title box / location for a calc (pages + text only)")}, strict)

    # ---- links ----
    if exp:
        flat = [{"global_id": e["global_id"], **l} for e in exp["elements"] for l in e["calcs"]]
        for l in flat:
            build(t, b, "links", Link, f"{l['global_id']}->{l['calc']}", lambda l=l: {
                "id": f"link:{eid(l['global_id'])}->{cid(l['calc'])}", "src": eid(l["global_id"]), "dst": cid(l["calc"]),
                "tier": l["tier"], "status": _status(l.get("review")),
                "provenance": prov([_raise("export link carries page + matched text but no box (the store has it)")],
                                   f"matcher.{l['tier']}", R_MAP, confidence=l["confidence"], rule_version=run_engine,
                                   engine=run_engine)}, strict)
    else:
        for l in s["links"]:
            def make(l=l):
                if l["status"] == "manual" and not l.get("rects"):
                    from ..models import Provenance
                    p = Provenance(evidence=[], rule_id="human.manual_link", rule_version="n/a", engine=ENGINE_VERSION,
                                   method="human", confidence=1.0, actor=l.get("decided_by") or "unknown",
                                   at=l.get("decided_at"))
                else:
                    ev = evidence_list(_SingleDoc(csha), [{"doc": "calcs", "page": l["page"], "rects": l.get("rects"),
                                                         "text": l.get("token") or ""}])
                    if l.get("span"):
                        ev[0] = ev[0].model_copy(update={"char_span": tuple(l["span"])})
                    p = prov(ev, f"matcher.{l['tier']}", R_MAP, rule_text=l.get("rule") or "", confidence=l["conf"],
                             rule_version=run_engine, engine=run_engine, at=at)
                return {"id": f"link:{eid(l['global_id'])}->{cid(l['calc_key'])}", "src": eid(l["global_id"]),
                        "dst": cid(l["calc_key"]), "tier": l["tier"], "status": l["status"], "provenance": p}
            build(t, b, "links", Link, f"{l['global_id']}->{l['calc_key']}", make, strict)

    # ---- calc edges ----
    cedges = exp["calc_edges"] if exp else s["calc_edges"]
    for x in cedges:
        build(t, b, "relations", Relation, f"{x['src']}->{x['dst']}", lambda x=x: {
            "id": f"rel:feeds:{cid(x['src'])}->{cid(x['dst'])}", "kind": RelationKind.feeds, "src": cid(x["src"]),
            "dst": cid(x["dst"]), "attrs": {"rules": [str(r) for r in x.get("rules") or []]},
            "provenance": prov(evidence_list(_SingleDoc(csha), [{"doc": "calcs", **ev} for ev in x.get("evidence") or []]),
                               "calcdeps." + "+".join(sorted(set(x.get("rules") or []))), R_MAP,
                               rule_version=run_engine, engine=run_engine, at=at)}, strict)
    if not exp:
        t.notes.append("human decisions (append-only log) are applied as Link.status; the decision rows themselves are "
                       "not facts in F1")
    return b, t


def _slug(s):
    import re
    return re.sub(r"[^a-z0-9]+", "_", (s or "").lower()).strip("_")


def _status(review: str | None) -> str:
    return review if review in ("auto", "confirmed", "rejected", "manual") else "auto"


def _raise(msg: str):
    raise Reject(msg)


class _SingleDoc:
    """A DocRegistry stand-in for a store view where every evidence item is on the head calc revision."""

    def __init__(self, sha: str):
        self._sha = sha

    def sha(self, key):
        return self._sha
