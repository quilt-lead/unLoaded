"""Ingest + mapping pipeline shared by the API, the CLI and scripts/evaluate.py."""
from __future__ import annotations

import os

from . import ENGINE_VERSION, calcdeps, ifc_ingest, impact, loadpath, matcher, pdf_ingest, segment
from .store import Store

PALETTE = ["#4e79a7", "#f28e2b", "#59a14f", "#b07aa1", "#e15759", "#76b7b2", "#edc948", "#9c755f", "#ff9da7",
           "#2b8c8c", "#8f6ed5", "#d4a017", "#3d9970", "#c2185b", "#5f7d95"]


def ingest_model(st: Store, pid: int, path: str, source_name: str | None = None, label: str | None = None) -> int:
    data = ifc_ingest.read_ifc(path)
    edges = loadpath.infer(data["elements"])
    rid = st.add_revision(pid, "model", path, source_name or os.path.basename(path), label,
                          {**data["meta"], "elements": len(data["elements"]), "load_path_edges": len(edges)})
    st.put_elements(rid, data["elements"], edges)
    st.set_head(pid, "model", rid)
    st.commit()
    remap(st, pid)
    return rid


def ingest_calcs(st: Store, pid: int, path: str, source_name: str | None = None, label: str | None = None) -> int:
    data = pdf_ingest.read_pdf(path)
    calcs = segment.segment(data["pages"])
    rid = st.add_revision(pid, "calcs", path, source_name or os.path.basename(path), label,
                          {**data["meta"], "calcs": len(calcs)})
    st.put_calcs(rid, data["pages"], calcs)
    st.set_head(pid, "calcs", rid)
    st.commit()
    remap(st, pid)
    return rid


def remap(st: Store, pid: int) -> int | None:
    p = st.project(pid)
    if not (p["head_model_rev"] and p["head_calc_rev"]):
        return None
    els = st.elements(p["head_model_rev"])
    pages = st.pages(p["head_calc_rev"])
    calcs = st.calcs(p["head_calc_rev"], with_text=True)
    links = matcher.run_mapping(els, calcs, pages)
    cedges = calcdeps.infer(calcs, pages, links)
    run = st.put_run(pid, p["head_model_rev"], p["head_calc_rev"], ENGINE_VERSION, links, cedges)
    st.commit()
    return run


def effective_links(st: Store, pid: int, run_id: int, gids: set[str], calc_keys: set[str]) -> list[dict]:
    """Auto links of the run with the (carried-forward) human decisions applied."""
    links = st.links(run_id)
    by = {(l["global_id"], l["calc_key"]): l for l in links}
    for (g, k), d in st.effective_decisions(pid).items():
        if g not in gids or k not in calc_keys:
            continue  # element or calc no longer exists in the head revisions
        l = by.get((g, k))
        if d["action"] == "confirm" and l:
            l["status"] = "confirmed"
        elif d["action"] == "reject" and l:
            l["status"] = "rejected"
        elif d["action"] == "manual":
            if l:
                l["status"] = "confirmed"
            else:
                nl = {"global_id": g, "calc_key": k, "conf": 1.0, "tier": "manual", "rule": "Linked by hand",
                      "page": None, "token": "", "span": None, "snippet": None, "rects": [], "status": "manual"}
                links.append(nl)
                by[(g, k)] = nl
        if d["action"] in ("confirm", "manual", "reject"):
            by[(g, k)]["decided_at"] = d["at"]
            by[(g, k)]["decided_by"] = d["actor"]
    return links


def status_of(links: list[dict]) -> str:
    live = [l for l in links if l["status"] != "rejected"]
    if not live:
        return "unmapped"
    return "confirmed" if any(l["status"] in ("confirmed", "manual") or l["conf"] >= 0.8 for l in live) else "review"


def state(st: Store, pid: int) -> dict:
    p = st.project(pid)
    mrev, crev = p["head_model_rev"], p["head_calc_rev"]
    els = st.elements(mrev) if mrev else []
    calcs = st.calcs(crev) if crev else []
    for i, c in enumerate(calcs):
        c["color"] = PALETTE[i % len(PALETTE)]
    pages = st.pages(crev) if crev else []
    run = st.latest_run(pid, mrev, crev) if (mrev and crev) else None
    links = effective_links(st, pid, run["id"], {e["global_id"] for e in els}, {c["key"] for c in calcs}) if run else []
    cedges = calcdeps.infer([{**c, "text": ""} for c in calcs], pages, links) if run else []
    per_el: dict[str, list[dict]] = {}
    for l in links:
        per_el.setdefault(l["global_id"], []).append(l)
    counts = {"confirmed": 0, "review": 0, "unmapped": 0}
    for e in els:
        e["status"] = status_of(per_el.get(e["global_id"], []))
        counts[e["status"]] += 1
    return {
        "project": dict(p), "model_rev": dict(st.revision(mrev)) if mrev else None,
        "calc_rev": dict(st.revision(crev)) if crev else None, "run": dict(run) if run else None,
        "elements": els, "edges": st.element_edges(mrev) if mrev else [], "calcs": calcs,
        "pages": [{"n": pg["n"], "text": pg["text"], "scanned": pg["scanned"], "width": pg["width"], "height": pg["height"]}
                  for pg in pages],
        "links": links, "calc_edges": cedges, "counts": counts, "revisions": st.revisions(pid),
    }


def impact_of(st: Store, pid: int, gid: str, mode: str) -> dict:
    s = state(st, pid)
    els = {e["global_id"]: e for e in s["elements"]}
    return impact.propagate(gid, mode, s["edges"], s["links"], s["calc_edges"], els)


def export(st: Store, pid: int) -> dict:
    s = state(st, pid)
    cal = {c["key"]: c for c in s["calcs"]}
    per_el: dict[str, list[dict]] = {}
    for l in s["links"]:
        per_el.setdefault(l["global_id"], []).append(l)
    return {
        "model": s["model_rev"]["source_name"] if s["model_rev"] else None,
        "model_revision": s["model_rev"]["id"] if s["model_rev"] else None,
        "calc_package": s["calc_rev"]["source_name"] if s["calc_rev"] else None,
        "calc_revision": s["calc_rev"]["id"] if s["calc_rev"] else None,
        "engine": ENGINE_VERSION,
        "calcs": [{"key": c["key"], "title": c["title"], "software": c["software"], "element_type": c["cat"],
                   "pages": c["pages"], "scanned": c["scanned"], "front_matter": c["front"]} for c in s["calcs"]],
        "calc_edges": [{"src": e["src"], "dst": e["dst"], "rules": e["rules"]} for e in s["calc_edges"]],
        "load_path": [{"src": e["src"], "dst": e["dst"], "rule": e["rule"]} for e in s["edges"]],
        "elements": [{
            "global_id": e["global_id"], "ifc_type": e["ifc_type"], "mark": e["mark"], "storey": e["storey"],
            "size": e["profile"], "status": e["status"],
            "calcs": [{"calc": l["calc_key"], "title": cal[l["calc_key"]]["title"], "page": l["page"],
                       "confidence": round(l["conf"], 2), "tier": l["tier"], "rule": l["rule"], "matched_text": l["token"],
                       "review": l["status"]} for l in sorted(per_el.get(e["global_id"], []), key=lambda l: -l["conf"])],
        } for e in s["elements"]],
    }
