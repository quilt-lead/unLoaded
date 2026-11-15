"""The one revision store, for both paths: opening it, writing every snapshot's schema facts,
recording drawing-set builds as revisions, and reading schema Bundles back.

IFC path      pipeline.ingest_model / ingest_calcs / remap write the native rows (store.py), then
              write_revision_facts / write_run_facts store that snapshot's schema facts.
Drawing sets  set_pipeline writes each output (graph.json, calc_records.json, connections.json,
              integrated.json, model.ifc) and calls record_set_output(): the output becomes a
              content-addressed artifact of a new revision (kind set / records / connections /
              integrated), its source PDFs become content-addressed documents, and its schema
              facts (calcgraph.schema adapters) are stored with their provenance. The API serves
              the existing responses from those artifacts. import_sets() brings in set outputs
              that were written outside the store (pre-F2 builds, scripts writing data/sets
              directly): any file whose sha256 differs from its head artifact becomes a new revision.

Producer records: every snapshot built through here records the code that built it as
module@<sha1 of the module source>[:12] (plus the rule's declared confidence where the module
declares none per fact). Imported outputs record no producer: their versions are unknown.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import os
import threading
from collections import Counter

from .store import SET_KINDS, Store, now_et, sha256_file

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# drawing-set revision kind -> the output files it owns (first = the primary artifact)
SET_FILES = {"set": ["graph.json", "meta.json", "model.ifc"], "records": ["calc_records.json"],
             "connections": ["connections.json"], "integrated": ["integrated.json"]}
SET_PRODUCERS = {"set": ["drawing_ingest", "drawing_loadpath", "calcpkg_ingest", "set_graph", "registry_ingest"],
                 "records": ["calc_records"], "connections": ["connections"], "integrated": ["set_integrate"]}
DOC_KIND = {"Drawing set": "drawing", "Calc package": "calc"}

_STORES: dict[str, Store] = {}
_LOCK = threading.RLock()


from .store_root import store_dir  # noqa: E402,F401 - THE store root (CALCGRAPH_STORE), re-exported


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


# ---------------- drawing-set path ----------------
def _set_facts(kind: str, set_dir: str, sid: str):
    """Schema facts of one drawing-set output, via the F1 adapters. Returns (facts, calibrations, tally)."""
    from .schema.adapters import calc_records, connections, drawing_set, ifc_model
    if kind == "set":
        b, t = drawing_set.convert(set_dir)
        facts, cals = _facts_of(b), b.calibrations
        mp = os.path.join(set_dir, "model.ifc")
        if os.path.exists(mp):
            g = json.load(open(os.path.join(set_dir, "graph.json")))
            b2, t2 = ifc_model.convert(mp, sid, producer=(g.get("model") or {}).get("producer"))
            facts += _facts_of(b2)
            t.notes.append(f"model.ifc: converted {dict(t2.converted)}, rejected "
                           f"{ {k: sum(v.values()) for k, v in t2.rejected.items()} }")
        return facts, cals, t
    if kind == "records":
        b, t = calc_records.convert(set_dir)
    elif kind == "connections":
        b, t = connections.convert(set_dir)
    else:
        return [], [], None
    return _facts_of(b), b.calibrations, t


def _stamp_producer(facts: list[tuple[str, object]], prod: dict) -> list[tuple[str, object]]:
    """Facts whose engine / rule_version the output did not carry get them from the producer record
    of the build that made them (the module that ran, by source hash) - no longer adapter-supplied."""
    out = []
    for coll, f in facts:
        p = f.provenance
        mod = p.engine.split(" ")[0].split("@")[0]
        rec = prod.get(mod)
        if rec and ("engine" in p.adapter_supplied or "rule_version" in p.adapter_supplied):
            upd = {"adapter_supplied": [x for x in p.adapter_supplied if x not in ("engine", "rule_version")]}
            if "engine" in p.adapter_supplied:
                upd["engine"] = rec["engine"]
            if "rule_version" in p.adapter_supplied:
                upd["rule_version"] = rec["version"]
            f = f.model_copy(update={"provenance": p.model_copy(update=upd)})
        out.append((coll, f))
    return out


def record_set_output(st: Store, sid: str, kind: str, set_dir: str, built: bool = True, label: str | None = None) -> int:
    """Record the current files of one drawing-set output as a new revision. built=True: this
    process just built them (producer versions recorded); False: imported from disk."""
    if kind not in SET_KINDS:
        raise ValueError(kind)
    meta = json.load(open(os.path.join(set_dir, "meta.json")))
    with _LOCK:
        pid = st.ensure_set_project(sid, meta.get("name") or sid)
        docs = {}
        for key, d in meta["docs"].items():
            if os.path.exists(d["path"]):
                sha = st.put_document(d["path"], DOC_KIND.get(d.get("role"), "drawing"), d["name"], d.get("pages"),
                                      d.get("role", ""))
                docs[key] = (sha, d.get("role", ""))
        prod = producer(*SET_PRODUCERS[kind]) if built else {}
        facts, cals, t = _set_facts(kind, set_dir, sid)
        if t is not None:
            facts = _dedupe(_stamp_producer(facts, prod) if prod else facts, t)
        primary = os.path.join(set_dir, SET_FILES[kind][0])
        rmeta = {"source_name": SET_FILES[kind][0], "set_dir": os.path.abspath(set_dir),
                 "imported": None if built else now_et(),
                 "schema": ({k: v for k, v in t.summary().items() if k != "examples"} if t else None)}
        if os.path.exists(primary) and SET_FILES[kind][0].endswith(".json"):
            head = json.load(open(primary))
            rmeta["output_built_at"] = head.get("built_at")
        rid = st.add_set_revision(pid, kind, label or (f"{kind} build" if built else f"{kind} imported from disk"),
                                  docs, rmeta, prod, created_by="build" if built else "import")
        for name in SET_FILES[kind]:
            p = os.path.join(set_dir, name)
            if os.path.exists(p):
                st.put_artifact(rid, name, open(p, "rb").read())
        if facts:
            st.put_facts("revision", rid, facts)
        else:
            st.db.execute("UPDATE revision SET facts_at=? WHERE id=?", (now_et(), rid))
        if cals:
            st.put_calibrations(rid, cals)
        st.set_head(pid, kind, rid)
        st.commit()
        return rid


def import_sets(st: Store, sets_dir: str) -> int:
    """Sync data/sets/<sid>/ outputs into the store: a file that differs from its head artifact
    (or has none) becomes a new imported revision. Returns the number of revisions written."""
    if not os.path.isdir(sets_dir):
        return 0
    return sum(import_sets_one(st, sets_dir, sid) for sid in sorted(os.listdir(sets_dir)))


def import_sets_one(st: Store, sets_dir: str, sid: str) -> int:
    d = os.path.join(sets_dir, sid)
    if not os.path.exists(os.path.join(d, "meta.json")):
        return 0
    n = 0
    with _LOCK:
        p = st.set_project(sid)
        for kind in SET_KINDS:
            files = [f for f in SET_FILES[kind] if os.path.exists(os.path.join(d, f))]
            if not files:
                continue
            head = st.head(p["id"], kind) if p else None
            if head and all((st.artifact(head, f) or {}).get("sha256") == _file_sha(os.path.join(d, f)) for f in files):
                continue
            record_set_output(st, sid, kind, d, built=False)
            p = st.set_project(sid)
            n += 1
    return n


_SHA_CACHE: dict[str, tuple[float, int, str]] = {}


def _file_sha(path: str) -> str:
    """sha256 of a working-copy file, cached on (mtime, size) so a sync check costs a stat."""
    s = os.stat(path)
    c = _SHA_CACHE.get(path)
    if c and c[0] == s.st_mtime and c[1] == s.st_size:
        return c[2]
    sha = sha256_file(path)
    _SHA_CACHE[path] = (s.st_mtime, s.st_size, sha)
    return sha


def set_head_artifact(st: Store, sid: str, name: str) -> dict | None:
    p = st.set_project(sid)
    if not p:
        return None
    kind = next(k for k, files in SET_FILES.items() if name in files)
    rid = st.head(p["id"], kind)
    return st.artifact(rid, name) if rid else None


def set_load(st: Store, sid: str, name: str):
    a = set_head_artifact(st, sid, name)
    return json.load(open(a["path"])) if a else None


def list_sets(st: Store) -> list[dict]:
    out = []
    for r in st.db.execute("SELECT slug FROM project WHERE kind='drawing-set' ORDER BY slug").fetchall():
        m = set_load(st, r["slug"], "meta.json")
        if m:
            out.append({"id": r["slug"], "name": m["name"],
                        "docs": {k: {"name": v["name"], "role": v["role"]} for k, v in m["docs"].items()}})
    return out


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
