"""Run every evaluation, print one scorecard, exit non-zero on a regression vs the stored baseline.

  uv run python scripts/evaluate_all.py                    # everything whose inputs exist locally
  uv run python scripts/evaluate_all.py --synthetic-only   # CI: no drawing-set stages (no PDFs there)
  uv run python scripts/evaluate_all.py --update-baseline  # accept the current numbers as the baseline

Stages (a stage whose inputs are missing is SKIPPED, never failed). Everything runs on the synthetic v2
(Harbor View) building:
  v2_design        synth v2 ground truth self-consistency (AISC table verified, no infeasible members,
                   no clashes, every member has a design record); generates data/synthetic_v2 if absent
  v2_ifc           v2 model.ifc through the production ifc_ingest + loadpath vs design.json: element P/R,
                   profile + storey accuracy, load-path P/R (frames-into + bears-on), directed and not
  v2_ifc_mapping   the IFC path (pipeline: ifc_ingest + segment over calcpkg_ingest + matcher) on v2 model.ifc +
                   calc_package.pdf in a throwaway store vs design.json designed-by: a link is right when its calc
                   covers a page of a record that designs the element (precision / recall, xref links apart)
  etabs_export     the ETABS .e2k (base + a column move) read back: load totals within 1% of design.json,
                   areas, rigid diaphragm, loads-only mass source, split eccentricity, 15 combos (pass/fail)
  ifc_contract     scripts/validate_ifc.py --fresh-only: a freshly written v2 base + move revision against
                   our IDS (ifctester), schema validation, GlobalId stability, analytical model (pass/fail)
  v2_documents     scripts/evaluate_v2_docs.py when it exists (v2 drawings / calc package / specs through
                   the generic pipeline); else lists which v2 PDFs exist
  ai_step          scripts/check_llm_imports.py + scripts/check_ai_step.py (pass/fail)
  copyright        scripts/check_no_copyrighted.py --tracked (pass/fail)
  move_answer_key  scripts/evaluate_move.py when it exists (contract below); else reports whether the
                   synth v2 answer key exists
  registry         scripts/evaluate_registry.py when it exists (contract below); else whether the v2
                   registry truth exists
  set_coverage     drawing-set coverage numbers from data/sets/<sid>/graph.json (default the Harbor View set
                   synthetic-v2; info, not gated)
  schema_strict    scripts/schema_audit.py --strict over every local set output + the store: every fact's rule id,
                   rule version, engine and confidence come from its producer, none adapter-supplied (pass/fail;
                   skipped when no drawing set has been built locally)

Retired 2026-11-14 (Issy: retire the Dana Point permit set and the synthetic v1 building once v2 documents
ingest through the generic pipeline - gate met: IFC 100/100, drawings 0.92/0.97, calcs 0.98/0.99, specs
0.73/0.67): synthetic_v1 (scripts/evaluate.py, the v1 package; its design-mapping score is replaced by
v2_ifc_mapping) and the Dana hand-label stages calc_spot / slice_tags / slice_links (their labels were of that
set only). Their baseline entries were removed with them; tag pre-v2-cleanup has both.

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
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PY = sys.executable
BASELINE = os.path.join(ROOT, "eval", "baseline.json")
SETS = os.path.join(ROOT, "data", "sets")


class Skip(Exception):
    pass


def run(cmd: list[str], timeout: int = 1800) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout)


def prf(tp: int, fp: int, fn: int) -> tuple[float | None, float | None]:
    return (tp / (tp + fp) if tp + fp else None, tp / (tp + fn) if tp + fn else None)


# ----------------------------------------------------------------------------- stages
V2 = os.path.join(ROOT, "data", "synthetic_v2")
V2_SET = "synthetic-v2"
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


def st_v2_ifc_mapping(a) -> dict:
    """The IFC path end to end on the v2 documents, in a throwaway store, scored against design.json."""
    d = _v2_design(a)
    for f in ("model.ifc", "calc_package.pdf"):
        if not os.path.exists(os.path.join(V2, f)):
            raise Skip(f"no data/synthetic_v2/{f}")
    sys.path.insert(0, os.path.join(ROOT, "backend"))
    from calcgraph import pipeline, revstore
    with tempfile.TemporaryDirectory() as tmp:
        st = revstore.open_store(tmp)
        pid = st.ensure_project("eval")
        pipeline.ingest_model(st, pid, os.path.join(V2, "model.ifc"))
        pipeline.ingest_calcs(st, pid, os.path.join(V2, "calc_package.pdf"))
        s = pipeline.state(st, pid)
        st.db.close()
    gid = {e["id"]: e.get("global_id") for e in d["elements"]}
    page = {r["id"]: r["page"] for r in d["records"]}
    truth: dict[str, set[int]] = defaultdict(set)
    for r in d["relations"]:
        if r["kind"] == "designed-by" and gid.get(r["src"]) and r["dst"] in page:
            truth[gid[r["src"]]].add(page[r["dst"]])
    model = {e["global_id"] for e in s["elements"]}
    truth = {g: p for g, p in truth.items() if g in model}
    pages = {c["key"]: set(c["pages"]) for c in s["calcs"]}
    design = [l for l in s["links"] if l["tier"] != "xref"]
    ok = [l for l in design if truth.get(l["global_id"], set()) & pages[l["calc_key"]]]
    found = {l["global_id"] for l in ok}
    tiers = Counter(l["tier"] for l in design)
    good = Counter(l["tier"] for l in ok)
    m = {"calcs": len(s["calcs"]), "design_precision": len(ok) / len(design) if design else None,
         "design_recall": len(found) / len(truth) if truth else None,
         "xref_links": sum(1 for l in s["links"] if l["tier"] == "xref")}
    notes = [f"{len(model)} model elements, {len(truth)} with a designed-by record, {len(design)} design links "
             f"(xref apart); precision by tier: " + ", ".join(f"{t} {good[t]}/{n}" for t, n in tiers.most_common())]
    return {"metrics": m, "gated": ["design_precision", "design_recall"], "notes": notes}


def st_etabs_export(a) -> dict:
    """The .e2k the ETABS adapter writes (base design + a column move, the path move-a-column's
    "send to ETABS" uses), read back with calcgraph.analysis.e2k and compared with design.json:
    D / L / Lr totals, L / Lr per level, mass-source weight per level, ELF V and story forces,
    wind story forces - each within 1% - plus areas, rigid diaphragm, loads-only mass source,
    one eccentricity per seismic pattern and the 15 design combos (analysis.etabs.e2k_load_check)."""
    exp = _v2_design(a)
    sys.path.insert(0, os.path.join(ROOT, "backend"))
    from calcgraph.analysis import etabs
    ad = etabs.EtabsAdapter(exp)
    out, notes = {}, []
    with tempfile.TemporaryDirectory() as tmp:
        for name, change in (("base", None), ("move_2B", {"moved": {"2B": [5.0, 0.0]}})):
            path = os.path.join(tmp, f"{name}.e2k")
            ad.export_model(path, change=change)
            r = etabs.e2k_load_check(path, exp)
            out[name] = r
            bad = [f"{x['quantity']} {x['level']} {100 * x['rel_err']:+.2f}%" for x in r["rows"] if not x["ok"]]
            bad += [k for k, v in r["structure"].items() if not v]
            notes.append(f"{name}: {len(r['rows'])} load totals, max |err| {100 * r['max_abs_rel_err']:.2f}%"
                         + (f"; FAILING: {', '.join(bad)}" if bad else ""))
    m = {f"{k}_max_abs_load_err": v["max_abs_rel_err"] for k, v in out.items()}
    return {"metrics": m, "gated": [], "notes": notes,
            "checks": {"e2k_loads_within_1pct_of_design": all(v["ok"] for v in out.values())}}


def st_v2_documents(a) -> dict:
    """The v2 drawing set / calc package / spec book through the generic pipeline (contract evaluator)."""
    if os.path.exists(os.path.join(ROOT, "scripts", "evaluate_v2_docs.py")):
        return _optional_eval("evaluate_v2_docs.py")
    have = [f for f in ("calc_package.pdf", "drawings.pdf", "specs.pdf") if os.path.exists(os.path.join(V2, f))]
    raise Skip(f"v2 documents present: {have or 'none yet'}; no scripts/evaluate_v2_docs.py evaluator yet")


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


def st_schema_strict(a) -> dict:
    if a.synthetic_only:
        raise Skip("--synthetic-only")
    if not any(os.path.exists(os.path.join(SETS, d, "graph.json")) for d in (os.listdir(SETS) if os.path.isdir(SETS) else [])):
        raise Skip("no data/sets/<sid>/graph.json (build one: uv run calc-graph ingest-set ...)")
    c = _check([PY, "scripts/schema_audit.py", "--strict"], "schema strict")
    return {"checks": {"provenance_from_producers": c[0]}, "notes": [c[1]]}


def st_ifc_contract(a) -> dict:
    """The IFC writers' contract: a freshly written v2 base + move revision against our IDS
    (backend/calcgraph/ids/calc-graph-v2.ids, ifctester), schema validation, GlobalId stability,
    profile consistency and the analytical model links (scripts/validate_ifc.py --fresh-only)."""
    if not os.path.exists(os.path.join(ROOT, "scripts", "validate_ifc.py")):
        raise Skip("scripts/validate_ifc.py not present")
    c = _check([PY, "scripts/validate_ifc.py", "--fresh-only"], "ifc contract")
    return {"checks": {"v2_ifc_contract": c[0]}, "notes": [c[1]]}


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


STAGES = [("v2_design", st_v2_design), ("v2_ifc", st_v2_ifc), ("v2_ifc_mapping", st_v2_ifc_mapping),
          ("ifc_contract", st_ifc_contract),
          ("etabs_export", st_etabs_export),
          ("v2_documents", st_v2_documents),
          ("move_answer_key", st_move_answer_key), ("registry", st_registry),
          ("ai_step", st_ai_step), ("copyright", st_copyright), ("set_coverage", st_set_coverage),
          ("schema_strict", st_schema_strict)]
# stages retired with the Dana Point set and the synthetic v1 building (2026-11-14): dropped from the baseline
RETIRED = ("synthetic_v1", "calc_spot", "slice_tags", "slice_links")


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
    ap.add_argument("--sid", default=V2_SET)
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
        dep = ""
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
                       "scripts/evaluate_all.py --update-baseline.", "updated": now,
              "stages": {k: v for k, v in base["stages"].items() if k not in RETIRED}}
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
