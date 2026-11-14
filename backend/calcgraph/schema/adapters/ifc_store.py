"""The IFC-path revision store -> schema facts.

Per-snapshot builders, used by the revision store when it writes a snapshot's facts
(revstore) and by the audit:
  model_facts(st, rid)    elements (evidence: the IFC entity in that model revision) + load-path
                          relations (evidence: both entities; gap_m with its unit)
  calc_facts(st, rid)     calc sheets (evidence: the calc's title box, which the store keeps per
                          calc since F2 - title-line word boxes, or the whole first page for a
                          scanned / front-matter page, saying so)
  run_facts(st, run_id)   links (the matcher's span + word boxes) + calc-edge feeds relations
                          (calcdeps evidence), keyed by the run
Provenance comes from what the store recorded when the snapshot was produced:
revision.producer_json / mapping_run.producer_json (engine = module@source-hash, rule id,
declared confidence) and the run's engine_version. Snapshots produced before F2 carry no
producer record: those fields fall back to the rule table below and are listed in
provenance.adapter_supplied, so the gap stays counted.

convert(store_dir, scratch, view) - the audit's two views of the head revisions:
- "state":  the head snapshots' facts with the carried-forward human decisions applied (link
            status; a link made by hand is a Link with human provenance)
- "export": GET /api/projects/{pid}/export, which since F2 carries the evidence boxes, calc
            title boxes and calc-edge evidence it used to drop.
Reads a COPY of the sqlite file, never the live one.
"""
from __future__ import annotations

import json
import os
import re
import shutil
from collections import Counter

from ..models import (Bundle, CalcSheet, DocKind, Document, Element, Link, ModelEvidence, Provenance, Relation,
                      RelationKind, Revision)
from ._common import Reject, Rule, Tally, build, evidence_list, prov, to_values

# pre-4512334 loadpath stored kind "load_path" for every edge; the relation type is in its rule text
LOADPATH_RULE = [("framed to connection", RelationKind.connected_by), ("bears on", RelationKind.bears_on),
                 ("end on", RelationKind.bears_on)]
# fallbacks for snapshots stored before producers were recorded (flagged adapter_supplied)
R_IFC = Rule(engine="ifc_ingest (pre-F2 revision: no producer record)", confidence=1.0)
R_LP = Rule(engine="loadpath (pre-F2 revision: no producer record)", confidence=1.0)
R_SEG = Rule(engine="segment (pre-F2 revision: no producer record)", confidence=1.0)
R_DEPS = Rule(engine="calcdeps (pre-F2 run: no producer record)", confidence=1.0)


def eid(g: str) -> str:
    return f"el:ifc-store:{g}"


def cid(k: str) -> str:
    return f"calc:ifc-store:{k}"


def _rel_kind(kind: str, rule: str) -> RelationKind:
    """loadpath since 4512334 stores the relation kind itself (frames-into / bears-on / connected-by);
    revisions built before it store kind 'load_path' with the relation type in the rule text."""
    try:
        return RelationKind(kind)
    except ValueError:
        pass
    r = (rule or "").lower()
    for key, rk in LOADPATH_RULE:
        if key in r:
            return rk
    raise Reject(f"unmapped load-path edge rule {rule!r} (kind {kind!r})")


def _slug(s):
    return re.sub(r"[^a-z0-9]+", "_", (s or "").lower()).strip("_")


def _producer(st, table: str, sid: int) -> dict:
    r = st.db.execute(f"SELECT producer_json FROM {table} WHERE id=?", (sid,)).fetchone()
    return json.loads(r[0]) if r and r[0] else {}


def _pkw(p: dict | None, with_rule: bool = True) -> dict:
    """prov() keyword args from one producer record (absent fields stay None -> fallback, flagged)."""
    p = p or {}
    out = {"rule_version": p.get("version"), "engine": p.get("engine"), "confidence": p.get("confidence")}
    if with_rule:
        out["rule_id"] = p.get("rule_id")
    return out


class _SingleDoc:
    """A DocRegistry stand-in: every evidence item is on one document."""

    def __init__(self, sha: str):
        self._sha = sha

    def sha(self, key):
        return self._sha


# ---------------- per-snapshot builders ----------------
def model_facts(st, rid: int, t: Tally, b: Bundle, strict: bool = False) -> None:
    rev = st.revision(rid)
    msha, at = rev["sha256"], rev["created_at"]
    prod = _producer(st, "revision", rid)
    pi, pl = prod.get("ifc_ingest"), prod.get("loadpath")
    for e in st.elements(rid):
        def make(e=e):
            uc = Counter()
            ev = ModelEvidence(doc_sha=msha, global_id=e["global_id"], entity=e["ifc_type"], text=e.get("mark") or "")
            kw = _pkw(pi)
            rule_id = kw.pop("rule_id")
            return {"_units": uc, "id": eid(e["global_id"]), "category": e.get("cat") or e["ifc_type"],
                    "mark": e.get("mark") or "", "designation": e.get("profile") or "", "level": e.get("storey") or "",
                    "attrs": to_values(uc, e.get("params") or {}),
                    "provenance": prov([ev], rule_id, R_IFC, declared_rule_id="ifc_ingest.read_ifc", at=at, **kw)}
        build(t, b, "elements", Element, e["global_id"], make, strict)
    for x in st.element_edges(rid):
        def make(x=x):
            uc = Counter()
            evs = [ModelEvidence(doc_sha=msha, global_id=x["src"], text="source element"),
                   ModelEvidence(doc_sha=msha, global_id=x["dst"], text="target element")]
            return {"_units": uc, "id": f"rel:{x['kind']}:{eid(x['src'])}->{eid(x['dst'])}",
                    "kind": _rel_kind(x["kind"], x["rule"]), "src": eid(x["src"]), "dst": eid(x["dst"]),
                    "attrs": to_values(uc, {"source_kind": x["kind"], "gap_m": x.get("gap_m")}),
                    "provenance": prov(evs, f"loadpath.{_slug(x.get('rule'))}", R_LP, rule_text=x.get("rule") or "",
                                       at=at, **_pkw(pl, with_rule=False))}
        build(t, b, "relations", Relation, f"{x['src']}->{x['dst']}", make, strict)


def calc_facts(st, rid: int, t: Tally, b: Bundle, strict: bool = False) -> None:
    rev = st.revision(rid)
    csha, at = rev["sha256"], rev["created_at"]
    ps = _producer(st, "revision", rid).get("segment")
    for c in st.calcs(rid, with_params=True):
        def make(c=c):
            tb = (c.get("params") or {}).get("title_box")
            if not tb:
                raise Reject("calc has no title box in the store")
            ev = evidence_list(_SingleDoc(csha), [{"doc": "calcs", "page": tb["page"], "rects": tb["rects"],
                                                   "text": c.get("title") or "", "note": tb.get("note", "")}])
            if tb.get("span"):
                ev[0] = ev[0].model_copy(update={"char_span": tuple(tb["span"])})
            kw = _pkw(ps)
            rule_id = kw.pop("rule_id")
            if (c.get("params") or {}).get("title_box_backfilled"):
                kw["engine"] = None  # computed at store migration, not by the ingest that made the revision
            return {"id": cid(c["key"]), "doc_sha": csha, "page": c["pages"][0], "sheet_id": c["key"],
                    "title": c.get("title") or "", "software": c.get("software") or "",
                    "role": "front matter" if c["front"] else ("scanned" if c["scanned"] else "calc"),
                    "provenance": prov(ev, rule_id or tb.get("rule"), R_SEG, at=at, **kw)}
        build(t, b, "calc_sheets", CalcSheet, c["key"], make, strict)


def _link_fact(l: dict, csha: str, engine: str, at: str | None) -> dict:
    ev = evidence_list(_SingleDoc(csha), [{"doc": "calcs", "page": l["page"], "rects": l.get("rects"),
                                           "text": l.get("token") or ""}])
    if l.get("span"):
        ev[0] = ev[0].model_copy(update={"char_span": tuple(l["span"])})
    return {"id": f"link:{eid(l['global_id'])}->{cid(l['calc_key'])}", "src": eid(l["global_id"]),
            "dst": cid(l["calc_key"]), "tier": l["tier"], "status": l.get("status") or "auto",
            "provenance": prov(ev, f"matcher.{l['tier']}", Rule(engine=engine), rule_text=l.get("rule") or "",
                               confidence=l["conf"], rule_version=engine, engine=engine, at=at)}


def run_facts(st, run_id: int, t: Tally, b: Bundle, strict: bool = False) -> None:
    run = st.db.execute("SELECT * FROM mapping_run WHERE id=?", (run_id,)).fetchone()
    csha = st.revision(run["calc_rev"])["sha256"]
    engine, at = run["engine_version"], run["created_at"]
    pd = _producer(st, "mapping_run", run_id).get("calcdeps")
    for l in st.links(run_id):
        build(t, b, "links", Link, f"{l['global_id']}->{l['calc_key']}", lambda l=l: _link_fact(l, csha, engine, at),
              strict)
    for x in st.stored_calc_edges(run_id):
        build(t, b, "relations", Relation, f"{x['src']}->{x['dst']}", lambda x=x: {
            "id": f"rel:feeds:{cid(x['src'])}->{cid(x['dst'])}", "kind": RelationKind.feeds, "src": cid(x["src"]),
            "dst": cid(x["dst"]), "attrs": {"rules": [str(r) for r in x.get("rules") or []]},
            "provenance": prov(evidence_list(_SingleDoc(csha), [{"doc": "calcs", **ev} for ev in x.get("evidence") or []]),
                               "calcdeps." + "+".join(sorted(set(x.get("rules") or []))), R_DEPS,
                               rule_version=engine, engine=(pd or {}).get("engine") or engine,
                               confidence=(pd or {}).get("confidence"), at=at)}, strict)


def documents_and_revisions(st, pid: int, b: Bundle) -> None:
    seen = set()
    for r in st.revisions(pid):
        if r["sha256"] not in seen:
            seen.add(r["sha256"])
            b.documents.append(Document(sha256=r["sha256"], kind=DocKind.ifc if r["kind"] == "model" else DocKind.calc,
                                        name=r["source_name"] or r["blob"]))
        b.revisions.append(Revision(id=f"rev:{pid}:{r['id']}", kind=r["kind"], seq=r["seq"],
                                    parent_id=f"rev:{pid}:{r['parent_id']}" if r["parent_id"] else None,
                                    doc_sha=r["sha256"], label=r["label"] or "", source_name=r["source_name"] or "",
                                    created_at=r["created_at"], created_by="ingest"))


def apply_decisions(st, pid: int, links: list[Link], gids: set[str], keys: set[str]) -> list[Link]:
    """The append-only decision log, carried forward: status on auto links; a manual link with no
    auto link becomes a Link with human provenance (the decision is its evidence of record)."""
    by = {(l.src, l.dst): l for l in links}
    out = list(links)
    for (g, k), d in st.effective_decisions(pid).items():
        if g not in gids or k not in keys:
            continue
        key = (eid(g), cid(k))
        l = by.get(key)
        status = {"confirm": "confirmed", "reject": "rejected", "manual": "confirmed" if l else "manual"}[d["action"]]
        if l:
            i = out.index(l)
            out[i] = l.model_copy(update={"status": status})
        elif d["action"] == "manual":
            out.append(Link(id=f"link:{key[0]}->{key[1]}", src=key[0], dst=key[1], tier="manual", status="manual",
                            provenance=Provenance(evidence=[], rule_id="human.manual_link", rule_text=d.get("note") or "",
                                                  rule_version="decision-log", engine="store.decision",
                                                  method="human", confidence=1.0, actor=d["actor"] or "unknown",
                                                  at=d["at"])))
    return out


def head_bundle(st, pid: int, t: Tally, strict: bool = False) -> Bundle:
    """State view: the head model / calc revisions and their latest mapping run, decisions applied."""
    p = st.project(pid)
    b = Bundle(source=t.source)
    documents_and_revisions(st, pid, b)
    mrev, crev = p["head_model_rev"], p["head_calc_rev"]
    if mrev:
        model_facts(st, mrev, t, b, strict)
    if crev:
        calc_facts(st, crev, t, b, strict)
    run = st.latest_run(pid, mrev, crev) if (mrev and crev) else None
    if run:
        run_facts(st, run["id"], t, b, strict)
        gids = {e["global_id"] for e in st.elements(mrev)}
        keys = {c["key"] for c in st.calcs(crev)}
        b.links = apply_decisions(st, pid, b.links, gids, keys)
        t.notes.append("human decisions (append-only log) applied as Link.status; manual links carry human provenance")
    return b


# ---------------- audit views ----------------
def open_copy(store_dir: str, scratch: str):
    from ...store import Store
    os.makedirs(scratch, exist_ok=True)
    shutil.copyfile(os.path.join(store_dir, "calcgraph.sqlite"), os.path.join(scratch, "calcgraph.sqlite"))
    blobs = os.path.join(store_dir, "blobs")
    if os.path.isdir(blobs) and not os.path.exists(os.path.join(scratch, "blobs")):
        os.symlink(blobs, os.path.join(scratch, "blobs"))
    return Store(scratch)


def convert(store_dir: str, scratch: str, view: str = "state", pid: int | None = None,
            strict: bool = False) -> tuple[Bundle, Tally]:
    st = open_copy(store_dir, scratch)
    pid = pid or st.ensure_project()
    t = Tally(source=f"ifc-store/{view}")
    if view == "state":
        return head_bundle(st, pid, t, strict), t
    from ... import pipeline
    exp = pipeline.export(st, pid)
    s = pipeline.state(st, pid)
    b = Bundle(source=t.source)
    documents_and_revisions(st, pid, b)
    msha, csha = s["model_rev"]["sha256"], s["calc_rev"]["sha256"]
    at = s["run"]["created_at"] if s["run"] else None
    run_engine = s["run"]["engine_version"] if s["run"] else None
    prods = exp.get("producers") or {}
    pi, pl = (prods.get("model") or {}).get("ifc_ingest"), (prods.get("model") or {}).get("loadpath")
    ps, pd = (prods.get("calcs") or {}).get("segment"), (prods.get("mapping") or {}).get("calcdeps")

    def make_el(e):
        kw = _pkw(pi)
        rule_id = kw.pop("rule_id")
        return {"id": eid(e["global_id"]), "category": e["ifc_type"], "mark": e.get("mark") or "",
                "designation": e.get("size") or "", "level": e.get("storey") or "",
                "provenance": prov([ModelEvidence(doc_sha=msha, global_id=e["global_id"], entity=e["ifc_type"])], rule_id,
                                   R_IFC, declared_rule_id="ifc_ingest.read_ifc", at=at, **kw)}
    for e in exp["elements"]:
        build(t, b, "elements", Element, e["global_id"], lambda e=e: make_el(e), strict)
    kinds = {(x["src"], x["dst"]): x.get("kind", "") for x in s["edges"]}
    for x in exp["load_path"]:
        build(t, b, "relations", Relation, f"{x['src']}->{x['dst']}", lambda x=x: {
            "id": f"rel:{kinds.get((x['src'], x['dst']), '')}:{eid(x['src'])}->{eid(x['dst'])}",
            "kind": _rel_kind(kinds.get((x["src"], x["dst"]), ""), x["rule"]), "src": eid(x["src"]), "dst": eid(x["dst"]),
            "provenance": prov([ModelEvidence(doc_sha=msha, global_id=x["src"]), ModelEvidence(doc_sha=msha, global_id=x["dst"])],
                               f"loadpath.{_slug(x.get('rule'))}", R_LP, rule_text=x.get("rule") or "", at=at,
                               **_pkw(pl, with_rule=False))}, strict)
    for c in exp["calcs"]:
        def make(c=c):
            tb = c.get("title_box") or _raise("export calc carries no title box")
            ev = evidence_list(_SingleDoc(csha), [{"doc": "calcs", "page": tb["page"], "rects": tb["rects"],
                                                   "text": c.get("title") or "", "note": tb.get("note", "")}])
            return {"id": cid(c["key"]), "doc_sha": csha, "page": c["pages"][0], "sheet_id": c["key"],
                    "title": c.get("title") or "", "software": c.get("software") or "",
                    "provenance": prov(ev, tb.get("rule"), R_SEG, at=at, **{k: v for k, v in _pkw(ps).items()
                                                                              if k != "rule_id"})}
        build(t, b, "calc_sheets", CalcSheet, c["key"], make, strict)
    for e in exp["elements"]:
        for l in e["calcs"]:
            def make(l=l, g=e["global_id"]):
                ev = l.get("evidence") or _raise("export link carries no evidence")
                if l.get("review") == "manual" and not ev.get("rects"):
                    return {"id": f"link:{eid(g)}->{cid(l['calc'])}", "src": eid(g), "dst": cid(l["calc"]),
                            "tier": l["tier"], "status": "manual",
                            "provenance": Provenance(evidence=[], rule_id="human.manual_link", rule_version="decision-log",
                                                     engine="store.decision", method="human", confidence=1.0,
                                                     actor=l.get("decided_by") or "unknown", at=l.get("decided_at"))}
                return _link_fact({"global_id": g, "calc_key": l["calc"], "page": ev.get("page"), "rects": ev.get("rects"),
                                   "span": ev.get("span"), "token": l.get("matched_text"), "tier": l["tier"],
                                   "rule": l.get("rule"), "conf": l["confidence"], "status": l.get("review")},
                                  csha, run_engine, at)
            build(t, b, "links", Link, f"{e['global_id']}->{l['calc']}", make, strict)
    for x in exp["calc_edges"]:
        build(t, b, "relations", Relation, f"{x['src']}->{x['dst']}", lambda x=x: {
            "id": f"rel:feeds:{cid(x['src'])}->{cid(x['dst'])}", "kind": RelationKind.feeds, "src": cid(x["src"]),
            "dst": cid(x["dst"]), "attrs": {"rules": [str(r) for r in x.get("rules") or []]},
            "provenance": prov(evidence_list(_SingleDoc(csha), [{"doc": "calcs", **ev} for ev in x.get("evidence") or []]),
                               "calcdeps." + "+".join(sorted(set(x.get("rules") or []))), R_DEPS,
                               rule_version=run_engine, engine=(pd or {}).get("engine") or run_engine,
                               confidence=(pd or {}).get("confidence"), at=at)}, strict)
    return b, t


def _raise(msg: str):
    raise Reject(msg)
