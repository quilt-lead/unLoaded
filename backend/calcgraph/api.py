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

from . import graph_ingest, pipeline, revstore
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
async def upload_model(pid: int, file: UploadFile = File(...), graph: UploadFile = File(...),
                       label: str | None = Form(None)):
    """A model revision = the IFC (`file`, stored content-addressed: /api/revisions/{rid}/file) plus
    the element graph the client built from it (`graph`: ElementGraph.serialize() JSON, format
    unloaded.element-graph v1, sent as a file part; stored verbatim: /api/revisions/{rid}/graph).
    Elements and load path come from the graph; the backend does not parse the IFC."""
    _pid(pid)
    raw = await graph.read()
    path = await _save(file, ".ifc")
    try:
        rid = pipeline.ingest_model(st, pid, path, raw, file.filename, label)
    except graph_ingest.GraphError as e:  # validated before anything is stored
        raise HTTPException(400, f"Could not read that element graph: {e}")
    except Exception as e:  # surface the reason to the UI, never a silent 500
        raise HTTPException(400, f"Could not store that model: {e}")
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


def _synthetic() -> str:
    """The synthetic package dir, generated on first use (python -m synth.generate)."""
    if not os.path.exists(os.path.join(SYNTH_DIR, "ground_truth.json")):
        from synth.generate import generate
        generate(SYNTH_DIR)
    return SYNTH_DIR


@app.post("/api/projects/{pid}/sample")
def load_sample(pid: int):
    """Ingest the synthetic CALC PACKAGE as a new calc revision. The sample MODEL is loaded by the
    client like any upload: fetch /api/sample/files/model_rev1.ifc (or model_rev2.ifc), build its
    element graph, POST both to /api/projects/{pid}/model."""
    _pid(pid)
    return {"calcs": pipeline.ingest_calcs(st, pid, os.path.join(_synthetic(), "calc_package.pdf"), "calc_package.pdf",
                                           "Sample calc package")}


SAMPLE_FILES = {"model_rev1.ifc": "application/x-step", "model_rev2.ifc": "application/x-step",
                "calc_package.pdf": "application/pdf"}


@app.get("/api/sample/files/{name}")
def sample_file(name: str):
    """The synthetic sample's source files (model_rev1.ifc = Rev 1 issued for permit, model_rev2.ifc =
    Rev 2 with column C8 removed, calc_package.pdf). Not generated on demand: run synth.generate."""
    if name not in SAMPLE_FILES:
        raise HTTPException(404, f"no sample file {name!r}; available: {', '.join(SAMPLE_FILES)}")
    path = os.path.join(SYNTH_DIR, name)
    if not os.path.exists(path):
        raise HTTPException(404, f"sample file {name} is not generated yet - run: cd backend && "
                                 "uv run python -m synth.generate (or POST /api/projects/1/sample once)")
    return FileResponse(path, media_type=SAMPLE_FILES[name], filename=name)


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


@app.get("/api/revisions/{rid}/graph")
def revision_graph(rid: int):
    """The serialized element graph stored with a model revision, verbatim (no re-parse of the IFC)."""
    try:
        r = st.revision(rid)
    except KeyError:
        raise HTTPException(404)
    if r["kind"] != "model":
        raise HTTPException(400, f"revision {rid} is not a model revision")
    path = pipeline.model_graph(st, rid)
    if not path:
        raise HTTPException(404, f"model revision {rid} has no stored element graph (stored before graphs were)")
    return FileResponse(path, media_type="application/json", headers={"Cache-Control": "no-store"})


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
