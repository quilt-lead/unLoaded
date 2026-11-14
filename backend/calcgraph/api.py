"""FastAPI app. Run: uv run calc-graph serve  (http://127.0.0.1:8000)."""
from __future__ import annotations

import os
import tempfile

import pymupdf
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import BaseModel

from . import pipeline, revstore
from .store_api import router as store_router

STORE_DIR = revstore.store_dir()                      # backend/data/store (override: CALCGRAPH_STORE)
SYNTH_DIR = os.path.join(revstore.ROOT, "data", "synthetic")
# the frontend is the Vite app at the repo root; `npm run build` writes <repo>/dist
DIST = os.path.abspath(os.path.join(revstore.ROOT, "..", "dist"))

app = FastAPI(title="calc-graph", version="0.1.0")
app.include_router(store_router)  # schema-shaped /api/store/* endpoints (store_api.py)
st = revstore.open_store(STORE_DIR)  # the revision store (migrates a v1 store on open)
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
    """IFC-path projects with the v1 columns (everything: /api/store/projects)."""
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


class _SpaStatic(StaticFiles):
    """Built UI (<repo>/dist). Real files are served as-is;
    any other non-API path that is not a file returns index.html, so client-side router deep links
    load the app instead of a 404."""

    async def get_response(self, path, scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as e:  # StaticFiles raises starlette's (the base of FastAPI's) for misses
            if e.status_code != 404 or path.startswith("api/") or path == "api" or os.path.splitext(path)[1]:
                raise
            return await super().get_response("index.html", scope)


if os.path.isdir(DIST):
    app.mount("/", _SpaStatic(directory=DIST, html=True), name="ui")
