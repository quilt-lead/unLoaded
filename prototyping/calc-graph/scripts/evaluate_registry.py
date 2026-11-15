"""Score the element registry REBUILT from the documents against the generator's registry TRUTH.

    uv run python scripts/evaluate_registry.py [--dir data/synthetic_v2] [--out-dir PATH] [--json-out PATH] [--rebuild]

Inputs: <dir>/registry_truth.json (synth.v2.generate, source data, read only) and
<out-dir>/registry_ingested.json (scripts/build_registry.py; --rebuild runs it first, as does a missing or
stale file). <out-dir> defaults to calcgraph.store_root.derived_for(<dir>) (data/eval/synthetic_v2/).

Node alignment: same id; else (elements) same IFC GlobalId; else (calc records, whose ids are
document-local REC:<sheet>#<n>) the ingested record whose calcs occurrence is on the same page with
the best box overlap (IoU >= 0.3), one to one.

Metrics
- occurrences, per doc kind (ifc, drawings, specs, calcs, etabs): precision / recall. A match is the
  same (aligned) node + same doc + same page + box IoU >= 0.3, or the same GlobalId for ifc; one to
  one per node and page. Recall per `how` (plan_tag, schedule_row ...) is printed, not gated.
  Truth occurrences on pages with no text layer stay in the denominator (counted separately).
- relations, per kind: precision / recall of (src, dst) after alignment.
- node recall per node type (truth kind:type) + overall node precision.
Writes <out-dir>/registry_eval.json; --json-out writes the evaluate_all.py contract
{"metrics": {...}, "gated": [...]} (every P/R except etabs, which the documents do not carry).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import Counter, defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from calcgraph.store_root import SYNTH_V2_DIR, derived_for  # noqa: E402
DOCS = ("ifc", "drawings", "specs", "calcs", "etabs")
RELS = ("frames-into", "bears-on", "connected-by", "instance-of", "specified-by", "designed-by", "detailed-by", "member-of", "feeds")


def iou(a, b) -> float:
    x0, y0, x1, y1 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    i = max(0.0, x1 - x0) * max(0.0, y1 - y0)
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - i
    return i / u if u > 0 else 0.0


def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else None
    r = tp / (tp + fn) if tp + fn else None
    return p, r


def align(truth: dict, ing: dict) -> dict:
    """ingested id -> truth id."""
    tn = {n["id"]: n for n in truth["nodes"]}
    m = {}
    gid_t = {n["global_id"]: n["id"] for n in truth["nodes"] if n.get("global_id")}
    for n in ing["nodes"]:
        if n["id"] in tn and n["kind"] != "record":
            m[n["id"]] = n["id"]
        elif n.get("global_id") in gid_t:
            m[n["id"]] = gid_t[n["global_id"]]
    # records by printed location
    cand = []
    t_occ = [(n["id"], o) for n in truth["nodes"] if n["kind"] == "record" for o in n["occurrences"] if o["doc"] == "calcs"]
    by_page = defaultdict(list)
    for tid, o in t_occ:
        by_page[o["page"]].append((tid, o))
    for n in ing["nodes"]:
        if n["kind"] != "record":
            continue
        for o in n["occurrences"]:
            if o["doc"] != "calcs":
                continue
            for tid, to in by_page.get(o["page"], []):
                v = iou(o["bbox"], to["bbox"])
                if v >= 0.3:
                    cand.append((v, n["id"], tid))
    used_i, used_t = set(), set()
    for v, iid, tid in sorted(cand, reverse=True):
        if iid in used_i or tid in used_t:
            continue
        used_i.add(iid)
        used_t.add(tid)
        m[iid] = tid
    return m


def score(truth: dict, ing: dict) -> dict:
    amap = align(truth, ing)
    tn = {n["id"]: n for n in truth["nodes"]}
    # ---------------- occurrences
    T = defaultdict(list)    # (node, doc) -> [occ]
    for n in truth["nodes"]:
        for o in n["occurrences"]:
            T[(n["id"], o["doc"])].append(o)
    I = defaultdict(list)
    n_ing = Counter()
    for n in ing["nodes"]:
        for o in n["occurrences"]:
            n_ing[o["doc"]] += 1
            if n["id"] in amap:
                I[(amap[n["id"]], o["doc"])].append(o)
    tp, n_truth = Counter(), Counter()
    how_n, how_tp = Counter(), Counter()
    unreadable = Counter()
    misses = defaultdict(Counter)
    for (nid, doc), tos in T.items():
        n_truth[doc] += len(tos)
        ios = list(I.get((nid, doc), []))
        for to in tos:
            how_n[(doc, to.get("how"))] += 1
            if to.get("text_layer") is False:
                unreadable[doc] += 1
            hit = None
            for k, io in enumerate(ios):
                if doc == "ifc":
                    ok = io.get("global_id") == to.get("global_id")
                elif doc == "etabs":
                    ok = (io.get("label"), io.get("story"), io.get("object_type")) == (to.get("label"), to.get("story"), to.get("object_type"))
                else:
                    ok = io.get("page") == to.get("page") and iou(io["bbox"], to["bbox"]) >= 0.3
                if ok:
                    hit = k
                    break
            if hit is not None:
                ios.pop(hit)
                tp[doc] += 1
                how_tp[(doc, to.get("how"))] += 1
            else:
                misses[doc][f"{to.get('how')}:{tn[nid]['kind']}:{tn[nid]['type']}"] += 1
    occ = {}
    for doc in DOCS:
        p, r = prf(tp[doc], n_ing[doc] - tp[doc], n_truth[doc] - tp[doc])
        occ[doc] = {"truth": n_truth[doc], "ingested": n_ing[doc], "matched": tp[doc], "precision": p, "recall": r,
                    "truth_on_unreadable_pages": unreadable[doc],
                    "recall_by_how": {h: f"{how_tp[(d, h)]}/{c}" for (d, h), c in sorted(how_n.items(), key=lambda x: str(x)) if d == doc},
                    "top_misses": dict(misses[doc].most_common(8))}
    # ---------------- relations
    trel = defaultdict(set)
    for r in truth["relations"]:
        trel[r["kind"]].add((r["src"], r["dst"]))
    irel = defaultdict(set)
    for r in ing["relations"]:
        irel[r["kind"]].add((amap.get(r["src"], "?" + r["src"]), amap.get(r["dst"], "?" + r["dst"])))
    rel = {}
    for k in RELS:
        t, i = trel[k], irel[k]
        p, r_ = prf(len(t & i), len(i - t), len(t - i))
        fps = Counter(f"{tn.get(s, {}).get('type', '?')}->{tn.get(d, {}).get('type', '?')}" for s, d in i - t)
        fns = Counter(f"{tn[s]['type'] if s in tn else '?'}->{tn[d]['type'] if d in tn else '?'}" for s, d in t - i)
        rel[k] = {"truth": len(t), "ingested": len(i), "matched": len(t & i), "precision": p, "recall": r_,
                  "top_false_positives": dict(fps.most_common(5)), "top_misses": dict(fns.most_common(5))}
    # ---------------- nodes
    got = set(amap.values())
    by = defaultdict(lambda: [0, 0])
    for n in truth["nodes"]:
        k = f"{n['kind']}:{n['type']}" if n["kind"] in ("element", "record") else n["kind"]
        if n["kind"] == "record":
            k = "record"
        by[k][0] += 1
        by[k][1] += n["id"] in got
    nodes = {k: {"truth": a, "found": b, "recall": b / a} for k, (a, b) in sorted(by.items())}
    extra = [n["id"] for n in ing["nodes"] if n["id"] not in amap]
    node_p = 1 - len(extra) / max(1, len(ing["nodes"]))
    return {"occurrences": occ, "relations": rel, "nodes": nodes, "node_precision": node_p,
            "unaligned_ingested_nodes": {"count": len(extra), "examples": extra[:15]}}


def metrics(res: dict) -> tuple[dict, list]:
    m, gated = {}, []
    for doc, v in res["occurrences"].items():
        for k in ("precision", "recall"):
            name = f"occ_{doc}_{k}"
            m[name] = v[k] if v[k] is not None else 0.0
            if doc != "etabs":
                gated.append(name)
    for kind, v in res["relations"].items():
        for k in ("precision", "recall"):
            name = f"rel_{kind}_{k}"
            m[name] = v[k] if v[k] is not None else 0.0
            gated.append(name)
    for t, v in res["nodes"].items():
        name = "node_recall_" + t.replace(":", "_")
        m[name] = v["recall"]
        gated.append(name)
    m["node_precision"] = res["node_precision"]
    gated.append("node_precision")
    return m, gated


def _f(v):
    return "  -  " if v is None else f"{v:5.3f}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=SYNTH_V2_DIR)
    ap.add_argument("--out-dir", default=None, help="derived outputs (default store_root.derived_for(--dir))")
    ap.add_argument("--json-out", default=None)
    ap.add_argument("--rebuild", action="store_true")
    a = ap.parse_args()
    out_dir = a.out_dir or derived_for(a.dir)
    os.makedirs(out_dir, exist_ok=True)
    tp, ip = os.path.join(a.dir, "registry_truth.json"), os.path.join(out_dir, "registry_ingested.json")
    if not os.path.exists(tp):
        raise SystemExit(f"{tp} missing - run `uv run python -m synth.v2.generate`")
    if a.rebuild or not os.path.exists(ip) or os.path.getmtime(ip) < os.path.getmtime(tp):
        p = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "build_registry.py"), "--dir", a.dir, "--out", ip],
                           capture_output=True, text=True, cwd=ROOT)
        if p.returncode:
            raise SystemExit(f"build_registry failed: {p.stderr[-1500:]}")
    truth, ing = json.load(open(tp)), json.load(open(ip))
    res = score(truth, ing)
    m, gated = metrics(res)
    res["metrics"] = m
    with open(os.path.join(out_dir, "registry_eval.json"), "w") as fh:
        json.dump(res, fh, indent=1, sort_keys=True)
    print(f"{'occurrences':14s} {'truth':>6s} {'ingest':>6s} {'match':>6s}  {'P':>5s}  {'R':>5s}")
    for doc, v in res["occurrences"].items():
        print(f"  {doc:12s} {v['truth']:6d} {v['ingested']:6d} {v['matched']:6d}  {_f(v['precision'])}  {_f(v['recall'])}"
              + (f"   ({v['truth_on_unreadable_pages']} truth on unreadable pages)" if v["truth_on_unreadable_pages"] else ""))
    for doc, v in res["occurrences"].items():
        if v["recall_by_how"]:
            print(f"    {doc} recall by how: " + ", ".join(f"{h} {s}" for h, s in v["recall_by_how"].items()))
    print(f"{'relations':14s} {'truth':>6s} {'ingest':>6s} {'match':>6s}  {'P':>5s}  {'R':>5s}")
    for k, v in res["relations"].items():
        print(f"  {k:12s} {v['truth']:6d} {v['ingested']:6d} {v['matched']:6d}  {_f(v['precision'])}  {_f(v['recall'])}")
    print("node recall by type: " + ", ".join(f"{k} {v['found']}/{v['truth']}" for k, v in res["nodes"].items()))
    print(f"node precision {res['node_precision']:.3f} ({res['unaligned_ingested_nodes']['count']} ingested nodes not in truth)")
    if a.json_out:
        with open(a.json_out, "w") as fh:
            json.dump({"metrics": m, "gated": gated}, fh, indent=1, sort_keys=True)


if __name__ == "__main__":
    main()
