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

from . import calcpkg_ingest, drawing_ingest, drawing_loadpath, set_graph

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
    sheets = [{k: v for k, v in s.items()} for s in dr["sheets"]]
    graph = {
        "id": sid, "name": name, "built_at": time.strftime("%Y-%m-%d %H:%M:%S %Z"), "build_seconds": round(time.time() - t0, 1),
        "docs": {k: {kk: vv for kk, vv in v.items() if kk != "path"} for k, v in docs.items()},
        "sheets": sheets, "elements": dr["elements"], "element_edges": edges,
        "calcs": [_slim_page(p) for p in pages], "calc_edges": cedges, "links": links,
        "findings": finds, "coverage": cov,
    }
    out = os.path.join(SETS_DIR, sid)
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "graph.json"), "w") as fh:
        json.dump(graph, fh)
    with open(os.path.join(out, "meta.json"), "w") as fh:
        json.dump({"id": sid, "name": name, "docs": docs}, fh, indent=1)
    return graph


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
