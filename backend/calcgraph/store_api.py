"""Schema-shaped endpoints over the revision store, alongside the v1 responses.

  GET /api/store/projects                       every project with its heads
  GET /api/store/projects/{pid}/revisions       every revision: documents, artifacts, producer, fact counts
  GET /api/store/projects/{pid}/bundle          schema Bundle of the head snapshots (IFC: decisions applied)
  GET /api/store/revisions/{rid}                one revision
  GET /api/store/revisions/{rid}/bundle         schema facts of one revision
  GET /api/store/runs/{run_id}/bundle           schema facts of one IFC mapping run (links, calc edges)
  GET /api/store/diff?a=&b=[&scope=revision|run] key join of two snapshots' facts on (collection, id)
  GET /api/store/documents/{sha256}             a content-addressed source document's metadata
Bundles validate against calcgraph.schema (src/types/schema.ts at the repo root).
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from . import revstore

router = APIRouter(prefix="/api/store", tags=["revision-store"])


def _st():
    return revstore.open_store()


def _json_bundle(b) -> Response:
    return Response(b.model_dump_json(), media_type="application/json", headers={"Cache-Control": "no-store"})


@router.get("/projects")
def projects():
    return _st().all_projects()


@router.get("/projects/{pid}/revisions")
def project_revisions(pid: int):
    st = _st()
    if not st.db.execute("SELECT 1 FROM project WHERE id=?", (pid,)).fetchone():
        raise HTTPException(404, f"project {pid} not found")
    runs = [dict(r) | {"facts": dict(st.db.execute("SELECT coll, COUNT(*) FROM fact WHERE scope='run' AND scope_id=?"
                                                   " GROUP BY coll", (r["id"],)).fetchall())}
            for r in st.db.execute("SELECT id, model_rev, calc_rev, engine_version, created_at, producer_json"
                                   " FROM mapping_run WHERE project_id=? ORDER BY id", (pid,))]
    return {"revisions": st.all_revisions(pid), "runs": runs}


@router.get("/projects/{pid}/bundle")
def project_bundle(pid: int):
    try:
        return _json_bundle(revstore.project_bundle(_st(), pid))
    except KeyError:
        raise HTTPException(404, f"project {pid} not found")


@router.get("/revisions/{rid}")
def revision(rid: int):
    try:
        return _st().revision_full(rid)
    except KeyError:
        raise HTTPException(404)


@router.get("/revisions/{rid}/bundle")
def revision_bundle(rid: int):
    try:
        return _json_bundle(revstore.revision_bundle(_st(), rid))
    except KeyError:
        raise HTTPException(404)


@router.get("/runs/{run_id}/bundle")
def run_bundle(run_id: int):
    try:
        return _json_bundle(revstore.run_bundle(_st(), run_id))
    except KeyError:
        raise HTTPException(404)


@router.get("/diff")
def diff(a: int, b: int, scope: str = "revision"):
    st = _st()
    if scope == "revision":
        try:
            ra, rb = st.revision_full(a), st.revision_full(b)
        except KeyError:
            raise HTTPException(404)
        if (ra["project_id"], ra["kind"]) != (rb["project_id"], rb["kind"]):
            raise HTTPException(400, "diff needs two revisions of the same kind in the same project")
    elif scope != "run":
        raise HTTPException(400, "scope must be revision | run")
    return {"scope": scope, "a": a, "b": b, "collections": st.diff_facts(scope, a, b)}


@router.get("/documents/{sha}")
def document(sha: str):
    d = _st().document(sha)
    if not d:
        raise HTTPException(404)
    d.pop("source_path", None)  # local path: not part of the document's identity
    return d
