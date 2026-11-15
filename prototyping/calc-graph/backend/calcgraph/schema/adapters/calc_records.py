"""data/sets/<set>/calc_records.json (calc_records.py output) -> schema Bundle.

record      -> CalcRecord: one evidence item per table row (row bbox on its page) or the
               record's own evidence; values with units from the field name / header
               ("max_start_reaction_k", "PreDL[ksf]") or, for RISA coordinates, the unit the
               output declares once ("... feet" in geometry.axes); governing UC = max of the
               *_uc fields; member geometry -> points in the calc model's own frame
load_path   -> Relation (feeds for loads, bears-on for members / stacks / footings); an
               'absent' join has no target, so it becomes a Finding (load path gap)
commentary  -> Finding (engineer's note, attached to its record)
runs, tables, reaction_check, sketch_fit, positional are analysis metadata, not facts: skipped
(positional.kept == False is why CalcModelFt has no registration to BuildingFt).
"""
from __future__ import annotations

import json
import os
from collections import Counter

from ..frames import CalcModelFt, Point2
from ..models import Bundle, CalcRecord, Finding, Relation, RelationKind
from ..units import Quantity
from ._common import DocRegistry, Reject, Rule, Tally, build, evidence_list, hid, pdf_ev, produced_by, prov, to_values
from .drawing_set import registry_for

R_REC = Rule(engine="calc_records (calc_records.json carries no engine version)", confidence=1.0)
# for an output written before calc_records stated join confidence itself (calc_records.JOIN_CONFIDENCE)
JOIN_CONF = {"exact": 1.0, "inferred": 0.7}
FEEDS = {"load_area->area_load_def", "area_load_def->floor", "floor->member", "line_load->member", "point_load->member"}
BEARS = {"member->column_stack", "column_stack->footing", "member->member", "member->support"}
LABEL_KEYS = frozenset({"col0", "Label", "gov_lc", "grid", "start", "end", "Point Label", "Point", "Start Point",
                        "End Point", "LL Type", "label"})
# units RISA output declares once for the whole run (feet), applied to fields that carry none
RISA_COORDS = {"z": "ft", "x": "ft", "y": "ft", "elev_offset": "ft", "bot_el": "ft", "top_el": "ft"}
# dimensionless by definition of the field (a count, a ratio check)
DIMENSIONLESS = {"studs": "1", "defl_check": "1"}
# locations stored inside values: the record's row evidence already carries them (verified:
# every end_reactions page+bbox is one of the record's rows), so they are not values
LOCATION_KEYS = {"page", "bbox", "rect", "rects"}


def _unmapped(kind: str):
    raise Reject(f"unmapped load-path kind {kind}")


def _strip_locations(d):
    if isinstance(d, dict):
        return {k: _strip_locations(v) for k, v in d.items() if k not in LOCATION_KEYS}
    return d


def _row_text(cells: dict) -> str:
    return " | ".join(str(v) for v in cells.values() if v not in ("", None))


def convert(set_dir: str, strict: bool = False) -> tuple[Bundle, Tally]:
    path = os.path.join(set_dir, "calc_records.json")
    cr = json.load(open(path))
    graph = json.load(open(os.path.join(set_dir, "graph.json")))
    sid = cr.get("set") or graph["id"]
    t = Tally(source=f"{sid}/calc_records.json")
    reg: DocRegistry = registry_for(set_dir, graph)
    b = Bundle(source=t.source, documents=list(reg.docs.values()))
    built = cr.get("built_at")
    axes = (cr.get("geometry") or {}).get("axes", "")
    coords_declared = RISA_COORDS if "feet" in axes else {}
    if coords_declared:
        t.notes.append(f"RISA node coordinates take the unit the output declares once: {axes[:90]!r}")
    runs = cr.get("runs") or {}
    P = produced_by(cr, "calc_records")

    def rid(x):
        return f"rec:{sid}:{x}"

    for r in cr["records"]:
        def make(r=r):
            uc = Counter()
            if r.get("rows"):
                ev = [pdf_ev(reg, w["doc"], w["page"], [w.get("bbox")], _row_text(w.get("cells") or {}),
                             note=w.get("table", ""), sheet=w.get("sheet")) for w in r["rows"]]
                doc = r["rows"][0]["doc"]
            else:
                ev = evidence_list(reg, r.get("evidence"))
                doc = r.get("doc")
            vals = dict(r.get("values") or {})
            geom = vals.pop("geom", None)
            values = to_values(uc, _strip_locations(vals), label_keys=LABEL_KEYS,
                               declared={**DIMENSIONLESS, **(coords_declared if r["run"].startswith("risa") else {})})
            ucs = [v for k, v in values.items() if (k == "uc" or k.endswith("_uc")) and isinstance(v, Quantity)]
            gpts = []
            if geom and geom.get("start") and geom.get("end"):
                fr = CalcModelFt(model=runs.get(r["run"], r["run"]))
                gpts = [Point2(frame=fr, x=geom["start"][0], y=geom["start"][1]),
                        Point2(frame=fr, x=geom["end"][0], y=geom["end"][1])]
                values.update(to_values(uc, {k: v for k, v in geom.items() if k not in ("start", "end")}, prefix="geom."))
            return {"_units": uc, "id": rid(r["id"]), "doc_sha": reg.sha(doc), "run": r["run"], "record_type": r["type"],
                    "section": r.get("section") or "", "label": str(r.get("label") or ""), "level": r.get("level") or "",
                    "tables": r.get("tables") or [], "values": values,
                    "uc": max(ucs, key=lambda x: x.value) if ucs else None,
                    "governing_lc": str(vals["gov_lc"]) if vals.get("gov_lc") not in (None, "") else None,
                    "geometry": gpts,
                    "provenance": prov(ev, r.get("rule"), R_REC, declared_rule_id=f"calc_records.{r['run']}.{r['type']}",
                                       confidence=r.get("confidence"), at=built, **P)}
        build(t, b, "calc_records", CalcRecord, r["id"], make, strict)

    for x in cr.get("load_path", []):
        ev_items = (x["evidence"].get("src") or []) + (x["evidence"].get("dst") or [])
        if not x.get("dst"):
            build(t, b, "findings", Finding, x["src"], lambda x=x, ev_items=ev_items: {
                "id": f"finding:{sid}:{hid('load path gap', x['src'], x['kind'])}", "kind": "calc load path gap",
                "severity": "medium", "text": f"{x['kind']}: {x['rule']}", "subjects": [rid(x["src"])],
                "provenance": prov(evidence_list(reg, ev_items), f"calc_records.load_path.{x['kind']}", R_REC,
                                   rule_text=x["rule"], confidence=x.get("confidence"), at=built, **P)}, strict)
            continue
        kind = RelationKind.feeds if x["kind"] in FEEDS else RelationKind.bears_on if x["kind"] in BEARS else None
        build(t, b, "relations", Relation, f"{x['src']}->{x['dst']}", lambda x=x, kind=kind, ev_items=ev_items: {
            "id": f"rel:{x['kind']}:{rid(x['src'])}->{rid(x['dst'])}" + (f":{x['end']}" if x.get("end") else ""),
            "kind": kind or _unmapped(x["kind"]),
            "src": rid(x["src"]), "dst": rid(x["dst"]),
            "attrs": {"source_kind": x["kind"], "join": x["join"], **({"end": str(x["end"])} if x.get("end") else {})},
            "provenance": prov(evidence_list(reg, ev_items), f"calc_records.load_path.{x['kind']}",
                               Rule(engine=R_REC.engine, confidence=JOIN_CONF.get(x["join"])), rule_text=x["rule"],
                               confidence=x.get("confidence"), at=built, **P)}, strict)

    for c in cr.get("commentary", []):
        build(t, b, "findings", Finding, c["id"], lambda c=c: {
            "id": f"finding:{sid}:{c['id']}", "kind": "engineer commentary", "severity": "info", "text": c["text"],
            "subjects": [rid(a["record"]) for a in c.get("attached", [])],
            "provenance": prov([pdf_ev(reg, c["doc"], c["page"], c.get("rects") or [c.get("bbox")], c["text"][:200],
                                       note=f"{c.get('colour', '')} note", sheet=c.get("sheet"))], c.get("rule"), R_REC,
                               declared_rule_id="calc_records.commentary", confidence=c.get("confidence"), at=built,
                               **P)}, strict)

    t.skipped["runs (descriptions only, no evidence)"] = len(runs)
    t.skipped["tables (names kept on CalcRecord.tables)"] = len(cr.get("tables", []))
    t.skipped["reaction_check / sketch_fit / positional (analysis metadata)"] = 3
    if cr.get("load_path") and "confidence" not in cr["load_path"][0]:
        t.notes.append("load-path join confidence is adapter-declared: exact 1.0, inferred 0.7 (this output gives a "
                       "join class, not a number)")
    return b, t
