"""Synthetic v2 API: move a column, health meter, redo calcs, registry element pages, original
documents with highlights, construction platforms (mock), ETABS (mock). Mounted from api.py
with one include line. Every route is read-only on the source data except /apply and /rerun,
which write NEW revisions (store / data/synthetic_v2/revisions) and never overwrite.

All routes are under /api/v2. Route list + response shapes: docs/2026-11-14-move-a-column-notes.md.
"""
from __future__ import annotations

import json
import os
import tempfile
import threading

import pymupdf
from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel

from . import move_impact, recalc

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
    m = os.path.getmtime(p)
    if _CACHE.get("design_mtime") != m:
        _CACHE.clear()
        _CACHE["design"] = json.load(open(p))
        _CACHE["design_mtime"] = m
    return _CACHE["design"]


def _adapters():
    if "adapters" not in _CACHE:
        from .platforms import get_adapters
        _CACHE["adapters"] = get_adapters(_design())
    return _CACHE["adapters"]


def _status_fn():
    try:
        from .platforms import construction_status
        ads = _adapters()
        d = _design()
        return lambda eid: construction_status(eid, ads, d)
    except Exception:
        return None


class Move(BaseModel):
    column: str                 # "COL-2B" or "2B"
    dx: float = 0.0             # ft
    dy: float = 0.0
    remove: bool = False
    records: list[str] | None = None
    label: str | None = None


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


@router.get("/elements/{eid}")
def element(eid: str):
    """Registry element page: the element, its type/material, every relation in and out, the
    calc records that design it, and every occurrence (IFC GlobalId, drawings, specs, calcs, ETABS)."""
    d = _design()
    el = next((e for e in d["elements"] if e["id"] == eid), None) or next((t for t in d.get("types", []) if t["id"] == eid), None)
    rec = next((r for r in d["records"] if r["id"] == eid), None)
    if not el and not rec:
        raise HTTPException(404, f"no element, type or record {eid!r}")
    rels_out = [r for r in d["relations"] if r["src"] == eid]
    rels_in = [r for r in d["relations"] if r["dst"] == eid]
    designed = [r for r in d["records"] if eid in r.get("elements", [])]
    occ = [o for o in d.get("occurrences", []) if o["ref"] == eid]
    if el and el.get("global_id"):
        occ.insert(0, {"ref": eid, "doc": "ifc", "global_id": el["global_id"], "how": "ifc-element"})
    try:
        from .analysis import get_adapter
        if "etabs_occ" not in _CACHE:
            _CACHE["etabs_occ"] = get_adapter("etabs", d).occurrences()
        occ += [o for o in _CACHE["etabs_occ"] if o["ref"] == eid]
    except Exception as e:
        occ.append({"ref": eid, "doc": "etabs", "error": str(e)})
    return {"element": el, "record": rec, "relations_out": rels_out, "relations_in": rels_in,
            "designed_by": designed, "occurrences": occ,
            "occurrence_kinds_reserved": ["discussed-in (meeting id, time range, speaker, transcript span) - not built yet"]}


@router.get("/records/{rid}")
def record(rid: str):
    d = _design()
    r = next((x for x in d["records"] if x["id"] == rid), None)
    if not r:
        raise HTTPException(404, f"no record {rid!r}")
    return {**r, "fed_by": r["inputs"], "feeds": [x["id"] for x in d["records"] if rid in x["inputs"]]}


@router.get("/registry")
def registry():
    """Registry truth (generator) and, when built, the registry rebuilt from the documents."""
    out = {}
    for k, f in (("truth", "registry_truth.json"), ("ingested", "registry_ingested.json"), ("eval", "registry_eval.json")):
        p = os.path.join(V2, f)
        out[k] = os.path.exists(p)
    return out


@router.get("/registry/{which}")
def registry_file(which: str):
    f = {"truth": "registry_truth.json", "ingested": "registry_ingested.json", "eval": "registry_eval.json"}.get(which)
    if not f or not os.path.exists(os.path.join(V2, f)):
        raise HTTPException(404, f"registry {which} not built")
    return FileResponse(os.path.join(V2, f), media_type="application/json", headers={"Cache-Control": "no-store"})


# ------------------------------------------------------------------ move / impact / health
@router.post("/impact")
def impact(m: Move):
    """Stale calc records with reason chains, screened estimates (labelled), health meter,
    affected occurrences, construction status and the potential change order."""
    d = _design()
    try:
        res = move_impact.impact(d, _col(m.column), m.dx, m.dy, m.remove, platform_status=_status_fn())
    except KeyError:
        raise HTTPException(404, f"no column {m.column!r}")
    res["change_order"] = _change_order(d, res)
    return JSONResponse(_safe(res))


def _change_order(d: dict, res: dict) -> dict:
    try:
        from .platforms import estimate
    except Exception as e:
        return {"error": f"platform adapters unavailable: {e}"}
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
    specs = sorted({o["ref"] for o in d.get("occurrences", []) if o.get("doc") == "specs" and o["ref"].startswith("SPEC:")
                    and any(r["src"] in {els.get(e, {}).get("size") and f"TYPE:{els[e]['size']}" for e in touched}
                            and r["dst"] == o["ref"] for r in d["relations"] if r["kind"] == "specified-by")})
    imp = {"elements": touched, "resized": resized, "connections_changed": conns, "footings_changed": ftgs,
           "records": [s["record"] for s in res["stale"] if s["screened"]], "sheets": sheets, "spec_articles": specs}
    try:
        return estimate(imp, _adapters(), d)
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}", "input": imp}


def d_rec(d: dict, rid: str) -> dict:
    if "rec_index" not in _CACHE:
        _CACHE["rec_index"] = {r["id"]: r for r in d["records"]}
    return _CACHE["rec_index"].get(rid, {"elements": []})


@router.get("/health")
def health(probe: float = 2.0):
    """Health meter of every column for a +/- probe move (heat view of 'how hard to move')."""
    key = f"heat:{probe}"
    if key not in _CACHE:
        _CACHE[key] = _safe(move_impact.heat(_design(), probe, platform_status=_status_fn()))
    return _CACHE[key]


@router.post("/rerun")
def rerun(m: Move):
    """Redo calcs directly: re-run the stale records (or m.records) with the v2 design code; old
    vs new per record in load-path order; regenerated calc pages as a NEW calc revision."""
    d = _design()
    recs = m.records
    if recs is None:
        res = move_impact.impact(d, _col(m.column), m.dx, m.dy, m.remove)
        recs = [s["record"] for s in res["stale"]]
    with _LOCK:
        return JSONResponse(_safe(recalc.rerun(d, _change(m), recs)))


@router.get("/revisions")
def revisions():
    return {"calc_revisions": recalc.list_revisions(), "model_revisions": _store_revs()}


@router.get("/revisions/{rev_id}")
def revision(rev_id: str):
    p = os.path.join(V2, "revisions", os.path.basename(rev_id), "revision.json")
    if not os.path.exists(p):
        raise HTTPException(404)
    return FileResponse(p, media_type="application/json")


@router.get("/revisions/{rev_id}/calc_revision.pdf")
def revision_pdf(rev_id: str):
    p = os.path.join(V2, "revisions", os.path.basename(rev_id), "calc_revision.pdf")
    if not os.path.exists(p):
        raise HTTPException(404, "no regenerated pages for this revision")
    return FileResponse(p, media_type="application/pdf")


def _store():
    from .api import st
    return st


def _store_revs() -> list[dict]:
    st = _store()
    pid = _v2_project(st)
    return st.revisions(pid)


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


@router.post("/apply")
def apply(m: Move):
    """Apply the move as a NEW model revision in the revision store (minimum-change re-design,
    IFC written and ingested through the production pipeline) and return the element diff."""
    from synth.v2 import ifc_v2
    from synth.v2.generate import build
    from . import pipeline
    d = _design()
    st = _store()
    with _LOCK:
        pid = _v2_project(st)
        if not st.project(pid)["head_model_rev"]:
            pipeline.ingest_model(st, pid, os.path.join(V2, "model.ifc"), "model.ifc", "Synthetic v2 - base design")
        prev = st.project(pid)["head_model_rev"]
        L = recalc.layout_from_change(_change(m))
        _, exp = build(L, keep={e["id"]: e for e in d["elements"]})
        label = m.label or (f"Remove {m.column}" if m.remove else f"Move {m.column} ({m.dx:+g}, {m.dy:+g}) ft")
        fd, path = tempfile.mkstemp(suffix=".ifc")
        os.close(fd)
        try:
            ifc_v2.write(exp, path, label=label)
            rid = pipeline.ingest_model(st, pid, path, f"{label}.ifc", label)
        finally:
            os.unlink(path)
        diff = st.compare_models(prev, rid)
    return _safe({"project": pid, "revision": rid, "parent": prev, "label": label, "diff": diff})


@router.get("/compare")
def compare(a: int, b: int):
    return _store().compare_models(a, b)


# ------------------------------------------------------------------ documents
_DOCS_OPEN: dict[str, pymupdf.Document] = {}


def _local_only(request: Request) -> None:
    if request.client and request.client.host not in ("127.0.0.1", "::1", "localhost", "testclient"):
        raise HTTPException(403, "localhost only")


@router.get("/docs/{doc}/file")
def doc_file(doc: str):
    f = DOCS.get(doc)
    if not f or not os.path.exists(os.path.join(V2, f)):
        raise HTTPException(404, f"no {doc} document yet")
    return FileResponse(os.path.join(V2, f), media_type="application/pdf")


@router.get("/docs/{doc}/pages/{n}.png")
def doc_page(doc: str, n: int, hl: str = "", w: int = 1400):
    """Page n (1-based) of a v2 document; hl = 'x0,y0,x1,y1;...' PDF points drawn as highlights."""
    f = DOCS.get(doc)
    p = os.path.join(V2, f) if f else ""
    if not f or not os.path.exists(p):
        raise HTTPException(404, f"no {doc} document yet")
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


# ------------------------------------------------------------------ construction platforms (mock)
@router.get("/platforms")
def platforms():
    return [{"name": a.name, "label": a.label, "capabilities": sorted(a.capabilities), "counts": a.counts(),
             "doc_urls": a.doc_urls, "mock": True} for a in _adapters()]


@router.get("/platforms/{name}/{record_type}")
def platform_records(name: str, record_type: str, raw: bool = False):
    a = next((x for x in _adapters() if x.name == name), None)
    if not a:
        raise HTTPException(404, f"no platform {name!r}")
    if record_type not in a.capabilities:
        raise HTTPException(404, f"{name} has no {record_type}")
    return a.list_raw(record_type) if raw else [r.to_dict(include_raw=False) for r in a.list(record_type)]


@router.get("/construction-status/{eid}")
def construction_status(eid: str):
    fn = _status_fn()
    if not fn:
        raise HTTPException(503, "platform adapters unavailable")
    return _safe(fn(eid))


@router.post("/change-order")
def change_order(m: Move):
    d = _design()
    res = move_impact.impact(d, _col(m.column), m.dx, m.dy, m.remove)
    return _safe(_change_order(d, res))


# ------------------------------------------------------------------ analysis software (mock ETABS)
def _etabs():
    from .analysis import get_adapter
    return get_adapter("etabs", _design())


@router.get("/etabs/objects")
def etabs_objects(kind: str | None = None):
    objs = [o.to_dict() for o in _etabs().model_objects()]
    return [o for o in objs if not kind or o["kind"] == kind]


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
                                                            "X-Note": "written by calc-graph; ETABS did not open it"})


@router.post("/etabs/send")
def etabs_send(m: Move):
    return _etabs().send_change(_design(), _change(m))


@router.post("/etabs/pull/{job_id}")
def etabs_pull(job_id: str):
    return _etabs().pull_results(job_id)


# ------------------------------------------------------------------ ground truth / evaluation
@router.get("/scenarios")
def scenarios():
    p = os.path.join(V2, "answer_key.json")
    if not os.path.exists(p):
        raise HTTPException(404, "no answer key - run: uv run python -m synth.v2.scenarios")
    k = json.load(open(p))
    return [{x: s[x] for x in ("id", "label", "kind", "column", "dx", "dy", "difficulty", "difficulty_why")} |
            {"stale": len(s["changed_records"]), "resized": len(s["resized"])} for s in k["scenarios"]]


@router.get("/eval")
def evaluation():
    p = os.path.join(V2, "move_eval.json")
    if not os.path.exists(p):
        raise HTTPException(404, "run: uv run python scripts/evaluate_move.py")
    return json.load(open(p))["summary"]
