"""Drawing-set project: plans PDF (element source) + calc package PDF(s) -> one graph JSON.

Output lives in data/sets/<sid>/ (gitignored: it is derived from copyrighted PDFs).
graph.json holds elements, element_edges, calcs, calc_edges, links, findings, coverage;
meta.json maps doc keys to the LOCAL source paths the server streams / renders from.
"""
from __future__ import annotations

import json
import os
import re
import time

from collections import Counter

from . import calcpkg_ingest, drawing_ingest, drawing_loadpath, plans_to_ifc, set_graph

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SETS_DIR = os.environ.get("CALCGRAPH_SETS", os.path.join(ROOT, "data", "sets"))


def _slim_page(p: dict) -> dict:
    return {k: p[k] for k in ("id", "doc", "page", "sheet_id", "sheet_rect", "section", "group", "title", "title_rect",
                              "tables", "level", "software", "toc", "width", "height", "drawing_refs")} | {
        "labels": {k: len(v) for k, v in p["labels"].items()}, "sizes": sorted(p["sizes"]), "kind": set_graph.page_kind(p),
        "role": set_graph.page_role(p)}


def ingest_set(sid: str, name: str, plans: str, calcs: list[tuple[str, str, str | None]]) -> dict:
    t0 = time.time()
    dr = drawing_ingest.read_plans(plans)
    edges, lp_stats = drawing_loadpath.infer(plans, dr["sheets"], dr["elements"])
    pages = []
    docs = {"plans": {"name": os.path.basename(plans), "path": os.path.abspath(plans), "role": "Drawing set"}}
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
    model = plans_to_ifc.build(sid, plans, dr["sheets"], dr["elements"], edges, links, finds, os.path.join(out, "model.ifc"))
    cov["model_3d"] = {"elements_in_3d": model["elements_in_3d"], "counts_by_type": model["counts_by_type"]}
    sheets = [{k: v for k, v in s.items()} for s in dr["sheets"]]
    graph = {
        "id": sid, "name": name, "built_at": time.strftime("%Y-%m-%d %H:%M:%S %Z"), "build_seconds": round(time.time() - t0, 1),
        "docs": {k: {kk: vv for kk, vv in v.items() if kk != "path"} for k, v in docs.items()},
        "sheets": sheets, "elements": dr["elements"], "element_edges": edges,
        "calcs": [_slim_page(p) for p in pages], "calc_edges": cedges, "links": links,
        "findings": finds, "coverage": cov, "model": model,
    }
    with open(os.path.join(out, "graph.json"), "w") as fh:
        json.dump(graph, fh)
    with open(os.path.join(out, "meta.json"), "w") as fh:
        json.dump({"id": sid, "name": name, "docs": docs}, fh, indent=1)
    # the record and connection layers read this graph's elements: rebuild them in the same run so
    # integrated.json can never pair a new graph with old records / connections
    build_records(sid)
    build_connections(sid)
    finish_set(sid)
    return graph


def _dir(sid: str) -> str:
    return os.path.join(SETS_DIR, safe_sid(sid))


def _load(sid: str, name: str):
    p = os.path.join(_dir(sid), name)
    return json.load(open(p)) if os.path.exists(p) else None


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
    with open(os.path.join(d, "calc_records.json"), "w") as fh:
        json.dump(out, fh)
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
           "coverage": cov} | out
    with open(os.path.join(d, "connections.json"), "w") as fh:
        json.dump(res, fh, default=lambda o: list(o) if isinstance(o, tuple) else str(o))
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
    return out


def list_sets() -> list[dict]:
    if not os.path.isdir(SETS_DIR):
        return []
    out = []
    for sid in sorted(os.listdir(SETS_DIR)):
        mp = os.path.join(SETS_DIR, sid, "meta.json")
        if os.path.exists(mp):
            m = json.load(open(mp))
            out.append({"id": sid, "name": m["name"], "docs": {k: {"name": v["name"], "role": v["role"]} for k, v in m["docs"].items()}})
    return out


def safe_sid(s: str) -> str:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,60}", s):
        raise ValueError("set id must be lowercase letters, digits and hyphens")
    return s
