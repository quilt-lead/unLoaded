"""Drawing-set project: plans PDF (element source) + calc package PDF(s) [+ the building's IFC model]
-> one graph JSON.

Every build is a REVISION in the revision store (revstore / store.py, data/store - gitignored):
ingest_set -> kind 'set' (graph.json + meta.json + model.ifc when the set has a model), build_records -> 'records',
build_connections -> 'connections', finish_set -> 'integrated'. The output files become
content-addressed artifacts of that revision, the source PDFs content-addressed documents, and
the schema facts of each output are stored with their provenance. The API reads the head
revisions. The same files are still written to data/sets/<sid>/ (gitignored: derived data)
as a working copy for scripts; revstore.import_sets() picks up any file there
that changed outside a build.
graph.json holds elements, element_edges, calcs, calc_edges, links, findings, coverage, model;
meta.json maps doc keys to the LOCAL source paths the server streams / renders from.

3D: the set's model.ifc IS the building's IFC (copied as the set's artifact), and each drawing tag
is tied to its model element by the registry's resolver (registry_ingest: plan / elevation tags and
schedule rows -> the IFC element, with its rule and confidence) - the same resolution the element
registry is scored on. A set without a model has no 3D view.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import time

from collections import Counter

from . import calcpkg_ingest, drawing_ingest, drawing_loadpath, revstore, set_graph

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SETS_DIR = os.environ.get("CALCGRAPH_SETS", os.path.join(ROOT, "data", "sets"))


def _slim_page(p: dict) -> dict:
    return {k: p[k] for k in ("id", "doc", "page", "sheet_id", "sheet_rect", "section", "group", "title", "title_rect",
                              "tables", "level", "software", "toc", "width", "height", "drawing_refs", "rule", "confidence")} | {
        "labels": {k: len(v) for k, v in p["labels"].items()}, "sizes": sorted(p["sizes"]), "kind": set_graph.page_kind(p),
        "role": set_graph.page_role(p)}


# registry occurrence kinds that place a drawn tag on one model element
_TAG_OCCURRENCES = ("plan_tag", "elevation_tag", "schedule_row")


def _overlap(a, b) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    m = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
    return ix * iy / m if m > 0 else 0.0


def link_model(sid: str, plans: str, model: str, elements: list[dict], links: list[dict], findings: list[dict]) -> dict:
    """Tie each drawing element to its element in the building's IFC through the registry resolver,
    sets element["model"] in place and returns graph["model"]. A tag resolves when a registry occurrence
    of an IFC element (plan / elevation tag, schedule row) on the same page overlaps it by half."""
    from . import ifc_ingest, registry_ingest
    reg = registry_ingest.build({"ifc": model, "drawings": plans})
    by_page: dict[int, list[tuple[dict, dict]]] = {}
    for n in reg["nodes"]:
        if not n.get("global_id"):
            continue
        for o in n["occurrences"]:
            if o["doc"] == "drawings" and o.get("how") in _TAG_OCCURRENCES and o.get("bbox"):
                by_page.setdefault(o["page"], []).append((n, o))
    geom = {e["global_id"]: e for e in ifc_ingest.read_ifc(model)["elements"]}
    linked = {l["el"] for l in links}
    mism = [f["text"] for f in findings if f["kind"] == "size mismatch"]
    placed, skipped = Counter(), Counter()
    for e in elements:
        rects = e.get("rects") or [e["bbox"]]
        best = max(((max(_overlap(r, o["bbox"]) for r in rects), n, o) for n, o in by_page.get(e["page"], [])),
                   key=lambda t: t[0], default=(0.0, None, None))
        if best[0] < 0.5:
            reason = ("the registry resolved no model element for this tag" if by_page.get(e["page"])
                      else f"no tag on {e['sheet']} resolved to the model")
            e["model"] = {"in3d": False, "reason": reason}
            skipped[reason] += 1
            continue
        _, n, o = best
        g = geom.get(n["global_id"], {})
        status = ("linked" if e["id"] in linked else
                  "size mismatch" if e.get("size_norm") and any(e["size_norm"] in t for t in mism) else "no calc found")
        mn, mx = (g.get("geom") or {}).get("min"), (g.get("geom") or {}).get("max")
        e["model"] = {"in3d": True, "gid": n["global_id"], "node": n["id"], "rule": o["rule"], "confidence": o.get("confidence"),
                      "position": f"model element {n['id']} ({g.get('ifc_type', '')}, {g.get('storey', '')})",
                      "elevation": f"from the model ({g.get('storey', '')})", "assumed": [],
                      "profile": g.get("profile") or n.get("type") or "", "status3d": status, "grid3d": e.get("grid", ""),
                      # three.js metres, IFC Y-up (x = east, y = up, z = -north): the element's box centre
                      "center": [round((mn[0] + mx[0]) / 2, 3), round((mn[2] + mx[2]) / 2, 3), round(-(mn[1] + mx[1]) / 2, 3)]
                      if mn and mx else None}
        placed[e["type"]] += 1
    shutil.copyfile(model, os.path.join(SETS_DIR, sid, "model.ifc"))
    return {"url": f"/api/sets/{sid}/model.ifc", "source": os.path.basename(model),
            # who read the model's elements into this set, and what it states about them (same declaration as the
            # IFC path's pipeline.MODEL_PRODUCER): the schema adapter takes rule id / confidence / engine from here
            "producer": revstore.producer("ifc_ingest", ifc_ingest={"rule_id": "ifc_ingest.read_ifc", "confidence": 1.0}),
            "elements_in_3d": sum(placed.values()), "elements_total": len(elements),
            "counts_by_type": dict(placed.most_common()), "skipped": dict(skipped.most_common()),
            "rule": "drawing tag -> registry occurrence (same page, overlap >= 0.5) -> its IFC element",
            "storeys": sorted({g["storey"] for g in geom.values() if g.get("storey")})}


def ingest_set(sid: str, name: str, plans: str, calcs: list[tuple[str, str, str | None]], model: str | None = None) -> dict:
    t0 = time.time()
    dr = drawing_ingest.read_plans(plans)
    edges, lp_stats = drawing_loadpath.infer(plans, dr["sheets"], dr["elements"])
    pages = []
    docs = {"plans": {"name": os.path.basename(plans), "path": os.path.abspath(plans), "role": "Drawing set"}}
    if model:
        docs["model"] = {"name": os.path.basename(model), "path": os.path.abspath(model), "role": "BIM model"}
    for path, key, prefix in calcs:
        r = calcpkg_ingest.read_package(path, key, prefix)
        pages += r["pages"]
        docs[key] = {"name": os.path.basename(path), "path": os.path.abspath(path), "role": "Calc package",
                     "pages": r["meta"]["page_count"]}
    cedges, ce_stats = set_graph.calc_edges(pages)
    links, link_stats = set_graph.link(dr["elements"], pages)
    finds = set_graph.findings(dr["elements"], pages, links, dr["sheets"])
    cov = set_graph.coverage(dr["elements"], edges, pages, cedges, links, lp_stats, ce_stats, link_stats, None)
    out = os.path.join(SETS_DIR, sid)
    os.makedirs(out, exist_ok=True)
    if os.path.exists(os.path.join(out, "model.ifc")):
        os.unlink(os.path.join(out, "model.ifc"))   # never pair a new graph with another build's model
    m3d = link_model(sid, plans, model, dr["elements"], links, finds) if model else None
    if m3d:
        cov["model_3d"] = {"elements_in_3d": m3d["elements_in_3d"], "counts_by_type": m3d["counts_by_type"]}
    sheets = [{k: v for k, v in s.items()} for s in dr["sheets"]]
    graph = {
        "id": sid, "name": name, "built_at": time.strftime("%Y-%m-%d %H:%M:%S %Z"), "build_seconds": round(time.time() - t0, 1),
        "docs": {k: {kk: vv for kk, vv in v.items() if kk != "path"} for k, v in docs.items()},
        "sheets": sheets, "elements": dr["elements"], "element_edges": edges,
        "calcs": [_slim_page(p) for p in pages], "calc_edges": cedges, "links": links,
        "findings": finds, "coverage": cov, "model": m3d,
        # engine + version of every module that made a fact in this file (module@source hash); each fact
        # carries its own rule id and confidence
        "producers": revstore.producer(*revstore.SET_PRODUCERS["set"]),
    }
    with open(os.path.join(out, "graph.json"), "w") as fh:
        json.dump(graph, fh)
    with open(os.path.join(out, "meta.json"), "w") as fh:
        json.dump({"id": sid, "name": name, "docs": docs}, fh, indent=1)
    revstore.record_set_output(revstore.open_store(), sid, "set", out)
    # the record and connection layers read this graph's elements: rebuild them in the same run so
    # integrated.json can never pair a new graph with old records / connections
    build_records(sid)
    build_connections(sid)
    finish_set(sid)
    return graph


def _dir(sid: str) -> str:
    return os.path.join(SETS_DIR, safe_sid(sid))


def _load(sid: str, name: str):
    """The head revision's artifact from the store; the working-copy file only for a set the store
    does not have yet (it is imported first, so the two cannot disagree)."""
    st = revstore.open_store()
    if os.path.exists(os.path.join(_dir(sid), "meta.json")):
        revstore.import_sets_one(st, SETS_DIR, sid)
    return revstore.set_load(st, sid, name)


def build_records(sid: str) -> dict:
    """Calc package -> design records (calc_records.json). Reads graph.json for the positional fit."""
    from . import calc_records
    d, meta, graph = _dir(sid), _load(sid, "meta.json"), _load(sid, "graph.json")
    calcs = [(v["path"], k, None if k == "calcs" else k.upper()) for k, v in meta["docs"].items() if v["role"] == "Calc package"]
    t0 = time.time()
    out = calc_records.build(calcs, graph, meta["docs"]["plans"]["path"])
    out["set"] = sid
    out["built_at"] = time.strftime("%Y-%m-%d %H:%M:%S %Z")
    out["source_graph_built_at"] = (graph or {}).get("built_at")
    out["build_seconds"] = round(time.time() - t0, 1)
    out["producers"] = revstore.producer(*revstore.SET_PRODUCERS["records"])
    with open(os.path.join(d, "calc_records.json"), "w") as fh:
        json.dump(out, fh)
    revstore.record_set_output(revstore.open_store(), sid, "records", d)
    return out


def build_connections(sid: str) -> dict:
    """S8 details -> connection types; callouts / plan symbols -> instances attached to elements (connections.json)."""
    from . import connections
    d, meta, g = _dir(sid), _load(sid, "meta.json"), _load(sid, "graph.json")
    docs = meta["docs"]
    calc_docs = [(k, v["path"]) for k, v in docs.items() if v.get("role") == "Calc package"]
    calc_ids = {(c["doc"], c["page"]): c["id"] for c in g["calcs"]}
    t0 = time.time()
    s_sheets = [s for s in g["sheets"] if s["sheet"].startswith("S")]
    out = connections.build(docs["plans"]["path"], s_sheets, g["elements"], calc_docs, calc_ids)
    inst = out["instances"]
    att = [i for i in inst if i["attached"]]
    cov = {
        "connection_types": len(out["types"]),
        "connection_types_titled_as_connections": sum(t["is_connection"] for t in out["types"]),
        "types_with_instances": sum(1 for t in out["types"] if t["instances"]),
        "instances": len(inst),
        "instances_attached": len(att),
        "instances_unattached": len(inst) - len(att),
        "unattached_located_via_view": sum(1 for i in inst if not i["attached"] and i.get("located_via_view")),
        "unattached_located_via_view_with_elements": sum(1 for i in inst if not i["attached"] and i.get("view_elements")),
        "unattached_by_sheet": dict(Counter(i["sheet"] for i in inst if not i["attached"])),
        "views": len(out["views"]),
        "instances_by_via": dict(Counter(i["via"] for i in inst)),
        "instances_by_sheet_via": dict(Counter(f"{i['sheet']} {i['via']}{' ' + i['symbol'] if i['symbol'] else ''}" for i in inst)),
        "instances_missing_type": sorted({i["ref"] for i in inst if i.get("missing_type")}),
        "detail_to_detail_refs": len(out["detail_refs"]),
        "other_callouts": len(out["other_callouts"]),
        "note_refs": len(out["note_refs"]),
        "legend_check": out["legend_check"],
        "calc_hits_by_rule": dict(Counter(h["rule"] for h in out["calc"]["hits"])),
        "calc_pages_designing_connections": sorted({f"{h['calc']} ({h['doc']} p{h['page']})" for h in out["calc"]["hits"] if h["designs_connection"]}),
        "calc_detail_refs": sorted({f"{r['calc']} -> {r['ref']} ({r['target_kind']})" for r in out["calc"]["detail_refs"]}),
        "unresolved_refs": sorted({o["ref"] for o in out["other_callouts"] if "not found" in o["kind"]} | {r["ref"] for r in out["detail_refs"] if not r["known"]}),
        "stats": out["stats"],
        "build_seconds": round(time.time() - t0, 1),
    }
    res = {"id": sid, "built_at": time.strftime("%Y-%m-%d %H:%M:%S %Z"), "source_graph_built_at": g.get("built_at"),
           "coverage": cov, "producers": revstore.producer(*revstore.SET_PRODUCERS["connections"])} | out
    with open(os.path.join(d, "connections.json"), "w") as fh:
        json.dump(res, fh, default=lambda o: list(o) if isinstance(o, tuple) else str(o))
    revstore.record_set_output(revstore.open_store(), sid, "connections", d)
    return res


def finish_set(sid: str) -> dict | None:
    """graph.json + calc_records.json + connections.json -> integrated.json (what the app reads).
    Every builder calls this last, so the integrated view always reflects the files on disk."""
    from . import set_integrate
    graph, cr, conns, meta = (_load(sid, n) for n in ("graph.json", "calc_records.json", "connections.json", "meta.json"))
    if not (graph and cr and conns):
        return None
    out = set_integrate.build(graph, cr, conns, meta)
    out["built_at"] = time.strftime("%Y-%m-%d %H:%M:%S %Z")
    with open(os.path.join(_dir(sid), "integrated.json"), "w") as fh:
        json.dump(out, fh)
    revstore.record_set_output(revstore.open_store(), sid, "integrated", _dir(sid))
    return out


def list_sets() -> list[dict]:
    """Drawing sets in the revision store (after importing any working-copy output that changed)."""
    st = revstore.open_store()
    revstore.import_sets(st, SETS_DIR)
    return revstore.list_sets(st)


def safe_sid(s: str) -> str:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,60}", s):
        raise ValueError("set id must be lowercase letters, digits and hyphens")
    return s
