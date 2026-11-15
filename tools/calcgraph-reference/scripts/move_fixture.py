"""Fixture step of the move-impact gate: calc facts + move scenarios for packages/move-impact.

    cd tools/calcgraph-reference
    uv run python scripts/move_fixture.py            # -> data/synthetic_v2/{move_facts,move_scenarios}.json

Reads data/synthetic_v2/design.json (written by synth.v2.generate), its element graph
model.graph.json (scripts/build_graph.mjs over model.ifc - the graph the app builds), and
answer_key.json (synth.v2.scenarios).

STAND-IN FOR MATCHER OUTPUT. The facts are the values the v2 calc package PRINTS for each calc row
(the calc-sheet data calc_pdf_v2.py typesets, rounded to the precision it prints them at, with the
page and box it printed them in), linked to the row's element by GlobalId. That is what a calc
matcher reading the PDF would hand the engine; packages/calc-mapper does not extract row values yet,
so this script reads them from the generator's calc-sheet data instead of from the PDF text. It
never passes design-only data (design loads, analysis results, sizes from the design run, the
generator's relations) to the engine: only printed row values, the row's calc, page and box, and
two things a matcher reads from the sheet header - whether the calc is a lateral-system calc and
which frame line the row is on.

Scenarios: the answer key's moves with the column as its GlobalId and the move in metres.
Sections: properties of the profiles the model names, from the shape table the generator already uses
(synth/v2/data/aisc_v16_subset.csv) - optional reference input the engine accepts from its caller.
"""
from __future__ import annotations

import argparse
import json
import os
import re

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
V2 = os.path.join(ROOT, "data", "synthetic_v2")
FT = 0.3048

LATERAL = {"smf_beam", "brace", "scbf_girder", "collector", "frame_analysis"}
GOVERNS = {"flexure": "flexure", "shear": "shear", "defl_live": "deflection_live", "defl_total": "deflection_total"}


def r(x, n):
    return None if x is None else round(float(x), n)


def q(value, unit, n):
    return None if value is None else {"value": r(value, n), "unit": unit}


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def drop_none(d: dict) -> dict:
    return {k: v for k, v in d.items() if v is not None}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=V2)
    a = ap.parse_args()
    des = json.load(open(os.path.join(a.dir, "design.json")))
    graph = json.load(open(os.path.join(a.dir, "model.graph.json")))
    key = json.load(open(os.path.join(a.dir, "answer_key.json")))
    gid = {e["id"]: e["global_id"] for e in des["elements"] if e.get("global_id")}
    el = {e["id"]: e for e in des["elements"]}
    nodes = {n["id"]: n for n in graph["nodes"]}
    frame_of: dict[str, list[str]] = {}
    members_of: dict[str, list[str]] = {}
    for rel in des["relations"]:
        if rel["kind"] == "member-of" and rel["dst"].startswith("FRAME:"):
            frame_of.setdefault(rel["src"], []).append(rel["dst"][6:])
            members_of.setdefault(rel["dst"][6:], []).append(rel["src"])

    def flipped(eid: str) -> bool:
        """True when the row's end 1 ("far left", the design's p1) is the graph axis END - so the
        printed reactions are re-labelled to the model's axis ends, as a reader of the sheet would."""
        e, n = el.get(eid), nodes.get(gid.get(eid, ""))
        if not e or not n or "p1" not in e or not (n.get("geometry") or {}).get("axis"):
            return False
        ax = n["geometry"]["axis"]
        p1 = (e["p1"][0] * FT, e["p1"][1] * FT)
        d0 = ((ax["start"][0] - p1[0]) ** 2 + (ax["start"][1] - p1[1]) ** 2) ** 0.5
        d1 = ((ax["end"][0] - p1[0]) ** 2 + (ax["end"][1] - p1[1]) ** 2) ** 0.5
        return d1 < d0

    facts = []
    for rec in des["records"]:
        k, v = rec["kind"], rec["values"]
        els = [gid[e] for e in rec["elements"] if e in gid]
        group = None
        if k == "frame_analysis":
            fr = rec["elements"][0][6:]
            els = sorted(gid[m] for m in members_of.get(fr, []) if m in gid)
            group = fr
        elif rec["elements"]:
            group = (frame_of.get(rec["elements"][0]) or [None])[0]
        role = "lateral" if (k in LATERAL or (k == "column_design" and rec["section"] == "C")) else "gravity"
        f = {"id": rec["id"], "elements": els,
             "source": {"calcKey": slug(f"{rec['calc']} {rec['calc_title']}"), "page": rec.get("page"),
                        "rects": [rec["bbox"]] if rec.get("bbox") else []},
             "role": role, "group": group if role == "lateral" else None,
             "utilisation": r(rec.get("uc"), 3)}
        if k == "beam_design":
            flip = flipped(rec["elements"][0])
            ri = {"dead": r(v["R_i_D"], 2), "live": r(v["R_i_L"], 2), "unit": "kip"}
            rj = {"dead": r(v["R_j_D"], 2), "live": r(v["R_j_L"], 2), "unit": "kip"}
            f.update(kind="beam", span=q(v["span_ft"], "ft", 2), governs=GOVERNS.get(v["governs"], v["governs"]),
                     lineLoad={"dead": r(v["w_D_klf"], 3), "live": r(v["w_L_klf"], 3), "roofLive": r(v["w_Lr_klf"], 3), "unit": "klf"},
                     reactions={"i": rj if flip else ri, "j": ri if flip else rj,
                                "factoredI": q(v["R_j_k"] if flip else v["R_i_k"], "kip", 1),
                                "factoredJ": q(v["R_i_k"] if flip else v["R_j_k"], "kip", 1)},
                     checks=[{"mode": "flexure", "demand": q(v["Mu_kft"], "kip-ft", 1), "capacity": q(v["phiMn_kft"], "kip-ft", 1)},
                             {"mode": "shear", "demand": q(v["Vu_k"], "kip", 1), "capacity": q(v["phiVn_k"], "kip", 1)},
                             {"mode": "deflection_live", "demand": q(v["defl_L_in"], "in", 2), "capacity": q(v["defl_L_allow_in"], "in", 2)},
                             {"mode": "deflection_total", "demand": q(v["defl_T_in"], "in", 2), "capacity": q(v["defl_T_allow_in"], "in", 2)}])
        elif k == "smf_beam":
            f.update(kind="beam", span=q(v.get("span_ft"), "ft", 2),
                     checks=[{"mode": "flexure", "demand": q(v["Mu_kft"], "kip-ft", 1), "capacity": q(v["phiMn_kft"], "kip-ft", 1)}])
        elif k == "column_design":
            f.update(kind="column", axial=q(v["Pu_k"], "kip", 1), capacity=q(v.get("phiPn_k"), "kip", 1), combination=rec.get("lc") or None)
        elif k == "footing":
            f.update(kind="footing", serviceLoad=q(v["P_service_k"], "kip", 1), allowableBearing=q(v["qa_ksf"], "ksf", 2),
                     width=q(v["B_ft"], "ft", 1))
        elif k == "connection":
            f.update(kind="connection", demand=q(v["Ru_k"], "kip", 1), capacity=q(v["phiRn_k"], "kip", 1), detailType=v["type"])
        elif k == "typical_detail":
            f.update(kind="typical_detail", detailType=rec["id"].split(":", 1)[1], capacity=q(v.get("phiRn_k"), "kip", 1),
                     bolts=v.get("bolts"))
        elif k == "brace":
            f.update(kind="brace", axial=q(v["Pu_k"], "kip", 1), capacity=q(v["phiPn_k"], "kip", 1))
        elif k == "scbf_girder":
            f.update(kind="frame_girder", governs="F2.3" if v.get("governs_combo") == "F2.3" else "frame",
                     span=q(v.get("span_ft"), "ft", 2))
            f23 = v.get("F2_3")
            if f23 and f23.get("Pv_unbalanced") is not None and v.get("phiPn_k") and v.get("phiMn_kft"):
                f["chevron"] = {"unbalancedLoad": q(f23["Pv_unbalanced"], "kip", 1), "gravityMoment": q(f23.get("M_gravity") or 0, "kip-ft", 1),
                                "axial": q(f23.get("P_axial") or 0, "kip", 1), "axialCapacity": q(v["phiPn_k"], "kip", 1),
                                "momentCapacity": q(v["phiMn_kft"], "kip-ft", 1), "equation": f23.get("eq", "H1-1b")}
        elif k == "collector":
            f.update(kind="collector", axial=q(v.get("Pu_k"), "kip", 1))
        elif k == "frame_analysis":
            f.update(kind="frame", demand=q(rec.get("demand"), "ratio", 3), capacity=q(rec.get("capacity"), "ratio", 3))
        elif k == "seismic":
            f.update(kind="seismic", seismic=drop_none({"cs": r(v.get("Cs"), 4), "r": v.get("R"), "ie": v.get("Ie"), "system": v.get("system")}))
        elif rec["elements"]:
            f.update(kind="other", demand=q(rec.get("demand"), rec.get("unit") or "", 1), capacity=q(rec.get("capacity"), rec.get("unit") or "", 1))
        else:
            continue   # criteria / area loads / ELF / wind: no element to link
        for c in f.get("checks", []):
            for kk in ("demand", "capacity"):
                if c.get(kk) is None:
                    c.pop(kk, None)
        facts.append(drop_none(f))
    scen = [{"id": s["id"], "label": s["label"], "column": gid[s["column"]],
             "move": ({"column": gid[s["column"]], "remove": True} if s["kind"] == "remove"
                      else {"column": gid[s["column"]], "dx": round(s["dx"] * FT, 6), "dy": round(s["dy"] * FT, 6)})}
            for s in key["scenarios"]]
    json.dump({"about": "STAND-IN FOR MATCHER OUTPUT: values the v2 calc package prints per calc row, linked by GlobalId (scripts/move_fixture.py)", "facts": facts}, open(os.path.join(a.dir, "move_facts.json"), "w"), indent=1)
    json.dump({"scenarios": scen}, open(os.path.join(a.dir, "move_scenarios.json"), "w"), indent=1)
    # section properties for the profiles the MODEL names, from the shape table the generator uses
    # (published reference data the caller supplies - the TS package ships no shape table)
    import csv
    table = {r_["AISC_Manual_Label"]: r_ for r_ in csv.DictReader(open(os.path.join(ROOT, "synth", "v2", "data", "aisc_v16_subset.csv")))}
    prof = sorted({n.get("profile") for n in graph["nodes"] if n.get("profile") in table})
    def num(x):
        try:
            return float(x)
        except (TypeError, ValueError):
            return None
    keys = ("d", "tf", "bf", "A", "Ix", "Zx", "Sx", "ry", "rts", "ho", "J")
    sections = {p_: drop_none({"unit": "in", **{k_: num(table[p_].get(k_)) for k_ in keys}}) for p_ in prof}
    json.dump({"about": "AISC Shapes Database v16.0 subset (synth/v2/data, see data/SOURCES.md) for the model's profiles",
               "sections": sections}, open(os.path.join(a.dir, "move_sections.json"), "w"), indent=1)
    print(f"{len(facts)} calc facts, {len(scen)} scenarios, {len(sections)} sections -> {a.dir}")


if __name__ == "__main__":
    main()
