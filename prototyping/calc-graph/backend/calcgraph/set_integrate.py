"""Integrate the calc records (calc_records.json) and connection nodes (connections.json) into
the drawing-set app: one integrated.json beside graph.json, read by /api/sets/{sid}/integrated.

What it adds, all derived and gitignored (data/sets/<sid>/):
  records       every design record with its row / page evidence (pages become evidence locations)
  record_edges  the calc load path (exact / inferred / absent joins), evidence on both rows
  notes         engineer commentary attached to records
  record_links  each element -> calc PAGE link re-targeted to the records on that page whose
                size / level (footings: plan dimensions) match the element; the page link stays
  connections   connection types (S8 details), instances (bubbles / plan symbols) and what they
                attach to, plus 3D marker positions for instances attached to modelled elements
  overlay       the 2021 RISAFloor model geometry in ITS OWN coordinates (no registration claimed)
  findings      load-path gaps, unsupported member ends, storey-height mismatch, connection calcs
Nothing here re-reads the PDFs except the stair package's parapet pages (one connection-design
record whose words need boxes) - everything else is built on the two track outputs.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict

import pymupdf

from . import plans_to_ifc, sizes

FT = plans_to_ifc.FT
ROW_TYPES_NOT_LINKABLE = {"node", "r3d_node", "grid_line", "parameter", "floor", "floor_load", "area_load_def"}
PAGE_TYPE_TABLE = {
    "enercalc_design": "Enercalc designs", "cfs_design": "CFS Designer runs", "hand_calc": "Hand / spreadsheet calcs",
    "load_criteria": "Load criteria", "model_sketch": "Model sketches", "connection_design": "Connection designs",
}
RUN_SECTION = {"risafloor": "B", "risa3d": "C", "risafoundation": "D", "enercalc": "E", "cfs": "E"}
GAP_DL_K = 2.0  # a stack carrying more dead load than this while its joined members deliver under half of it is a gap


def _row_ev(row: dict, note: str = "") -> dict:
    text = " | ".join(str(v) for v in row.get("cells", {}).values() if str(v).strip())
    return {"doc": row["doc"], "page": row["page"], "sheet": row.get("sheet", ""), "table": row.get("table", ""),
            "rects": [row["bbox"]], "text": text, "note": note}


def _ev(e: dict, note: str = "") -> dict:
    rects = e.get("rects") or ([e["bbox"]] if e.get("bbox") else [])
    return {"doc": e["doc"], "page": e["page"], "sheet": e.get("sheet", ""), "table": e.get("table", ""),
            "rects": rects, "text": e.get("text", ""), "note": e.get("note", note)}


def _cell_size(rows: list[dict]) -> str:
    for row in rows:
        for k, v in row.get("cells", {}).items():
            if re.search(r"shape|size", k, re.I):
                n = sizes.norm(str(v), risa=True)
                if n:
                    return n["norm"]
    return ""


def _size_of(r: dict) -> str:
    v = r.get("values", {})
    return (v.get("size_norm") or "").upper() or _cell_size(r.get("rows", []))


def _title(r: dict, size: str) -> str:
    v, t = r.get("values", {}), r["type"]
    if t == "footing" and v.get("length_ft"):
        return f"{r['label']} {v['length_ft']:g}x{v['width_ft']:g} ft x {v.get('thick_in', 0):g} in"
    if t in ("member", "r3d_member", "column_stack") and size:
        return f"{r['label']} {size}"
    return r["label"]


def _slim_records(recs: list[dict], runs: dict) -> list[dict]:
    out = []
    for r in recs:
        size = _size_of(r)
        if "rows" in r:
            ev = [_row_ev(row) for row in r["rows"]]
            table = r["rows"][0]["table"] if r["rows"] else r["type"]
        else:
            ev = [_ev(e) for e in r.get("evidence", [])]
            table = PAGE_TYPE_TABLE.get(r["type"], r["type"])
        sec = "STAIR" if r["run"].startswith("stair") else r.get("section") or RUN_SECTION.get(r["run"], "")
        vals = {k: v for k, v in r.get("values", {}).items() if k not in ("subtotal",)}
        out.append({"id": r["id"], "type": r["type"], "run": r["run"], "run_title": runs.get(r["run"], r["run"]),
                    "section": sec, "label": r["label"], "title": _title(r, size), "level": r.get("level", ""),
                    "size": size, "table": table, "tables": r.get("tables", []), "pages": r.get("pages", []),
                    "values": vals, "ev": ev})
    return out


# ---------------- element links re-targeted to records ----------------
def _sizes_of_page_rec(r: dict) -> set[str]:
    out = set()
    for s in r.get("values", {}).get("sizes", []) or []:
        n = sizes.norm(str(s), risa=True)
        out.add(n["norm"] if n else str(s).upper())
    return out


def retarget(elements: list[dict], calcs: list[dict], links: list[dict], recs: list[dict]) -> tuple[list[dict], dict]:
    E = {e["id"]: e for e in elements}
    C = {c["id"]: c for c in calcs}
    on_page: dict[tuple, list[dict]] = defaultdict(list)
    for r in recs:
        seen = set()
        for ev in r["ev"]:
            k = (ev["doc"], ev["page"])
            if k not in seen:
                seen.add(k)
                on_page[k].append(r)
    out, why = [], Counter()
    for l in links:
        e, c = E[l["el"]], C[l["calc"]]
        cands = on_page.get((c["doc"], c["page"]), [])
        size, lvl = e.get("size_norm", ""), e.get("level", "")
        hit, rule = [], ""
        if l["tier"] == "footing schedule" and e.get("schedule"):
            sch = e["schedule"]
            for r in cands:
                v = r["values"]
                if r["type"] == "footing" and v.get("length_ft") == sch["length_ft"] and v.get("width_ft") == sch["width_ft"]:
                    hit.append(r)
            if hit:
                thick = {r["values"].get("thick_in") for r in hit}
                agree = thick == {round(sch["thick_ft"] * 12, 1)} or thick == {sch["thick_ft"] * 12}
                rule = (f"footing {sch['length_ft']:g}x{sch['width_ft']:g} ft = {len(hit)} RISAFoundation footing record(s) of that plan size; "
                        f"thickness {'agrees' if agree else 'differs: drawn ' + format(sch['thick_ft'] * 12, 'g') + ' in vs calc ' + ', '.join(format(t, 'g') + ' in' for t in sorted(thick))}"
                        "; which joint is this footing is not determined (no coordinates join drawings to calcs)")
        else:
            row_hits = [r for r in cands if r["type"] not in ROW_TYPES_NOT_LINKABLE and r["type"] not in PAGE_TYPE_TABLE
                        and size and r["size"] == size]
            lvl_ok = [r for r in row_hits if not r["level"] or not lvl or r["level"] == lvl or not lvl.startswith(("Level 2", "Roof"))]
            page_recs = [r for r in cands if r["type"] in PAGE_TYPE_TABLE and (not _sizes_of_page_rec(r) or size in _sizes_of_page_rec(r))]
            if lvl_ok:
                hit = lvl_ok
                n = len(hit)
                rule = (f"{size} {('at ' + lvl) if lvl else ''} = {n} record{'s' if n > 1 else ''} on {c['sheet_id']} printing that size"
                        + (" - the size cannot say which one (positional match dropped: the 2021 calc model is a different geometry)" if n > 1 else ""))
            elif page_recs:
                hit = page_recs
                rule = f"page record covering {c['sheet_id']}" + (f" (prints {size})" if size and size in _sizes_of_page_rec(page_recs[0]) else "")
            elif row_hits:
                why["size on the page but at another level"] += 1
            elif not cands:
                why["no record on that page"] += 1
            else:
                why["no record on that page prints the element's size"] += 1
        if hit:
            out.append({"el": l["el"], "calc": l["calc"], "records": [r["id"] for r in hit], "tier": l["tier"], "score": l["score"],
                        "rule": rule})
    return out, dict(why)


# ---------------- parapet connection design (stair package) ----------------
def parapet_record(stair_path: str | None) -> dict | None:
    if not stair_path:
        return None
    d = pymupdf.open(stair_path)
    ev = []

    def find(pno: int, needles: list[str], note: str):
        if pno > len(d):
            return
        page = d[pno - 1]
        rects, txt = [], []
        for n in needles:
            for q in page.search_for(n)[:2]:
                rects.append([round(q.x0, 1), round(q.y0, 1), round(q.x1, 1), round(q.y1, 1)])
                txt.append(n)
        if rects:
            ev.append({"doc": "stair", "page": pno, "sheet": f"STAIR-{pno}", "table": "", "rects": rects, "text": " | ".join(dict.fromkeys(txt)),
                       "note": note})

    find(15, ["PARAPET DESIGN", "GRID B & 4", "GRID D & 5", "HSS POST PER PLAN", "FULL HT STIFFNER"], "parapet sections at grid B & 4 and D & 5 (2023 drawing grids)")
    find(16, ["hparapet", "Components & Cladding"], "parapet wind pressures (components & cladding)")
    find(17, ["CONN1", "to Post", "CHECKANGLE", "WELD"], "CONN1 - post to column, angle and weld check (handwritten)")
    find(18, ["Angle Design", "Parapet.ec6"], "Enercalc angle design (DPH - Bldg 12 Parapet.ec6)")
    find(20, ["CONN2", "toBMWEB"], "CONN2 - post to beam web (handwritten)")
    if not ev:
        return None
    return {"id": "stair:connection_design:PARAPET", "type": "connection_design", "run": "stair:hand",
            "run_title": "KPFF stair hand calcs (stair package, 2023)", "section": "STAIR", "label": "Parapet post connections",
            "title": "Parapet post connections - CONN1 post to column, CONN2 post to beam web", "level": "Roof", "size": "",
            "table": PAGE_TYPE_TABLE["connection_design"], "tables": [], "pages": sorted({e["page"] for e in ev}),
            "values": {"designs": "parapet post connections: angle, weld (CONN1) and beam-web plate (CONN2)",
                       "locations_named": "grid B & 4, grid D & 5 (section marks on p15)", "detail_cited": "none"},
            "ev": ev}


# ---------------- connections ----------------
def _slim_conn(conns: dict) -> tuple[list[dict], list[dict]]:
    tkeep = ("id", "detail", "sheet", "page", "doc", "sheet_title", "category", "title", "is_connection", "scale", "bbox",
             "number_rect", "title_rects", "spec", "sizes", "instances", "referenced_from_details", "calc_refs", "rule")
    ikeep = ("id", "type_id", "ref", "sheet", "page", "doc", "via", "symbol", "symbol_name", "legend_text", "bbox", "rects",
             "point", "grid", "grid_node", "attached", "attach_rule", "unattached_reason", "in_view", "attach_from", "context")
    types = [{k: t.get(k) for k in tkeep} for t in conns["types"]]
    inst = []
    for i in conns["instances"]:
        x = {k: i.get(k) for k in ikeep}
        x["leader_end"] = (i.get("leader") or {}).get("end")
        inst.append(x)
    return types, inst


def conn_markers(graph: dict, inst: list[dict]) -> tuple[list[dict], Counter]:
    """3D positions (three.js metres, IFC Y-up: x = east, y = up, z = -north) for instances attached
    to a modelled element on a plan sheet, through the same grid calibration the 3D model was built with."""
    m = graph.get("model") or {}
    cal, sheets = m.get("calibration") or {}, {s["sheet"]: s for s in graph["sheets"]}
    ref = m.get("reference_sheet")
    stats = Counter()
    if not ref or ref not in cal:
        return [], stats
    frame = plans_to_ifc.Frame(cal[ref], sheets[ref])
    maps = {sh: frame.mapper(sheets[sh], cal[sh]) for sh in cal if sh in sheets}
    E = {e["id"]: e for e in graph["elements"]}
    el_ft = (m.get("elevations") or {})
    lv = {"Level 2": el_ft.get("level2", {}).get("ft"), "Roof": el_ft.get("roof", {}).get("ft"), "Level 1 / Foundation": 0.0}
    out = []
    for i in inst:
        if not i["attached"]:
            continue
        att3d = [a for a in i["attached"] if (E.get(a["id"], {}).get("model") or {}).get("in3d")]
        if not att3d:
            stats["attached element not in 3D"] += 1
            continue
        if i["sheet"] not in maps:
            stats["not on a calibrated plan sheet"] += 1
            continue
        e = E[att3d[0]["id"]]
        z = lv.get(e.get("level", ""))
        if z is None:
            stats["no level elevation"] += 1
            continue
        p = i["leader_end"] if i.get("attach_from") == "leader end" and i.get("leader_end") else i["point"]
        X, Y = maps[i["sheet"]](p[0], p[1])
        out.append({"inst": i["id"], "el": e["id"], "pos": [round(X * FT, 3), round(z * FT, 3), round(-Y * FT, 3)],
                    "rule": f"{i['sheet']} {'leader end' if p is i.get('leader_end') else 'symbol / bubble point'} through the {ref} grid calibration, "
                            f"at the attached element's level ({e.get('level')}, {z:g} ft)"})
    return out, stats


# ---------------- 3D overlay of the 2021 calc model ----------------
def overlay(cr: dict, recs: list[dict], graph: dict, findings: list[dict]) -> dict:
    R = {r["id"]: r for r in recs}
    members, columns = [], []
    absent_ends = Counter(e["src"] for e in cr["load_path"] if e["kind"] == "member->support" and e["join"] == "absent")
    for r in recs:
        v = r["values"]
        if r["run"] == "risafloor" and r["type"] == "member" and v.get("geom"):
            g = v["geom"]
            members.append({"rec": r["id"], "label": r["label"], "size": r["size"], "level": r["level"], "a": g["start"], "b": g["end"],
                            "elev": g["elev_ft"], "absent_ends": absent_ends.get(r["id"], 0)})
        elif r["run"] == "risafloor" and r["type"] == "column_stack" and v.get("z") is not None:
            columns.append({"rec": r["id"], "label": r["label"], "size": r["size"] or v.get("shape", ""), "z": v["z"], "x": v["x"],
                            "bot": v.get("bot_el", 0.0), "top": v.get("top_el", 0.0)})
    lv = cr["geometry"]["levels"]
    m = graph.get("model") or {}
    el = m.get("elevations") or {}
    diff = []
    calc_lv_ev = [_ev(lv[k]["source"], f"calc {k} = {lv[k]['elev_ft']:g} ft") for k in ("Level 2", "Roof") if k in lv]
    draw_lv_ev = [_ev(el[k] | {"doc": "plans"}, f"drawings {k} = {el[k]['ft']:g} ft" + (" (assumed)" if el[k].get("assumed") else ""))
                  for k in ("level2", "roof") if k in el]
    if calc_lv_ev and draw_lv_ev:
        diff.append({"what": "Storey heights", "text": (f"calc Level 2 {lv['Level 2']['elev_ft']:g} ft, roof {lv['Roof']['elev_ft']:g} ft (RISAFloor Floors table, B32) - "
                                                         f"drawings Level 2 {el['level2']['ft']:g} ft, top of parapet {el['roof']['ft']:g} ft (S3.0.1)"),
                     "calc": calc_lv_ev, "draw": draw_lv_ev})
    for f in findings:
        if f["kind"] in ("grid mismatch", "size mismatch"):
            evs = f["evidence"]
            calc = [x for x in evs if x["doc"] != "plans"]
            draw = [x for x in evs if x["doc"] == "plans"]
            diff.append({"what": "Grids" if f["kind"] == "grid mismatch" else "Moment frame sizes", "text": f["text"],
                         "calc": calc, "draw": draw})
    return {"levels": {k: v["elev_ft"] for k, v in lv.items()}, "axes": cr["geometry"]["axes"], "members": members, "columns": columns,
            "orientation": ("numbered grids run the same way as the drawings' (1 at one end) and lettered grids A..E the same way as A..F; "
                            "that is all the two share - spacings, grid lines and storey heights differ"),
            "transform_dropped": cr.get("positional", {}).get("reason", ""), "differences": diff}


# ---------------- findings ----------------
def new_findings(cr: dict, recs: list[dict], parapet: dict | None, conns: dict, types: list[dict], graph: dict) -> list[dict]:
    R = {r["id"]: r for r in recs}
    out = []
    # gravity load-path gap / disagreement (column dead load vs reactions of the members joined to the stack)
    for row in cr.get("reaction_check", {}).get("rows", []):
        rid = f"risafloor:column_stack:{row['stack']}"
        r = R.get(rid)
        evs = []
        if r:
            for ev in r["ev"]:
                if ev["table"] == "Column Stacks" or (ev["table"].startswith("Column Forces/Moments, Dead & Other Categories : Axial Force")
                                                      and row["level"] in ev["text"]):
                    evs.append(ev | {"note": "column stack" if ev["table"] == "Column Stacks" else f"column dead load at {row['level']}"})
        if row["column_dl_k"] > GAP_DL_K and row["sum_member_dl_k"] < 0.5 * row["column_dl_k"]:
            out.append({"kind": "gravity load-path gap", "severity": "high", "rec": rid,
                        "text": (f"{row['stack']} at {row['level']} carries {row['column_dl_k']:g} k dead load, but the members joined to it in the "
                                 f"RISAFloor tables deliver {row['sum_member_dl_k']:g} k - the load reaches the column by a path the printed tables do not show"),
                        "evidence": evs})
        elif not row["agree"]:
            out.append({"kind": "column load vs member reactions differ", "severity": "info", "rec": rid,
                        "text": f"{row['stack']} at {row['level']}: column dead load {row['column_dl_k']:g} k vs joined member reactions {row['sum_member_dl_k']:g} k (more than 5 % apart)",
                        "evidence": evs})
    for e in cr["load_path"]:
        if e["join"] != "absent":
            continue
        src = R.get(e["src"])
        name = src["title"] if src else e["src"]
        evs = [_ev(x) for x in e["evidence"]["src"]]
        if e["kind"] == "member->support":
            out.append({"kind": "unsupported member end", "severity": "high", "rec": e["src"],
                        "text": f"{name} ({src['level'] if src else ''}) {e.get('end', '')} end: {e['rule']}", "evidence": evs})
        else:
            out.append({"kind": "calc load not traced", "severity": "info", "rec": e["src"],
                        "text": f"{name}: {e['kind']} - {e['rule']}", "evidence": evs})
    lv = cr["geometry"]["levels"]
    el = (graph.get("model") or {}).get("elevations") or {}
    out.append({"kind": "storey height mismatch", "severity": "high",
                "text": (f"The calc model's storeys are Level 2 = {lv['Level 2']['elev_ft']:g} ft and Roof = {lv['Roof']['elev_ft']:g} ft (RISAFloor Floors table); "
                         "the drawings put Level 2 at 16'-0\" and the top of parapet at 32'-0\" (S3.0.1). Column lengths, frame heights and drift in the "
                         "calcs are for a taller building than the one drawn."),
                "evidence": [_ev(lv[k]["source"]) for k in ("Level 2", "Roof")]
                + [_ev(el[k] | {"doc": "plans"}, f"drawings: {el[k]['text']}" + (" (roof placed here - assumed)" if el[k].get("assumed") else ""))
                   for k in ("level2", "roof") if k in el]})
    hits = conns.get("calc", {}).get("hits", [])
    main_conn = [h for h in hits if h["doc"] == "calcs" and h["designs_connection"]]
    risa = [h for h in hits if h["rule"] == "risa_connection_props"]
    out.append({"kind": "no connection calcs in the main package", "severity": "high",
                "text": (f"No page of the main KPFF package designs a steel connection: the RISA-3D 'Member RISAConnection Properties' table (C14) "
                         f"assigns none; the only connection checks are Simpson clip / connector checks inside the CFS stud runs "
                         f"({', '.join(sorted({h['calc'].split(':')[1] for h in main_conn})) or 'none'}). {sum(1 for t in types if t['is_connection'])} connection details "
                         f"are drawn and called out {sum(len(t['instances'] or []) for t in types if t['is_connection'])} times on the plans and elevations."),
                "evidence": [{"doc": h["doc"], "page": h["page"], "rects": h["rects"], "text": h["what"], "note": h["snippet"][:160]} for h in risa + main_conn]})
    if parapet:
        cand = next((t for t in types if t["id"] == "2/S8.2.7"), None)
        evs = [parapet["ev"][0]] + [x for x in parapet["ev"] if x["page"] in (17, 20)]
        if cand:
            evs.append({"doc": cand["doc"], "page": cand["page"], "rects": [cand["number_rect"]] + (cand["title_rects"] or []),
                        "text": f"{cand['id']} {cand['title']}", "note": "candidate detail by title only"})
        out.append({"kind": "parapet calc not tied to a detail", "severity": "warn", "rec": parapet["id"],
                    "text": ("The 2023 stair package designs the parapet post connections (CONN1 post to column, CONN2 post to beam web, pp 15-20) "
                             "but cites no detail number; " + (f"{cand['id']} '{cand['title']}' ({len(cand['instances'] or [])} callouts) is the likely detail by its title only - not a link."
                                                              if cand else "no PARAPET POST detail was found on S8.x.")),
                    "evidence": evs})
    return out


# ---------------- entry ----------------
def build(graph: dict, cr: dict, conns: dict, meta: dict) -> dict:
    stale = []
    if conns.get("source_graph_built_at") != graph.get("built_at"):
        stale.append(f"connections.json was built from graph {conns.get('source_graph_built_at')} - graph is {graph.get('built_at')}")
    if cr.get("source_graph_built_at") and cr["source_graph_built_at"] != graph.get("built_at"):
        stale.append(f"calc_records.json was built from graph {cr.get('source_graph_built_at')} - graph is {graph.get('built_at')}")
    recs = _slim_records(cr["records"], cr.get("runs", {}))
    stair = meta["docs"].get("stair", {}).get("path")
    par = parapet_record(stair)
    if par:
        recs.append(par)
    rlinks, rl_why = retarget(graph["elements"], graph["calcs"], graph["links"], recs)
    types, inst = _slim_conn(conns)
    markers, mk_stats = conn_markers(graph, inst)
    finds = new_findings(cr, recs, par, conns, types, graph)
    ov = overlay(cr, recs, graph, graph["findings"])
    edges = [e | {"evidence": {k: [_ev(x) for x in e["evidence"][k]] for k in ("src", "dst")}} for e in cr["load_path"]]
    if par:
        cand = next((t for t in types if t["id"] == "2/S8.2.7"), None)
        if cand:
            par["values"]["candidate_detail"] = f"{cand['id']} {cand['title']} (title only, not a link)"
    links_with = {(l["el"], l["calc"]) for l in rlinks}
    cov = {
        "records": len(recs), "records_by_run_type": dict(Counter(f"{r['run']} / {r['type']}" for r in recs)),
        "record_rows": sum(len(r["ev"]) for r in recs),
        "record_edges": len(edges), "record_edges_by_kind_join": dict(Counter(f"{e['kind']} [{e['join']}]" for e in edges)),
        "record_edges_by_join": dict(Counter(e["join"] for e in edges)),
        "notes": len(cr.get("commentary", [])),
        "page_links": len(graph["links"]), "page_links_retargeted": len(links_with),
        "page_links_not_retargeted": len(graph["links"]) - len(links_with), "not_retargeted_why": rl_why,
        "record_link_pairs": sum(len(l["records"]) for l in rlinks),
        "records_linked_to_elements": len({r for l in rlinks for r in l["records"]}),
        "elements_with_record_links": len({l["el"] for l in rlinks}),
        "connection_types": len(types), "connection_instances": len(inst),
        "connection_instances_attached": sum(1 for i in inst if i["attached"]),
        "connection_element_edges": sum(len(i["attached"]) for i in inst),
        "connection_markers_3d": len(markers), "connection_markers_not_placed": dict(mk_stats),
        "overlay_members": len(ov["members"]), "overlay_columns": len(ov["columns"]),
        "new_findings": dict(Counter(f["kind"] for f in finds)),
    }
    return {"built_at": None, "sources": {"graph": graph.get("built_at"), "calc_records": cr.get("built_at"), "connections": conns.get("built_at")},
            "stale": stale, "runs": cr.get("runs", {}) | {"stair:hand": "KPFF stair hand calcs (stair package, 2023)"},
            "records": recs, "record_edges": edges, "notes": cr.get("commentary", []), "reaction_check": cr.get("reaction_check"),
            "record_links": rlinks, "conn_types": types, "conn_instances": inst, "conn_markers": markers,
            "conn_legends": conns.get("legends", {}), "overlay": ov, "findings": finds, "coverage": cov}
