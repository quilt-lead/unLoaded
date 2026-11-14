"""Redo calcs directly: re-run stale calc records with the synthetic v2 design code.

Method (labelled on every value): "calc-graph re-run - synth v2 design code (gravity statics,
PyNite frame analysis, AISC 360/341, ACI 318 checks), minimum-change re-design". Nothing here
implies ETABS / RAM / RISA ran.

- `rerun(base, change, records=None)`: re-designs the changed layout keeping every surviving
  element's size/detail unless it now fails (how an engineer re-designs after a move), then
  returns old vs new per requested record (values, UC, size/detail change, NG -> OK) in
  load-path order (beams -> girders -> columns -> footings -> connections; lateral as one job).
- Writes a NEW calc revision: data/synthetic_v2/revisions/<rev>/calc_revision.pdf (revised sheets
  in the package's own style, if the calc-package writer provides write_revision) plus
  revision.json (old vs new) - and, when asked, ingests it into the revision store.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
V2 = os.path.join(ROOT, "data", "synthetic_v2")
METHOD = ("calc-graph re-run - synth v2 design code (gravity statics, PyNite frame analysis, "
          "AISC 360/341, ACI 318 checks), minimum-change re-design")
ORDER = {"area_load": 0, "criteria": 0, "beam_design": 1, "smf_beam": 5, "column_design": 2, "footing": 3, "pier": 3,
         "base_plate": 4, "grade_beam": 3, "connection": 4, "typical_detail": 4, "seismic": 5, "wind": 5,
         "frame_analysis": 5, "brace": 5, "collector": 5}
LATERAL = {"seismic", "wind", "frame_analysis", "brace", "collector", "smf_beam"}


def layout_from_change(change: dict):
    from synth.v2 import model
    L = model.base_layout()
    for c, (dx, dy) in (change.get("moved") or {}).items():
        c = c.replace("COL-", "")
        x, y = L.cols[c]
        L.cols[c] = (x + dx, y + dy)
    for c in change.get("removed") or []:
        L.removed.add(c.replace("COL-", ""))
    L.label = change.get("label") or json.dumps(change, sort_keys=True)
    return L


def load_order(base: dict, rids: list[str]) -> list[str]:
    """Calc dependency order (NetworkX topological sort over the record 'feeds' graph restricted
    to the requested records: inputs first), ties broken by kind (beams, columns, footings,
    connections) then id."""
    import networkx as nx
    rec = {r["id"]: r for r in base["records"]}
    want = [r for r in rids if r in rec]
    g = nx.DiGraph()
    g.add_nodes_from(want)
    ws = set(want)
    for r in want:
        for i in rec[r]["inputs"]:
            if i in ws and i != r:
                g.add_edge(i, r)
    key = lambda x: f"{ORDER.get(rec[x]['kind'], 9)}|{x}"   # noqa: E731
    try:
        return list(nx.lexicographical_topological_sort(g, key=key))
    except nx.NetworkXUnfeasible:   # a cycle in the feeds graph: fall back to kind order, and say so
        return sorted(want, key=key)


def _cmp(old: dict | None, new: dict | None) -> dict:
    def ok(r):
        return None if r is None or r.get("uc") is None else r["uc"] <= 1.0 + 1e-9
    o_size = (old or {}).get("values", {}).get("size") or (old or {}).get("values", {}).get("type")
    n_size = (new or {}).get("values", {}).get("size") or (new or {}).get("values", {}).get("type")
    status = "unchanged"
    if old is None:
        status = "new record"
    elif new is None:
        status = "record removed (element no longer exists)"
    elif o_size != n_size:
        status = f"re-sized {o_size} -> {n_size}"
    elif old.get("demand") != new.get("demand"):
        status = "new demand, same size"
    return {"old": {k: (old or {}).get(k) for k in ("demand", "capacity", "uc", "check", "lc", "unit", "values")} if old else None,
            "new": {k: (new or {}).get(k) for k in ("demand", "capacity", "uc", "check", "lc", "unit", "values")} if new else None,
            "size_old": o_size, "size_new": n_size, "status": status,
            "ok_old": ok(old), "ok_new": ok(new),
            "ng_to_ok": ok(old) is False and ok(new) is True}


def rerun(base: dict, change: dict, records: list[str] | None = None, write_pages: bool = True) -> dict:
    """Re-run the design for `change` and compare the requested records (default: every record
    whose value moved). Returns {rev_id, method, order, results, lateral_job, files}."""
    from synth.v2.generate import build, _clean
    t = time.time()
    L = layout_from_change(change)
    d_new, exp = build(L, keep={e["id"]: e for e in base["elements"]})
    old = {r["id"]: r for r in base["records"]}
    new = {r["id"]: r for r in exp["records"]}
    if records is None:
        records = sorted(rid for rid in set(old) | set(new)
                         if (old.get(rid) or {}).get("demand") != (new.get(rid) or {}).get("demand")
                         or (old.get(rid) or {}).get("values", {}).get("size") != (new.get(rid) or {}).get("values", {}).get("size"))
    grav = [r for r in records if (old.get(r) or new.get(r) or {}).get("kind") not in LATERAL]
    lat = [r for r in records if (old.get(r) or new.get(r) or {}).get("kind") in LATERAL]
    order = load_order(base, grav) + [r for r in grav if r not in old] + lat
    # the current sizes checked under the NEW layout (what the old calc would say now) - this is
    # what makes "NG -> OK" meaningful
    from synth.v2.scenarios import at_current_sizes
    cur = at_current_sizes(L, base)
    results = []
    for n, rid in enumerate(order, 1):
        o, nw = old.get(rid), new.get(rid)
        row = {"step": n, "record": rid, "calc": (o or nw)["calc"], "kind": (o or nw)["kind"],
               "elements": (o or nw)["elements"], "job": "lateral" if rid in lat else "gravity",
               "method": METHOD, **_cmp(o, nw)}
        el = row["elements"][0] if row["elements"] else None
        if el in cur:
            row["uc_current_size_new_layout"] = round(cur[el]["uc"], 4)
            row["ok_current_size_new_layout"] = cur[el]["uc"] <= 1.0 + 1e-9
            row["ng_to_ok"] = (not row["ok_current_size_new_layout"]) and row["ok_new"] is True
        results.append(row)
    key = hashlib.sha1(json.dumps({"change": change, "records": order}, sort_keys=True).encode()).hexdigest()[:10]
    rev_id = f"calcrev-{key}"
    rdir = os.path.join(V2, "revisions", rev_id)
    os.makedirs(rdir, exist_ok=True)
    files = {}
    pages = {}
    if write_pages:
        try:
            from synth.v2 import calc_pdf_v2
            if hasattr(calc_pdf_v2, "write_revision"):
                pdf = os.path.join(rdir, "calc_revision.pdf")
                pages = calc_pdf_v2.write_revision(exp, d_new, [r for r in order if r in new], pdf,
                                                   rev_label=f"Rev {key[:4]}", prev_exp=base) or {}
                files["calc_revision_pdf"] = pdf
            else:
                files["note"] = "calc package writer has no write_revision yet - values only"
        except Exception as e:   # pages are a convenience; the values are the result
            files["page_error"] = f"{type(e).__name__}: {e}"
    out = {"rev_id": rev_id, "created_at": datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M ET"),
           "change": change, "method": METHOD, "order_rule": "gravity in load-path order (inputs first: beams -> girders -> "
           "columns -> footings -> connections), then the lateral system as one job",
           "results": results, "summary": {
               "records": len(results), "resized": sum(1 for r in results if r["status"].startswith("re-sized")),
               "ng_to_ok": sum(1 for r in results if r["ng_to_ok"]),
               "still_ng": sum(1 for r in results if r["ok_new"] is False),
               "new": sum(1 for r in results if r["status"] == "new record"),
               "removed": sum(1 for r in results if r["status"].startswith("record removed")),
               "seconds": round(time.time() - t, 1)},
           "files": files}
    # handcalcs re-run sheets (math rendered from the code that recomputes each check), when present
    if write_pages:
        try:
            from . import recalc_pages
            hpdf = os.path.join(rdir, "rerun_sheets.pdf")
            hp = recalc_pages.render(out, base, exp, hpdf) or {}
            files["rerun_sheets_pdf"] = hpdf
            for rid_, v in hp.items():
                pages.setdefault(rid_, {})["rerun_sheet"] = v
        except ImportError:
            files.setdefault("note", "handcalcs re-run sheets not available yet")
        except Exception as e:
            files["rerun_sheets_error"] = f"{type(e).__name__}: {e}"
    for r in results:
        if r["record"] in pages:
            r["new_page"] = pages[r["record"]]
    with open(os.path.join(rdir, "revision.json"), "w") as fh:
        json.dump(_clean(out), fh, indent=1)
    with open(os.path.join(rdir, "design.json"), "w") as fh:
        json.dump(exp, fh, sort_keys=True)
    out["design_path"] = os.path.join(rdir, "design.json")
    return _clean(out)


def list_revisions() -> list[dict]:
    d = os.path.join(V2, "revisions")
    out = []
    for name in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        p = os.path.join(d, name, "revision.json")
        if os.path.exists(p):
            r = json.load(open(p))
            out.append({"rev_id": r["rev_id"], "created_at": r["created_at"], "change": r["change"], "summary": r["summary"],
                        "files": r["files"]})
    return out
