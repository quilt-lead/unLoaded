"""Generate the Harborview sample: IFC (rev 1 + rev 2), calc PDFs (rev 1 set + combined package, the rev 2
reissues and new L06 calcs) and ground truth, from the demo model bundles.

    cd tools/calcgraph-reference
    uv run python -m synth.harborview.generate [--out ../../data/harborview] [--check]

Output (default data/harborview/, next to the bundles; committed, PDFs in Git LFS):
    harborview-rev1.ifc, harborview-rev2.ifc
    calcs/rev1/<title> - Rev A.pdf           one PDF per calc document (78)
    calcs/harborview-calcs-rev1.pdf          the same pages as one package, in sheet order
    calcs/rev2/<title> - <rev>.pdf           documents whose revision changed in rev 2, and the new L06 ones
    ground_truth.json                        what the engine should find (scripts/evaluate_harborview.py scores it)
    manifest.json                            the files the app's "Harborview sample" loads, in order
A Rev B file has the same name as its Rev A file apart from the revision token, so the app files it as the
next revision of that document (calcset.ts documentStem). --check generates twice and compares sha256.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile

from . import calc_pdf, ifc, model

OUT = model.DATA
BUMP = {"W18x46": "W18x50", "W21x62": "W21x68", "W16x31": "W16x36"}
MISMATCH_DOC = "doc-infill-l03"   # planted size mismatch: its first beam is written one size up


def ifc_fields(e: model.Element) -> tuple:
    return (e.mark, e.label, e.profile, e.material, e.storey, json.dumps(e.geom, sort_keys=True))


def generate(out: str = OUT) -> dict:
    os.makedirs(os.path.join(out, "calcs", "rev1"), exist_ok=True)
    os.makedirs(os.path.join(out, "calcs", "rev2"), exist_ok=True)
    m1, m2 = model.load(1), model.load(2)
    g1 = ifc.write(m1, os.path.join(out, "harborview-rev1.ifc"))
    g2 = ifc.write(m2, os.path.join(out, "harborview-rev2.ifc"))

    mis_doc = next(d for d in m1.documents if d.key == MISMATCH_DOC)
    mis_el = m1.by_id[mis_doc.calcs[0].elements[0]]
    mismatch = {mis_el.id: BUMP[mis_el.profile]}

    w1 = calc_pdf.Writer(m1, mismatch)
    rev1_files = {}
    for d in sorted(m1.documents, key=calc_pdf.sheet_key):
        rel = f"calcs/rev1/{d.file_name}"
        w1.document(d, os.path.join(out, rel))
        rev1_files[d.key] = rel
    calc_pdf.combine([os.path.join(out, rev1_files[d.key]) for d in sorted(m1.documents, key=calc_pdf.sheet_key)],
                     os.path.join(out, "calcs", "harborview-calcs-rev1.pdf"), "Calculation package Rev 1")

    w2 = calc_pdf.Writer(m2, mismatch)
    rev1_docs = {d.key: d for d in m1.documents}
    rev2_files = {}
    for d in sorted(m2.documents, key=calc_pdf.sheet_key):
        old = rev1_docs.get(d.key)
        if old and old.rev == d.rev:
            continue
        rel = f"calcs/rev2/{d.file_name}"
        w2.document(d, os.path.join(out, rel))
        rev2_files[d.key] = rel

    # ---------------- ground truth (rev 1 unless stated) ----------------
    design1 = m1.design_calc()
    calcs1 = {c.id: c for c in m1.calcs()}
    refs = {cid: ids for cid, ids in w1.refs.items()}
    ref_calcs: dict[str, list[str]] = {}
    for cid, ids in refs.items():
        for i in ids:
            ref_calcs.setdefault(i, []).append(cid)
    edges = sorted({(design1[i], cid) for cid, ids in refs.items() for i in ids if i in design1 and design1[i] != cid})
    truth: dict = {
        "generator": "calc-graph synth harborview v1",
        "source": "data/harborview/*.bundle.json + synth/harborview/legacy_params.json",
        "units": "IFC metres; calcs US customary",
        "files": {"model_rev1": "harborview-rev1.ifc", "model_rev2": "harborview-rev2.ifc",
                  "calc_package": "calcs/harborview-calcs-rev1.pdf", "calc_documents_rev1": rev1_files,
                  "calc_documents_rev2": rev2_files},
        "calcs": [{"id": c.id, "doc": c.doc, "title": c.title, "element_type": c.cat, "family": c.family, "rev": c.rev}
                  for c in sorted(calcs1.values(), key=lambda c: (calc_pdf.sheet_key(next(d for d in m1.documents if d.key == c.doc)), c.id))],
        "calc_edges": [list(e) for e in edges],
        "elements": {g1[e.id]: {"id": e.id, "mark": e.mark, "label": e.label, "kind": e.kind, "storey": e.storey,
                                "design_calc": design1.get(e.id), "ref_calcs": sorted(set(ref_calcs.get(e.id, [])) - {design1.get(e.id)})}
                     for e in m1.elements},
        "mismatches": [{"global_id": g1[i], "calc": design1[i], "model_size": m1.by_id[i].profile, "calc_size": s}
                       for i, s in mismatch.items()],
        "load_path": sorted([g1[e["a"]], g1[e["b"]]] for e in m1.edges if e["kind"] == "supports"),
    }
    k1, k2 = m1.by_id, m2.by_id
    # the rev 2 calc set: reissued / new documents from rev 2, every other document is still its rev 1 PDF
    design2: dict[str, str] = {}
    for d in m2.documents:
        src = d if d.key in rev2_files else rev1_docs[d.key]
        for c in src.calcs:
            for i in c.elements:
                if i in k2:
                    design2[i] = c.id
    truth["rev2"] = {
        "label": m2.label,
        "removed": sorted(g1[i] for i in k1.keys() - k2.keys()),
        "added": sorted(g2[i] for i in k2.keys() - k1.keys()),
        "changed": sorted(g1[i] for i in k1.keys() & k2.keys() if ifc_fields(k1[i]) != ifc_fields(k2[i])),
        "documents": [{"doc": k, "rev": next(d.rev for d in m2.documents if d.key == k),
                       "kind": "revision" if k in rev1_docs else "new", "file": f} for k, f in rev2_files.items()],
        "design_calc": {g2[i]: c for i, c in sorted(design2.items()) if i in k2 and c},
    }
    with open(os.path.join(out, "ground_truth.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(truth, fh, indent=1, sort_keys=True)
        fh.write("\n")
    # what the app loads (scripts/copy-assets.mjs copies these; src/engine/hooks.ts useLoadHarborview reads it)
    manifest = {
        "project": m1.project,
        "models": {"rev1": "harborview-rev1.ifc", "rev2": "harborview-rev2.ifc"},
        "labels": {"rev1": f"{m1.label} (IFC)", "rev2": f"{m2.label} (IFC)"},
        "calcs": {"rev1": list(rev1_files.values()), "rev2": list(rev2_files.values())},
        "package": "calcs/harborview-calcs-rev1.pdf",
    }
    with open(os.path.join(out, "manifest.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(manifest, fh, indent=1)
        fh.write("\n")
    return truth


def _digest(d: str) -> dict[str, str]:
    out = {}
    for root, _, files in os.walk(d):
        for n in files:
            p = os.path.join(root, n)
            out[os.path.relpath(p, d).replace(os.sep, "/")] = hashlib.sha256(open(p, "rb").read()).hexdigest()
    return dict(sorted(out.items()))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--check", action="store_true", help="generate twice and compare bytes")
    a = ap.parse_args()
    if a.check:
        with tempfile.TemporaryDirectory() as t1, tempfile.TemporaryDirectory() as t2:
            generate(t1)
            generate(t2)
            d1, d2 = _digest(t1), _digest(t2)
            diff = [n for n in d1 if d1[n] != d2.get(n)]
            print(f"{len(d1)} files, {len(diff)} differ" + (": " + ", ".join(diff[:10]) if diff else ""))
            if diff or d1.keys() != d2.keys():
                raise SystemExit("not byte-stable")
    t = generate(a.out)
    n_design = sum(1 for e in t["elements"].values() if e["design_calc"])
    print(f"wrote {a.out}: {len(t['elements'])} elements ({n_design} with a designing calc), {len(t['calcs'])} calcs in "
          f"{len(t['files']['calc_documents_rev1'])} rev 1 PDFs, {len(t['calc_edges'])} calc edges; rev 2: "
          f"+{len(t['rev2']['added'])} / -{len(t['rev2']['removed'])} / ~{len(t['rev2']['changed'])} elements, "
          f"{len(t['rev2']['documents'])} PDFs")


if __name__ == "__main__":
    main()
