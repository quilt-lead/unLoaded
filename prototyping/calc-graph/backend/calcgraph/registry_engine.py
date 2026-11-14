"""Feed the move-a-column impact engine from the registry REBUILT FROM THE DOCUMENTS
(registry_ingested.json + model.ifc), not from the generator's design export.

- topology: the ingested relations (frames-into / bears-on with `via`, connected-by,
  instance-of, designed-by, member-of, feeds) as the registry ingest produced them
- geometry: the production IFC ingest (ifc_ingest) - PHYSICAL members (they stop at faces), so
  the analytical centreline model is rebuilt: each member end is extended to the support it
  frames into (column centre projected on the member axis, or the support member's axis)
- calc values: parsed from the printed calc rows (the ingested record's row text), with the
  report layouts declared below (RAM gravity beam / column tables, the footing and connection
  schedules, the typical shear tab table). Values a row does not print are derived where the
  statics is exact (uniform-load beam reactions split D / L from its printed wD, wL and the
  AISC self-weight) and otherwise left out.
"""
from __future__ import annotations

import math
import re

M2FT = 3.28084
NUM = re.compile(r"^-?\d+(?:\.\d+)?$")

# printed report layouts: token positions after the subject id (RAM / spreadsheet conventions)
LAYOUTS = {
    "beam": ["size", "span_ft", "Lb_ft", "w_D_klf", "w_L_klf", "pt_loads", "Mu_kft", "phiMn_kft", "flex_eq", "Vu_k",
             "phiVn_k", "defl_L", "defl_T", "camber", "studs", "R_i_k", "R_j_k", "uc", "governs"],
    "column": ["size", "storey", "KL_ft", "KL_r", "Pu_k", "phiPn_k", "Mux_kft", "phiMnx_kft", "Muy_kft", "phiMny_kft",
               "eq", "lc", "uc", "P_base_D", "P_base_L", "P_base_Lr"],
}


def _num(t):
    t = t.replace(",", "")
    return float(t) if NUM.match(t) else None


def _row_values(text: str, subject: str, layout: list[str]) -> dict:
    toks = text.split()
    if subject not in toks:
        return {}
    toks = toks[toks.index(subject) + 1:]
    out = {}
    for k, t in zip(layout, toks):
        v = _num(t)
        out[k] = v if v is not None else t
    return out


def to_engine(ingested: dict, ifc_path: str) -> dict:
    from . import ifc_ingest
    nodes = {n["id"]: n for n in ingested["nodes"]}
    rels = ingested["relations"]
    ifc = {e["global_id"]: e for e in ifc_ingest.read_ifc(ifc_path)["elements"]}
    sup: dict[tuple[str, str], str] = {}
    for r in rels:
        if r["kind"] == "frames-into" and r.get("end"):
            sup[(r["src"], r["end"])] = r["dst"]
    # an ingested frames-into edge may lack the end: decide it from geometry below
    fi = [(r["src"], r["dst"]) for r in rels if r["kind"] == "frames-into"]

    def g(nid):
        n = nodes.get(nid)
        return ifc.get(n.get("global_id")) if n and n.get("global_id") else None

    def centre(e):
        mn, mx = e["geom"]["min"], e["geom"]["max"]
        return ((mn[0] + mx[0]) / 2 * M2FT, (mn[1] + mx[1]) / 2 * M2FT, (mn[2] + mx[2]) / 2 * M2FT)

    def axis(e):
        p1, p2 = e["geom"]["p1"], e["geom"]["p2"]
        return [v * M2FT for v in p1], [v * M2FT for v in p2]

    els, ends = [], {}
    for nid, n in nodes.items():
        if n["kind"] != "element":
            continue
        t = n.get("type")
        e = {"id": nid, "type": t, "global_id": n.get("global_id"), "size": n["attrs"].get("section")}
        ge = g(nid)
        if t == "column" and ge:
            cx, cy, _ = centre(ge)
            e.update(x=round(cx, 3), y=round(cy, 3))
        elif t == "footing" and ge:
            cx, cy, _ = centre(ge)
            mn, mx = ge["geom"]["min"], ge["geom"]["max"]
            e.update(x=round(cx, 3), y=round(cy, 3), B_ft=round((mx[0] - mn[0]) * M2FT * 2) / 2)
        elif t == "grade_beam" and ge:
            a, b = axis(ge)
            mn, mx = ge["geom"]["min"], ge["geom"]["max"]
            w = min(mx[0] - mn[0], mx[1] - mn[1]) * M2FT * 12
            e.update(p1=a, p2=b, b_in=round(w))
        elif t in ("beam", "girder", "brace") and ge:
            a, b = axis(ge)
            e.update(p1=a, p2=b)
        if t == "connection":
            e["conn_type"] = n["attrs"].get("conn_type") or ""
        els.append(e)
    byid = {e["id"]: e for e in els}
    # analytical centreline: extend each member end to what it frames into
    for src, dst in fi:
        m, s = byid.get(src), byid.get(dst)
        if not m or not s or "p1" not in m or m["type"] == "grade_beam":
            continue
        a, b = m["p1"][:2], m["p2"][:2]
        d = (b[0] - a[0], b[1] - a[1])
        n_ = math.hypot(*d) or 1.0
        u = (d[0] / n_, d[1] / n_)
        if s["type"] == "column" and "x" in s:
            t = (s["x"] - a[0]) * u[0] + (s["y"] - a[1]) * u[1]
            pt = (a[0] + u[0] * t, a[1] + u[1] * t)
        elif "p1" in s:
            sa, sb = s["p1"][:2], s["p2"][:2]
            ex, ey = sb[0] - sa[0], sb[1] - sa[1]
            den = u[0] * ey - u[1] * ex
            if abs(den) < 1e-9:
                continue
            t = ((sa[0] - a[0]) * ey - (sa[1] - a[1]) * ex) / den
            pt = (a[0] + u[0] * t, a[1] + u[1] * t)
        else:
            continue
        end = "i" if math.dist(pt, a) < math.dist(pt, b) else "j"
        z = m["p1"][2] if end == "i" else m["p2"][2]
        if end == "i":
            m["p1"] = [pt[0], pt[1], z]
        else:
            m["p2"] = [pt[0], pt[1], z]
        ends[(src, dst)] = end
    for e in els:
        if "p1" in e and e["type"] in ("beam", "girder"):
            e["span_ft"] = round(math.dist(e["p1"][:2], e["p2"][:2]), 3)
            e["level"] = {"Level 2": "L2", "Level 3": "L3", "Roof": "RF"}.get(nodes[e["id"]]["attrs"].get("storey"), "")
    # roles from frame membership (member-of FRAME:*) - SFRS
    for r in rels:
        if r["kind"] == "member-of" and r["dst"].startswith("FRAME:") and r["src"] in byid:
            byid[r["src"]]["sfrs"] = True
            byid[r["src"]].setdefault("roles", []).append("sfrs")
            if byid[r["src"]]["type"] in ("beam", "girder"):
                byid[r["src"]]["frame"] = r["dst"][6:]
    # records with values parsed from their rows
    from synth.v2 import aisc   # section property table (data)
    recs = []
    for nid, n in nodes.items():
        if n["kind"] != "record":
            continue
        a = n["attrs"]
        subj = a.get("subject") or ""
        text = " ".join(o.get("text") or "" for o in n.get("occurrences", [])[:1])
        sheet = a.get("sheet") or ""
        sw = a.get("software") or ""
        kind, vals, uc, demand, cap = "other", {}, None, None, None
        st = byid.get(subj, {}).get("type")
        if sw.startswith("RAM") and st in ("beam", "girder"):
            v = _row_values(text, subj, LAYOUTS["beam"])
            if isinstance(v.get("w_D_klf"), float):
                kind = "beam_design"
                size = v.get("size") or byid[subj].get("size")
                swt = aisc.get(size)["W"] / 1000 if size else 0.0
                roof = byid[subj].get("level") == "RF"
                L = v.get("span_ft") or 0
                wl = v["w_L_klf"]
                vals = {"size": size, "span_ft": L, "w_D_klf": v["w_D_klf"], "w_L_klf": 0.0 if roof else wl,
                        "w_Lr_klf": wl if roof else 0.0, "self_wt_klf": swt, "Mu_kft": v.get("Mu_kft"),
                        "phiMn_kft": v.get("phiMn_kft")}
                if not v.get("pt_loads"):   # uniform load: reactions split exactly by statics
                    for e_ in ("i", "j"):
                        vals[f"R_{e_}_D"] = (v["w_D_klf"] + swt) * L / 2
                        vals[f"R_{e_}_L"] = wl * L / 2
                uc, demand, cap = v.get("uc"), v.get("Mu_kft"), v.get("phiMn_kft")
        elif sw.startswith("RAM") and st == "column":
            v = _row_values(text, subj, LAYOUTS["column"])
            if isinstance(v.get("Pu_k"), float):
                kind = "column_design"
                vals = {k: v.get(k) for k in ("size", "Pu_k", "phiPn_k", "P_base_D", "P_base_L", "P_base_Lr")}
                uc, demand, cap = v.get("uc"), v.get("Pu_k"), v.get("phiPn_k")
        elif st == "footing":
            toks = text.split()
            if subj in toks:
                rest = [_num(t) for t in toks[toks.index(subj) + 2:]]
                nums = [x for x in rest if x is not None]
                if len(nums) >= 6:
                    kind = "footing"
                    vals = {"P_service_k": nums[0], "B_ft": nums[2], "h_in": nums[3], "q_ksf": nums[4], "qa_ksf": nums[5]}
                    uc = _num(toks[-1])
                    demand, cap = nums[0], nums[5] * nums[2] ** 2
        elif st == "connection":
            toks = text.split()
            nums = [_num(t) for t in toks]
            if toks and nums[-1] is not None and len([x for x in nums if x is not None]) >= 3:
                kind = "connection"
                tail = [x for x in nums if x is not None][-3:]
                vals = {"Ru_k": tail[0], "phiRn_k": tail[1]}
                uc, demand, cap = tail[2], tail[0], tail[1]
        elif subj.startswith("DETAIL:ST-"):
            toks = text.split()
            nums = [_num(t) for t in toks if _num(t) is not None]
            if nums:
                kind = "typical_detail"
                cap = nums[-1]                      # governing phiRn (last value on the row)
                vals = {"bolts": int(nums[0])}      # bolt count (first value after the plate)
        elif subj.startswith("FRAME:"):
            kind = "frame_analysis"
        recs.append({"id": nid, "calc": sheet.split("-")[0], "kind": kind, "elements": [subj] if subj else [],
                     "values": vals, "uc": uc, "demand": demand, "capacity": cap, "inputs": []})
    rel_out = []
    for r in rels:
        rr = dict(r)
        if r["kind"] == "frames-into" and not rr.get("end"):
            rr["end"] = ends.get((r["src"], r["dst"]), "i")
        rel_out.append(rr)
    bolts = {r["elements"][0]: r["values"].get("bolts") for r in recs if r["kind"] == "typical_detail" and r["elements"]}
    return {"elements": els, "relations": rel_out, "records": recs, "types": [
        {"id": n["id"], "bolts": bolts.get(n["id"])} for n in nodes.values() if n["kind"] in ("type", "detail", "material")],
        "occurrences": [o | {"ref": n["id"]} for n in nodes.values() for o in n.get("occurrences", [])],
        "source": "registry rebuilt from documents (registry_ingested.json + model.ifc)"}
