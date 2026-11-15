"""data/sets/<set>/graph.json (set_pipeline / set_graph output) -> schema Bundle.

graph.json element  -> Element (+ Occurrence plan-tag / elevation, + ElementType by size or
                       mark, + Relation instance-of); schedule rows -> Occurrence schedule-row
                       on the type; positions -> BuildingFt via the sheet's own SheetCalibration
                       (sheet points when the sheet has no calibration)
element_edges       -> Relation (beam->column / beam->beam frames-into, column->footing /
                       column->column bears-on)
calcs (pages)       -> CalcSheet;  calc_edges -> Relation feeds;  links -> Link
findings            -> Finding
Identity across sheets is NOT resolved here (one Element per drawn tag, as graph.json has it).
"""
from __future__ import annotations

import json
import os
from collections import Counter

from ..frames import BuildingFt, GridAnchor, Point2, SheetCalibration, SheetPt
from ..models import (Bundle, CalcSheet, DocKind, Element, ElementType, Finding, Link, Occurrence, OccurrenceKind,
                      Relation, RelationKind)
from ._common import ADAPTER_VERSION, DocRegistry, Reject, Rule, Tally, build, evidence_list, hid, pdf_ev, \
    produced_by, prov, to_values

R_TAG = Rule(engine="drawing_ingest (graph.json carries no engine version)", confidence=1.0)
R_LOADPATH = Rule(engine="drawing_loadpath (graph.json carries no engine version)", confidence=1.0)
R_CALC = Rule(engine="set_graph (graph.json carries no engine version)", confidence=1.0)
R_ADAPTER = Rule(engine=ADAPTER_VERSION, version=ADAPTER_VERSION, confidence=1.0)

EDGE_KIND = {"beam->column": RelationKind.frames_into, "beam->beam": RelationKind.frames_into,
             "column->footing": RelationKind.bears_on, "column->column": RelationKind.bears_on}
OCC_KIND = {"smf": OccurrenceKind.elevation, "wall": OccurrenceKind.elevation}
DOC_KIND = {"Drawing set": DocKind.drawing, "Calc package": DocKind.calc}


def registry_for(set_dir: str, graph: dict) -> DocRegistry:
    meta = json.load(open(os.path.join(set_dir, "meta.json")))
    reg = DocRegistry()
    for key, d in meta["docs"].items():
        g = graph.get("docs", {}).get(key, {})
        reg.add(key, d.get("path"), DOC_KIND.get(d.get("role"), DocKind.drawing), d["name"], g.get("pages") or d.get("pages"),
                d.get("role", ""))
    return reg


def calibrations(set_id: str, reg: DocRegistry, graph: dict, t: Tally) -> dict[str, SheetCalibration]:
    model = graph.get("model") or {}
    cal, gft = model.get("calibration") or {}, model.get("grid_ft") or {}
    cols_ft, rows_ft = gft.get("cols") or {}, gft.get("rows_from_A") or {}
    out = {}
    for s in graph.get("sheets", []):
        c = cal.get(s["sheet"])
        if not c:
            continue
        try:
            sc = SheetCalibration(
                sheet=SheetPt(doc_sha=reg.sha("plans"), page=s["page"], sheet=s["sheet"]),
                building=BuildingFt(building=set_id),
                cols=[GridAnchor(label=g["label"], pt=g["pos"], ft=cols_ft[g["label"]]) for g in s["grid"]["cols"]
                      if g["label"] in cols_ft],
                rows=[GridAnchor(label=g["label"], pt=g["pos"], ft=rows_ft[g["label"]]) for g in s["grid"]["rows"]
                      if g["label"] in rows_ft],
                kx_ft_per_pt=c["kx_ft_per_pt"], ky_ft_per_pt=c["ky_ft_per_pt"], depth_ft=max(rows_ft.values()),
                source=f"{s['sheet']} grid bubbles + {c.get('dims_found')} dimension strings "
                       f"(rms {c.get('rms_residual_in')} in, reference sheet {model.get('reference_sheet')})")
        except (Reject, ValueError, KeyError) as e:
            t.notes.append(f"calibration {s['sheet']} not built: {e}")
            continue
        out[s["sheet"]] = sc
    return out


def convert(set_dir: str, strict: bool = False) -> tuple[Bundle, Tally]:
    graph = json.load(open(os.path.join(set_dir, "graph.json")))
    sid = graph["id"]
    t = Tally(source=f"{sid}/graph.json")
    reg = registry_for(set_dir, graph)
    for k, m in reg.missing.items():
        t.notes.append(m)
    b = Bundle(source=t.source, documents=list(reg.docs.values()))
    cals = calibrations(sid, reg, graph, t)
    b.calibrations = list(cals.values())
    built = graph.get("built_at")
    P_TAG, P_LP, P_CALC, P_SET = (produced_by(graph, m) for m in ("drawing_ingest", "drawing_loadpath", "calcpkg_ingest",
                                                                  "set_graph"))

    def el_id(x):
        return f"el:{sid}:{x}"

    def calc_id(x):
        return f"calc:{sid}:{x}"

    # ---- elements, types, occurrences ----
    types: dict[str, list] = {}
    for e in graph["elements"]:
        designation = e.get("size_norm") or e.get("mark") or ""
        tid = f"type:{sid}:{e['type']}:{designation}" if designation else None

        def ev(e=e):
            return pdf_ev(reg, e["doc"], e["page"], e.get("rects") or [e.get("bbox")], e.get("text", ""),
                          sheet=e.get("sheet"))

        def make_el(e=e, tid=tid, designation=designation):
            uc = Counter()
            pos = None
            pt = e.get("at") or (e.get("line") and [(e["line"][0] + e["line"][2]) / 2, (e["line"][1] + e["line"][3]) / 2])
            if pt:
                sp = Point2(frame=SheetPt(doc_sha=reg.sha(e["doc"]), page=e["page"], sheet=e["sheet"]), x=pt[0], y=pt[1])
                pos = cals[e["sheet"]].to_building(sp) if e["sheet"] in cals else sp
            attrs = to_values(uc, {
                "sheet": e.get("sheet"), "sheet_title": e.get("sheet_title"), "sheet_kind": e.get("sheet_kind"),
                "type": e.get("type"), "family": e.get("family"), "text": e.get("text"),
                "vertical_text": e.get("vertical_text"), "grid_node": e.get("grid_node"),
                "grid_node_dist": e.get("grid_node_dist"), "params": e.get("params") or {},
                "schedule": {k: v for k, v in (e.get("schedule") or {}).items() if k not in ("rects", "page", "sheet")},
                "model": {k: v for k, v in (e.get("model") or {}).items() if k != "assumed"},
                "position_rule": "leader end" if e.get("at") else ("drawn line mid-point" if e.get("line") else None),
            }, label_keys=frozenset({"grid_node", "mark", "gid"}))
            return {"_units": uc, "id": el_id(e["id"]), "category": e["cat"], "type_id": tid, "mark": e.get("mark") or "",
                    "designation": designation, "level": e.get("level") or "", "grid": e.get("grid") or "",
                    "position": pos, "attrs": attrs,
                    "provenance": prov([ev()], e.get("rule"), R_TAG, declared_rule_id=f"drawing_ingest.tag.{e.get('family')}",
                                       confidence=e.get("confidence"), at=built, **P_TAG)}

        el = build(t, b, "elements", Element, e["id"], make_el, strict)
        if not el:
            continue
        if tid:
            types.setdefault(tid, []).append((e, el))
        build(t, b, "occurrences", Occurrence, e["id"], lambda e=e, el=el: {
            "id": f"occ:{sid}:{e['id']}", "kind": OCC_KIND.get(e.get("sheet_kind"), OccurrenceKind.plan_tag),
            "subject_id": el.id, "at": el.provenance.evidence[0], "label": f"{e.get('text')} on {e.get('sheet')}",
            "provenance": el.provenance}, strict)
        if tid:
            build(t, b, "relations", Relation, e["id"], lambda el=el, tid=tid: {
                "id": f"rel:instance-of:{el.id}->{tid}", "kind": RelationKind.instance_of, "src": el.id, "dst": tid,
                "provenance": prov(el.provenance.evidence, "schema.instance_of.same_designation", R_ADAPTER,
                                   rule_version=ADAPTER_VERSION, engine=ADAPTER_VERSION, confidence=1.0,
                                   rule_text="same type and normalised size / mark text")}, strict)

    for tid, members in types.items():
        e0 = members[0][0]
        build(t, b, "element_types", ElementType, tid, lambda tid=tid, members=members, e0=e0: {
            "id": tid, "category": e0["cat"], "designation": e0.get("size_norm") or e0.get("mark"),
            "name": e0["type"],
            "provenance": prov([el.provenance.evidence[0] for _, el in members[:20]], "schema.type.by_designation",
                               R_ADAPTER, rule_version=ADAPTER_VERSION, engine=ADAPTER_VERSION, confidence=1.0,
                               rule_text=f"{len(members)} drawn tags share this type + designation (evidence capped at 20)")},
              strict)
        sch = next((e.get("schedule") for e, _ in members if e.get("schedule")), None)
        if sch:
            build(t, b, "occurrences", Occurrence, tid, lambda tid=tid, sch=sch: (lambda ev: {
                "id": f"occ:{sid}:schedule:{tid}", "kind": OccurrenceKind.schedule_row, "subject_id": tid, "at": ev,
                "label": f"schedule row {sch.get('mark')} on {sch.get('sheet')}",
                "provenance": prov([ev], sch.get("rule"), R_TAG, declared_rule_id="drawing_ingest.footing_schedule_row",
                                   confidence=sch.get("confidence"), at=built, **P_TAG)})(
                pdf_ev(reg, "plans", sch.get("page"), sch.get("rects"), sch.get("text", ""), sheet=sch.get("sheet"))),
                strict)

    # ---- element load-path edges ----
    for x in graph.get("element_edges", []):
        build(t, b, "relations", Relation, f"{x['src']}->{x['dst']}", lambda x=x: {
            "id": f"rel:{x['rule']}:{el_id(x['src'])}->{el_id(x['dst'])}",
            "kind": EDGE_KIND[x["rule"]], "src": el_id(x["src"]), "dst": el_id(x["dst"]),
            "attrs": {"source_rule": x["rule"]},
            "provenance": prov(evidence_list(reg, x.get("evidence")), f"drawing_loadpath.{x['rule']}", R_LOADPATH,
                               rule_text=x["rule"], confidence=x.get("confidence"), at=built, **P_LP)}, strict)

    # ---- calc sheets ----
    for c in graph.get("calcs", []):
        build(t, b, "calc_sheets", CalcSheet, c["id"], lambda c=c: {
            "id": calc_id(c["id"]), "doc_sha": reg.sha(c["doc"]), "page": c["page"], "sheet_id": c["sheet_id"],
            "section": c.get("section") or "", "title": c.get("title") or "", "software": c.get("software") or "",
            "role": c.get("role") or "", "level": c.get("level") or "",
            "provenance": prov([pdf_ev(reg, c["doc"], c["page"], [c.get("title_rect")], c.get("title", ""),
                                       note="calc sheet title")], c.get("rule"), R_CALC,
                               declared_rule_id="calcpkg_ingest.sheet_id_and_title", confidence=c.get("confidence"),
                               at=built, **P_CALC)}, strict)

    for x in graph.get("calc_edges", []):
        build(t, b, "relations", Relation, f"{x['src']}->{x['dst']}", lambda x=x: {
            "id": f"rel:feeds:{calc_id(x['src'])}->{calc_id(x['dst'])}:{x['rule']}", "kind": RelationKind.feeds,
            "src": calc_id(x["src"]), "dst": calc_id(x["dst"]), "attrs": {"labels": [str(v) for v in x.get("labels", [])]},
            "provenance": prov(evidence_list(reg, (x["evidence"].get("src") or []) + (x["evidence"].get("dst") or [])),
                               f"set_graph.calc_edge.{x['rule']}", R_CALC, rule_text=x["rule"],
                               confidence=x.get("confidence"), at=built, **P_SET)}, strict)

    # ---- links ----
    for x in graph.get("links", []):
        build(t, b, "links", Link, f"{x['el']}->{x['calc']}", lambda x=x: {
            "id": f"link:{el_id(x['el'])}->{calc_id(x['calc'])}", "src": el_id(x["el"]), "dst": calc_id(x["calc"]),
            "tier": x["tier"], "system": x.get("system") or "",
            "provenance": prov(evidence_list(reg, [x["evidence"]["el"], x["evidence"]["calc"]]), f"set_graph.link.{x['tier']}",
                               R_CALC, rule_text=x.get("rule", ""), confidence=x["score"], at=built, **P_SET)}, strict)

    # ---- findings ----
    for x in graph.get("findings", []):
        subj = [el_id(x["el"])] if x.get("el") else []
        subj += [calc_id(x["calc"])] if x.get("calc") else []
        build(t, b, "findings", Finding, x["kind"], lambda x=x, subj=subj: {
            "id": f"finding:{sid}:{hid(x['kind'], x['text'], subj)}", "kind": x["kind"], "severity": x["severity"],
            "text": x["text"], "subjects": subj,
            "provenance": prov(evidence_list(reg, x.get("evidence")), x.get("rule") or f"set_graph.finding.{x['kind']}", R_CALC,
                               confidence=x.get("confidence"), at=built, **P_SET)},
              strict)

    t.skipped["sheets (no Sheet entity in F1; sheet number kept on occurrences / evidence frames)"] = len(graph.get("sheets", []))
    if not graph.get("producers"):
        t.notes.append("graph.json carries no producers block: every fact's rule_version + engine are adapter-supplied")
    return b, t
