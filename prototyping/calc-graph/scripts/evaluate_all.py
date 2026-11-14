"""Run every evaluation, print one scorecard, exit non-zero on a regression vs the stored baseline.

  uv run python scripts/evaluate_all.py                    # everything whose inputs exist locally
  uv run python scripts/evaluate_all.py --synthetic-only   # CI: no drawing-set stages (no PDFs there)
  uv run python scripts/evaluate_all.py --update-baseline  # accept the current numbers as the baseline

Stages (a stage whose inputs are missing is SKIPPED, never failed). Synthetic v2 is the centre;
v1 and Dana Point stages are DEPRECATED (retiring once v2 documents ingest end to end):
  v2_design        synth v2 ground truth self-consistency (AISC table verified, no infeasible members,
                   no clashes, every member has a design record); generates data/synthetic_v2 if absent
  v2_ifc           v2 model.ifc through the production ifc_ingest + loadpath vs design.json: element P/R,
                   profile + storey accuracy, load-path P/R (frames-into + bears-on), directed and not
  v2_documents     scripts/evaluate_v2_docs.py when it exists (v2 drawings / calc package / specs through
                   the generic pipeline); else lists which v2 PDFs exist
  synthetic_v1     [deprecated] scripts/evaluate.py on the v1 synthetic package (segmentation, design-mapping P/R,
                   xref, load path, calc edges, revisions)
  ai_step          scripts/check_llm_imports.py + scripts/check_ai_step.py (pass/fail)
  copyright        scripts/check_no_copyrighted.py --tracked (pass/fail)
  move_answer_key  scripts/evaluate_move.py when it exists (contract below); else reports whether the
                   synth v2 answer key exists
  registry         scripts/evaluate_registry.py when it exists (contract below); else whether the v2
                   registry truth exists
  set_coverage     [deprecated] drawing-set coverage numbers from data/sets/<sid>/graph.json (info, not gated)
  calc_spot        [deprecated] calc-record spot checks: data/labels/<sid>/calc_spot_checks.json vs calc_records.json
  slice_tags       [deprecated] hand-labelled tags (data/labels/<sid>/tags_<sheet>.json) vs pipeline elements:
                   tag precision / recall, type accuracy, size-text accuracy, grid agreement
  slice_links      [deprecated] hand-judged element<->calc links (data/labels/<sid>/links_judged.json) vs the
                   current graph: precision of judged links still emitted, correct links retained

Optional evaluator contract (evaluate_v2_docs.py / evaluate_move.py / evaluate_registry.py): accept `--json-out PATH` and
write {"metrics": {name: number}, "gated": [names that are higher-is-better]}; exit 0.

Gating: a metric is compared with the baseline when it is listed as gated; a drop larger than
--tolerance (default 0.005 absolute) is a regression; a pass/fail check that passed in the baseline
and fails now is a regression. Metrics of skipped stages are not compared. The baseline file
(eval/baseline.json) holds numbers only - no drawing text - and is committed.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PY = sys.executable
BASELINE = os.path.join(ROOT, "eval", "baseline.json")
LABELS = os.path.join(ROOT, "data", "labels")
SETS = os.path.join(ROOT, "data", "sets")


class Skip(Exception):
    pass


def run(cmd: list[str], timeout: int = 1800) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout)


def prf(tp: int, fp: int, fn: int) -> tuple[float | None, float | None]:
    return (tp / (tp + fp) if tp + fp else None, tp / (tp + fn) if tp + fn else None)


# ----------------------------------------------------------------------------- stages
V2 = os.path.join(ROOT, "data", "synthetic_v2")
V2_PHYSICAL = ("beam", "girder", "column", "pier", "footing", "grade_beam", "brace", "deck", "connection")


def _v2_design(a) -> dict:
    p = os.path.join(V2, "design.json")
    if not os.path.exists(p) or a.regen_v2:
        g = run([PY, "-m", "synth.v2.generate", "--out", V2])
        if g.returncode:
            raise RuntimeError(f"synth.v2.generate exit {g.returncode}: {g.stderr[-600:]}")
    return json.load(open(p))


def st_v2_design(a) -> dict:
    """Generator self-consistency: the ground truth every other v2 stage is scored against."""
    d = _v2_design(a)
    phys = [e for e in d["elements"] if e["type"] in V2_PHYSICAL and e["type"] != "connection"]
    designed = {r["src"] for r in d["relations"] if r["kind"] == "designed-by"}
    m = {"elements": len(d["elements"]), "relations": len(d["relations"]), "calc_records": len(d["records"]),
         "members_with_design_record": sum(e["id"] in designed for e in phys) / max(1, len(phys))}
    checks = {"aisc_table_verified": all(v["ok"] for v in d["aisc_verification"]),
              "no_infeasible_members": not d["infeasible"], "no_clashes": not d["clashes"]}
    return {"metrics": m, "gated": ["members_with_design_record"], "checks": checks}


def st_v2_ifc(a) -> dict:
    """Ingest the v2 model.ifc with the PRODUCTION ifc_ingest + loadpath and score against design.json."""
    d = _v2_design(a)
    sys.path.insert(0, os.path.join(ROOT, "backend"))
    from calcgraph import ifc_ingest, loadpath
    els = ifc_ingest.read_ifc(os.path.join(V2, "model.ifc"))["elements"]
    got = {e["global_id"]: e for e in els}
    truth = {e["global_id"]: e for e in d["elements"] if e["type"] in V2_PHYSICAL and e.get("global_id")}
    tp = got.keys() & truth.keys()
    ep, er = prf(len(tp), len(got.keys() - truth.keys()), len(truth.keys() - got.keys()))
    sized = [g for g in tp if truth[g].get("size")]
    prof_ok = sum(ifc_ingest.norm_profile(got[g].get("profile") or "") == ifc_ingest.norm_profile(truth[g]["size"]) for g in sized)
    lvl = {e["id"].split(":", 1)[1]: e["name"] for e in d["elements"] if e["type"] == "level"}
    leveled = [g for g in tp if truth[g].get("level")]
    lvl_ok = sum(got[g].get("storey") == lvl.get(truth[g]["level"]) for g in leveled)
    gid = {e["id"]: e.get("global_id") for e in d["elements"]}
    true_lp = {(gid[r["src"]], gid[r["dst"]]) for r in d["relations"]
               if r["kind"] in ("frames-into", "bears-on") and gid.get(r["src"]) and gid.get(r["dst"])}
    # the load path proper; connected-by edges are the connection nodes on it (not frames-into / bears-on)
    pred_lp = {(e["src"], e["dst"]) for e in loadpath.infer(els) if e.get("kind") in ("frames-into", "bears-on")}
    lp, lr = prf(len(pred_lp & true_lp), len(pred_lp - true_lp), len(true_lp - pred_lp))
    und = lambda s: {frozenset(x) for x in s}
    ulp, ulr = prf(len(und(pred_lp) & und(true_lp)), len(und(pred_lp) - und(true_lp)), len(und(true_lp) - und(pred_lp)))
    by = Counter(truth[g]["type"] for g in truth.keys() - got.keys())
    typ = {e.get("global_id"): e["type"] for e in d["elements"]}
    kinds = defaultdict(lambda: [0, 0])
    for s_, d_ in true_lp:
        k = f"{typ[s_]}->{typ[d_]}"
        kinds[k][0] += 1
        kinds[k][1] += (s_, d_) in pred_lp
    fps = Counter(f"{typ.get(s_, '?')}->{typ.get(d_, '?')}" for s_, d_ in pred_lp - true_lp)
    m = {"element_precision": ep, "element_recall": er, "profile_accuracy": prof_ok / len(sized) if sized else None,
         "storey_accuracy": lvl_ok / len(leveled) if leveled else None,
         "load_path_precision": lp, "load_path_recall": lr,
         "load_path_undirected_precision": ulp, "load_path_undirected_recall": ulr}
    notes = [f"{len(truth)} physical truth elements, {len(els)} ingested; missing by type {dict(by) or '-'}; "
             f"load path truth = frames-into + bears-on ({len(true_lp)}), predicted {len(pred_lp)}",
             "load-path recall by truth pair: " + ", ".join(f"{k} {ok}/{n}" for k, (n, ok) in sorted(kinds.items())),
             "load-path false positives by pair: " + ", ".join(f"{k} {n}" for k, n in fps.most_common(8))]
    return {"metrics": m, "gated": list(m), "notes": notes}


def st_v2_documents(a) -> dict:
    """The v2 drawing set / calc package / spec book through the generic pipeline (contract evaluator)."""
    if os.path.exists(os.path.join(ROOT, "scripts", "evaluate_v2_docs.py")):
        return _optional_eval("evaluate_v2_docs.py")
    have = [f for f in ("calc_package.pdf", "drawings.pdf", "specs.pdf") if os.path.exists(os.path.join(V2, f))]
    raise Skip(f"v2 documents present: {have or 'none yet'}; no scripts/evaluate_v2_docs.py evaluator yet")


def st_synthetic_v1(a) -> dict:
    p = run([PY, "scripts/evaluate.py"])
    if p.returncode:
        raise RuntimeError(f"scripts/evaluate.py exit {p.returncode}: {p.stderr[-600:]}")
    r = json.load(open(os.path.join(ROOT, "data", "eval", "latest.json")))
    d, sg = r["design_mapping"]["overall"], r["segmentation"]
    rv = r["revisions"]
    m = {
        "segmentation_exact": sg["exact"] / sg["truth_calcs"],
        "design_precision": d["precision"], "design_recall": d["recall"], "design_f1": d["f1"],
        "xref_precision": r["xref_tier"]["precision"],
        "load_path_precision": r["load_path_rev1"]["precision"], "load_path_recall": r["load_path_rev1"]["recall"],
        "calc_edges_precision": r["calc_edges"]["precision"], "calc_edges_recall": r["calc_edges"]["recall"],
        "rev2_load_path_recall": rv["load_path_rev2"]["recall"],
        "rev_diff_exact": float(rv["diff_removed"]["exact"] and rv["diff_changed"]["exact"]),
        "decisions_carried": float(rv["decisions_carried_forward"] == {"confirm": "confirmed", "reject": "rejected"}),
    }
    return {"metrics": m, "gated": list(m)}


def _check(cmd: list[str], name: str) -> tuple[bool, str]:
    p = run(cmd)
    tail = (p.stdout.strip().splitlines() or [""])[-1]
    return p.returncode == 0, f"{name}: {tail[:120]}"


def st_ai_step(a) -> dict:
    for s in ("check_llm_imports.py", "check_ai_step.py"):
        if not os.path.exists(os.path.join(ROOT, "scripts", s)):
            raise Skip(f"scripts/{s} not present")
    c1 = _check([PY, "scripts/check_llm_imports.py"], "llm imports")
    c2 = _check([PY, "scripts/check_ai_step.py"], "ai step")
    return {"checks": {"llm_imports_outside_ai": c1[0], "ai_step_replay": c2[0]}, "notes": [c1[1], c2[1]]}


def st_copyright(a) -> dict:
    c = _check([PY, "scripts/check_no_copyrighted.py", "--tracked"], "copyright")
    return {"checks": {"no_copyrighted_in_head": c[0]}, "notes": [c[1]]}


def _optional_eval(script: str) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "m.json")
        p = run([PY, f"scripts/{script}", "--json-out", out])
        if p.returncode or not os.path.exists(out):
            raise RuntimeError(f"scripts/{script} exit {p.returncode}: {(p.stderr or p.stdout)[-600:]}")
        r = json.load(open(out))
    return {"metrics": r["metrics"], "gated": r.get("gated", [])}


def st_move_answer_key(a) -> dict:
    if os.path.exists(os.path.join(ROOT, "scripts", "evaluate_move.py")):
        return _optional_eval("evaluate_move.py")
    key = os.path.join(V2, "answer_key.json")
    if os.path.exists(key):
        n = len(json.load(open(key)).get("scenarios", []))
        raise Skip(f"answer key present ({n} scenarios) but no scripts/evaluate_move.py impact-engine evaluator yet")
    raise Skip("no move-a-column answer key (data/synthetic_v2/answer_key.json) and no evaluator")


def st_registry(a) -> dict:
    if os.path.exists(os.path.join(ROOT, "scripts", "evaluate_registry.py")):
        return _optional_eval("evaluate_registry.py")
    t = "present" if os.path.exists(os.path.join(V2, "registry_truth.json")) else "not generated yet"
    raise Skip(f"registry truth (data/synthetic_v2/registry_truth.json) {t}; no scripts/evaluate_registry.py yet")


def _graph(a) -> dict:
    if a.synthetic_only:
        raise Skip("--synthetic-only")
    p = os.path.join(SETS, a.sid, "graph.json")
    if not os.path.exists(p):
        raise Skip(f"no data/sets/{a.sid}/graph.json (drawing-set PDFs are local only)")
    return json.load(open(p))


def st_set_coverage(a) -> dict:
    g = _graph(a)
    c = g["coverage"]
    m = {"elements": c["elements"], "elements_linked_frac": c["elements_linked"] / max(1, c["elements"]),
         "elements_linked_strong_frac": c["elements_linked_strong"] / max(1, c["elements"]),
         "calc_pages_linked_frac": c["calc_pages_linked"] / max(1, c["calc_pages"]),
         "links": c["links"], "calc_edges": c["calc_edges"], "load_path_edges": c["load_path_edges"],
         "findings": len(g["findings"])}
    return {"metrics": m, "gated": [], "notes": [f"graph built {g['built_at']}"]}


def _labels(a, name: str):
    if a.synthetic_only:
        raise Skip("--synthetic-only")
    p = os.path.join(LABELS, a.sid, name)
    if not os.path.exists(p):
        raise Skip(f"no hand labels data/labels/{a.sid}/{name} (gitignored, local only)")
    return json.load(open(p))


def st_calc_spot(a) -> dict:
    lab = _labels(a, "calc_spot_checks.json")
    p = os.path.join(SETS, a.sid, "calc_records.json")
    if not os.path.exists(p):
        raise Skip(f"no data/sets/{a.sid}/calc_records.json")
    recs = {r["id"]: r for r in json.load(open(p))["records"]}
    n = ok = 0
    fails = []
    for ch in lab["checks"]:
        r = recs.get(ch["record"])
        for k, want in ch["expect"].items():
            n += 1
            got = None if r is None else r["values"].get(k)
            good = (abs(got - want) <= 1e-6 * max(1, abs(want))) if isinstance(want, float) and isinstance(got, (int, float)) \
                else got == want
            ok += good
            if not good:
                fails.append(f"{ch['record']}.{k}: got {got!r}, want {want!r}" + ("" if r else " (record missing)"))
    return {"metrics": {"spot_pass_rate": ok / n, "spot_checks": n}, "gated": ["spot_pass_rate"], "notes": fails}


def _rects(e: dict) -> list:
    return e.get("rects") or [e["bbox"]]


def _overlap(r1, r2) -> float:
    ix = max(0.0, min(r1[2], r2[2]) - max(r1[0], r2[0]))
    iy = max(0.0, min(r1[3], r2[3]) - max(r1[1], r2[1]))
    a = min((r1[2] - r1[0]) * (r1[3] - r1[1]), (r2[2] - r2[0]) * (r2[3] - r2[1]))
    return ix * iy / a if a > 0 else 0.0


def _norm_size(t: str) -> str:
    return re.sub(r"[^0-9a-z/]", "", t.lower().split("(")[0])


def _axis(s: str) -> tuple[str, ...]:
    """A grid axis token as the set of grid lines it touches: '3' -> (3,), '3-4' -> (3,4),
    'beyond 6' / '<6' / '>1' -> ('beyond', 6)."""
    s = s.strip()
    m = re.match(r"^(?:beyond\s+|[<>])(.+)$", s)
    if m:
        return ("beyond", m.group(1))
    return tuple(sorted(x for x in s.split("-") if x))  # a bay is unordered: "4-5" == "5-4"


def _grid_agree(pred: str, lab: str) -> tuple[bool, bool]:
    """(exact, compatible): compatible = each axis equal, or one is a line bounding the other's bay."""
    try:
        pr, pc = pred.split("/")
        lr, lc = lab.split("/")
    except ValueError:
        return False, False
    exact = compat = True
    for p, l in ((pr, lr), (pc, lc)):
        P, L = _axis(p), _axis(l)
        if P != L:
            exact = False
            if not (len(P) == 1 and P[0] in L or len(L) == 1 and L[0] in P or (P[0] == L[0] == "beyond" and P == L)
                    or ("beyond" in (P[0], L[0]) and set(P) & set(L))):
                compat = False
    return exact, compat


def st_slice_tags(a) -> dict:
    g = _graph(a)
    out_m, gated, notes = {}, [], []
    files = sorted(f for f in os.listdir(os.path.join(LABELS, a.sid)) if f.startswith("tags_")) \
        if os.path.isdir(os.path.join(LABELS, a.sid)) else []
    if not files:
        raise Skip(f"no data/labels/{a.sid}/tags_<sheet>.json")
    for f in files:
        lab = json.load(open(os.path.join(LABELS, a.sid, f)))
        sheet, tmap = lab["sheet"], lab.get("type_map", {})
        pred = [e for e in g["elements"] if e["sheet"] == sheet]
        used = set()
        pairs = []
        for t in lab["tags"]:
            best, bo = None, 0.0
            for i, e in enumerate(pred):
                if i in used:
                    continue
                o = max(_overlap(t["bbox"], r) for r in _rects(e))
                if o > bo:
                    best, bo = i, o
            if best is not None and bo >= 0.5:
                used.add(best)
                pairs.append((t, pred[best]))
        tp = len(pairs)
        p, r = prf(tp, len(pred) - tp, len(lab["tags"]) - tp)
        type_ok = sum(tmap.get(e["type"], e["type"]) == t["type"] for t, e in pairs)
        size_ok = sum(_norm_size(e["text"]).startswith(_norm_size(t["text"])) or _norm_size(t["text"]) == _norm_size(e.get("size") or "")
                      or (t["type"] == "smf-marker" and "smf" in e["text"].lower()) for t, e in pairs)
        gp = [(t, e) for t, e in pairs if t["type"] in ("beam", "trellis", "smf-marker") and t.get("grid") and e.get("grid")]
        ge = sum(_grid_agree(e["grid"], t["grid"])[0] for t, e in gp)
        gc = sum(_grid_agree(e["grid"], t["grid"])[1] for t, e in gp)
        k = sheet.replace(".", "_")
        m = {f"{k}_tag_precision": p, f"{k}_tag_recall": r, f"{k}_type_accuracy": type_ok / tp if tp else None,
             f"{k}_size_accuracy": size_ok / tp if tp else None,
             f"{k}_grid_exact": ge / len(gp) if gp else None, f"{k}_grid_compatible": gc / len(gp) if gp else None,
             f"{k}_labelled": len(lab["tags"]), f"{k}_predicted": len(pred)}
        out_m.update(m)
        gated += [f"{k}_tag_precision", f"{k}_tag_recall", f"{k}_type_accuracy", f"{k}_size_accuracy", f"{k}_grid_compatible"]
        conf = Counter((t["type"], tmap.get(e["type"], e["type"])) for t, e in pairs if tmap.get(e["type"], e["type"]) != t["type"])
        missed = Counter(t["type"] for t in lab["tags"] if all(t is not x for x, _ in pairs))
        extra = Counter(e["type"] for i, e in enumerate(pred) if i not in used)
        notes.append(f"{sheet}: matched {tp}/{len(lab['tags'])} labelled, {len(pred)} predicted; "
                     f"type confusions (label->pred) {dict(conf) or '-'}; missed by type {dict(missed) or '-'}; "
                     f"unmatched predictions by type {dict(extra) or '-'}; grid compared on {len(gp)} at-member tags "
                     "(leader-tagged HSS are positioned at the leader end by the pipeline, at the text by the labels)")
    return {"metrics": out_m, "gated": gated, "notes": notes}


def st_slice_links(a) -> dict:
    g = _graph(a)
    lab = _labels(a, "links_judged.json")
    calcs = {(c["doc"], c["sheet_id"]): c["id"] for c in g["calcs"]}
    by_sheet = defaultdict(list)
    for e in g["elements"]:
        by_sheet[e["sheet"]].append(e)
    links = {(l["el"], l["calc"]) for l in g["links"]}
    present = correct_present = correct_total = incorrect_present = 0
    by_tier = defaultdict(lambda: [0, 0])
    for j in lab["links"]:
        k = j["key"]
        cid = calcs.get((k["calc_doc"], k["calc_sheet"]))
        els = [e for e in by_sheet[k["sheet"]] if e["text"] == k["el_text"] and _overlap(e["bbox"], k["el_bbox"]) >= 0.5]
        here = bool(cid and any((e["id"], cid) in links for e in els))
        correct_total += j["correct"]
        if here:
            present += 1
            correct_present += j["correct"]
            incorrect_present += not j["correct"]
            by_tier[k["tier"]][0] += 1
            by_tier[k["tier"]][1] += j["correct"]
    m = {"judged": len(lab["links"]), "judged_present": present,
         "link_precision": correct_present / present if present else None,
         "correct_links_retained": correct_present / correct_total if correct_total else None,
         "incorrect_links_present": incorrect_present}
    notes = [f"precision by tier (present judged links): " + ", ".join(
        f"{t} {ok}/{n}" for t, (n, ok) in sorted(by_tier.items()))]
    return {"metrics": m, "gated": ["link_precision", "correct_links_retained"], "notes": notes}


STAGES = [("v2_design", st_v2_design), ("v2_ifc", st_v2_ifc), ("v2_documents", st_v2_documents),
          ("move_answer_key", st_move_answer_key), ("registry", st_registry),
          ("ai_step", st_ai_step), ("copyright", st_copyright),
          ("synthetic_v1", st_synthetic_v1), ("set_coverage", st_set_coverage),
          ("calc_spot", st_calc_spot), ("slice_tags", st_slice_tags), ("slice_links", st_slice_links)]
# Retiring once synthetic v2 is ingested end to end (Issy, 2026-11-14): still run and gated until the
# cleanup step deletes them, but labelled so nobody tunes against them.
DEPRECATED = {"synthetic_v1": "synthetic v1", "set_coverage": "Dana Point", "calc_spot": "Dana Point",
              "slice_tags": "Dana Point", "slice_links": "Dana Point"}


# ----------------------------------------------------------------------------- scorecard

def fmt(v) -> str:
    if v is None:
        return "-"
    if isinstance(v, bool):
        return "PASS" if v else "FAIL"
    if isinstance(v, float) and 0 <= v <= 1:
        return f"{100 * v:.1f}%"
    return f"{v:g}" if isinstance(v, float) else str(v)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sid", default="dana-point-bldg12")
    ap.add_argument("--synthetic-only", action="store_true")
    ap.add_argument("--regen-v2", action="store_true", help="regenerate data/synthetic_v2 first")
    ap.add_argument("--only", default="", help="comma-separated stage names")
    ap.add_argument("--update-baseline", action="store_true")
    ap.add_argument("--tolerance", type=float, default=0.005)
    ap.add_argument("--baseline", default=BASELINE)
    ap.add_argument("--json-out", default=os.path.join(ROOT, "data", "eval", "scorecard.json"))
    a = ap.parse_args()
    only = set(filter(None, a.only.split(",")))
    res: dict[str, dict] = {}
    for name, fn in STAGES:
        if only and name not in only:
            continue
        try:
            res[name] = {"status": "ok", **fn(a)}
        except Skip as s:
            res[name] = {"status": "skipped", "reason": str(s)}
        except Exception as e:  # a crashed stage is a failure, never a pass
            res[name] = {"status": "error", "reason": f"{type(e).__name__}: {e}"}

    base = json.load(open(a.baseline)) if os.path.exists(a.baseline) else {"stages": {}}
    regressions, improvements = [], []
    for name, r in res.items():
        b = base["stages"].get(name, {})
        if r["status"] == "error":
            regressions.append(f"{name}: stage crashed - {r['reason']}")
            continue
        if r["status"] != "ok" or not b:
            continue
        for k in r.get("gated", []):
            v, bv = r["metrics"].get(k), b.get("metrics", {}).get(k)
            if bv is None:
                continue
            if v is None or v < bv - a.tolerance:
                regressions.append(f"{name}.{k}: {fmt(v)} < baseline {fmt(bv)}")
            elif v > bv + a.tolerance:
                improvements.append(f"{name}.{k}: {fmt(v)} > baseline {fmt(bv)}")
        for k, v in r.get("checks", {}).items():
            if b.get("checks", {}).get(k) and not v:
                regressions.append(f"{name}.{k}: FAIL (passed in baseline)")

    now = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M %Z")
    print(f"calc-graph scorecard - {now} (Eastern){'  [synthetic only]' if a.synthetic_only else ''}")
    print(f"baseline: {os.path.relpath(a.baseline, ROOT)} ({base.get('updated', 'none')})\n")
    for name, r in res.items():
        dep = f"  [DEPRECATED - {DEPRECATED[name]}, retiring]" if name in DEPRECATED else ""
        if r["status"] != "ok":
            print(f"{name:<16} {r['status'].upper()}: {r['reason']}{dep}")
            continue
        b = base["stages"].get(name, {})
        print(f"{name}{dep}")
        for k, v in r.get("checks", {}).items():
            print(f"  {k:<36} {fmt(v)}")
        for k, v in r.get("metrics", {}).items():
            bv = b.get("metrics", {}).get(k)
            mark = "" if k in r.get("gated", []) else "   (info)"
            print(f"  {k:<36} {fmt(v):>8}   baseline {fmt(bv):>8}{mark}")
        for n in r.get("notes", []):
            print(f"  - {n}")
    print()
    failing_checks = [f"{n}.{k}" for n, r in res.items() for k, v in r.get("checks", {}).items() if not v]
    if failing_checks:
        print("FAILING CHECKS: " + ", ".join(failing_checks))
    for x in improvements:
        print(f"improved   {x}")
    for x in regressions:
        print(f"REGRESSION {x}")

    os.makedirs(os.path.dirname(a.json_out), exist_ok=True)
    json.dump({"run_at": now, "synthetic_only": a.synthetic_only, "stages": res, "regressions": regressions},
              open(a.json_out, "w"), indent=1, default=str)

    if a.update_baseline:
        nb = {"about": "calc-graph evaluation baseline - numbers only, no drawing text. Written by "
                       "scripts/evaluate_all.py --update-baseline.", "updated": now, "stages": dict(base["stages"])}
        for name, r in res.items():
            if r["status"] == "ok":
                nb["stages"][name] = {k: r[k] for k in ("metrics", "checks") if k in r}
        os.makedirs(os.path.dirname(os.path.abspath(a.baseline)), exist_ok=True)
        json.dump(nb, open(a.baseline, "w"), indent=1, sort_keys=True)
        print(f"baseline updated: {os.path.relpath(a.baseline, ROOT)}")
        return
    sys.exit(1 if regressions or failing_checks else 0)


if __name__ == "__main__":
    main()
