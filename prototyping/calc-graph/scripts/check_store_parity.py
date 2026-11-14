"""Parity gate for the revision store (F2): capture every API response the current frontend
reads, from a FROZEN copy of the inputs, as canonical JSON; or compare two captures.

    uv run python scripts/check_store_parity.py freeze <dir>          # copy data/store + data/sets
                                                                      # (no render cache) to <dir>/inputs
    uv run python scripts/check_store_parity.py freeze-decisions <inputs> <dir2>  # + a human decision log
    uv run python scripts/check_store_parity.py snapshot <inputs> <out> [--after]
    uv run python scripts/check_store_parity.py compare <before> <after>

`snapshot` copies <inputs> to a temp dir first, so the frozen inputs are never touched, points
CALCGRAPH_STORE / CALCGRAPH_SETS at the copy, imports calcgraph.api and calls the endpoint
functions in-process (no server, no httpx). `freeze-decisions` writes a second frozen input whose
store carries an append-only decision log posted through the (pre-F2) API, so the migration of
that history is part of the gate. `--after` (the new store only) proves the drawing-set responses come from the store:
it imports the set outputs into the store, then points the set builders at an EMPTY dir before
capturing. JSON responses are compared as canonical JSON; files and PNGs by sha256.

Captures are DERIVED FROM COPYRIGHTED PDFs (the drawing-set responses): write them only to a
gitignored dir (data/eval/...) or a scratchpad, never into the repo.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
# CALCGRAPH_BACKEND: capture with another checkout of backend/ (e.g. `git archive HEAD` for "before")
sys.path.insert(0, os.environ.get("CALCGRAPH_BACKEND", os.path.join(ROOT, "backend")))

DECISIONS = [  # (auto-link index in state, action); "manual" also links a pair the mapper did not link
    (0, "confirm"), (1, "reject"), (2, "confirm"), (0, "undo"), (3, "manual-unlinked"), (4, "reject"), (4, "undo"),
    (5, "confirm"),
]


def canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


class _Req:
    class client:  # noqa: N801 - mimics starlette Request.client
        host = "127.0.0.1"


def _body(resp):
    """Normalise an endpoint return value to something comparable."""
    from fastapi.responses import FileResponse, JSONResponse, Response
    if isinstance(resp, FileResponse):
        data = open(resp.path, "rb").read()
        if resp.media_type == "application/json":
            return json.loads(data)
        return {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data), "media_type": resp.media_type}
    if isinstance(resp, JSONResponse):
        return json.loads(resp.body)
    if isinstance(resp, Response):
        return {"sha256": hashlib.sha256(resp.body).hexdigest(), "media_type": resp.media_type}
    from fastapi.encoders import jsonable_encoder
    return jsonable_encoder(resp)


def freeze(dst: str) -> None:
    inp = os.path.join(dst, "inputs")
    if os.path.exists(inp):
        raise SystemExit(f"{inp} exists - freeze once")
    store = os.environ.get("CALCGRAPH_STORE", os.path.join(ROOT, "data", "store"))
    sets = os.environ.get("CALCGRAPH_SETS", os.path.join(ROOT, "data", "sets"))
    shutil.copytree(store, os.path.join(inp, "store"))
    shutil.copytree(sets, os.path.join(inp, "sets"), ignore=shutil.ignore_patterns("cache"))
    print(f"froze {store} and {sets} -> {inp}")


def freeze_decisions(inputs: str, dst: str) -> None:
    """Copy frozen inputs to dst and post DECISIONS through the API of the code on sys.path
    (run it with CALCGRAPH_BACKEND = the pre-F2 checkout so the log is written by the old store)."""
    if os.path.exists(dst):
        raise SystemExit(f"{dst} exists")
    shutil.copytree(inputs, dst)
    os.environ["CALCGRAPH_STORE"] = os.path.join(dst, "store")
    os.environ["CALCGRAPH_SETS"] = os.path.join(dst, "sets")
    from calcgraph import api
    pid = 1
    s = _body(api.get_state(pid))
    links = [l for l in s["links"] if l["status"] == "auto"]
    linked = {(l["global_id"], l["calc_key"]) for l in s["links"]}
    calcs = [c["key"] for c in s["calcs"] if not c["front"] and not c["scanned"]]
    for i, action in DECISIONS:
        if action == "manual-unlinked":
            g = links[i]["global_id"]
            k = next(c for c in calcs if (g, c) not in linked)
            api.decide(pid, api.DecisionIn(global_id=g, calc_key=k, action="manual", actor="parity", note="by hand"))
        else:
            l = links[i]
            api.decide(pid, api.DecisionIn(global_id=l["global_id"], calc_key=l["calc_key"], action=action,
                                           actor="parity", note=f"{action} link {i}"))
    print(f"posted {len(DECISIONS)} decisions into {dst}/store")


def snapshot(inputs: str, out: str, after: bool) -> None:
    tmp = tempfile.mkdtemp(prefix="cg-parity-")
    shutil.copytree(os.path.join(inputs, "store"), os.path.join(tmp, "store"))
    shutil.copytree(os.path.join(inputs, "sets"), os.path.join(tmp, "sets"))
    os.environ["CALCGRAPH_STORE"] = os.path.join(tmp, "store")
    os.environ["CALCGRAPH_SETS"] = os.path.join(tmp, "sets")
    from calcgraph import api, set_pipeline
    if after:
        from calcgraph import revstore
        n = revstore.import_sets(api.st, os.path.join(tmp, "sets"))
        print(f"imported {n} set(s) into the store; set builders now point at an empty dir")
        empty = os.path.join(tmp, "empty-sets")
        os.makedirs(empty)
        set_pipeline.SETS_DIR = empty
    caps: dict[str, object] = {}

    def cap(name, fn, *a, **kw):
        try:
            caps[name] = _body(fn(*a, **kw))
        except Exception as e:  # noqa: BLE001 - an error is a captured outcome too
            caps[name] = {"error": type(e).__name__, "detail": getattr(e, "detail", str(e))}

    pid = 1
    cap("projects", api.projects)
    cap("state", api.get_state, pid)
    cap("revisions", api.revisions, pid)
    cap("decisions", api.decisions, pid)
    cap("export", api.export, pid)
    revs = [r["id"] for r in caps["revisions"]["revisions"]] if isinstance(caps["revisions"], dict) else []
    models = [r["id"] for r in caps["revisions"]["revisions"] if r["kind"] == "model"] if revs else []
    for a, b in zip(models, models[1:]):
        cap(f"compare {a}-{b}", api.compare, pid, a, b)
    els = caps["state"].get("elements", []) if isinstance(caps["state"], dict) else []
    for e in els[:3] + [x for x in els if x["cat"] == "Column"][:2]:
        for mode in ("change", "remove"):
            cap(f"impact {e['global_id']} {mode}", api.impact, pid, e["global_id"], mode)
    for r in revs:
        cap(f"revision file {r}", api.revision_file, r)
    calc_revs = [r["id"] for r in caps["revisions"]["revisions"] if r["kind"] == "calcs"] if revs else []
    for r in calc_revs[:1]:
        cap(f"page png {r} 1", api.page_png, r, 1)
        cap(f"page png {r} 3 hl", api.page_png, r, 3, hl="72,72,200,90;100,300,300,320")
    cap("sets", api.sets)
    for sset in caps["sets"] if isinstance(caps["sets"], list) else []:
        sid = sset["id"]
        cap(f"set {sid} graph", api.set_graph, sid)
        cap(f"set {sid} integrated", api.set_integrated, sid)
        cap(f"set {sid} model.ifc", api.set_model_ifc, sid, _Req())
        for doc in sset["docs"]:
            cap(f"set {sid} doc {doc} file", api.set_doc_file, sid, doc, _Req())
    os.makedirs(out, exist_ok=True)
    for name, body in caps.items():
        with open(os.path.join(out, name.replace("/", "_").replace(" ", "__") + ".json"), "w") as fh:
            fh.write(canon(body))
    print(f"captured {len(caps)} responses -> {out}")
    shutil.rmtree(tmp, ignore_errors=True)


def _first_diff(a, b, path="$"):
    if type(a) is not type(b):
        return f"{path}: {type(a).__name__} vs {type(b).__name__}"
    if isinstance(a, dict):
        for k in sorted(a.keys() | b.keys()):
            if k not in a or k not in b:
                return f"{path}.{k}: only in {'after' if k not in a else 'before'}"
            d = _first_diff(a[k], b[k], f"{path}.{k}")
            if d:
                return d
    elif isinstance(a, list):
        if len(a) != len(b):
            return f"{path}: length {len(a)} vs {len(b)}"
        for i, (x, y) in enumerate(zip(a, b)):
            d = _first_diff(x, y, f"{path}[{i}]")
            if d:
                return d
    elif a != b:
        return f"{path}: {str(a)[:80]!r} vs {str(b)[:80]!r}"
    return None


# Intended, ADDITIVE differences (F2): the IFC export now carries the evidence the store holds.
# compare() removes exactly these keys from the AFTER capture (and fails if one is missing there),
# so everything else in the response must still be identical.
INTENDED_ADDITIONS = {
    "export.json": ["producers", "calcs[].title_box", "calc_edges[].evidence", "elements[].calcs[].evidence"],
}


def _strip(obj, path: list[str], fname: str):
    head, rest = path[0], path[1:]
    if head.endswith("[]"):
        for item in obj.get(head[:-2], []):
            if rest:
                _strip(item, rest, fname)
        return
    if not rest:
        if head not in obj:
            raise SystemExit(f"{fname}: intended addition {head!r} missing from the after capture")
        del obj[head]
    else:
        _strip(obj[head], rest, fname)


def compare(before: str, after: str) -> int:
    fa, fb = set(os.listdir(before)), set(os.listdir(after))
    bad = 0
    for f in sorted(fa | fb):
        if f not in fa or f not in fb:
            print(f"ONLY IN {'after' if f not in fa else 'before'}: {f}")
            bad += 1
            continue
        a, b = open(os.path.join(before, f)).read(), open(os.path.join(after, f)).read()
        if f in INTENDED_ADDITIONS:
            bj = json.loads(b)
            for spec in INTENDED_ADDITIONS[f]:
                parts = spec.split(".")
                _strip(bj, parts, f)
            b = canon(bj)
            print(f"{f}: removed intended additions {INTENDED_ADDITIONS[f]} before comparing")
        if a == b:
            continue
        bad += 1
        print(f"DIFF {f}: {_first_diff(json.loads(a), json.loads(b))}")
    print(f"{len(fa & fb) - (bad if bad else 0)} identical of {len(fa | fb)}; {bad} differ")
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("freeze")
    f.add_argument("dir")
    s = sub.add_parser("snapshot")
    s.add_argument("inputs")
    s.add_argument("out")
    s.add_argument("--after", action="store_true")
    fd = sub.add_parser("freeze-decisions")
    fd.add_argument("inputs")
    fd.add_argument("dst")
    c = sub.add_parser("compare")
    c.add_argument("before")
    c.add_argument("after")
    a = ap.parse_args()
    if a.cmd == "freeze":
        freeze(a.dir)
    elif a.cmd == "snapshot":
        snapshot(a.inputs, a.out, a.after)
    elif a.cmd == "freeze-decisions":
        freeze_decisions(a.inputs, a.dst)
    else:
        return compare(a.before, a.after)
    return 0


if __name__ == "__main__":
    sys.exit(main())
