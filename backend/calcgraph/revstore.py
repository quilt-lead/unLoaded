"""The revision store: opening it, writing every snapshot's schema facts, and reading schema
Bundles back.

IFC path      pipeline.ingest_model / ingest_calcs / remap write the native rows (store.py), then
              write_revision_facts / write_run_facts store that snapshot's schema facts.

(The hackathon's drawing-set path - record_set_output / import_sets, which converted set outputs
through the drawing_set / calc_records / connections adapters - was not ported. The store's tables
still accept drawing-set projects so an existing store opens unchanged.)

Producer records: every snapshot built through here records the code that built it as
module@<sha1 of the module source>[:12] (plus the rule's declared confidence where the module
declares none per fact). Imported outputs record no producer: their versions are unknown.
"""
from __future__ import annotations

import hashlib
import importlib
import os
import threading
from collections import Counter

from .store import Store

# backend/ - the uv project root; local data (store, synthetic package, eval output) lives in backend/data/
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

_STORES: dict[str, Store] = {}
_LOCK = threading.RLock()


def store_dir() -> str:
    return os.environ.get("CALCGRAPH_STORE", os.path.join(ROOT, "data", "store"))


def open_store(root: str | None = None) -> Store:
    """One Store per directory per process; migrates a v1 store and backfills missing facts."""
    root = root or store_dir()
    with _LOCK:
        st = _STORES.get(root)
        if st is None:
            st = _STORES[root] = Store(root)
            backfill_ifc_facts(st)
        return st


def module_version(name: str) -> str:
    mod = importlib.import_module(f"calcgraph.{name}")
    with open(mod.__file__, "rb") as fh:
        return hashlib.sha1(fh.read()).hexdigest()[:12]


def producer(*names: str, **declared: dict) -> dict:
    """{module: {"engine": "module@hash", "version": hash, ...declared fields}}."""
    out = {}
    for n in names:
        v = module_version(n)
        out[n] = {"engine": f"{n}@{v}", "version": v} | declared.get(n, {})
    return out


# ---------------- IFC path facts ----------------
def _tally(source: str):
    from .schema.adapters._common import Tally
    return Tally(source=source)


def _facts_of(bundle) -> list[tuple[str, object]]:
    out = []
    for coll in ("element_types", "elements", "occurrences", "relations", "calc_sheets", "calc_records",
                 "connection_types", "connection_instances", "links", "findings"):
        out += [(coll, f) for f in getattr(bundle, coll)]
    return out


def _dedupe(facts: list[tuple[str, object]], t) -> list[tuple[str, object]]:
    """Two adapter facts with one id (the source emitted a duplicate) keep the first; counted."""
    seen, out = set(), []
    for coll, f in facts:
        if (coll, f.id) in seen:
            t.skipped[f"duplicate id in {coll}"] += 1
            continue
        seen.add((coll, f.id))
        out.append((coll, f))
    return out


def write_revision_facts(st: Store, rid: int) -> dict:
    from .schema.adapters import ifc_store
    from .schema.models import Bundle
    kind = st.revision(rid)["kind"]
    t = _tally(f"revision/{rid}")
    b = Bundle(source=t.source)
    (ifc_store.model_facts if kind == "model" else ifc_store.calc_facts)(st, rid, t, b)
    st.put_facts("revision", rid, _dedupe(_facts_of(b), t))
    return t.summary()


def write_run_facts(st: Store, run_id: int) -> dict:
    from .schema.adapters import ifc_store
    from .schema.models import Bundle
    t = _tally(f"run/{run_id}")
    b = Bundle(source=t.source)
    ifc_store.run_facts(st, run_id, t, b)
    st.put_facts("run", run_id, _dedupe(_facts_of(b), t))
    return t.summary()


def backfill_ifc_facts(st: Store) -> dict:
    """Facts for IFC-path snapshots stored before F2 (or whose fact write was interrupted)."""
    n = Counter()
    for (rid,) in st.db.execute("SELECT id FROM revision WHERE kind IN ('model','calcs') AND facts_at IS NULL").fetchall():
        write_revision_facts(st, rid)
        n["revisions"] += 1
    for (run_id,) in st.db.execute("SELECT id FROM mapping_run WHERE facts_at IS NULL").fetchall():
        write_run_facts(st, run_id)
        n["runs"] += 1
    if n:
        st.commit()
    return dict(n)


# ---------------- schema bundles ----------------
def _bundle(st: Store, source: str, pid: int, scopes: list[tuple[str, int]]):
    from .schema.models import Bundle, Document, Revision
    from .schema.frames import SheetCalibration
    from .schema.adapters import ifc_store
    data: dict[str, list] = {}
    shas: list[str] = []
    for scope, sid in scopes:
        for coll, f in st.facts(scope, sid):
            data.setdefault(coll, []).append(f)
        if scope == "revision":
            shas += [d["sha256"] for d in st.revision_docs(sid)]
    b = Bundle.model_validate({"source": source, **data})
    for sha in dict.fromkeys(shas):
        d = st.document(sha)
        b.documents.append(Document(sha256=sha, kind=d["kind"], name=d["name"], pages=d["pages"], role=d["role"] or ""))
    for r in st.all_revisions(pid):
        b.revisions.append(Revision(id=f"rev:{pid}:{r['id']}", kind=r["kind"], seq=r["seq"],
                                    parent_id=f"rev:{pid}:{r['parent_id']}" if r["parent_id"] else None,
                                    doc_sha=r["sha256"], label=r["label"] or "", source_name=r["source_name"] or "",
                                    created_at=r["created_at"], created_by=r["created_by"]))
    for scope, sid in scopes:
        if scope == "revision":
            b.calibrations += [SheetCalibration.model_validate_json(c) for c in st.calibrations(sid)]
    return b, ifc_store


def project_bundle(st: Store, pid: int):
    """Schema Bundle of a project's head snapshots, read from the stored facts. IFC projects get
    the append-only decision log applied (status; manual links with human provenance)."""
    proj = st.db.execute("SELECT * FROM project WHERE id=?", (pid,)).fetchone()
    if not proj:
        raise KeyError(pid)
    heads = st.heads(pid)
    if proj["kind"] == "ifc":
        mrev, crev = heads.get("model"), heads.get("calcs")
        scopes = [("revision", r) for r in (mrev, crev) if r]
        run = st.latest_run(pid, mrev, crev) if (mrev and crev) else None
        if run:
            scopes.append(("run", run["id"]))
        b, ifc_store = _bundle(st, f"store/project/{pid}", pid, scopes)
        if run:
            gids = {e["global_id"] for e in st.elements(mrev)}
            keys = {c["key"] for c in st.calcs(crev)}
            b.links = ifc_store.apply_decisions(st, pid, b.links, gids, keys)
        return b
    scopes = [("revision", heads[k]) for k in ("set", "records", "connections") if k in heads]
    return _bundle(st, f"store/set/{proj['slug']}", pid, scopes)[0]


def revision_bundle(st: Store, rid: int):
    pid = st.revision(rid)["project_id"]
    return _bundle(st, f"store/revision/{rid}", pid, [("revision", rid)])[0]


def run_bundle(st: Store, run_id: int):
    run = st.db.execute("SELECT project_id FROM mapping_run WHERE id=?", (run_id,)).fetchone()
    if not run:
        raise KeyError(run_id)
    return _bundle(st, f"store/run/{run_id}", run["project_id"], [("run", run_id)])[0]
