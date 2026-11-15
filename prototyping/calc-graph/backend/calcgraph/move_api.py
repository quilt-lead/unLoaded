"""Synthetic v2 API: move a column, health meter, redo calcs, registry element pages, original
documents with highlights, construction platforms (live when configured, else mock), ETABS (mock). Mounted from api.py
with one include line. Every route is read-only on the source data except /apply, /rerun and the
two /revisions/{model,calc}/restore routes (undo / redo), which write NEW revisions (the revision
store and <store>/calc_revisions, both under store_root.py's CALCGRAPH_STORE) and never overwrite or delete.

All routes are under /api/v2. Route list + response shapes: docs/2026-11-14-move-a-column-notes.md.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
import threading
import time

import pymupdf
from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, Field

from . import move_impact, recalc
from .move_model import Move  # noqa: F401 - re-exported: move_api.Move is the name callers use
from .store_root import derived_for

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
V2 = os.path.join(ROOT, "data", "synthetic_v2")
DOCS = {"calcs": "calc_package.pdf", "drawings": "drawings.pdf", "specs": "specs.pdf"}
router = APIRouter(prefix="/api/v2", tags=["synthetic-v2"])
_LOCK = threading.Lock()
_CACHE: dict = {}


def _safe(o):
    """JSON-safe (numpy scalars from the analysis -> Python)."""
    from synth.v2.generate import _clean
    return _clean(o)


def _design() -> dict:
    p = os.path.join(V2, "design.json")
    if not os.path.exists(p):
        raise HTTPException(404, "no synthetic v2 design yet - run: uv run python -m synth.v2.generate")
    m = os.stat(p).st_mtime_ns
    if _CACHE.get("design_mtime") != m:
        raw = open(p, "rb").read()
        _CACHE.clear()
        _CACHE["design"] = json.loads(raw)
        _CACHE["design_sha"] = hashlib.sha256(raw).hexdigest()   # of the exact bytes parsed (heat cache key)
        _CACHE["design_mtime"] = m
    return _CACHE["design"]


def _adapters():
    """The platform adapters (platforms.get_adapters: live when selected and signed in, else mock),
    cached while the design AND platforms.adapters_fingerprint() (env selection + stored credentials /
    tokens) are unchanged - so a login made after the server started is picked up on the next call.
    Everything derived from the adapters is cached under the same entry and goes with it."""
    from .platforms import adapters_fingerprint, get_adapters
    d = _design()
    fp = adapters_fingerprint()
    hit = _CACHE.get("adapters")
    if hit is None or hit["fp"] != fp:
        hit = _CACHE["adapters"] = {"fp": fp, "list": get_adapters(d), "derived": {}}
    return hit["list"]


def _adapters_derived(name: str, build):
    """A value computed from the current adapter list, dropped whenever the list is rebuilt."""
    _adapters()
    der = _CACHE["adapters"]["derived"]
    if name not in der:
        der[name] = build(_CACHE["adapters"]["list"])
    return der[name]


def _doc_words(doc: str, page: int) -> list[tuple]:
    """The words of one page of an original document (DOCS), cached with the design; for occurrence
    labels (registry_view: a schedule row's row header)."""
    words = _CACHE.setdefault("doc_words", {})
    k = (doc, page)
    if k not in words:
        with pymupdf.open(os.path.join(V2, DOCS[doc])) as pdf:
            words[k] = [tuple(w[:5]) for w in pdf[page - 1].get_text("words")]
    return words[k]


def _registry():
    from .registry_view import RegistryView
    d = _design()
    if "registry_view" not in _CACHE:
        _CACHE["registry_view"] = RegistryView(d, words=_doc_words)
    return _CACHE["registry_view"]


def _status_fn(ads=None):
    try:
        from .platforms import construction_status
        ads = ads if ads is not None else _adapters()
        d = _design()
        return lambda eid: construction_status(eid, ads, d)
    except Exception:
        return None


def _adapters_as_of(as_of: str | None):
    """(adapters, as-of date) for an approval date: the ONE projection (platforms.get_adapters(as_of=...)),
    today's cached adapters when the date reads today's state."""
    from . import as_of as asof
    try:
        d_as_of = asof.parse(as_of)
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    return asof.adapters(_design(), d_as_of, _adapters), d_as_of


def _col(c: str) -> str:
    return c if c.startswith("COL-") else f"COL-{c}"


def _change(m: Move) -> dict:
    c = _col(m.column)[4:]
    return {"removed": [c]} if m.remove else {"moved": {c: [m.dx, m.dy]}}


# ------------------------------------------------------------------ model / registry
@router.get("/summary")
def summary():
    d = _design()
    from collections import Counter
    return {"building": d.get("building"), "elements": Counter(e["type"] for e in d["elements"]),
            "records": Counter(r["kind"] for r in d["records"]), "relations": Counter(r["kind"] for r in d["relations"]),
            "calcs": d.get("calcs"), "sections": d.get("sections"), "aisc_verification": d.get("aisc_verification"),
            "documents": {k: os.path.exists(os.path.join(V2, f)) for k, f in DOCS.items()},
            "occurrences": len(d.get("occurrences", []))}


@router.get("/design")
def design_file():
    _design()
    return FileResponse(os.path.join(V2, "design.json"), media_type="application/json", headers={"Cache-Control": "no-store"})


@router.get("/model.ifc")
def model_ifc():
    p = os.path.join(V2, "model.ifc")
    if not os.path.exists(p):
        raise HTTPException(404, "no model.ifc - run the generator")
    return FileResponse(p, media_type="application/x-step", filename="synthetic-v2-model.ifc", headers={"Cache-Control": "no-store"})


@router.get("/elements/{eid:path}")   # :path - registry ids contain "/" (SPEC:05 12 00/1.3.B, DET:4/S-502)
def element(eid: str):
    """Registry element page for ANY registry id (element, type, calc record, spec article SPEC:...,
    drawing detail DET:...): the entity, every relation in and out, the calc records that design it,
    and every occurrence - IFC GlobalId, drawings, specs, calcs, ETABS objects and construction-platform
    records (registry_view.RegistryView)."""
    v = _registry()
    if not v.resolve(eid):
        raise HTTPException(404, f"no element, type, record, spec article or detail {eid!r}")
    analysis, plat, errors = [], {}, []
    try:
        from .analysis import get_adapter
        if "etabs_occ" not in _CACHE:
            _CACHE["etabs_occ"] = get_adapter("etabs", _design()).occurrences()
        analysis = _CACHE["etabs_occ"]
    except Exception as e:   # surface, never hide
        errors.append({"ref": eid, "doc": "etabs", "how": "error", "error": f"{type(e).__name__}: {e}"})
    try:
        from .registry_view import platform_occurrences
        plat = _adapters_derived("platform_occurrences", platform_occurrences)
    except Exception as e:
        errors.append({"ref": eid, "doc": "platforms", "how": "error", "error": f"{type(e).__name__}: {e}"})
    out = v.view(eid, analysis, plat)
    out["occurrences"] += errors
    return JSONResponse(_safe(out))


@router.get("/records/{rid:path}")
def record(rid: str):
    d = _design()
    r = next((x for x in d["records"] if x["id"] == rid), None)
    if not r:
        raise HTTPException(404, f"no record {rid!r}")
    return {**r, "fed_by": r["inputs"], "feeds": [x["id"] for x in d["records"] if rid in x["inputs"]]}


# truth = source data (the generator); ingested / eval = derived outputs (scripts/evaluate_registry.py,
# store_root.derived_for), never written into the source dir
REGISTRY_FILES = {"truth": lambda: os.path.join(V2, "registry_truth.json"),
                  "ingested": lambda: derived_for(V2, "registry_ingested.json"),
                  "eval": lambda: derived_for(V2, "registry_eval.json")}


@router.get("/registry")
def registry():
    """Registry truth (generator) and, when built, the registry rebuilt from the documents."""
    return {k: os.path.exists(f()) for k, f in REGISTRY_FILES.items()}


@router.get("/registry/{which}")
def registry_file(which: str):
    f = REGISTRY_FILES.get(which)
    if not f or not os.path.exists(f()):
        raise HTTPException(404, f"registry {which} not built")
    return FileResponse(f(), media_type="application/json", headers={"Cache-Control": "no-store"})


# ------------------------------------------------------------------ move / impact / health
@router.post("/impact")
def impact(m: Move):
    """Stale calc records with reason chains, screened estimates (labelled), health meter,
    affected occurrences, construction status and the potential change order."""
    return JSONResponse(_safe(impact_result(m)))


def impact_result(m: Move) -> dict:
    """/impact's body as a dict, at the move's approval date (m.as_of; default today): health, construction
    status and the change order all read the same projected adapters. Also used by the inbox (inbox.py)."""
    from . import as_of as asof
    d = _design()
    ads, d_as_of = _adapters_as_of(m.as_of)
    res = _impact(d, m, platform_status=_status_fn(ads))
    res["change_order"] = _change_order(d, res, ads)
    res["as_of"] = asof.describe(ads, d_as_of)
    return res


def _impact(d: dict, m: Move, platform_status=None) -> dict:
    """move_impact.impact for a request: 404 only when the column does not exist; any other failure
    propagates as itself (a 500 with its real error), never disguised as "not found"."""
    try:
        return move_impact.impact(d, _col(m.column), m.dx, m.dy, m.remove, platform_status=platform_status)
    except move_impact.UnknownColumn:
        raise HTTPException(404, f"no column {m.column!r}") from None


def _change_order(d: dict, res: dict, adapters=None) -> dict:
    """The change-order estimate for an impact result, over `adapters` (default: today's)."""
    try:
        from .platforms import estimate
    except Exception as e:
        return {"error": f"platform adapters unavailable: {e}"}
    imp = _change_order_input(d, res)
    try:
        return estimate(imp, adapters if adapters is not None else _adapters(), d)
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}", "input": imp}


def _change_order_input(d: dict, res: dict) -> dict:
    """The estimator's input (change_order.estimate `impact`) built from an impact result."""
    els = {e["id"]: e for e in d["elements"]}
    resized, conns, ftgs = [], [], []
    for k, v in res["estimates"].items():
        if (v.get("uc_new") or 0) <= 1.0:
            continue
        if v.get("size_est") and k in els:
            resized.append({"id": k, "old_size": els[k]["size"], "new_size": v["size_est"], "length_ft": els[k].get("span_ft")})
        if k.startswith("CX-"):
            conns.append({"id": k, "old_type": els.get(k, {}).get("conn_type"), "new_type": v.get("next_typical") or "special"})
        if k.startswith("F-"):
            ftgs.append({"id": k, "old_B_ft": v["B_old"], "new_B_ft": max(v["B_req"], v["B_old"]),
                         "old_h_in": els[k]["h_in"], "new_h_in": els[k]["h_in"]})
    touched = sorted({e for s in res["stale"] for e in d_rec(d, s["record"])["elements"]} | {res["column"]})
    sheets = sorted({o.get("sheet") for e in touched for o in res["occurrences"].get(e, []) if o.get("doc") == "drawings" and o.get("sheet")})
    reg = _registry()   # the ONE derivation of what governs an element (registry_view.governing_specs)
    arts: dict[str, set] = {}                 # article -> the registry links (via) that bring it in
    links: dict[str, dict[str, set]] = {}     # link -> the touched elements it reaches and the articles it brings
    for e in touched:
        for a, via in reg.governing_specs(e).items():
            arts.setdefault(a, set()).update(via)
            for v in via:
                ln = links.setdefault(v, {"elements": set(), "articles": set()})
                ln["elements"].add(e)
                ln["articles"].add(a)
    return {"elements": touched, "resized": resized, "connections_changed": conns, "footings_changed": ftgs,
            "records": [s["record"] for s in res["stale"] if s["screened"]], "sheets": sheets,
            "spec_articles": sorted(arts), "spec_via": {a: sorted(v) for a, v in sorted(arts.items())},
            "spec_links": {v: {"elements": sorted(x["elements"]), "articles": sorted(x["articles"])} for v, x in sorted(links.items())}}


def d_rec(d: dict, rid: str) -> dict:
    if "rec_index" not in _CACHE:
        _CACHE["rec_index"] = {r["id"]: r for r in d["records"]}
    return _CACHE["rec_index"].get(rid, {"elements": []})


@router.get("/health")
def health(probe: float = 2.0):
    """Health meter of every column for a +/- probe move (heat view of 'how hard to move').
    Persisted to data/cache/heat/ keyed by a hash of every input heat() reads (heat_cache), so a
    restart serves it instantly and only a real input change recomputes. Headers say which:
    X-Heat-Cache (hit | computed), X-Heat-Key, X-Heat-Computed-At (ET), X-Heat-Seconds."""
    heat, how, meta = _heat(probe)
    return JSONResponse(heat, headers={"X-Heat-Cache": how, "X-Heat-Key": meta["key"],
                                       "X-Heat-Computed-At": meta["computed_at"], "X-Heat-Seconds": str(meta["seconds"]),
                                       "Cache-Control": "no-store"})


def _heat(probe: float):
    from . import heat_cache
    d = _design()
    sha = _CACHE["design_sha"]
    status = _status_fn()
    inp = heat_cache.inputs(sha, d, probe, status)
    return heat_cache.get_or_compute(inp, lambda: _safe(move_impact.heat(d, probe, platform_status=status)))


def _warm_heat() -> None:
    """At server start, make sure the default heat view (probe 2 ft) is on disk: a no-op when the inputs
    are unchanged, else the recompute starts now instead of when someone opens the page."""
    log = logging.getLogger("calcgraph.move_api")
    try:
        _, how, meta = _heat(2.0)
        log.warning("heat view probe=2: %s (key %s, computed %s in %s s)", how, meta["key"], meta["computed_at"], meta["seconds"])
    except HTTPException:
        pass                       # no design yet
    except Exception:              # noqa: BLE001 - a warm-up failure must not stop the server; the route will raise it
        log.exception("heat view warm-up failed")


_WARM_STARTED = threading.Event()


def _warm_heat_bg() -> None:
    if _WARM_STARTED.is_set():      # the startup hook can fire more than once (router + app); warm once
        return
    _WARM_STARTED.set()
    threading.Thread(target=_warm_heat, name="heat-warm", daemon=True).start()


router.add_event_handler("startup", _warm_heat_bg)


class RerunProgress(BaseModel):
    """Where the re-run in flight is (one at a time: /rerun holds the move lock)."""
    running: bool = Field(description="a /rerun is in progress")
    column: str | None = Field(default=None, description="the column of the move being re-run")
    stage: str | None = Field(default=None, description="design | math | layout | package_sheets | done | failed")
    stage_label: str | None = Field(default=None, description="what the stage is doing, for the UI")
    done: int = Field(default=0, description="units of the stage finished (layout: sheet chunks laid out, incl. cached)")
    total: int = Field(default=0, description="units in the stage")
    seconds: float = Field(default=0.0, description="seconds since the re-run started")
    rev_id: str | None = Field(default=None, description="the calc revision written, once done")


STAGE_LABEL = {"design": "re-running the design", "math": "printing the math (handcalcs + KaTeX)",
               "layout": "laying out the re-run sheets", "package_sheets": "writing the package-style revised sheets",
               "done": "done", "failed": "failed"}
_PROGRESS: dict = {"running": False}
_PROGRESS_LOCK = threading.Lock()


def _set_progress(**kw) -> None:
    with _PROGRESS_LOCK:
        _PROGRESS.update(kw)
        if "stage" in kw:
            _PROGRESS["stage_label"] = STAGE_LABEL.get(kw["stage"], kw["stage"])
        if _PROGRESS.get("t0"):
            _PROGRESS["seconds"] = round(time.time() - _PROGRESS["t0"], 1)


@router.post("/rerun")
def rerun(m: Move):
    """Redo calcs directly: re-run the stale records (or m.records) with the v2 design code; old
    vs new per record in load-path order; regenerated calc pages (package style + handcalcs re-run
    sheets) as a NEW calc revision. Progress while it runs: GET /api/v2/rerun/progress."""
    d = _design()
    recs = m.records
    if recs is None:
        res = _impact(d, m)
        recs = [s["record"] for s in res["stale"]]
    with _LOCK:
        with _PROGRESS_LOCK:
            _PROGRESS.clear()
            _PROGRESS.update({"running": True, "column": _col(m.column), "t0": time.time(), "done": 0, "total": 0, "rev_id": None})
        try:
            out = recalc.rerun(d, _change(m), recs, progress=lambda st, dn, tot: _set_progress(stage=st, done=dn, total=tot))
        except Exception:
            _set_progress(stage="failed", running=False)
            raise
        _set_progress(stage="done", running=False, rev_id=out["rev_id"])
        return JSONResponse(_safe(out))


@router.get("/rerun/progress", response_model=RerunProgress)
def rerun_progress() -> RerunProgress:
    """The /rerun in flight: stage, units done of total, seconds so far (the last re-run's final
    state when none is running). Read only."""
    with _PROGRESS_LOCK:
        p = dict(_PROGRESS)
    if p.get("running") and p.get("t0"):
        p["seconds"] = round(time.time() - p["t0"], 1)
    p.pop("t0", None)
    return RerunProgress(**p)


@router.get("/revisions")
def revisions():
    """calc_revisions (recalc.list_revisions) and the Synthetic v2 MODEL revisions split by design, newest
    first: model_revisions = the current design's history (the base revision of the current model.ifc and
    every revision descended from it), earlier_model_revisions = revisions of earlier designs (their
    root is another base), base_revision = the current base (None until the first apply ingests it)."""
    cur, earlier, base = _model_revs_by_design()
    return {"calc_revisions": recalc.list_revisions(), "model_revisions": cur, "earlier_model_revisions": earlier,
            "base_revision": base}


@router.get("/revisions/{rev_id}")
def revision(rev_id: str):
    p = os.path.join(recalc.revision_dir(rev_id), "revision.json")
    if not os.path.exists(p):
        raise HTTPException(404)
    return FileResponse(p, media_type="application/json")


@router.get("/revisions/{rev_id}/{name}.pdf")
def revision_pdf(rev_id: str, name: str):
    """calc_revision.pdf (revised sheets in the package style) or rerun_sheets.pdf (handcalcs)."""
    if name not in ("calc_revision", "rerun_sheets"):
        raise HTTPException(404)
    p = os.path.join(recalc.revision_dir(rev_id), f"{name}.pdf")
    if not os.path.exists(p):
        raise HTTPException(404, f"no {name}.pdf for this revision")
    return FileResponse(p, media_type="application/pdf")


def _store():
    from .api import st
    return st


def _model_revs_by_design() -> tuple[list[dict], list[dict], int | None]:
    """(current design's model revisions, earlier designs' model revisions, current base id), each list
    newest first. A revision belongs to the design of the root its parent chain ends at; the current
    design's roots are the base revisions holding the current model.ifc's bytes (never ingested here)."""
    st = _store()
    pid = _v2_project(st)
    models = [r for r in st.revisions(pid) if r["kind"] == "model"]
    parent = {r["id"]: r["parent_id"] for r in models}

    def root(i: int) -> int:
        seen = set()
        while parent.get(i) is not None and i not in seen:
            seen.add(i)
            i = parent[i]
        return i

    base = _find_base_rev(st, pid)
    base_sha = next((r["sha256"] for r in models if r["id"] == base), None)
    # every root holding the current model.ifc's bytes (the generator re-run unchanged makes a second one)
    roots = {r["id"] for r in models if r["parent_id"] is None and base_sha and r["sha256"] == base_sha}
    newest = sorted(models, key=lambda r: r["id"], reverse=True)
    cur = [r for r in newest if root(r["id"]) in roots]
    return cur, [r for r in newest if root(r["id"]) not in roots], base


def _find_base_rev(st, pid: int) -> int | None:
    """The model revision holding the current base design (data/synthetic_v2/model.ifc), by content hash;
    None when the store has no copy yet."""
    from .store import sha256_file
    p = os.path.join(V2, "model.ifc")
    if not os.path.exists(p):
        return None
    row = st.db.execute("SELECT MIN(id) FROM revision WHERE project_id=? AND kind='model' AND sha256=?",
                        (pid, sha256_file(p))).fetchone()
    return row[0] if row and row[0] else None


def _v2_project(st) -> int:
    row = st.db.execute("SELECT id FROM project WHERE name = ?", ("Synthetic v2",)).fetchone()
    if row:
        return row[0]
    return _new_project(st)


def _new_project(st) -> int:
    from .store import now_et
    cur = st.db.execute("INSERT INTO project(name, created_at) VALUES (?,?)", ("Synthetic v2", now_et()))
    st.commit()
    return cur.lastrowid


def _base_rev(st, pid: int) -> int:
    """The model revision holding the CURRENT base design (data/synthetic_v2/model.ifc, which every
    move is computed from), found by content hash; ingested as a new root revision when the store
    has no copy (first apply, or the generator was re-run)."""
    from . import pipeline
    found = _find_base_rev(st, pid)
    if found is not None:
        return found
    return pipeline.ingest_model(st, pid, os.path.join(V2, "model.ifc"), "model.ifc", "Synthetic v2 - base design", parent=None)


@router.post("/apply")
def apply(m: Move):
    """Apply the move as a NEW model revision in the revision store (minimum-change re-design,
    IFC written and ingested through the production pipeline) and return the element diff.

    Every move is computed from the base design, never from the head, so the new revision's parent
    is the BASE revision and diff = base -> revision is exactly this move. previous_head = the head
    it replaces (what undo restores)."""
    from synth.v2 import ifc_v2
    from synth.v2.generate import build
    from . import pipeline
    d = _design()
    st = _store()
    with _LOCK:
        pid = _v2_project(st)
        base = _base_rev(st, pid)
        prev = st.project(pid)["head_model_rev"]
        L = recalc.layout_from_change(_change(m))
        dd, exp = build(L, keep={e["id"]: e for e in d["elements"]})
        label = m.label or (f"Remove {m.column}" if m.remove else f"Move {m.column} ({m.dx:+g}, {m.dy:+g}) ft")
        fd, path = tempfile.mkstemp(suffix=".ifc")
        os.close(fd)
        try:
            ifc_v2.write(exp, path, dd, label=label)
            rid = pipeline.ingest_model(st, pid, path, f"{label}.ifc", label, parent=base)
        finally:
            os.unlink(path)
        diff = st.compare_models(base, rid)
    return _safe({"project": pid, "revision": rid, "parent": base, "previous_head": prev, "label": label, "diff": diff})


@router.get("/compare")
def compare(a: int, b: int, engine: str = "store"):
    """Element diff of two model revisions: engine=store (key join over the ingested elements) or
    engine=ifcdiff (ifcdiff on the two revision IFCs, analytical items included; the store diff is
    returned alongside under "store")."""
    if engine == "ifcdiff":
        from . import ifc_diff
        return _safe(ifc_diff.diff_revisions(_store(), a, b))
    if engine != "store":
        raise HTTPException(400, "engine must be 'store' or 'ifcdiff'")
    return _store().compare_models(a, b)


class ModelRestore(BaseModel):
    target: int                 # model revision whose IFC becomes the new head
    of: int                     # the applied revision being undone / redone
    verb: str                   # "undo" | "redo"
    expect_head: int            # the head the client last saw; refused (409) if it moved since


@router.post("/revisions/model/restore")
def restore_model(r: ModelRestore):
    """Undo / redo of /apply without deleting history: ingests model revision `target`'s own IFC
    (the store's content-addressed blob) through the production pipeline as a NEW head revision,
    labelled with what it undoes or redoes. Same parent rule as /apply - parent = the revision its
    content was derived from, here `target` itself (so parent -> revision diffs empty: it is a copy).
    Response: /apply's shape with parent = target, previous_head = the head it superseded and
    diff = previous_head -> new revision (what the undo / redo changed), plus {restored, of, verb}."""
    from . import pipeline
    if r.verb not in ("undo", "redo"):
        raise HTTPException(400, "verb must be 'undo' or 'redo'")
    st = _store()
    with _LOCK:
        pid = _v2_project(st)
        head = st.project(pid)["head_model_rev"]
        if head != r.expect_head:
            raise HTTPException(409, f"the model head is revision {head}, not {r.expect_head}: another apply or undo "
                                     "happened since. Reload the page to pick up the current history.")
        try:
            t = st.revision(r.target)
            st.revision(r.of)
        except KeyError as e:
            raise HTTPException(404, f"no model revision {e.args[0]}")
        if t["project_id"] != pid or t["kind"] != "model":
            raise HTTPException(404, f"revision {r.target} is not a Synthetic v2 model revision")
        if r.target == head:
            raise HTTPException(409, f"revision {r.target} is already the head")
        label = f"{'Undo' if r.verb == 'undo' else 'Redo'} R{r.of}: restore R{r.target}"
        rid = pipeline.ingest_model(st, pid, st.blob_path(r.target), t["source_name"], label, parent=r.target)
        diff = st.compare_models(head, rid)
    return _safe({"project": pid, "revision": rid, "parent": r.target, "previous_head": head, "label": label, "diff": diff,
                  "restored": r.target, "of": r.of, "verb": r.verb})


class CalcRestore(BaseModel):
    target: str | None          # calc revision whose content is restored; None = the original package
    reverts: str                # the calc revision this one supersedes (the current one)
    of: str                     # the re-run being undone / redone
    verb: str                   # "undo" | "redo"


@router.post("/revisions/calc/restore")
def restore_calc(r: CalcRestore):
    """Undo / redo of /rerun without deleting history: a NEW calc revision carrying `target`'s
    results and pages (or none, for the original package) - see recalc.restore."""
    with _LOCK:
        try:
            return JSONResponse(_safe(recalc.restore(r.target, r.reverts, r.of, r.verb)))
        except KeyError as e:
            raise HTTPException(404, f"no calc revision {e.args[0]}")
        except ValueError as e:
            raise HTTPException(400, str(e))


# ------------------------------------------------------------------ documents
_DOCS_OPEN: dict[str, pymupdf.Document] = {}


def _local_only(request: Request) -> None:
    from .access import require_local
    require_local(request, "source documents")


@router.get("/docs/{doc}/file")
def doc_file(doc: str):
    f = DOCS.get(doc)
    if not f or not os.path.exists(os.path.join(V2, f)):
        raise HTTPException(404, f"no {doc} document yet")
    return FileResponse(os.path.join(V2, f), media_type="application/pdf")


@router.get("/revisions/{rev_id}/{name}/pages/{n}.png")
def revision_page(rev_id: str, name: str, n: int, hl: str = "", w: int = 1400):
    if name not in ("calc_revision", "rerun_sheets"):
        raise HTTPException(404)
    p = os.path.join(recalc.revision_dir(rev_id), f"{name}.pdf")
    if not os.path.exists(p):
        raise HTTPException(404, f"no {name}.pdf for this revision")
    return _render(p, n, hl, w)


@router.get("/docs/{doc}/pages/{n}.png")
def doc_page(doc: str, n: int, hl: str = "", w: int = 1400):
    """Page n (1-based) of a v2 document; hl = 'x0,y0,x1,y1;...' PDF points drawn as highlights."""
    f = DOCS.get(doc)
    p = os.path.join(V2, f) if f else ""
    if not f or not os.path.exists(p):
        raise HTTPException(404, f"no {doc} document yet")
    return _render(p, n, hl, w)


def _render(p: str, n: int, hl: str, w: int) -> Response:
    with _LOCK:
        dd = pymupdf.open(p)
        if not 1 <= n <= len(dd):
            raise HTTPException(404, "no such page")
        page = dd[n - 1]
        for part in filter(None, hl.split(";")):
            try:
                x0, y0, x1, y1 = (float(v) for v in part.split(","))
            except ValueError:
                raise HTTPException(400, f"bad highlight {part!r}")
            page.draw_rect(pymupdf.Rect(x0 - 2, y0 - 2, x1 + 2, y1 + 2), color=(0.9, 0.55, 0), fill=(1, 0.8, 0),
                           fill_opacity=0.35, width=1.5)
        zoom = max(0.3, min(4.0, max(64, min(w, 4096)) / page.rect.width))
        png = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False).tobytes("png")
    return Response(png, media_type="image/png", headers={"Cache-Control": "no-store"})


# ------------------------------------------------------------------ construction platforms (live or mock)
@router.get("/platforms")
def platforms():
    """Each platform with where its records come from: source live | mock, the selected mode and, when
    live was selected but could not be used, fallback_reason."""
    out = []
    for a in _adapters():
        dsc = a.describe()
        out.append({"name": a.name, "label": a.label, "capabilities": sorted(a.capabilities), "counts": a.counts(),
                    "doc_urls": a.doc_urls, "mock": dsc.get("synthetic", True), "source": dsc.get("source", "mock"),
                    "selected": dsc.get("selected", "mock"), "fallback_reason": dsc.get("fallback_reason")})
    return out


@router.post("/platforms/refresh")
def platforms_refresh():
    """Drop the cached adapters (and everything derived from them) so the next call rebuilds them:
    re-reads env selection, credentials and tokens, and re-fetches live records."""
    _CACHE.pop("adapters", None)
    return platforms()


def _platform(name: str):
    a = next((x for x in _adapters() if x.name == name), None)
    if not a:
        raise HTTPException(404, f"no platform {name!r}")
    return a


@router.get("/platforms/{name}/{record_type}")
def platform_records(name: str, record_type: str, raw: bool = False):
    a = _platform(name)
    if record_type not in a.capabilities:
        raise HTTPException(404, f"{name} has no {record_type}")
    return a.list_raw(record_type) if raw else [r.to_dict(include_raw=False) for r in a.list(record_type)]


def _record_out(a, record_type: str, r) -> dict:
    return {**r.to_dict(include_raw=True), "record_type": record_type, "platform_label": a.label,
            "source": r.fields.get("source", "mock"), "source_label": r.fields.get("source_label")}


@router.get("/platforms/{name}/{record_type}/{rid:path}")
def platform_record(name: str, record_type: str, rid: str):
    """One platform record by the platform's id or the canonical ref: normalized fields + the
    platform-shaped raw object + where it came from (source live | mock)."""
    a = _platform(name)
    if record_type not in a.capabilities:
        raise HTTPException(404, f"{name} has no {record_type}")
    r = a.get_normalized(record_type, rid)
    if r is None:
        raise HTTPException(404, f"no {record_type} {rid!r} in {name}")
    return _safe(_record_out(a, record_type, r))


@router.get("/platform-record")
def platform_record_by_link(url: str):
    """The platform record a link points at (any record's links.self, mock:// or a live API URL)."""
    for a in _adapters():
        for rt in sorted(a.capabilities):
            for r in a.list(rt):
                if r.links.get("self") == url:
                    return _safe(_record_out(a, rt, r))
    raise HTTPException(404, f"no platform record has the link {url!r}")


@router.get("/construction-status/{eid:path}")
def construction_status(eid: str, as_of: str | None = None):
    fn = _status_fn(_adapters_as_of(as_of)[0])
    if not fn:
        raise HTTPException(503, "platform adapters unavailable")
    return _safe(fn(eid))


@router.post("/change-order")
def change_order(m: Move):
    d = _design()
    res = _impact(d, m)
    return _safe(_change_order(d, res, _adapters_as_of(m.as_of)[0]))


# ------------------------------------------------------------------ analysis software (mock ETABS)
def _etabs():
    from .analysis import get_adapter
    return get_adapter("etabs", _design())


def _answered(payload, a):
    """Tag a response with the adapter that answered (mock vs Windows bridge)."""
    from .analysis import etabs_adapter_name
    info = {"adapter": etabs_adapter_name(), "adapter_name": getattr(a, "name", type(a).__name__),
            "mock": etabs_adapter_name() == "etabs"}
    if isinstance(payload, dict):
        return {**payload, "answered_by": info}
    return {"answered_by": info, "items": payload}


@router.get("/etabs/objects")
def etabs_objects(kind: str | None = None):
    a = _etabs()
    objs = [o.to_dict() for o in a.model_objects()]
    return _safe(_answered([o for o in objs if not kind or o["kind"] == kind], a))


@router.get("/etabs/model.e2k")
def etabs_e2k(column: str | None = None, dx: float = 0.0, dy: float = 0.0, remove: bool = False):
    a = _etabs()
    change = None
    if column:
        change = _change(Move(column=column, dx=dx, dy=dy, remove=remove))
    fd, path = tempfile.mkstemp(suffix=".e2k")
    os.close(fd)
    a.export_model(path, change=change)
    data = open(path, "rb").read()
    os.unlink(path)
    return Response(data, media_type="text/plain", headers={"Content-Disposition": 'attachment; filename="calc-graph-v2.e2k"',
                                                            "X-Note": "written by calc-graph; ETABS did not open it",
                                                            "X-Answered-By": getattr(a, "name", type(a).__name__)})


@router.post("/etabs/send")
def etabs_send(m: Move):
    """Stage the move as an ETABS job. A move that changes nothing (no offset, not a removal) is refused:
    there is nothing to send."""
    if not m.remove and m.dx == 0 and m.dy == 0:
        raise HTTPException(400, "no move to send: give an offset (dx / dy) or remove=true")
    a = _etabs()
    return _safe(_answered(a.send_change(_design(), _change(m)), a))


@router.post("/etabs/pull/{job_id}")
def etabs_pull(job_id: str):
    a = _etabs()
    return _safe(_answered(a.pull_results(job_id), a))


@router.get("/etabs/runs")
def etabs_runs(design: str = "current"):
    """Saved REAL ETABS runs of a design ("current" = model.e2k, or a design scenario id such as ORIG):
    `runs` = runs of exactly this design's e2k (sha1 match) with what each found, `stale` = runs of that
    design whose e2k has changed since (etabs_runs.for_design). Read only; numbers from the saved fixtures."""
    from . import etabs_runs as er
    if design != er.CURRENT and not any(s["id"] == design for s in er.design_scenarios()):
        raise HTTPException(404, f"no design {design!r} (use 'current' or a design scenario id)")
    return er.for_design(design)


@router.get("/etabs/runs/{run_id}")
def etabs_run(run_id: str):
    """One saved real ETABS run in full: modes, base shear, line forces, drift, and every per-member ETABS vs
    PyNite row with the agreement summary."""
    from . import etabs_runs as er
    r = er.get(run_id)
    if r is None:
        raise HTTPException(404, f"no saved ETABS run {run_id!r}")
    return {**r, "label": er.label(r), "finding": er.finding(r)}


# ------------------------------------------------------------------ ground truth / evaluation
@router.get("/scenarios")
def scenarios():
    p = os.path.join(V2, "answer_key.json")
    if not os.path.exists(p):
        raise HTTPException(404, "no answer key - run: uv run python -m synth.v2.scenarios")
    k = json.load(open(p))
    return _design_scenarios(k) + [{x: s[x] for x in ("id", "label", "kind", "column", "dx", "dy", "difficulty", "difficulty_why")} |
                                   {"stale": len(s["changed_records"]), "resized": len(s["resized"])} for s in k["scenarios"]]


def _design_scenarios(k: dict) -> list[dict]:
    """The answer key's design scenarios (kind "design": another lateral layout, not a move - column None),
    each with its frames, the design's own drift ratios and its saved real ETABS runs (etabs_runs)."""
    from . import etabs_runs as er
    out = []
    for s in k.get("design_scenarios", []):
        et = er.for_design(s["id"])
        out.append({"id": s["id"], "label": s["label"], "kind": "design", "column": None, "dx": 0.0, "dy": 0.0,
                    "difficulty": None, "difficulty_why": None, "stale": 0, "resized": 0,
                    "lateral": s.get("lateral", {}).get("name"), "frames": s.get("frames", {}),
                    "design_drift": s.get("drift", {}), "real_etabs": et["runs"], "stale_etabs": et["stale"]})
    return out


@router.get("/eval")
def evaluation():
    p = derived_for(V2, "move_eval.json")   # scripts/evaluate_move.py (derived output, not source data)
    if not os.path.exists(p):
        raise HTTPException(404, "run: uv run python scripts/evaluate_move.py")
    return json.load(open(p))["summary"]
