"""Element registry TRUTH for the v2 synthetic building: every node and every place it occurs.

    write(exp, path)      # called by synth.v2.generate after the document writers

Standalone copy (tools/calcgraph-reference): the ifc / drawings / calcs occurrences are built; the
"specs" and "etabs" ones are not (their writers are not part of this copy) - see write().

The registry is the project's index of THINGS (not of documents): every element instance, every
type / material / typical detail, every drawn detail (DET:), every spec paragraph (SPEC:) and
every calc record, each carrying ALL of its occurrences across the model and the documents, plus
the typed relations between them. registry_ingest.py rebuilds the same shape from the documents
alone; scripts/evaluate_registry.py scores the rebuild against this file.

Schema (version 1) - the same for truth and for the ingested rebuild
--------------------------------------------------------------------
{"schema": "calcgraph.registry/1", "source": "truth" | "ingested", "meta": {...},
 "nodes": [NODE], "relations": [RELATION], "counts": {...}}

NODE      {"id": str, "kind": KIND, "type": str, "name": str, "attrs": {...},
           "global_id": str | null, "occurrences": [OCCURRENCE]}
  KIND    element   physical instance or grouping (type: beam girder column brace pier footing
                    grade_beam connection deck | level grid frame)
          type      section / pier type (TYPE:W18X40, TYPE:P-1)
          material  MAT:A992 ...
          detail    typical detail TYPE (DETAIL:ST-3) - what a connection instance is an instance of
          drawn     a drawn detail panel on a sheet (DET:4/S-502 = detail 4 on S-502)
          spec      a spec paragraph (SPEC:05 12 00/2.1.A)
          record    a calc record (the engineer's unit: one member row, one footing, one ELF)

OCCURRENCE - always {"doc": DOC, "how": str, ...} plus per-doc keys; bbox in PDF points
[x0, y0, x1, y1], page 1-based:
  ifc        {"global_id", "ifc_type"}
  drawings   {"sheet", "page", "bbox", "how": plan_tag | schedule_row | elevation_tag |
              grid_bubble | detail | detail_callout | section_cut | note, "text"}
  specs      {"section", "article", "paragraph", "page", "bbox", "how": "spec_article", "text"}
  calcs      {"record", "page", "bbox", "sheet", "how": calc_row | calc_block, "text",
              "text_layer": bool}   (text_layer false = scanned page, unreadable without OCR)
  etabs      {"object_type", "label", "story", "how": "etabs-object"}
  ingested occurrences additionally carry {"rule": str, "confidence": "exact" | "inferred"}.
  RESERVED, not built: discussed-in (meetings) -
             {"doc": "meetings", "how": "discussed-in", "meeting_id", "t0_s", "t1_s",
              "speaker", "transcript_span": [char_start, char_end], "text"}
             a node mentioned in a recorded design meeting; the occurrence model is open, so a
             new doc kind needs no schema change - evaluators score per doc kind they know.

RELATION  {"src", "dst", "kind", ...}; kind is one of
  frames-into  member -> support (via = connection node, end = i | j)
  bears-on     deck -> member, column -> pier (via base plate), pier -> footing
  connected-by member -> connection node, connection node -> support
  instance-of  element -> type / material / detail
  specified-by type / material / detail / frame / deck -> spec paragraph
  designed-by  element / detail -> calc record
  detailed-by  connection instance / detail type -> drawn detail (DET:)
  member-of    element -> level / grid / frame
  feeds        calc record -> calc record (an input of)
  ingested relations additionally carry {"rule", "confidence"}.

Truth assembly (all from exp, which the writers filled in place; ETABS occurrences from the ETABS
adapter over the same exp): IFC occurrence for every element with a global_id; each writer
occurrence attached to its ref (calc occurrences get the record they print, spec occurrences the
paragraph they sit in); a node designed by a record also occurs where that record prints
(designed-by fan-out, e.g. DETAIL:ST-3 at its E1 rows); drawn details occur at their panel.
"""
from __future__ import annotations

import json
from collections import defaultdict

SCHEMA = "calcgraph.registry/1"
DOCS = ("ifc", "drawings", "specs", "calcs", "etabs")
RELATION_KINDS = ("frames-into", "bears-on", "connected-by", "instance-of", "specified-by",
                  "designed-by", "detailed-by", "member-of", "feeds")

_EL_ATTRS = ("size", "level", "line", "grid", "kind", "roles", "frame", "frames", "conn_type", "member", "end",
             "to", "mark", "pier_type", "B_ft", "h_in", "b_in", "system", "axis", "pos_ft", "elev_ft", "sfrs")


def _key(o: dict) -> tuple:
    return (o["doc"], o.get("page"), tuple(o.get("bbox") or ()), o.get("global_id"), o.get("label"),
            o.get("story"), o.get("how"))


def build(exp: dict, etabs_occurrences: list[dict] | None = None) -> dict:
    nodes: dict[str, dict] = {}

    def node(nid, kind, typ, name="", attrs=None, gid=None):
        if nid not in nodes:
            nodes[nid] = {"id": nid, "kind": kind, "type": typ, "name": name, "attrs": attrs or {},
                          "global_id": gid, "occurrences": []}
        return nodes[nid]

    for e in exp["elements"]:
        n = node(e["id"], "element", e["type"], e.get("name") or e["id"],
                 {k: e[k] for k in _EL_ATTRS if e.get(k) not in (None, "", [])}, e.get("global_id"))
    for t in exp["types"]:
        kind = {"section": "type", "pier": "type", "material": "material", "detail": "detail"}[t["kind"]]
        node(t["id"], kind, t["kind"], t.get("name", ""), {k: v for k, v in t.items() if k not in ("id", "kind", "name")})
    for dt in exp.get("details", []):
        node(dt["id"], "drawn", "drawn_detail", dt.get("title", ""), {"detail_type": dt.get("detail_type"),
                                                                       "sheet": dt["sheet"]})
    arts = {a["id"]: a for a in exp.get("spec_articles", [])}
    for a in arts.values():
        node(a["id"], "spec", "spec_paragraph", a.get("title", ""),
             {"section": a["section"], "section_title": a.get("section_title"), "article": a["article"],
              "paragraph": a["paragraph"], "text": a.get("text", "")})
    recs = {r["id"]: r for r in exp["records"]}
    for r in recs.values():
        node(r["id"], "record", r["kind"], r.get("calc_title", ""),
             {"calc": r["calc"], "section": r["section"], "software": r.get("software"), "table": r.get("table"),
              "elements": r.get("elements", []), "check": r.get("check"), "uc": r.get("uc")})

    def add(nid, occ):
        if nid not in nodes:
            return False
        n = nodes[nid]
        if all(_key(o) != _key(occ) for o in n["occurrences"]):
            n["occurrences"].append(occ)
        return True

    # ifc
    for n in list(nodes.values()):
        if n["global_id"]:
            add(n["id"], {"doc": "ifc", "how": "ifc_product", "global_id": n["global_id"]})
    # writer occurrences
    occs = exp.get("occurrences", [])
    calc_at = {(o["page"], tuple(o["bbox"])): o["ref"] for o in occs if o["doc"] == "calcs" and o["ref"] in recs}
    art_at = {(a["page"], tuple(a["bbox"])): a for a in arts.values()}
    orphans = defaultdict(int)
    for o in occs:
        base = {"doc": o["doc"], "how": o["how"], "page": o["page"], "bbox": o["bbox"], "text": o.get("text", "")}
        if o["doc"] == "drawings":
            occ = {**base, "sheet": o["sheet"]} | ({"symbol": o["symbol"]} if o.get("symbol") else {})
        elif o["doc"] == "specs":
            a = art_at.get((o["page"], tuple(o["bbox"]))) or {}
            occ = {**base, "section": a.get("section", o.get("sheet")), "article": a.get("article"),
                   "paragraph": a.get("paragraph"), "spec": a.get("id")}
        elif o["doc"] == "calcs":
            rid = o["ref"] if o["ref"] in recs else calc_at.get((o["page"], tuple(o["bbox"])))
            occ = {**base, "sheet": o["sheet"], "record": rid, "text_layer": o.get("text_layer", True)}
        else:
            occ = base
        if not add(o["ref"], occ):
            orphans[o["ref"]] += 1
    # designed-by fan-out: a node designed by a record occurs where the record prints
    for r in recs.values():
        for o in [x for x in nodes[r["id"]]["occurrences"] if x["doc"] == "calcs"]:
            for el in r.get("elements", []):
                add(el, dict(o))
    # drawn details occur at their panel
    for dt in exp.get("details", []):
        add(dt["id"], {"doc": "drawings", "how": "detail", "sheet": dt["sheet"], "page": dt["page"],
                       "bbox": dt["bbox"], "text": dt.get("title", "")})
    # etabs
    for o in etabs_occurrences or []:
        if not add(o["ref"], {"doc": "etabs", "how": o.get("how", "etabs-object"), "object_type": o["object_type"],
                              "label": o["label"], "story": o["story"]}):
            orphans[o["ref"]] += 1
    # relations (deduped, order kept)
    rels, seen = [], set()
    for r in exp["relations"]:
        k = (r["src"], r["dst"], r["kind"])
        if k in seen:
            continue
        seen.add(k)
        rels.append(dict(r))
    for n in nodes.values():
        n["occurrences"].sort(key=lambda o: (DOCS.index(o["doc"]) if o["doc"] in DOCS else 99, o.get("page") or 0,
                                             o.get("bbox") or [], o.get("how", ""), o.get("label") or ""))
    out_nodes = sorted(nodes.values(), key=lambda n: n["id"])
    return {"schema": SCHEMA, "source": "truth",
            "meta": {"building": exp.get("building", {}).get("name"), "orphan_occurrence_refs": dict(sorted(orphans.items()))},
            "nodes": out_nodes, "relations": rels, "counts": counts(out_nodes, rels)}


def counts(nodes: list[dict], rels: list[dict]) -> dict:
    by_kind, by_type, occ = defaultdict(int), defaultdict(int), defaultdict(int)
    for n in nodes:
        by_kind[n["kind"]] += 1
        by_type[f"{n['kind']}:{n['type']}"] += 1
        for o in n["occurrences"]:
            occ[o["doc"]] += 1
    rk = defaultdict(int)
    for r in rels:
        rk[r["kind"]] += 1
    return {"nodes": len(nodes), "nodes_by_kind": dict(sorted(by_kind.items())),
            "nodes_by_type": dict(sorted(by_type.items())), "occurrences": sum(occ.values()),
            "occurrences_by_doc": dict(sorted(occ.items())), "relations": len(rels),
            "relations_by_kind": dict(sorted(rk.items()))}


def write(exp: dict, path: str) -> dict:
    # Standalone copy: no ETABS adapter here, so the truth carries no "etabs" occurrences (the
    # hackathon version added them from calcgraph.analysis.etabs). No "specs" occurrences either -
    # the spec book writer (specs_v2.py) is not part of this copy. Everything else is unchanged.
    reg = build(exp, [])
    with open(path, "w") as fh:
        json.dump(reg, fh, indent=1, sort_keys=True)
    return reg["counts"]
