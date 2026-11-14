"""Generate the synthetic dataset.

    uv run python -m synth.generate --out data/synthetic --seed 7

Writes model_rev1.ifc, model_rev2.ifc (column C8 removed), calc_package.pdf and
ground_truth.json. Re-running with the same seed is byte-stable (checked by
``--check``, which generates twice into temp dirs and compares sha256).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile

from . import analysis, building, calc_pdf, ifc_writer
from .building import K_BEAM, K_COL, K_MF1, K_SLAB, K_ST1


def _refs(b: building.Building, res: analysis.Results) -> None:
    """Calcs that mention an element's mark without designing it (as written by calc_pdf)."""
    marks = {}
    for e in b.elements:
        if e.mark:
            marks.setdefault(e.mark, []).append(e)

    def ref(mark: str, calc: str):
        for e in marks.get(mark, []):
            if calc not in e.ref_calcs:
                e.ref_calcs.append(calc)

    for m in ("C7", "C8", "C12", "C13"):
        ref(m, K_SLAB)
    ref(res.st1["gov"], K_ST1)
    for lv in ("2", "3", "R"):
        for n in range(13, 17):
            ref(f"{lv}B{n}" if lv != "R" else f"RB{n}", K_MF1)
    for n in range(16, 21):
        ref(f"C{n}", K_MF1)
    ref("2CB1", K_COL)
    ref("2CB1", K_BEAM)
    # beam report summary: "carried to ST-1 ...", "end moments to MF-1 ..."; column report: "Mu from MF-1",
    # "Brace forces from BR1 calc"
    ref("ST-1", K_BEAM)
    ref("MF-1", K_BEAM)
    ref("MF-1", K_COL)
    for n in range(1, 7):
        ref(f"BR1-{n}", K_COL)


def generate(out: str, seed: int = 7) -> dict:
    os.makedirs(out, exist_ok=True)
    truth: dict = {"seed": seed, "generator": "calc-graph synth v1", "units": "IFC metres; calcs US customary"}
    builds = {}
    for rev in (1, 2):
        b = building.build(rev)
        res = analysis.run(b)
        analysis.apply_footing_sizes(b, res)
        if rev == 1:
            _refs(b, res)
        gids = ifc_writer.write(b, os.path.join(out, f"model_rev{rev}.ifc"))
        builds[rev] = (b, res, gids)
    b1, res1, g1 = builds[1]
    calc_pdf.write(b1, res1, os.path.join(out, "calc_package.pdf"), seed=seed)

    truth["files"] = {"model_rev1": "model_rev1.ifc", "model_rev2": "model_rev2.ifc", "calc_package": "calc_package.pdf"}
    truth["calcs"] = [
        {"id": cid, "title": title, "pages": pages, "software": sw, "element_type": cat,
         "front": cid == building.K_FRONT, "scanned": cid == building.K_CANT, "no_elements": cid == building.K_CRIT}
        for cid, title, pages, sw, cat in calc_pdf.PLAN
    ]
    truth["calc_edges"] = [list(e) for e in calc_pdf.CALC_EDGES]
    truth["elements"] = {
        g1[e.key]: {"key": e.key, "mark": e.mark, "ifc_class": e.ifc_class, "storey": e.storey,
                    "design_calc": e.design_calc, "ref_calcs": sorted(set(e.ref_calcs) - {e.design_calc})}
        for e in b1.elements
    }
    truth["load_path"] = sorted([g1[s], g1[d]] for s, d in b1.load_path)
    b2, _, g2 = builds[2]
    k1 = {e.key: e for e in b1.elements}
    k2 = {e.key: e for e in b2.elements}
    truth["rev2"] = {
        "label": b2.label,
        "removed": sorted(g1[k] for k in k1.keys() - k2.keys()),
        "added": sorted(g2[k] for k in k2.keys() - k1.keys()),
        "changed": sorted(g1[k] for k in k1.keys() & k2.keys()
                          if (k1[k].object_type, k1[k].psets) != (k2[k].object_type, k2[k].psets)),
        "load_path": sorted([g2[s], g2[d]] for s, d in b2.load_path),
    }
    with open(os.path.join(out, "ground_truth.json"), "w") as fh:
        json.dump(truth, fh, indent=1, sort_keys=True)
    return truth


def _digest(d: str) -> dict[str, str]:
    return {n: hashlib.sha256(open(os.path.join(d, n), "rb").read()).hexdigest() for n in sorted(os.listdir(d))}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "synthetic"))
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--check", action="store_true", help="generate twice and compare bytes")
    a = ap.parse_args()
    if a.check:
        with tempfile.TemporaryDirectory() as t1, tempfile.TemporaryDirectory() as t2:
            generate(t1, a.seed)
            generate(t2, a.seed)
            d1, d2 = _digest(t1), _digest(t2)
            for n in d1:
                print(f"{'SAME' if d1[n] == d2[n] else 'DIFF'}  {d1[n][:16]}  {n}")
            if d1 != d2:
                raise SystemExit("not byte-stable")
    t = generate(a.out, a.seed)
    n_design = sum(1 for e in t["elements"].values() if e["design_calc"])
    print(f"wrote {a.out}: {len(t['elements'])} elements ({n_design} with a designing calc), "
          f"{len(t['calcs'])} calc segments, {len(t['calc_edges'])} calc edges, {len(t['load_path'])} load-path edges; "
          f"rev2 removed {len(t['rev2']['removed'])} / changed {len(t['rev2']['changed'])}")


if __name__ == "__main__":
    main()
