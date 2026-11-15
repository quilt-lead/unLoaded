"""Redo calcs directly: re-run stale calc records with the synthetic v2 design code.

Method (labelled on every value): "calc-graph re-run - synth v2 design code (gravity statics,
PyNite frame analysis, AISC 360/341, ACI 318 checks), minimum-change re-design". Nothing here
implies ETABS / RAM / RISA ran.

- `rerun(base, change, records=None)`: re-designs the changed layout keeping every surviving
  element's size/detail unless it now fails (how an engineer re-designs after a move), then
  returns old vs new per requested record (values, UC, size/detail change, NG -> OK) in
  load-path order (beams -> girders -> columns -> footings -> connections; lateral as one job).
- Writes a NEW calc revision (id from new_revision(): never reused, so a revision folder is
  written once and never overwritten): <store>/calc_revisions/<rev>/calc_revision.pdf (revised sheets
  in the package's own style, if the calc-package writer provides write_revision) plus
  revision.json (old vs new) - and, when asked, ingests it into the revision store.
- `restore(target, reverts, of, verb)`: undo / redo of a re-run without deleting history - writes
  ANOTHER new calc revision whose content is `target`'s (or the original package when target is
  None), recording which revision it supersedes and which re-run it undoes or redoes.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from .store_root import store_path

METHOD = ("calc-graph re-run - synth v2 design code (gravity statics, PyNite frame analysis, "
          "AISC 360/341, ACI 318 checks), minimum-change re-design")
ORDER = {"area_load": 0, "criteria": 0, "beam_design": 1, "smf_beam": 5, "column_design": 2, "footing": 3, "pier": 3,
         "base_plate": 4, "grade_beam": 3, "connection": 4, "typical_detail": 4, "seismic": 5, "wind": 5,
         "frame_analysis": 5, "brace": 5, "collector": 5, "scbf_girder": 5}
LATERAL = {"seismic", "wind", "frame_analysis", "brace", "collector", "smf_beam", "scbf_girder"}


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


def rerun(base: dict, change: dict, records: list[str] | None = None, write_pages: bool = True, progress=None) -> dict:
    """Re-run the design for `change` and compare the requested records (default: every record
    whose value moved). Returns {rev_id, method, order, results, lateral_job, files, summary (with
    seconds and per-stage timings)}. progress(stage, done, total), when given, is called as the
    stages run (design, package_sheets, math, layout)."""
    from synth.v2.generate import build, _clean
    t = time.time()
    if progress:
        progress("design", 0, 1)
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
    content_key = hashlib.sha1(json.dumps({"change": change, "records": order}, sort_keys=True).encode()).hexdigest()[:10]
    key, rev_id, rdir = new_revision({"change": change, "records": order})
    files: dict = {}
    pages: dict = {}
    timings = {"design_and_compare": round(time.time() - t, 1)}
    out = {"rev_id": rev_id, "content_key": content_key,
           "created_at": datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M ET"),
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
    if write_pages:
        _write_pages(out, base, exp, d_new, [r for r in order if r in new], key, rdir, files, pages, timings, progress)
    out["summary"]["seconds"] = round(time.time() - t, 1)
    out["summary"]["timings"] = timings
    for r in results:
        if r["record"] in pages:
            r["new_page"] = pages[r["record"]]
    with open(os.path.join(rdir, "revision.json"), "x") as fh:
        json.dump(_clean(out), fh, indent=1)
    with open(os.path.join(rdir, "design.json"), "x") as fh:
        json.dump(exp, fh, sort_keys=True)
    out["design_path"] = os.path.join(rdir, "design.json")
    return _clean(out)


def _write_pages(out: dict, base: dict, exp: dict, d_new: dict, recs: list[str], key: str, rdir: str, files: dict,
                 pages: dict, timings: dict, progress=None) -> None:
    """Both page sets of a re-run, at the same time on different cores: the package-style revised
    sheets (calc_pdf_v2.write_revision, in a worker process: recalc_package.py) and the handcalcs
    re-run sheets (recalc_pages: math here, layout in worker processes). Each failure is recorded in
    `files` under its own key (page_error / rerun_sheets_error) and never hides the other set or the
    values. Every record of a re-run that wrote its sheets carries new_page.rerun_sheet; a record
    whose block could not be placed says why (rerun_sheet.missing)."""
    import tempfile
    from synth.v2 import calc_pdf_v2
    from . import recalc_package
    t0 = time.time()
    pkg = None
    job_dir = tempfile.mkdtemp(prefix="recalc_package_")
    job = os.path.join(job_dir, "job.pickle")
    pdf = os.path.join(rdir, "calc_revision.pdf")
    if hasattr(calc_pdf_v2, "write_revision"):
        try:
            pkg = recalc_package.start({"exp": exp, "d_new": d_new, "recs": recs, "pdf": pdf, "rev_label": f"Rev {key[:4]}",
                                        "base": base}, job)
        except Exception as e:
            files["page_error"] = f"{type(e).__name__}: {e}"
    else:
        files["note"] = "calc package writer has no write_revision yet - values only"
    sheet_pages: dict = {}
    try:   # handcalcs re-run sheets (math rendered from the code that recomputes each check)
        from . import recalc_pages
        hpdf = os.path.join(rdir, "rerun_sheets.pdf")
        hp, lay = recalc_pages.render(out, base, exp, hpdf, d_new["topo"].grade_beams, progress=progress)
        files["rerun_sheets_pdf"] = hpdf
        files["rerun_sheets_layout"] = lay
        for r in out["results"]:
            v = hp.get(r["record"])
            if v is None:
                v = {"page": None, "missing": "no block was built for this record"}
            elif v.get("page") is None:
                v = {**v, "missing": "the record's block was not found in the laid-out sheets"}
            sheet_pages[r["record"]] = v
    except Exception as e:   # incl. ImportError: a module that fails to import is a failure, said out loud
        files["rerun_sheets_error"] = f"{type(e).__name__}: {e}"
    timings["rerun_sheets"] = round(time.time() - t0, 1)
    pkg_pages: dict = {}
    if pkg is not None:
        if progress:
            progress("package_sheets", 0, 1)
        try:   # pages are a convenience; the values are the result
            pkg_pages = recalc_package.finish(pkg, job)
            files["calc_revision_pdf"] = pdf
        except Exception as e:
            files["page_error"] = f"{type(e).__name__}: {e}"
        timings["package_sheets"] = round(time.time() - t0, 1)
    import shutil
    shutil.rmtree(job_dir, ignore_errors=True)
    for rid_ in set(pkg_pages) | set(sheet_pages):
        pages[rid_] = {**(pkg_pages.get(rid_) or {}), **({"rerun_sheet": sheet_pages[rid_]} if rid_ in sheet_pages else {})}


def revisions_root() -> str:
    """<store>/calc_revisions (store_root.py: CALCGRAPH_STORE) - every calc revision read and write
    goes through here, so a run against a copied store never writes the real one. (The one-time move
    from the pre-store_root data/synthetic_v2/revisions folder ran on 2026-11-14 and was deleted: the
    source data dir is generator-only, store_root.install_source_write_guard.)"""
    return store_path("calc_revisions")


def revision_dir(rev_id: str) -> str:
    """The folder of calc revision `rev_id` (basename only: an id can never point outside the root)."""
    return os.path.join(revisions_root(), os.path.basename(rev_id))


def new_revision(seed: dict) -> tuple[str, str, str]:
    """Allocate a NEW calc revision: (key, rev_id, folder). The ONLY way a calc revision id is made.

    Revisions are immutable, so an id names one write, never one piece of content: the id hashes
    the seed (what was asked) together with the creation instant, and the folder is created with
    exist_ok=False, so a re-run of the exact same move gets its own revision instead of landing in
    (and overwriting) an earlier one. A collision on the 10-hex key retries with a new instant.
    Identical content is still recognisable through the revision's `content_key`."""
    os.makedirs(revisions_root(), exist_ok=True)
    while True:
        key = hashlib.sha1(json.dumps({"seed": seed, "t": time.time_ns()}, sort_keys=True,
                                      default=str).encode()).hexdigest()[:10]
        rev_id = f"calcrev-{key}"
        rdir = revision_dir(rev_id)
        try:
            os.makedirs(rdir)
        except FileExistsError:
            continue
        return key, rev_id, rdir


def _read_rev(rev_id: str) -> dict:
    p = os.path.join(revision_dir(rev_id), "revision.json")
    if not os.path.exists(p):
        raise KeyError(rev_id)
    return json.load(open(p))


def restore(target: str | None, reverts: str, of: str, verb: str) -> dict:
    """Undo / redo of a re-run as a NEW calc revision (nothing is deleted or rewritten).

    target  = the calc revision whose content is restored (None = the original calc package, i.e.
              no re-run); reverts = the calc revision this one supersedes (the current one);
    of      = the re-run being undone or redone; verb = "undo" | "redo".
    The new revision copies target's results, summary, change and pages (hard links when the
    filesystem allows), so it reads exactly like the revision it restores."""
    import shutil
    if verb not in ("undo", "redo"):
        raise ValueError("verb must be 'undo' or 'redo'")
    _read_rev(reverts)
    _read_rev(of)
    src = _read_rev(target) if target else None
    _, rev_id, rdir = new_revision({"target": target, "reverts": reverts, "of": of, "verb": verb})
    files: dict = {}
    if src:
        sdir = revision_dir(target)
        for name in sorted(os.listdir(sdir)):
            if name == "revision.json":
                continue
            a, b = os.path.join(sdir, name), os.path.join(rdir, name)
            try:
                os.link(a, b)
            except OSError:
                shutil.copy2(a, b)
        files = {k: (os.path.join(rdir, os.path.basename(v)) if isinstance(v, str) and v.startswith(sdir) else v)
                 for k, v in src.get("files", {}).items()}
    zero = {"records": 0, "resized": 0, "ng_to_ok": 0, "still_ng": 0, "new": 0, "removed": 0, "seconds": 0}
    out = {"rev_id": rev_id, "content_key": (src or {}).get("content_key"),
           "created_at": datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M ET"),
           "change": src["change"] if src else {}, "method": (src or {}).get("method", METHOD),
           "order_rule": (src or {}).get("order_rule", ""), "results": (src or {}).get("results", []),
           "summary": src["summary"] if src else zero, "files": files,
           "restore": {"verb": verb, "of": of, "restored": target, "parent": reverts}}
    with open(os.path.join(rdir, "revision.json"), "x") as fh:
        json.dump(out, fh, indent=1)
    return out


def list_revisions() -> list[dict]:
    """Oldest first, by the creation time each revision records (created_at, US Eastern, to the
    minute), then by when its revision.json was written (rev ids are content hashes, so their names
    say nothing about order). created_at first: a file's mtime does not survive a copy or a move."""
    d = revisions_root()
    paths = [os.path.join(d, n, "revision.json") for n in (os.listdir(d) if os.path.isdir(d) else [])]
    revs = [(json.load(open(p)), os.path.getmtime(p)) for p in paths if os.path.exists(p)]
    out = []
    for r, _ in sorted(revs, key=lambda x: (x[0].get("created_at") or "", x[1])):
        out.append({"rev_id": r["rev_id"], "content_key": r.get("content_key"), "created_at": r["created_at"], "change": r["change"], "summary": r["summary"],
                    "files": r["files"], **({"restore": r["restore"]} if r.get("restore") else {})})
    return out
