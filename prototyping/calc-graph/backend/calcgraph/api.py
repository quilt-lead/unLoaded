"""FastAPI app. Run: uv run calc-graph serve  (http://127.0.0.1:8000)."""
from __future__ import annotations

import os
import tempfile

import pymupdf
import hashlib
import json
import threading

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import BaseModel

from . import pipeline, revstore, set_pipeline

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
STORE_DIR = os.environ.get("CALCGRAPH_STORE", os.path.join(ROOT, "data", "store"))
SYNTH_DIR = os.path.join(ROOT, "data", "synthetic")
DIST = os.path.join(ROOT, "frontend", "dist")

app = FastAPI(title="calc-graph", version="0.1.0")
st = revstore.open_store(STORE_DIR)  # one revision store for both paths (migrates a v1 store on open)
st.ensure_project()


def _pid(pid: int) -> int:
    try:
        st.project(pid)
    except KeyError:
        raise HTTPException(404, f"project {pid} not found")
    return pid


@app.get("/api/health")
def health():
    return {"ok": True, "store": STORE_DIR}


@app.get("/api/projects")
def projects():
    """IFC-path projects with the v1 columns (drawing sets: /api/sets; everything: /api/store/projects)."""
    return st.legacy_projects()


@app.get("/api/projects/{pid}/state")
def get_state(pid: int):
    return JSONResponse(pipeline.state(st, _pid(pid)))


async def _save(upload: UploadFile, suffix: str) -> str:
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "wb") as fh:
        while chunk := await upload.read(1 << 20):
            fh.write(chunk)
    return path


@app.post("/api/projects/{pid}/model")
async def upload_model(pid: int, file: UploadFile = File(...), label: str | None = Form(None)):
    _pid(pid)
    path = await _save(file, ".ifc")
    try:
        rid = pipeline.ingest_model(st, pid, path, file.filename, label)
    except Exception as e:  # surface the reason to the UI, never a silent 500
        raise HTTPException(400, f"Could not read that IFC: {e}")
    finally:
        os.unlink(path)
    return {"revision": rid}


@app.post("/api/projects/{pid}/calcs")
async def upload_calcs(pid: int, file: UploadFile = File(...), label: str | None = Form(None)):
    _pid(pid)
    path = await _save(file, ".pdf")
    try:
        rid = pipeline.ingest_calcs(st, pid, path, file.filename, label)
    except Exception as e:
        raise HTTPException(400, f"Could not read that PDF: {e}")
    finally:
        os.unlink(path)
    return {"revision": rid}


@app.post("/api/projects/{pid}/sample")
def load_sample(pid: int, model_rev: int = 1):
    """Ingest the synthetic package (generated on first use). model_rev=2 loads the
    'column C8 removed' model revision on top of whatever is loaded."""
    _pid(pid)
    if not os.path.exists(os.path.join(SYNTH_DIR, "ground_truth.json")):
        from synth.generate import generate
        generate(SYNTH_DIR)
    p = st.project(pid)
    out = {}
    if model_rev == 1 or not p["head_model_rev"]:
        out["model"] = pipeline.ingest_model(st, pid, os.path.join(SYNTH_DIR, "model_rev1.ifc"), "model_rev1.ifc",
                                             "Sample - Rev 1 issued for permit")
    if model_rev == 2:
        out["model"] = pipeline.ingest_model(st, pid, os.path.join(SYNTH_DIR, "model_rev2.ifc"), "model_rev2.ifc",
                                             "Sample - Rev 2 column C8 removed")
    if not st.project(pid)["head_calc_rev"] or model_rev == 1:
        out["calcs"] = pipeline.ingest_calcs(st, pid, os.path.join(SYNTH_DIR, "calc_package.pdf"), "calc_package.pdf",
                                             "Sample calc package")
    return out


@app.get("/api/projects/{pid}/revisions")
def revisions(pid: int):
    return {"revisions": st.revisions(_pid(pid)), "runs": st.runs(pid)}


@app.get("/api/projects/{pid}/compare")
def compare(pid: int, a: int, b: int):
    """Element-level diff of two model revisions (backend foundation for redlines)."""
    _pid(pid)
    for r in (a, b):
        if st.revision(r)["kind"] != "model":
            raise HTTPException(400, f"revision {r} is not a model revision")
    return st.compare_models(a, b)


@app.get("/api/revisions/{rid}/file")
def revision_file(rid: int):
    try:
        r = st.revision(rid)
    except KeyError:
        raise HTTPException(404)
    media = "application/pdf" if r["kind"] == "calcs" else "application/x-step"
    return FileResponse(st.blob_path(rid), media_type=media, filename=r["source_name"])


@app.get("/api/revisions/{rid}/pages/{n}.png")
def page_png(rid: int, n: int, hl: str = "", width: int = 1100):
    """Render a calc page; hl = 'x0,y0,x1,y1;...' in PDF points is drawn as highlight boxes."""
    try:
        r = st.revision(rid)
    except KeyError:
        raise HTTPException(404)
    if r["kind"] != "calcs":
        raise HTTPException(400, "not a calc package revision")
    doc = pymupdf.open(st.blob_path(rid))
    if not 1 <= n <= len(doc):
        raise HTTPException(404, "no such page")
    page = doc[n - 1]
    for part in filter(None, hl.split(";")):
        try:
            x0, y0, x1, y1 = (float(v) for v in part.split(","))
        except ValueError:
            raise HTTPException(400, f"bad highlight box {part!r}")
        page.draw_rect(pymupdf.Rect(x0 - 2, y0 - 2, x1 + 2, y1 + 2), color=(0.9, 0.55, 0), fill=(1, 0.8, 0),
                       fill_opacity=0.35, width=1.5)
    zoom = max(0.5, min(4.0, width / page.rect.width))
    png = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom)).tobytes("png")
    return Response(png, media_type="image/png", headers={"Cache-Control": "no-store"})


class DecisionIn(BaseModel):
    global_id: str
    calc_key: str
    action: str
    actor: str | None = "reviewer"
    note: str | None = None


@app.post("/api/projects/{pid}/decisions")
def decide(pid: int, d: DecisionIn):
    _pid(pid)
    if d.action not in ("confirm", "reject", "manual", "undo"):
        raise HTTPException(400, "action must be confirm | reject | manual | undo")
    return {"id": st.add_decision(pid, d.global_id, d.calc_key, d.action, d.actor, d.note)}


@app.get("/api/projects/{pid}/decisions")
def decisions(pid: int):
    return st.decision_log(_pid(pid))


@app.get("/api/projects/{pid}/impact")
def impact(pid: int, gid: str, mode: str = "change"):
    if mode not in ("change", "remove"):
        raise HTTPException(400, "mode must be change | remove")
    return pipeline.impact_of(st, _pid(pid), gid, mode)


@app.get("/api/projects/{pid}/export")
def export(pid: int):
    return JSONResponse(pipeline.export(st, _pid(pid)),
                        headers={"Content-Disposition": 'attachment; filename="calc-graph-mapping.json"'})


# ---------------- drawing-set projects (PDF plans + calc packages, no BIM model) ----------------
_DOCS: dict[str, pymupdf.Document] = {}
_PDF_LOCK = threading.Lock()  # PyMuPDF documents are not thread-safe


def _set_meta(sid: str) -> dict:
    """The set's head 'set' revision in the revision store (a working-copy output in data/sets that
    changed outside a build is imported first, so the store is the only source of responses)."""
    try:
        set_pipeline.safe_sid(sid)
    except ValueError as e:
        raise HTTPException(400, str(e))
    revstore.import_sets_one(st, set_pipeline.SETS_DIR, sid)
    m = revstore.set_load(st, sid, "meta.json")
    if not m:
        raise HTTPException(404, f"set {sid} not found - run: uv run calc-graph ingest-set")
    return m


def _set_artifact(sid: str, name: str, missing: str) -> str:
    a = revstore.set_head_artifact(st, sid, name)
    if not a or not os.path.exists(a["path"]):
        raise HTTPException(404, missing)
    return a["path"]


def _local_only(request: Request) -> None:
    if request.client and request.client.host not in ("127.0.0.1", "::1", "localhost", "testclient"):
        raise HTTPException(403, "source documents are served to localhost only")


def _doc_path(sid: str, doc: str) -> str:
    m = _set_meta(sid)
    if doc not in m["docs"]:
        raise HTTPException(404, f"no document {doc!r} in set {sid}")
    path = m["docs"][doc]["path"]
    if not os.path.exists(path):
        raise HTTPException(404, f"source PDF missing on this machine: {os.path.basename(path)}")
    return path


@app.get("/api/sets")
def sets():
    return set_pipeline.list_sets()


@app.get("/api/sets/{sid}/graph")
def set_graph(sid: str):
    _set_meta(sid)
    return FileResponse(_set_artifact(sid, "graph.json", "no graph.json in the store for this set"),
                        media_type="application/json", headers={"Cache-Control": "no-store"})


@app.get("/api/sets/{sid}/integrated")
def set_integrated(sid: str):
    """Calc records, calc load path, connection nodes, 2021 calc-model overlay and their findings
    (built by every set builder via set_pipeline.finish_set)."""
    _set_meta(sid)
    path = _set_artifact(sid, "integrated.json", "no integrated.json yet - run: uv run python scripts/build_calc_records.py")
    return FileResponse(path, media_type="application/json", headers={"Cache-Control": "no-store"})


@app.get("/api/sets/{sid}/model.ifc")
def set_model_ifc(sid: str, request: Request):
    """3D structural model built from the plans (derived data: localhost only, never committed)."""
    _local_only(request)
    _set_meta(sid)
    path = _set_artifact(sid, "model.ifc", "no model.ifc yet - re-run: uv run calc-graph ingest-set ...")
    return FileResponse(path, media_type="application/x-step", filename=f"{sid}-model.ifc",
                        headers={"Cache-Control": "no-store"})


@app.get("/api/sets/{sid}/docs/{doc}/file")
def set_doc_file(sid: str, doc: str, request: Request):
    _local_only(request)
    path = _doc_path(sid, doc)
    return FileResponse(path, media_type="application/pdf", filename=os.path.basename(path))


@app.get("/api/sets/{sid}/docs/{doc}/pages/{n}.png")
def set_page_png(sid: str, doc: str, n: int, request: Request, clip: str = "", w: int = 1400):
    """Render page n (1-based) of an original PDF, optionally only the clip 'x0,y0,x1,y1' (PDF points),
    w pixels wide. Highlights are drawn by the client so renders stay cacheable. Cache: data/sets/<sid>/cache."""
    _local_only(request)
    path = _doc_path(sid, doc)
    w = max(64, min(int(w), 4096))
    key = hashlib.sha1(f"{doc}|{n}|{clip}|{w}".encode()).hexdigest()[:20]
    cdir = os.path.join(set_pipeline.SETS_DIR, sid, "cache")
    cfile = os.path.join(cdir, key + ".png")
    if os.path.exists(cfile):
        return FileResponse(cfile, media_type="image/png", headers={"Cache-Control": "private, max-age=3600"})
    with _PDF_LOCK:
        d = _DOCS.get(path)
        if d is None:
            d = _DOCS[path] = pymupdf.open(path)
        if not 1 <= n <= len(d):
            raise HTTPException(404, "no such page")
        page = d[n - 1]
        rect = page.rect
        if clip:
            try:
                x0, y0, x1, y1 = (float(v) for v in clip.split(","))
            except ValueError:
                raise HTTPException(400, f"bad clip {clip!r}")
            rect = pymupdf.Rect(x0, y0, x1, y1) & page.rect
            if rect.is_empty:
                raise HTTPException(400, "clip is outside the page")
        zoom = min(w / rect.width, 12.0)
        if rect.width * zoom * rect.height * zoom > 24e6:
            zoom = (24e6 / (rect.width * rect.height)) ** 0.5
        png = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), clip=rect, alpha=False).tobytes("png")
    os.makedirs(cdir, exist_ok=True)
    with open(cfile, "wb") as fh:
        fh.write(png)
    return Response(png, media_type="image/png", headers={"Cache-Control": "private, max-age=3600"})


from .move_api import router as _v2_router; app.include_router(_v2_router)  # synthetic v2: move/registry/platforms/ETABS (move_api.py)
from .as_of import router as _asof_router; app.include_router(_asof_router)  # as-of date on impact: presets + cost/slip timeline (as_of.py)
from .inbox import router as _inbox_router; app.include_router(_inbox_router)  # inbound RFI / change-event inbox (inbox.py)

from .store_api import router as _store_router; app.include_router(_store_router)  # schema-shaped store endpoints (store_api.py)

class _SpaStatic(StaticFiles):
    """Built UI (frontend/dist). Real files are served as-is;
    any other non-API path that is not a file returns index.html, so React Router deep links such as
    /dev/components or /set/... load the app instead of a 404."""

    async def get_response(self, path, scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as e:  # StaticFiles raises starlette's (the base of FastAPI's) for misses
            if e.status_code != 404 or path.startswith("api/") or path == "api" or os.path.splitext(path)[1]:
                raise
            return await super().get_response("index.html", scope)


if os.path.isdir(DIST):
    app.mount("/", _SpaStatic(directory=DIST, html=True), name="ui")
