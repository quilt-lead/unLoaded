"""Calc graph edges, element <-> calc links, findings and coverage for a drawing set.

Deterministic only. Every edge and link stores the rule that made it and evidence on
BOTH sides: {doc, page, rects (PDF points), text}.

Calc edges ("feeds"):
  label defined -> used      within one model output (B RISAFloor, C RISA-3D, D RISA
                             foundation, stair calcs): the page that DEFINES a label
                             (member / point / stack tables, label sketches) feeds every
                             page that uses it
  RISAFloor -> RISA-3D       RISA-3D names the RISAFloor floor-k labels F<k>_N# / F<k>_M#;
                             floor k -> level is fixed by matching point coordinates
                             (B Point Locations vs C Node Coordinates) - counts reported
  RISA-3D reaction -> footing  C node reaction pages for N# feed D pages using R3D_N#
  load area name             A load-area / wall-type names reappear in B / C (RISA area
                             load names, truncated "Exterior Balco..." prefix-matched)
  seismic weight             the seismic subtotal (psf) of an A page appears on a C seismic page
Element <-> calc links (score, rule):
  0.90 drawing ref + size    a calc page cites "<detail>/<sheet>" and prints the element's size
  0.75 footing schedule      scheduled pad L x W of the footing mark = a D "Footing Geometry
                             Results" row L x W
  0.62 size + type + level   size printed on a calc page of a compatible member type at the
                             element's level
  0.55 size + type           same, calc page names no level
  0.45 size only             the page's member type is unknown
  0.45 drawing ref only      calc cites the element's sheet, names the same role (jamb / header /
                             stud) but prints another size
Positional registration of plans against calc sketches is NOT used: the 2021 calc model
and the 2023 drawings use different grid systems (see findings).
"""
from __future__ import annotations

import re
from collections import defaultdict

from .drawing_ingest import GRID_LABEL

DEFINERS = {
    "M": re.compile(r"Member Labels|Beam Primary Data|Member Primary Data", re.I),
    "N": re.compile(r"Point Locations|Node Coordinates|NODE & BOUNDARY", re.I),
    "CS": re.compile(r"Column Stacks|Columns :", re.I),
    "STACK": re.compile(r"Columns :|Column Stacks", re.I),
    "FN": re.compile(r"Node Coordinates", re.I),
    "FM": re.compile(r"Member Primary Data|MEMBER LABELS", re.I),
    "R3D": re.compile(r"Ftn'?g|Footing", re.I),
    "FLR": re.compile(r"Ftn'?g|Footing", re.I),
    "SM": re.compile(r".", re.I),
}
SCOPES = {"B": ["M", "N", "CS", "STACK"], "C": ["FN", "FM", "N"], "D": ["R3D", "FLR"], "STAIR": ["SM"]}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def page_kind(p: dict) -> str:
    t = (p["title"] + " " + " ".join(x["title"] for x in p["tables"])).lower()
    if p["doc"] == "stair":
        return "Stair"
    if re.search(r"footing|ftn'?g|soil|sliding", t):
        return "Footing"
    if re.search(r"stud|jamb|header|opening|parapet|hdr|cfs", t):
        return "Stud"
    if re.search(r"column|stack", t):
        return "Column"
    if re.search(r"beam|girder|hot rolled|design results|bending|deflection|member|framing", t):
        return "Beam"
    return ""


def _ev(p: dict, rects, text: str, note: str = "") -> dict:
    return {"doc": p["doc"], "page": p["page"], "calc": p["id"], "rects": [r for r in rects if r][:4], "text": text,
            "note": note}


def _floor_levels(pages: list[dict]) -> tuple[dict, dict]:
    """F<k> (RISA-3D floor) -> RISAFloor level, by matching point coordinates."""
    bpts: dict[str, dict[str, tuple]] = defaultdict(dict)
    for p in pages:
        if p["doc"] == "calcs" and p["section"] == "B" and p["title"].startswith("Point Locations") and p["level"]:
            for r in p["rows"]:
                c = r["cells"]
                if len(c) >= 4 and re.fullmatch(r"N\d+", c[1]):
                    try:
                        bpts[p["level"]][c[1]] = (float(c[2]), float(c[3]))  # Z, X
                    except ValueError:
                        pass
    cpts: dict[str, dict[str, tuple]] = defaultdict(dict)
    for p in pages:
        if p["doc"] == "calcs" and p["section"] == "C":
            for r in p["rows"]:
                c = r["cells"]
                m = re.fullmatch(r"F(\d)_(N\d+)", c[1]) if len(c) >= 5 else None
                if m:
                    try:
                        cpts["F" + m.group(1)][m.group(2)] = (float(c[4]), float(c[2]))  # Z, X
                    except ValueError:
                        pass
    level_of, check = {}, {}
    for f, pts in cpts.items():
        best = None
        for lv, bp in bpts.items():
            shared = [n for n in pts if n in bp]
            agree = sum(1 for n in shared if abs(pts[n][0] - bp[n][0]) < 0.02 and abs(pts[n][1] - bp[n][1]) < 0.02)
            if shared and (best is None or agree > best[1]):
                best = (lv, agree, len(shared))
        if best and best[1]:
            level_of[f] = best[0]
            check[f] = {"level": best[0], "points_agree": best[1], "points_shared": best[2]}
    # the join is only trusted when it is one-to-one; otherwise the label numbers are not floor-specific
    if len(set(level_of.values())) != len(level_of):
        for f in check:
            check[f]["used"] = False
        check["verdict"] = "ambiguous - several RISA-3D floors match the same RISAFloor level; rule not applied"
        return {}, check
    check["verdict"] = "one-to-one - rule applied"
    return level_of, check


def calc_edges(pages: list[dict]) -> tuple[list[dict], dict]:
    by_id = {p["id"]: p for p in pages}
    edges: dict[tuple, dict] = {}
    stats: dict[str, int] = defaultdict(int)

    def add(src: dict, dst: dict, rule: str, ev_src: dict, ev_dst: dict, label: str = ""):
        if src["id"] == dst["id"]:
            return
        k = (src["id"], dst["id"], rule)
        e = edges.get(k)
        if e is None:
            e = edges[k] = {"src": src["id"], "dst": dst["id"], "rule": rule, "labels": [], "evidence": {"src": [], "dst": []}}
            stats[rule] += 1
        if label and len(e["labels"]) < 12 and label not in e["labels"]:
            e["labels"].append(label)
        if len(e["evidence"]["src"]) < 3:
            e["evidence"]["src"].append(ev_src)
            e["evidence"]["dst"].append(ev_dst)

    # stair calcs: member marks B1 / C1 drawn on the sketch pads and named in the designs
    for p in pages:
        if p["doc"] == "stair":
            sm = defaultdict(list)
            for l in p["lines"]:
                for m in re.finditer(r"\b([BC]\d)\b", l["text"]):
                    if len(sm[m.group(1)]) < 3:
                        sm[m.group(1)].append(l["rect"])
            p["labels"]["SM"] = dict(sm)

    # 1. label defined -> used, per model output
    for section, kinds in SCOPES.items():
        sec = [p for p in pages if p["section"] == section and not p["toc"]]
        for kind in kinds:
            rx = DEFINERS[kind]
            definer: dict[str, dict] = {}
            for p in sec:
                if not rx.search(p["title"] + " " + " ".join(t["title"] for t in p["tables"])):
                    continue
                for lab in p["labels"].get(kind, {}):
                    definer.setdefault(lab, p)
            for p in sec:
                for lab in p["labels"].get(kind, {}):
                    definer.setdefault(lab, p)  # fallback: first page that prints the label
            for p in sec:
                for lab, rects in p["labels"].get(kind, {}).items():
                    d = definer[lab]
                    if d["id"] != p["id"]:
                        add(d, p, "label defined -> used", _ev(d, d["labels"][kind][lab], lab, "defines"),
                            _ev(p, rects, lab, "uses"), lab)

    # 2. RISAFloor -> RISA-3D floor labels
    level_of, fcheck = _floor_levels(pages)
    bdef: dict[tuple, dict] = {}
    for p in pages:
        if p["section"] != "B" or not p["level"]:
            continue
        ttl = p["title"]
        for kind, rx in (("N", r"^Point Locations"), ("M", r"^Beam Primary Data")):
            if re.search(rx, ttl):
                for lab in p["labels"].get(kind, {}):
                    bdef.setdefault((kind, p["level"], lab), p)
    for p in pages:
        if p["section"] != "C":
            continue
        for kind, ck in (("N", "FN"), ("M", "FM")):
            for lab, rects in p["labels"].get(ck, {}).items():
                m = re.fullmatch(r"F(\d)_([MN]\d+)", lab)
                lv = level_of.get("F" + m.group(1)) if m else None
                d = bdef.get((kind, lv, m.group(2))) if lv else None
                if d:
                    add(d, p, "RISAFloor -> RISA-3D (floor label)", _ev(d, d["labels"][kind][m.group(2)], m.group(2),
                                                                        f"RISAFloor {lv}"),
                        _ev(p, rects, lab, f"RISA-3D floor F{m.group(1)} = {lv}"), lab)

    # 3. RISA-3D node reactions -> foundation joints R3D_N#
    react: dict[str, dict] = {}
    for p in pages:
        if p["section"] == "C" and "reaction" in p["title"].lower():
            for lab in p["labels"].get("N", {}):
                react.setdefault(lab, p)
    for p in pages:
        if p["section"] != "D":
            continue
        for lab, rects in p["labels"].get("R3D", {}).items():
            n = lab.replace("R3D_", "")
            d = react.get(n)
            if d:
                add(d, p, "RISA-3D reaction -> foundation joint", _ev(d, d["labels"]["N"][n], n, "base node reaction"),
                    _ev(p, rects, lab, "foundation joint named after the RISA-3D node"), lab)

    # 4. load-area / wall-type names from section A
    names = []
    for p in pages:
        if p["section"] != "A" or "_" in p["sheet_id"]:
            continue
        if p["title"] and p["title"] != "Wall Type Breakdown" and p["title_rect"]:
            names.append((p, p["title"], p["title_rect"]))
        for l in p["lines"]:
            if re.match(r"^(Exterior|Interior) Wall\b", l["text"]):
                names.append((p, l["text"], l["rect"]))
    for src, name, rect in names:
        nn = _norm(name)
        if len(nn) < 6:
            continue
        for p in pages:
            if p["section"] == "A" or p["toc"]:
                continue
            for l in p["lines"]:
                ln = _norm(l["text"])
                trunc = l["text"].rstrip().endswith("...")
                if (nn in ln) or (trunc and len(ln) >= 6 and nn.startswith(ln)) or \
                   (len(ln) >= 6 and re.sub(r"s$", "", nn).startswith(ln) and ln.startswith(nn[:8]) and len(ln) >= 0.7 * len(nn)):
                    add(src, p, "load area name", _ev(src, [rect], name, "load definition"),
                        _ev(p, [l["rect"]], l["text"], "same load area name"), name)
                    break

    # 5. seismic weight (psf) of an A page reused on a C seismic page
    for src in pages:
        sub = src.get("subtotal")
        if src["section"] != "A" or not sub:
            continue
        vals = re.findall(r"\d+\.\d", sub["text"])
        if not vals:
            continue
        v = vals[-1]
        for p in pages:
            alltext = " ".join(l["text"] for l in p["lines"]).lower()
            if p["section"] != "C" or "seismic" not in alltext or "psf" not in alltext:
                continue
            hit = next((l for l in p["lines"] if re.fullmatch(rf"{re.escape(v)}", l["text"].strip())), None)
            if hit:
                add(src, p, "seismic weight (psf)", _ev(src, [sub["rect"]], sub["text"], f"seismic subtotal {v} psf"),
                    _ev(p, [hit["rect"]], hit["text"], f"{v} psf used"), v)
    return list(edges.values()), {"by_rule": dict(stats), "floor_levels": fcheck}


def _footing_rows(p: dict) -> list[dict]:
    t = next((x for x in p["tables"] if x["title"].startswith("Footing Geometry")), None)
    if not t:
        return []
    out = []
    for r in p["rows"]:
        if r["rect"][1] <= t["rect"][3]:
            continue
        c = r["cells"]
        lab = next((x for x in c if re.match(r"^(R3D_N\d+|FLR_\d_N[\d_.]+)", x)), None)
        if not lab:
            continue
        nums = [x for x in c[c.index(lab) + 1:] if re.fullmatch(r"-?\d+(?:\.\d+)?", x)]
        if len(nums) >= 3:
            out.append({"label": lab, "L": float(nums[0]), "W": float(nums[1]), "T_in": float(nums[2]),
                        "rect": r["rect"], "text": " ".join(c)})
    return out


def _same_role(el_text: str, title: str) -> bool:
    """Both name the same member role (JAMB / HEADER / STUD): 'HSS6x6x1/4 EXT JAMB' vs 'HSS JAMB - 1/S4.0.1'."""
    roles = {"JAMB": r"\bJAMB", "HDR": r"\b(HDR|HEADER)", "STUD": r"\bSTUD"}
    return any(re.search(rx, el_text.upper()) and re.search(rx, title.upper()) for rx in roles.values())


def link(elements: list[dict], pages: list[dict]) -> tuple[list[dict], dict]:
    links: dict[tuple, dict] = {}
    stats: dict[str, int] = defaultdict(int)
    usable = [p for p in pages if not p["toc"]]

    def add(el, p, score, tier, rule, el_ev, c_ev):
        k = (el["id"], p["id"])
        if k in links and links[k]["score"] >= score:
            return
        if k not in links:
            stats[tier] += 1
        else:
            stats[links[k]["tier"]] -= 1
            stats[tier] += 1
        links[k] = {"el": el["id"], "calc": p["id"], "score": score, "tier": tier, "rule": rule,
                    "evidence": {"el": el_ev, "calc": c_ev}}

    def el_ev(el, note=""):
        return {"doc": el["doc"], "page": el["page"], "sheet": el["sheet"], "rects": el["rects"], "text": el["text"],
                "note": note}

    kinds = {p["id"]: page_kind(p) for p in usable}
    for el in elements:
        sn = el["size_norm"]
        # drawing reference + size
        for p in usable:
            for ref in p["drawing_refs"]:
                if ref["sheet"] != el["sheet"]:
                    continue
                if sn and sn in p["sizes"]:
                    add(el, p, 0.90, "drawing ref + size", f"calc cites {ref['text']} and prints {p['size_raw'][sn]}",
                        el_ev(el, f"tag on {el['sheet']}"),
                        _ev(p, [ref["rect"]] + p["sizes"][sn][:2], f"{ref['text']} / {p['size_raw'][sn]}",
                            "drawing reference and size"))
                elif el["family"] in ("HSS", "CFS") and _same_role(el["text"], p["title"]):
                    add(el, p, 0.45, "drawing ref only", f"calc cites {ref['text']} but prints a different size",
                        el_ev(el), _ev(p, [ref["rect"]], ref["text"], "drawing reference only"))
        if not sn:
            continue
        for p in usable:
            if sn not in p["sizes"]:
                continue
            kind = kinds[p["id"]]
            if el["sheet_kind"] == "stair" or p["doc"] == "stair":
                if not (el["sheet_kind"] == "stair" and p["doc"] == "stair"):
                    if kind == "Stair":
                        continue
            want = {"Beam": "Beam", "Column": "Column", "Wall": "Stud"}.get(el["cat"], "")
            if el["family"] == "HSS" and el["cat"] == "Beam":
                want = "Stud" if kind == "Stud" else "Beam"
            if el["family"] == "HSS" and el["cat"] == "Column" and kind == "Stud":
                want = "Stud"  # HSS jambs are designed with the wall openings (E)
            cev = _ev(p, p["sizes"][sn][:3], p["size_raw"][sn], f"size printed on {p['sheet_id']}")
            if kind == "Stair" and el["sheet_kind"] == "stair":
                add(el, p, 0.62, "size + type + level", "stair member size in the stair calcs", el_ev(el), cev)
                continue
            if kind and want and kind != want:
                continue
            lv_el, lv_p = el["level"], p["level"]
            if el["cat"] == "Column":
                lv_el = ""  # a column runs between levels: level not compared
            if lv_el and lv_p and not lv_el.startswith(lv_p) and lv_p not in lv_el:
                continue
            if kind and lv_el and lv_p:
                add(el, p, 0.62, "size + type + level", f"{sn} {el['cat'].lower()} at {lv_p}", el_ev(el), cev)
            elif kind:
                add(el, p, 0.55, "size + type", f"{sn} on a {kind.lower()} calc page", el_ev(el), cev)
            else:
                add(el, p, 0.45, "size only", f"{sn} printed on the page; member type not stated", el_ev(el), cev)
    # footing schedule vs RISA footing geometry
    rows = [(p, r) for p in usable if p["section"] == "D" for r in _footing_rows(p)]
    for el in elements:
        sch = el.get("schedule")
        if el["cat"] != "Footing" or not sch:
            continue
        for p, r in rows:
            if abs(r["L"] - sch["length_ft"]) < 0.01 and abs(r["W"] - sch["width_ft"]) < 0.01:
                th = sch["thick_ft"] * 12
                note = "thickness matches" if abs(th - r["T_in"]) < 0.5 else f"thickness differs: plan {th:.0f} in, calc {r['T_in']:.0f} in"
                add(el, p, 0.75, "footing schedule", f"{el['mark']} {sch['length_ft']:g}x{sch['width_ft']:g} ft = "
                    f"{r['label']} {r['L']:g}x{r['W']:g} ft ({note})",
                    {**el_ev(el), "extra": [{"doc": "plans", "page": sch["page"], "rects": sch["rects"], "text": sch["text"]}]},
                    _ev(p, [r["rect"]], r["text"], "footing geometry row"))
    return list(links.values()), dict(stats)


def findings(elements, pages, links, sheets) -> list[dict]:
    out = []
    by_el = defaultdict(list)
    for l in links:
        by_el[l["el"]].append(l)
    size_pages = defaultdict(list)
    for p in pages:
        for s in p["sizes"]:
            size_pages[s].append(p["sheet_id"])
    for el in elements:
        if by_el.get(el["id"]):
            continue
        if el["mark"] == "SMF":
            why = "moment frame marker (symbol, not a sized member) - frames are in section C, not linkable by text"
        elif el["mark"]:
            why = (f"foundation mark {el['mark']}: no calc prints the mark; "
                   + ("its scheduled size matches no RISA footing" if el.get("schedule") else "no schedule size to compare"))
        elif not size_pages.get(el["size_norm"]):
            why = f"size {el['size_norm']} is printed on no calc page"
        else:
            why = (f"size {el['size_norm']} appears only on calc pages of another member type or level: "
                   + ", ".join(sorted(set(size_pages[el['size_norm']]))[:8]))
        out.append({"kind": "no calc found", "severity": "high" if el["cat"] in ("Beam", "Column", "Footing") and not el["mark"] == "SMF" else "info",
                    "el": el["id"], "text": f"{el['text']} on {el['sheet']} ({el['grid'] or 'no grid'}): {why}",
                    "evidence": [{"doc": el["doc"], "page": el["page"], "rects": el["rects"], "text": el["text"]}]})
    linked_pages = {l["calc"] for l in links}
    for p in pages:
        if p["id"] not in linked_pages:
            out.append({"kind": "calc page linked to nothing", "severity": "info", "calc": p["id"],
                        "text": f"{p['sheet_id']} {p['title']} ({p['doc']} p{p['page']})",
                        "evidence": [{"doc": p["doc"], "page": p["page"], "rects": [p["title_rect"]] if p["title_rect"] else [],
                                      "text": p["title"]}]})
    # grid systems
    plan = next((s for s in sheets if s["kind"] == "framing" and s["grid"]["cols"]), None)
    sk = next((p for p in pages if p["section"] == "B" and "Member Labels" in p["title"]), None)
    if plan and sk:
        cl = sorted({l["text"] for l in sk["lines"] if GRID_LABEL.match(l["text"])})
        dl = sorted({g["label"] for g in plan["grid"]["cols"] + plan["grid"]["rows"]})
        if set(cl) != set(dl):
            out.append({"kind": "grid mismatch", "severity": "high",
                        "text": f"Calc model grids ({sk['sheet_id']}): {', '.join(cl)}. Drawing grids ({plan['sheet']}): "
                                f"{', '.join(dl)}. Grid labels cannot join drawings to calcs.",
                        "evidence": [{"doc": "plans", "page": plan["page"],
                                      "rects": [r for g in plan["grid"]["cols"][:3] + plan["grid"]["rows"][:3] for r in g["rects"][:1]],
                                      "text": f"{plan['sheet']} grid bubbles"},
                                     {"doc": sk["doc"], "page": sk["page"],
                                      "rects": [l["rect"] for l in sk["lines"] if GRID_LABEL.match(l["text"])][:8],
                                      "text": f"{sk['sheet_id']} grid bubbles"}]})
    # moment frame sizes drawn vs designed
    mf = [e for e in elements if e["sheet_kind"] == "smf"]
    csizes = sorted({s for p in pages if p["section"] == "C" for s in p["sizes"] if s.startswith("W")})
    missing = sorted({e["size_norm"] for e in mf if e["size_norm"] not in csizes})
    if missing:
        c9 = next((p for p in pages if p["section"] == "C" and p["sizes"]), None)
        out.append({"kind": "size mismatch", "severity": "high",
                    "text": f"Moment frame sizes drawn on S3.0.1 not found in the lateral calcs (C): {', '.join(missing)}. "
                            f"Sizes C prints: {', '.join(csizes) or 'none'}.",
                    "evidence": [{"doc": "plans", "page": mf[0]["page"], "rects": [e["bbox"] for e in mf if e["size_norm"] in missing][:6],
                                  "text": "S3.0.1 frame members"}] +
                                ([{"doc": c9["doc"], "page": c9["page"], "rects": [r for v in c9["sizes"].values() for r in v[:1]][:6],
                                   "text": f"{c9['sheet_id']} {c9['title']}"}] if c9 else [])})
    trunc = [(p, t) for p in pages for t in p["truncated"]]
    if trunc:
        out.append({"kind": "truncated sizes in calcs", "severity": "info",
                    "text": f"{len(trunc)} RISA shape names are cut off with '...' (e.g. {trunc[0][1]['text']}) and cannot be compared",
                    "evidence": [{"doc": p["doc"], "page": p["page"], "rects": [t["rect"]], "text": t["text"]} for p, t in trunc[:4]]})
    return out


def coverage(elements, element_edges, pages, cedges, links, lp_stats, ce_stats, link_stats, raw_counts) -> dict:
    by_el = defaultdict(int)
    for l in links:
        by_el[l["el"]] += 1
    tags = defaultdict(lambda: defaultdict(int))
    for e in elements:
        tags[e["sheet"]][e["type"]] += 1
    linked = sum(1 for e in elements if by_el[e["id"]])
    lp = sum(1 for p in pages if p["id"] in {l["calc"] for l in links})
    return {
        "elements": len(elements), "elements_linked": linked,
        "elements_linked_strong": sum(1 for e in elements if any(l["el"] == e["id"] and l["score"] >= 0.62 for l in links)),
        "tags_by_sheet_type": {k: dict(v) for k, v in tags.items()},
        "tags_by_type": dict(sorted(((t, sum(1 for e in elements if e["type"] == t)) for t in {e["type"] for e in elements}),
                                    key=lambda x: -x[1])),
        "raw_words_before_dedupe": raw_counts,
        "calc_pages": len(pages), "calc_pages_linked": lp, "calc_pages_unlinked": len(pages) - lp,
        "calc_edges": len(cedges), "calc_edges_by_rule": ce_stats["by_rule"], "floor_level_check": ce_stats["floor_levels"],
        "load_path_edges": len(element_edges), "load_path": lp_stats,
        "links": len(links), "links_by_tier": link_stats,
    }
