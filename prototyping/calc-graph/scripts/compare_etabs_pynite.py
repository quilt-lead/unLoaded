"""Compare a REAL ETABS run of data/synthetic_v2/model.e2k with calc-graph's PyNite analysis.

    uv run python scripts/compare_etabs_pynite.py --etabs DIR [--out report.md]
    uv run python scripts/compare_etabs_pynite.py --bridge http://127.0.0.1:8765 --save DIR

DIR holds what the Windows bridge returned for an analysed model (units kip, ft: call
SapModel.SetPresentUnits kip_ft_F before /csi/results):
  results_dead_eq.json  POST /csi/results {"kinds": [frame_forces, joint_reactions, story_drifts],
                                            "cases": ["Dead", "EQX", "EQY"]}
  labels.json           POST /csi/call {"path": "SapModel.FrameObj", "method": "GetLabelNameList"}
--bridge fetches both live (and sets the units) and --save writes them to DIR.

What is compared, and why only that
- The e2k carries frames, restraints, patterns and combos but NO floor/area/frame loads, no
  diaphragm and no wind load, so in ETABS only "Dead" (steel self weight) is a real load. The
  only like-for-like case is therefore Dead.
- calc-graph's PyNite analysis is per-line 2D frames (synth.v2.lateral._frame), not a 3D
  building. The SMF lines (MF_LINES) are rebuilt here through that same production function
  with NO floor load, so its "D" case is beam self weight only - the load ETABS sees on those
  beams (no infill beams frame into an SMF beam mid-span). Column axial is NOT like-for-like
  (ETABS adds column self weight and the reactions of pinned transverse framing; _frame applies
  no column self weight) and is reported separately, not flagged.
- Also reported (plumbing, not agreement): every ETABS frame (label, story) maps to a registry
  element through the adapter's label map; Dead base reaction vs the e2k self weight; EQX/EQY
  base shear vs the design ELF (ETABS sees self mass only); story drifts.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path[:0] = [os.path.join(ROOT, "backend"), ROOT]

from calcgraph.analysis import e2k  # noqa: E402
from calcgraph.analysis.base import DATA_DIR, load_design  # noqa: E402
from calcgraph.analysis.etabs import EtabsAdapter  # noqa: E402
from synth.v2 import aisc, lateral as LAT  # noqa: E402
from synth.v2.model import LEVELS, MF_LINES  # noqa: E402

FLAG_PCT = 5.0
TINY = 0.5   # kip / kip-ft: below this on both sides a % difference is noise, not reported


# ------------------------------------------------------------------ ETABS side
def _post(url: str, body: dict) -> dict:
    req = urllib.request.Request(url, json.dumps(body).encode(), {"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.load(r)


def fetch(bridge: str) -> tuple[dict, dict]:
    _post(f"{bridge}/csi/call", {"path": "SapModel", "method": "SetPresentUnits", "inputs": {"Units": "kip_ft_F"}})
    res = _post(f"{bridge}/csi/results", {"kinds": ["frame_forces", "joint_reactions", "story_drifts"],
                                          "cases": ["Dead", "EQX", "EQY"]})
    labels = _post(f"{bridge}/csi/call", {"path": "SapModel.FrameObj", "method": "GetLabelNameList"})
    return res, labels


def etabs_ends(res: dict, labels: dict, case: str = "Dead") -> dict:
    """{(label, story): {i, j: {P, V2, V3, M2, M3, sta}, L_out}} from FrameForce rows (first / last
    output station of each frame object)."""
    name_to = {n: (l, s) for n, l, s in zip(labels["MyName"], labels["MyLabel"], labels["MyStory"])}
    rows: dict[str, list] = {}
    for r in res["frame_forces"]:
        if r["LoadCase"] == case:
            rows.setdefault(r["Obj"], []).append(r)
    out = {}
    for obj, rs in rows.items():
        rs.sort(key=lambda r: r["ObjSta"])
        pick = lambda r: {k: r[k] for k in ("P", "V2", "V3", "M2", "M3", "ObjSta")}  # noqa: E731
        out[name_to[obj]] = {"i": pick(rs[0]), "j": pick(rs[-1]), "n_sta": len(rs)}
    return out


# ------------------------------------------------------------------ PyNite side
def pynite_smf(exp: dict) -> dict:
    """{element id | (column id, story): {member, L, kind}} for every SMF beam and column; the
    PyNite member is solved for combo "D" = self weight only (see at())."""
    els = exp["elements"]
    out = {}
    for yl in MF_LINES:
        cols = sorted(((e["id"][4:], e["x"]) for e in els if e["type"] == "column" and "smf_column" in e.get("roles", [])
                       and e["id"][4:][-1] == yl), key=lambda t: t[1])
        beams = [e for e in els if "smf_beam" in e.get("roles", []) and e["id"].split("-")[2] == yl]
        if len(cols) < 2 or not beams:
            continue
        sizes_b = {e["size"] for e in beams}
        sizes_c = {e["size"] for e in els if e["type"] == "column" and e["id"][4:] in {c for c, _ in cols}}
        if len(sizes_b) != 1 or len(sizes_c) != 1:
            raise ValueError(f"line {yl}: _frame takes one beam and one column size, design has {sizes_b} / {sizes_c}")
        m = LAT._frame(cols, {}, sizes_b.pop(), sizes_c.pop(), {}, base_fixed=True)
        m.add_load_combo("D", {"D": 1.0})
        m.analyze_linear(check_statics=False, check_stability=False)

        def ends(mem):
            return {"member": mem, "L": mem.L()}

        for zi, (lv, _, _) in enumerate(LEVELS, start=1):
            for bi in range(len(cols) - 1):
                eid = f"B-{lv}-{yl}-{cols[bi][0][:-1]}{cols[bi + 1][0][:-1]}"
                out[eid] = {**ends(m.members[f"B_{lv}_{bi}"]), "kind": "SMF beam"}
        for c, _ in cols:
            for zi in range(3):
                out[(f"COL-{c}", f"Story{zi + 1}")] = {**ends(m.members[f"C_{c}_{zi}"]), "kind": "SMF column"}
    return out


def at(mem, x: float) -> dict:
    """PyNite member forces at x ft from its i end (both bending / shear axes, larger kept: the
    frames are in-plane with Iy = Iz, so one axis carries everything)."""
    x = min(max(x, 0.0), mem.L())
    return {"M": max((mem.moment(d, x, "D") for d in ("My", "Mz")), key=abs),
            "V": max((mem.shear(d, x, "D") for d in ("Fy", "Fz")), key=abs), "P": mem.axial(x, "D")}


# ------------------------------------------------------------------ compare
def pct(e: float, p: float) -> float | None:
    """None when PyNite's value is below TINY: a % of ~0 is meaningless (absolute values shown)."""
    if abs(p) < TINY:
        return None
    return (abs(e) - abs(p)) / max(abs(p), 1e-9) * 100.0


def compare(res: dict, labels: dict, exp: dict) -> dict:
    ad = EtabsAdapter(exp)
    lm = ad.label_map()["by_element"]
    et = etabs_ends(res, labels)
    # label map plumbing: every ETABS frame (label, story) is a registry element
    adapter_keys = {(o.label, o.story): o.element_id for o in ad.model_objects() if o.kind == "frame"}
    etabs_keys = set(zip(labels["MyLabel"], labels["MyStory"]))
    mapping = {"etabs_frames": len(etabs_keys), "adapter_frames": len(adapter_keys),
               "unmapped_in_etabs": sorted(f"{l}@{s}" for l, s in etabs_keys - set(adapter_keys)),
               "missing_in_etabs": sorted(f"{l}@{s}" for l, s in set(adapter_keys) - etabs_keys)}
    rows = []
    for key, pn in pynite_smf(exp).items():
        eid, story = key if isinstance(key, tuple) else (key, None)
        cands = lm.get(eid, [])
        hit = [c for c in cands if story is None or c["story"] == story]
        if len(hit) != 1:
            rows.append({"element": eid, "story": story, "error": f"label map gave {hit}"})
            continue
        lab, st = hit[0]["label"], hit[0]["story"]
        e = et.get((lab, st))
        if not e:
            rows.append({"element": eid, "label": lab, "story": st, "error": "no ETABS Dead rows"})
            continue
        for end in ("i", "j"):
            ee = e[end]
            # PyNite evaluated at the SAME station ETABS reports (ETABS end offsets put the end
            # stations at the support faces); pp_cl = at the PyNite node (centreline)
            pp, pp_cl = at(pn["member"], ee["ObjSta"]), at(pn["member"], 0.0 if end == "i" else pn["L"])
            em = max((ee["M2"], ee["M3"]), key=abs)
            ev = max((ee["V2"], ee["V3"]), key=abs)
            rows.append({"element": eid, "kind": pn["kind"], "label": lab, "story": st, "end": end,
                         "sta_ft": ee["ObjSta"], "L_ft": pn["L"],
                         "M_etabs": em, "M_pynite": pp["M"], "M_pct": pct(em, pp["M"]),
                         "M_pynite_cl": pp_cl["M"], "M_pct_cl": pct(em, pp_cl["M"]),
                         "V_etabs": ev, "V_pynite": pp["V"], "V_pct": pct(ev, pp["V"]),
                         "P_etabs": ee["P"], "P_pynite": pp["P"],
                         "P_pct": pct(ee["P"], pp["P"]) if pn["kind"] == "SMF beam" else None})
    # global numbers
    react = [r for r in res["joint_reactions"] if r["LoadCase"] == "Dead"]
    fz_dead = sum(r["F3"] for r in react)
    segs = e2k.frame_segments(e2k.read_e2k(os.path.join(DATA_DIR, "model.e2k")))
    sw_nominal = sum(aisc.get(s["section"])["W"] * math.dist(s["i"], s["j"]) / 1000 for s in segs)
    shear = {}
    for case, d in (("EQX", "F1"), ("EQY", "F2")):
        steps: dict = {}
        for r in res["joint_reactions"]:
            if r["LoadCase"] == case:
                steps.setdefault((r["StepType"], r["StepNum"]), 0.0)
                steps[(r["StepType"], r["StepNum"])] += r[d]
        shear[case] = {f"{k[0]} {k[1]:g}": v for k, v in steps.items()}
    recs = {r["id"]: r for r in exp["records"]}
    elf = {"EQX": recs["C-ELF:X"]["values"], "EQY": recs["C-ELF:Y"]["values"]}
    return {"mapping": mapping, "rows": rows, "dead_fz": fz_dead, "sw_nominal": sw_nominal, "shear": shear,
            "elf": {k: {"V_k": v["V_k"], "W_k": v["W_k"]} for k, v in elf.items()},
            "drifts": [r for r in res.get("story_drifts", []) if r["LoadCase"] in ("EQX", "EQY")]}


def fmt(v, nd=1):
    return "-" if v is None else f"{v:.{nd}f}"


def report(c: dict) -> str:
    m = c["mapping"]
    out = ["## Label mapping (ETABS frames -> registry elements)", "",
           f"ETABS frames {m['etabs_frames']}, adapter frames {m['adapter_frames']}, "
           f"unmapped in ETABS {len(m['unmapped_in_etabs'])} {m['unmapped_in_etabs'][:10]}, "
           f"missing in ETABS {len(m['missing_in_etabs'])} {m['missing_in_etabs'][:10]}", "",
           "## Dead (self weight only): SMF lines, ETABS vs PyNite (synth.v2.lateral._frame, no floor load)", "",
           "Units kip, kip-ft. Magnitudes compared (sign conventions differ); % = (|ETABS| - |PyNite|) / |PyNite|. "
           f"`-` = PyNite value below {TINY} (no %). FLAG = over {FLAG_PCT:g}%. sta = ETABS output station of that end (ft from the "
           "object's i end); a non-zero / short-of-L station means ETABS reports at the support face (end offset). "
           "PyNite is evaluated at that same station; `M PyNite cl` / `M % cl` are PyNite at its node (centreline), "
           "for reference only (not flagged).", "",
           "| element | ETABS label@story | end | sta ft / L | M ETABS | M PyNite | M % | M PyNite cl | M % cl | V ETABS | V PyNite | V % | P ETABS | P PyNite | flag |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in c["rows"]:
        if "error" in r:
            out.append(f"| {r['element']} | {r.get('label', '')}@{r.get('story', '')} | | | ERROR {r['error']} | | | | | | | | | | |")
            continue
        flags = [k for k in ("M", "V", "P") if r[f"{k}_pct"] is not None and abs(r[f"{k}_pct"]) > FLAG_PCT]
        out.append(f"| {r['element']} | {r['label']}@{r['story']} | {r['end']} | {r['sta_ft']:.2f} / {r['L_ft']:.2f} | "
                   f"{fmt(r['M_etabs'])} | {fmt(r['M_pynite'])} | {fmt(r['M_pct'])} | {fmt(r['M_pynite_cl'])} | {fmt(r['M_pct_cl'])} | {fmt(r['V_etabs'], 2)} | "
                   f"{fmt(r['V_pynite'], 2)} | {fmt(r['V_pct'])} | {fmt(r['P_etabs'], 2)} | {fmt(r['P_pynite'], 2)} | "
                   f"{'FLAG ' + ','.join(flags) if flags else ''} |")
    out += ["", "Column axial (P) is not like-for-like and is not flagged: ETABS adds column self weight and pinned "
            "transverse framing reactions; _frame applies neither.", "",
            "## Global (plumbing, not agreement)", "",
            f"- Dead base reaction ETABS sum F3 = {c['dead_fz']:.1f} kip; e2k nominal self weight (AISC W x length) = "
            f"{c['sw_nominal']:.1f} kip ({(c['dead_fz'] / c['sw_nominal'] - 1) * 100:+.1f}%)."]
    for case in ("EQX", "EQY"):
        out.append(f"- {case} base shear ETABS by step: " + ", ".join(f"{k}: {abs(v):.1f}" for k, v in c["shear"][case].items())
                   + f" kip; design ELF V = {c['elf'][case]['V_k']} kip on W = {c['elf'][case]['W_k']} kip.")
    if c["drifts"]:
        out += ["", "| story | case | step | dir | drift (ETABS, self mass only) | label |", "|---|---|---|---|---|---|"]
        for r in c["drifts"]:
            out.append(f"| {r['Story']} | {r['LoadCase']} | {r['StepType']} {r['StepNum']:g} | {r['Direction']} | {r['Drift']:.2e} | {r['Label']} |")
    return "\n".join(out) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--etabs", help="dir with results_dead_eq.json + labels.json")
    ap.add_argument("--bridge", help="bridge URL to fetch live (e.g. http://127.0.0.1:8765)")
    ap.add_argument("--save", help="with --bridge: write the fetched JSON here")
    ap.add_argument("--out", help="write the markdown report here (default stdout)")
    ap.add_argument("--json", help="write the comparison rows as JSON here")
    a = ap.parse_args()
    if a.bridge:
        res, labels = fetch(a.bridge)
        if a.save:
            os.makedirs(a.save, exist_ok=True)
            for n, v in (("results_dead_eq.json", res), ("labels.json", labels)):
                with open(os.path.join(a.save, n), "w") as fh:
                    json.dump(v, fh)
    elif a.etabs:
        with open(os.path.join(a.etabs, "results_dead_eq.json")) as fh:
            res = json.load(fh)
        with open(os.path.join(a.etabs, "labels.json")) as fh:
            labels = json.load(fh)
    else:
        ap.error("give --etabs DIR or --bridge URL")
    c = compare(res, labels, load_design())
    md = report(c)
    if a.json:
        with open(a.json, "w") as fh:
            json.dump(c, fh, indent=1, default=str)
    if a.out:
        with open(a.out, "w") as fh:
            fh.write(md)
    else:
        sys.stdout.write(md)


if __name__ == "__main__":
    main()
