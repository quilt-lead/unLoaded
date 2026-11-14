"""Rebuild the ELEMENT REGISTRY from the documents alone: model (IFC), drawing set, spec book, calc package.

    build({"ifc": path, "drawings": path, "specs": path, "calcs": path}) -> registry (synth/v2/registry_truth.py schema)

Never reads a generator's ground truth. Every reader is a generic calc-graph reader (ifc_ingest +
loadpath, drawing_ingest, connections, spec_ingest, calcpkg_ingest + calc_rows); per-set
conventions come from the profile drawing_ingest / calcpkg_ingest resolve. This module only
RESOLVES what the readers saw to registry nodes, and every resolved occurrence / relation records
its rule and a confidence: exact (a printed identifier, a unique geometric match) or inferred (a
nearest-match, a vocabulary word).

Node identity
- element: the IFC product's Name (else Mark, else GlobalId); the model is the authority for what
  physically exists. Levels LEVEL:<L#|RF> from storey / sheet level names, grids GRID:<label>, frames
  FRAME:<initials of the system words>-<line> from frame elevation titles.
- type: TYPE:<normalised section> (sizes.norm) or TYPE:<type mark> ("Pier P-1"); typical detail
  DETAIL:<mark> from detail titles ("COLUMN BASE PLATE BP-1"); drawn detail DET:<n>/<sheet>.
- material: MAT:<canonical designation> from the standard designation the text cites (ASTM A992,
  F3125 Gr A325, f'c = 4,000 psi ...) - MATERIALS below.
- spec paragraph: SPEC:<section>/<article>.<paragraph>; calc record: REC:<calc sheet>#<n>.

Resolution rules (names used in the "rule" field)
- ifc: product -> node (exact); load path from loadpath.infer (its own rule); instance-of from the
  section / type mark parameter; member-of level (horizontal framing + slabs, by storey), grid
  (axis on a grid line within 0.3 m, columns at an intersection), frame (tagged in its elevation)
- drawings: grid registration per sheet (bubble positions -> model grid positions, which come from
  the columns' grid parameter); a plan tag resolves to the IFC member of the sheet's storey whose
  plan axis is nearest the tag and whose section matches (foundation marks: nearest footing /
  pier / grade beam); an elevation tag through the view's bubbles + level markers to a 3D point;
  a callout's leader end / a plan symbol to the nearest connection plate of the detail's type
  family; schedule rows keyed by grid ("1/A" columns) or by type mark (F5, P1, GB1, BP-1);
  note paragraphs through the vocabulary (governs)
- specs: paragraph -> specified-by for everything its text governs (governs)
- calcs: calc_rows records; the anchor -> designed-by, a mention designed by another record ->
  feeds (inferred); the record's box is an occurrence of the record and of its subject
"""
from __future__ import annotations

import math
import re
from collections import defaultdict

import numpy as np
import pymupdf

from . import calc_rows, calcpkg_ingest, connections, drawing_ingest, ifc_ingest, loadpath, profiles, sizes, spec_ingest

SCHEMA = "calcgraph.registry/1"

# canonical material designations: id -> (name, regex over upper-cased text). A material is cited by its
# standard designation; a few generic nouns are accepted as INFERRED when they are unambiguous in a
# structural set (reinforcing -> the rebar grade, headed studs -> the stud material).
MATERIALS = {
    "MAT:A992": ("ASTM A992 wide flange", r"\bA992\b", None),
    "MAT:A500C": ("ASTM A500 Gr C HSS", r"\bA500\b", None),
    "MAT:A36": ("ASTM A36 plate", r"\bA36\b", None),
    "MAT:F3125-A325": ("ASTM F3125 Gr A325 bolts", r"\bF3125\b|\bA325\b", r"\bHIGH-STRENGTH BOLT|\bBOLTING\b"),
    "MAT:F1554": ("ASTM F1554 anchor rods", r"\bF1554\b", r"\bANCHOR RODS?\b"),
    "MAT:REBAR-A615": ("ASTM A615 reinforcing", r"\bA615\b", r"\bREINFORCING\b|\bREBAR\b"),
    "MAT:STUD": ("Headed shear studs (ASTM A108)", r"\bA108\b", r"\bHEADED (?:SHEAR )?STUDS?\b"),
    "MAT:E70XX": ("E70XX weld metal", r"\bE70\w*", r"\bFILLER METAL\b|\bELECTRODES?\b|\bWELDERS?\b"),
    "MAT:CONC-4000": ("Concrete f'c 4,000 psi", r"F'?C\s*=\s*4,?000|4,000 PSI", None),
    "MAT:CONC-LW3000": ("Lightweight concrete f'c 3,000 psi", r"F'?C\s*=\s*3,?000|3,000 PSI|LIGHTWEIGHT (?:CONCRETE|AGGREGATE)", None),
    "MAT:DECK-3VLI20": ("20 ga steel deck", r"\b20 (?:GA|GAUGE)\b", r"\bCOMPOSITE (?:STEEL )?DECK\b|\bROOF DECK\b"),
    "MAT:SFRM": ("Sprayed fire-resistive material", r"\bSFRM\b|SPRAY(?:ED)?[- ]APPLIED FIRE|SPRAYED FIRE-RESIST", r"FIREPROOFING"),
}
_GENERIC_NOUNS = {"CONNECTION", "CONNECTIONS", "PLATE", "PLATES", "TAB", "DETAIL", "BEAM", "COLUMN", "BASE", "TYPICAL"}
_MARK = re.compile(r"\b([A-Z]{1,3})-(\d{1,2})\b")
_RANGE = re.compile(r"\b([A-Z]{1,3})-(\d{1,2})\s+(?:THROUGH|THRU|TO)\s+(?:\1-)?(\d{1,2})\b")
_SYS = {"SMF": "SPECIAL MOMENT FRAME", "SCBF": "SPECIAL CONCENTRICALLY BRACED FRAME", "OCBF": "ORDINARY CONCENTRICALLY BRACED FRAME",
        "IMF": "INTERMEDIATE MOMENT FRAME", "OMF": "ORDINARY MOMENT FRAME", "BRBF": "BUCKLING-RESTRAINED BRACED FRAME"}


def _r(b) -> list[float]:
    return [round(float(v), 2) for v in b]


def _union(rects) -> list[float]:
    return _r([min(r[0] for r in rects), min(r[1] for r in rects), max(r[2] for r in rects), max(r[3] for r in rects)])


def level_key(name: str) -> str | None:
    """'Level 2' / 'LEVEL 2' / 'L2' -> L2, 'Roof' -> RF, 'Level 1 / Foundation' -> L1, 'Foundation' -> None."""
    t = (name or "").upper()
    m = re.search(r"\bLEVEL\s*(\d+)\b|\bL(\d+)\b", t)
    if m:
        return f"L{m.group(1) or m.group(2)}"
    if "ROOF" in t:
        return "RF"
    return None


def _seg_dist(p, a, b) -> float:
    p, a, b = np.asarray(p, float), np.asarray(a, float), np.asarray(b, float)
    ab = b - a
    L2 = float(ab @ ab)
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, float((p - a) @ ab) / L2))
    return float(np.linalg.norm(p - (a + t * ab)))


class Registry:
    def __init__(self):
        self.nodes: dict[str, dict] = {}
        self.rels: dict[tuple, dict] = {}

    def node(self, nid, kind, typ, name="", attrs=None, gid=None):
        if nid not in self.nodes:
            self.nodes[nid] = {"id": nid, "kind": kind, "type": typ, "name": name, "attrs": attrs or {},
                               "global_id": gid, "occurrences": []}
        return self.nodes[nid]

    def occ(self, nid, occ):
        n = self.nodes.get(nid)
        if n is None:
            return
        k = (occ["doc"], occ.get("page"), tuple(occ.get("bbox") or ()), occ.get("global_id"), occ.get("how"))
        if all((o["doc"], o.get("page"), tuple(o.get("bbox") or ()), o.get("global_id"), o.get("how")) != k for o in n["occurrences"]):
            n["occurrences"].append(occ)

    def rel(self, src, dst, kind, rule, confidence="exact", **kw):
        if src == dst or src not in self.nodes or dst not in self.nodes:
            return
        k = (src, dst, kind)
        if k not in self.rels:
            self.rels[k] = {"src": src, "dst": dst, "kind": kind, "rule": rule, "confidence": confidence, **kw}


# =============================================================================== IFC

def _etype(e: dict, prof: str) -> str:
    t = e["ifc_type"]
    if t == "IfcPlate" or e["cat"] == "Connection":
        return "connection"
    if t == "IfcFooting":
        return "footing"
    if t in ("IfcSlab", "IfcRoof"):
        return "deck"
    if t == "IfcMember":
        return "brace"
    if t == "IfcColumn":
        return "column" if prof else "pier"
    if t == "IfcBeam":
        return "beam" if prof else "grade_beam"
    return t.replace("Ifc", "").lower()


def _type_mark(e: dict) -> str | None:
    flat = {k.split(".", 1)[1]: v for k, v in e["params"].items()}
    for k in ("Type", "Type Mark"):
        if flat.get(k) and _MARK.fullmatch(flat[k].strip()):
            return flat[k].strip()
    m = _MARK.search(e.get("type_name") or "")
    return m.group(0) if m else None


def _section(e: dict) -> str | None:
    flat = {k.split(".", 1)[1]: v for k, v in e["params"].items()}
    for v in [flat.get(k) for k in ifc_ingest.PROFILE_KEYS] + [e.get("type_name"), e.get("name")]:
        info = sizes.norm(v or "")
        if info and info["kind"] == "steel":
            return info["norm"]
    return None


def ingest_ifc(R: Registry, path: str) -> dict:
    els = ifc_ingest.read_ifc(path)["elements"]
    by_gid, info = {}, {}
    for e in els:
        nid = e["name"] or e["mark"] or e["global_id"]
        sec = _section(e)
        et = _etype(e, sec)
        g = e.get("geom") or {}
        R.node(nid, "element", et, nid, {"storey": e["storey"], "section": sec, "ifc_type": e["ifc_type"]}, e["global_id"])
        R.occ(nid, {"doc": "ifc", "how": "ifc_product", "global_id": e["global_id"], "ifc_type": e["ifc_type"],
                    "rule": "IFC product", "confidence": "exact"})
        by_gid[e["global_id"]] = nid
        info[nid] = {"e": e, "type": et, "section": sec, "mark": _type_mark(e), "storey": e["storey"],
                     "p1": g.get("p1"), "p2": g.get("p2"), "min": g.get("min"), "max": g.get("max")}
        if sec:
            R.node(f"TYPE:{sec}", "type", "section", sec)
            R.rel(nid, f"TYPE:{sec}", "instance-of", "IFC section parameter / type name")
        elif info[nid]["mark"]:
            mk = info[nid]["mark"]
            tid = f"DETAIL:{mk}" if et == "connection" else f"TYPE:{mk}"
            R.node(tid, "detail" if et == "connection" else "type", "detail" if et == "connection" else et, mk)
            R.rel(nid, tid, "instance-of", "IFC type parameter / type name mark")
    # load path
    for ed in loadpath.infer(els):
        s, d = by_gid.get(ed["src"]), by_gid.get(ed["dst"])
        if s and d:
            kw = {"via": by_gid.get(ed.get("via"))} if ed.get("via") else {}
            R.rel(s, d, ed["kind"], f"loadpath: {ed.get('rule', '')}", **kw)
    # girders: a beam that other beams frame into
    for (s, d, k) in list(R.rels):
        if k == "frames-into" and info.get(d, {}).get("type") == "beam" and info.get(s, {}).get("type") == "beam":
            info[d]["type"] = R.nodes[d]["type"] = "girder"
    # levels (storeys)
    for nid, x in info.items():
        lk = level_key(x["storey"])
        if lk:
            R.node(f"LEVEL:{lk}", "element", "level", x["storey"])
        if lk and x["type"] in ("beam", "girder", "deck"):
            R.rel(nid, f"LEVEL:{lk}", "member-of", "horizontal framing / slab belongs to its storey")
    grid = model_grid(info)
    for lab in grid:
        R.node(f"GRID:{lab}", "element", "grid", lab, {"axis": grid[lab]["axis"], "pos_m": round(grid[lab]["pos"], 3)})
    _grid_membership(R, info, grid)
    return {"info": info, "grid": grid, "elements": els}


def model_grid(info: dict) -> dict:
    """Grid label -> {axis: x|y, pos (m)} from the columns' grid-location parameter ("1/A", "A-1")."""
    pts = defaultdict(list)
    for nid, x in info.items():
        if x["type"] != "column" or not x["min"]:
            continue
        flat = {k.split(".", 1)[1]: v for k, v in x["e"]["params"].items()}
        g = next((flat[k] for k in ("Grid", "Column Location Mark", "Grid Location") if flat.get(k)), None)
        if not g:
            continue
        cx, cy = (x["min"][0] + x["max"][0]) / 2, (x["min"][1] + x["max"][1]) / 2
        for lab in re.split(r"[/-]", g.strip()):
            if lab:
                pts[lab.strip()].append((cx, cy))
    out = {}
    for lab, ps in pts.items():
        xs, ys = [p[0] for p in ps], [p[1] for p in ps]
        ax = "x" if np.std(xs) <= np.std(ys) else "y"
        out[lab] = {"axis": ax, "pos": float(np.median(xs if ax == "x" else ys))}
    return out


def _grid_membership(R: Registry, info: dict, grid: dict, tol: float = 0.3):
    for nid, x in info.items():
        if not x["p1"] or x["type"] not in ("beam", "girder", "grade_beam", "column"):
            continue
        if x["type"] == "column":
            cx, cy = (x["min"][0] + x["max"][0]) / 2, (x["min"][1] + x["max"][1]) / 2
            for lab, g in grid.items():
                if abs((cx if g["axis"] == "x" else cy) - g["pos"]) <= tol:
                    R.rel(nid, f"GRID:{lab}", "member-of", "column at a grid intersection (within 0.3 m)")
            continue
        p1, p2 = x["p1"], x["p2"]
        for lab, g in grid.items():
            i = 0 if g["axis"] == "x" else 1
            if abs(p1[i] - g["pos"]) <= tol and abs(p2[i] - g["pos"]) <= tol:
                R.rel(nid, f"GRID:{lab}", "member-of", "member axis on a grid line (within 0.3 m)")


# =============================================================================== drawings: registration

def _fit(pairs):
    """Least-squares v_model = a * v_pt + b from >= 2 (pt, m) pairs."""
    if len(pairs) < 2:
        return None
    A = np.array([[p, 1.0] for p, _ in pairs])
    y = np.array([m for _, m in pairs])
    a, b = np.linalg.lstsq(A, y, rcond=None)[0]
    return float(a), float(b)


def sheet_transform(sheet: dict, grid: dict):
    """(x_pt, y_pt) -> (x_m, y_m) for a plan sheet, from its grid bubbles matched to the model grid by label."""
    g = sheet.get("grid") or {}
    fx, fy = defaultdict(list), defaultdict(list)
    for c in g.get("cols", []):
        if c["label"] in grid:
            fx[grid[c["label"]]["axis"]].append((c["pos"], grid[c["label"]]["pos"]))
    for r in g.get("rows", []):
        if r["label"] in grid:
            fy[grid[r["label"]]["axis"]].append((r["pos"], grid[r["label"]]["pos"]))
    if len(fx) != 1 or len(fy) != 1:
        return None
    ax_x, ax_y = next(iter(fx)), next(iter(fy))
    if ax_x == ax_y:
        return None
    tx, ty = _fit(fx[ax_x]), _fit(fy[ax_y])
    if not tx or not ty:
        return None

    def f(x, y):
        u, v = tx[0] * x + tx[1], ty[0] * y + ty[1]
        return (u, v) if ax_x == "x" else (v, u)
    return f


def _storeys_for(level: str, info: dict) -> set[str]:
    lk = level_key(level)
    out = {x["storey"] for x in info.values() if level_key(x["storey"]) == lk} if lk else set()
    if "FOUNDATION" in (level or "").upper():
        out |= {x["storey"] for x in info.values() if not level_key(x["storey"]) or level_key(x["storey"]) == "L1"}
    return out


def _nearest(pt, cands, info, kind="axis"):
    best = []
    for nid in cands:
        x = info[nid]
        if not x["p1"]:
            continue
        if kind == "axis":
            d = _seg_dist(pt, x["p1"][:len(pt)], x["p2"][:len(pt)])
        else:
            c = [(x["min"][i] + x["max"][i]) / 2 for i in range(len(pt))]
            d = math.dist(pt, c)
        best.append((d, nid))
    best.sort()
    return best


def _conf(best, tol):
    if not best or best[0][0] > tol:
        return None, None
    conf = "exact" if len(best) == 1 or best[1][0] > 2 * best[0][0] + 0.15 else "inferred"
    return best[0][1], conf


# =============================================================================== drawings

def ingest_drawings(R: Registry, path: str, ifc: dict, pf) -> dict:
    info, grid = ifc["info"], ifc["grid"]
    plans = drawing_ingest.read_plans(path, pf)
    doc = pymupdf.open(path)
    stats = defaultdict(int)
    tag_of = {}          # drawing element id -> registry node
    marks = defaultdict(set)   # printed mark (F5, P1, GB1, BP-1) -> instance nodes
    for nid, x in info.items():
        if x["mark"]:
            marks[x["mark"]].add(nid)
            marks[x["mark"].replace("-", "")].add(nid)

    def docc(nid, sheet, bbox, how, text, rule, conf):
        R.occ(nid, {"doc": "drawings", "how": how, "sheet": sheet["sheet"], "page": sheet["page"], "bbox": _r(bbox),
                    "text": text, "rule": rule, "confidence": conf})

    sheets = {s["sheet"]: s for s in plans["sheets"]}
    _pw = {}

    _pl = {}

    def page_lines(pno):
        if pno not in _pl:
            _pl[pno] = _lines_of(doc[pno - 1])
        return _pl[pno]

    def page_words(pno):
        if pno not in _pw:
            _pw[pno] = doc[pno - 1].get_text("words")
        return _pw[pno]
    # ---- grid bubbles
    for s in plans["sheets"]:
        for ax in ("cols", "rows"):
            for g in (s.get("grid") or {}).get(ax, []):
                if f"GRID:{g['label']}" in R.nodes:
                    for rc in g["rects"]:
                        docc(f"GRID:{g['label']}", s, rc, "grid_bubble", g["label"], "grid bubble pair on the sheet", "exact")
                        stats["grid_bubbles"] += 1
    # ---- plan tags
    for el in plans["elements"]:
        s = sheets[el["sheet"]]
        if s["kind"] not in ("framing", "foundation"):
            continue
        T = sheet_transform(s, grid)
        if T is None:
            stats["tags: sheet not registered"] += 1
            continue
        cx, cy = (el["bbox"][0] + el["bbox"][2]) / 2, (el["bbox"][1] + el["bbox"][3]) / 2
        pt = T(cx, cy)
        storeys = _storeys_for(s["level"], info)
        bbox = _tag_box(page_words(s["page"]), el)
        if el["mark"]:
            want = {"F": ("footing", "centre"), "P": ("pier", "centre"), "G": ("grade_beam", "axis"), "T": ("grade_beam", "axis")}.get(el["mark"][0])
            if not want or el["mark"] == "SMF":
                continue
            cands = [n for n, x in info.items() if x["type"] == want[0]]
            nid, conf = _conf(_nearest(pt, cands, info, want[1]), 2.5)
            if nid:
                tag_of[el["id"]] = nid
                marks[el["mark"]].add(nid)
                docc(nid, s, bbox, "plan_tag", el["text"], f"plan mark -> nearest {want[0]} in plan (registered by grid)", conf)
                for (src, dst, k) in list(R.rels):
                    if src == nid and k == "instance-of" and R.nodes[dst]["kind"] == "type":
                        docc(dst, s, bbox, "plan_tag", el["text"], "plan mark of an instance of this type", conf)
                stats["plan tags resolved"] += 1
            else:
                stats["plan tags unresolved"] += 1
            continue
        if el["family"] != "W" and el["family"] != "HSS" and not el["size_norm"]:
            continue
        cands = [n for n, x in info.items() if x["storey"] in storeys and x["type"] in ("beam", "girder", "brace", "column")
                 and x["section"] == el["size_norm"]]
        nid, conf = _conf(_nearest(pt, cands, info), 1.2)
        tid = f"TYPE:{el['size_norm']}"
        if el["size_norm"]:
            R.node(tid, "type", "section", el["size_norm"])
            docc(tid, s, bbox, "plan_tag", el["text"], "size text on a plan", "exact")
        if nid:
            tag_of[el["id"]] = nid
            docc(nid, s, bbox, "plan_tag", el["text"], "plan size tag -> nearest IFC member of the sheet's storey with that section", conf)
            stats["plan tags resolved"] += 1
        else:
            stats["plan tags unresolved"] += 1
    # ---- frame markers on plans ("*SCBF", "SMF" along a grid line)
    sysrx = re.compile(r"^\*?(" + "|".join(_SYS) + r")$")
    for s in plans["sheets"]:
        if s["kind"] not in ("framing", "foundation"):
            continue
        g = s.get("grid") or {}
        for w in doc[s["page"] - 1].get_text("words"):
            m = sysrx.match(w[4])
            if not m or w[2] > s["cutoff"]:
                continue
            cx, cy = (w[0] + w[2]) / 2, (w[1] + w[3]) / 2
            lines = [(abs(c["pos"] - cx), c["label"]) for c in g.get("cols", [])] + [(abs(r["pos"] - cy), r["label"]) for r in g.get("rows", [])]
            if not lines:
                continue
            d, lab = min(lines)
            if d > 40:
                continue
            fid = f"FRAME:{m.group(1)}-{lab}"
            R.node(fid, "element", "frame", f"{_SYS[m.group(1)].title()} line {lab}")
            docc(fid, s, w[:4], "plan_tag", w[4], "frame system marker on a plan, nearest grid line", "inferred")
            stats["frame markers"] += 1
    # ---- elevations
    views = _elevations(R, doc, plans, info, grid, docc, stats, tag_of)
    # ---- details, callouts, plan symbols (connections reader)
    con = connections.build(path, plans["sheets"], plans["elements"], [], {}, profile=pf)
    det_type = {}
    for t in con["types"]:
        if not t["title"]:
            continue
        did = f"DET:{t['id']}"
        R.node(did, "drawn", "drawn_detail", t["title"], {"sheet": t["sheet"]})
        docc(did, sheets[t["sheet"]], t["bbox"], "detail", t["title"], t["rule"], "exact")
        m = _MARK.search(t["title"])
        if m:
            tid = f"DETAIL:{m.group(0)}"
            R.node(tid, "detail", "detail", t["title"])
            R.rel(tid, did, "detailed-by", "detail title names the typical detail mark")
            docc(tid, sheets[t["sheet"]], _union(t["title_rects"]), "detail", t["title"], "detail title", "exact")
            det_type[t["id"]] = tid
            pls = [l for l in page_lines(t["page"]) if t["bbox"][0] <= l["bbox"][0] and l["bbox"][2] <= t["bbox"][2]
                   and t["bbox"][1] <= l["bbox"][1] and l["bbox"][3] <= t["number_rect"][1] - 2 and l["dir"][0] > 0.99]
            for l in pls:
                g = governs(l["text"], R)
                for mid in g["materials"]:
                    docc(mid, sheets[t["sheet"]], l["bbox"], "detail", l["text"], f"material named inside a detail ({g['why'][mid]})",
                         "exact" if g["why"][mid] == "designation" else "inferred")
            # the detail's caption: the text line directly above its title bar (capacity / type summary)
            cap = [l for l in pls if 0 <= t["number_rect"][1] - l["bbox"][3] <= 50]
            if cap:
                l = max(cap, key=lambda l: l["bbox"][3])
                docc(tid, sheets[t["sheet"]], l["bbox"], "detail", l["text"], "caption line above the detail's title bar", "inferred")
    plates = [n for n, x in info.items() if x["type"] == "connection"]
    for ins in con["instances"]:
        s = sheets[ins["sheet"]]
        tid = det_type.get(ins.get("type_id") or "")
        sym = ins.get("symbol")
        if not tid and sym:
            leg = (con["legends"].get(ins["sheet"]) or {}).get(sym) or {}
            tid = det_type.get(leg.get("detail") or "")
        T = sheet_transform(s, grid) if s["kind"] in ("framing", "foundation") else None
        view = next((v for v in views if v["sheet"]["sheet"] == s["sheet"] and v["y0"] <= ins["point"][1] <= v["y1"]), None)
        if (T is None and view is None) or not tid:
            stats["connection instances not resolved (no plan / elevation registration or no type)"] += 1
            continue
        fam = tid.split(":")[1].split("-")[0]
        if T is not None:
            pt = T(*ins["point"])
            storeys = _storeys_for(s["level"], info)
            cands = [n for n in plates if info[n]["storey"] in storeys and (info[n]["mark"] or "").split("-")[0] == fam]
        else:      # an elevation: the leader end is a 3D point through the view's registration
            pt = view["to3d"](*ins["point"])
            cands = [n for n in plates if (info[n]["mark"] or "").split("-")[0] == fam]
        nid, conf = _conf(_nearest(pt, cands, info, "centre"), 1.0)
        if not nid:
            stats["connection instances unresolved"] += 1
            continue
        how = "plan_tag" if sym else "detail_callout"
        docc(nid, s, ins["bbox"], how, ins.get("ref") or "", ("plan symbol (legend) -> nearest plate of that detail family"
                                                                 if sym else "callout leader end -> nearest plate of that detail family"), conf)
        if not sym and ins.get("type_id"):
            R.rel(nid, f"DET:{ins['type_id']}", "detailed-by", "callout bubble points at the drawn detail", conf)
        stats[f"connection instances resolved ({how})"] += 1
    # ---- connection symbols on elevations: the set's plan legend exemplars, found in each registered view
    lg_sheet = next((sh for sh, lg in con["legends"].items() if lg), None)
    if lg_sheet and views:
        s0 = sheets[lg_sheet]
        pg = doc[s0["page"] - 1]
        legend = con["legends"][lg_sheet]
        tpl = connections.legend_templates(pg.get_drawings(), legend, min(v["rect"][0] for v in legend.values()))
        for v in views:
            s = v["sheet"]
            drw = doc[s["page"] - 1].get_drawings()
            for sym in connections.find_by_template(drw, tpl, (40, v["y0"], s["cutoff"], v["y1"])):
                r = sym["rect"]
                tid = det_type.get((legend.get(sym["kind"]) or {}).get("detail") or "")
                if not tid:
                    continue
                fam = tid.split(":")[1].split("-")[0]
                pt = v["to3d"]((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2)
                cands = [n for n in plates if (info[n]["mark"] or "").split("-")[0] == fam]
                nid, conf = _conf(_nearest(pt, cands, info, "centre"), 1.0)
                if nid:
                    docc(nid, s, [r.x0, r.y0, r.x1, r.y1], "elevation_tag", "", "elevation symbol (plan legend exemplar) -> nearest plate of that detail family", conf)
                    stats["elevation symbols resolved"] += 1
                else:
                    stats["elevation symbols unresolved"] += 1
    # ---- section cuts (a pair of bubbles with the same ref on a plan) and the labels in the cut view
    _sections(R, doc, con, sheets, info, grid, marks, docc, stats, page_lines)
    # ---- schedules
    _schedules(R, doc, plans, info, grid, marks, docc, stats, pf)
    # ---- notes
    _notes(R, doc, plans, info, docc, stats, pf)
    return {"sheets": plans["sheets"], "stats": dict(stats), "legend_check": con["legend_check"]}


def _tag_box(words: list, el: dict, gap: float = 8.0) -> list[float]:
    """The printed tag: the size / mark word plus the words that continue it on its baseline
    ("W18X40 (30) c=3/4\"") - reading direction followed for rotated tags, stopping at a gap."""
    b = el["bbox"]
    box = list(b)
    vert = el.get("vertical_text")
    for _ in range(6):
        nxt = None
        for w in words:
            if vert:   # rotated 90 deg, read bottom-up: the next word sits above
                if abs((w[0] + w[2]) / 2 - (box[0] + box[2]) / 2) < 2 and 0 <= box[1] - w[3] <= gap and (w[3] - w[1]) > (w[2] - w[0]):
                    nxt = w
            elif abs((w[1] + w[3]) / 2 - (box[1] + box[3]) / 2) < 2 and 0 <= w[0] - box[2] <= gap:
                nxt = w
            if nxt:
                break
        if not nxt:
            break
        box = [min(box[0], nxt[0]), min(box[1], nxt[1]), max(box[2], nxt[2]), max(box[3], nxt[3])]
    return _r(box)


def _seg_seg(a, b, c, d) -> float:
    """Plan distance between segments ab and cd (0 when they cross)."""
    def ccw(p, q, r):
        return (r[1] - p[1]) * (q[0] - p[0]) - (q[1] - p[1]) * (r[0] - p[0])
    if (ccw(a, c, d) > 0) != (ccw(b, c, d) > 0) and (ccw(a, b, c) > 0) != (ccw(a, b, d) > 0):
        return 0.0
    return min(_seg_dist(a, c, d), _seg_dist(b, c, d), _seg_dist(c, a, b), _seg_dist(d, a, b))


def _sections(R, doc, con, sheets, info, grid, marks, docc, stats, page_lines):
    """Section cuts: on a registered plan, two bubbles with the same ref ("1/S-601") are the ends of one cut
    line; the cut shows what the line passes through or right beside on that plan's storey(s) (within 1.0 m
    of the element's plan footprint: a cut is drawn just off the column it looks at). In the cut's
    view on the target sheet (the view whose numbered title is the nearest one below a label), each label
    resolves among those elements by the section, mark or noun it prints."""
    by = defaultdict(list)
    for o in con["other_callouts"]:
        by[(o["sheet"], o["ref"])].append(o)
    cut_els = defaultdict(set)          # ref -> elements it cuts
    for (sh, ref), bs in by.items():
        if len(bs) != 2 or sh not in sheets:
            continue
        s = sheets[sh]
        T = sheet_transform(s, grid) if s["kind"] in ("framing", "foundation") else None
        if T is None:
            continue
        ca = [((b["bbox"][0] + b["bbox"][2]) / 2, (b["bbox"][1] + b["bbox"][3]) / 2) for b in bs]
        A, B = T(*ca[0]), T(*ca[1])
        box = _union([b["bbox"] for b in bs])
        storeys = _storeys_for(s["level"], info)
        hit = []
        for nid, x in info.items():
            if x["storey"] not in storeys or not x["min"]:
                continue
            if x["type"] == "deck":
                inside = all(x["min"][0] - 0.01 <= p[0] <= x["max"][0] + 0.01 and x["min"][1] - 0.01 <= p[1] <= x["max"][1] + 0.01 for p in (A, B))
                if inside:
                    hit.append(nid)
                continue
            if x["type"] in ("beam", "girder", "grade_beam", "brace"):
                d = _seg_seg(A, B, x["p1"][:2], x["p2"][:2])
            else:      # distance from the cut line to the element's plan footprint
                corners = [(x["min"][0], x["min"][1]), (x["max"][0], x["min"][1]), (x["max"][0], x["max"][1]), (x["min"][0], x["max"][1])]
                d = min(_seg_seg(A, B, corners[i], corners[(i + 1) % 4]) for i in range(4))
                if x["min"][0] <= A[0] <= x["max"][0] and x["min"][1] <= A[1] <= x["max"][1]:
                    d = 0.0
            if d <= 1.0:
                hit.append(nid)
        for nid in hit:
            cut_els[ref].add(nid)
            docc(nid, s, box, "section_cut", ref, "section cut line passes through / beside it in plan (within 1.0 m of its footprint)", "inferred")
            for (src, dst, k) in [k for k in R.rels if k[0] == nid and k[2] == "instance-of"]:
                if R.nodes[dst]["kind"] == "type":
                    docc(dst, s, box, "section_cut", ref, "section cut crosses an instance of this type", "inferred")
            stats["section cut occurrences (plan)"] += 1
    # the views on the target sheets
    targets = defaultdict(list)
    for ref in cut_els:
        n, sh = ref.split("/", 1)
        targets[sh].append(n)
    for sh, nums in targets.items():
        if sh not in sheets:
            continue
        s = sheets[sh]
        lines = [l for l in page_lines(s["page"]) if l["dir"][0] > 0.99]
        titles = []
        for l in lines:
            if re.fullmatch(r"\d{1,2}", l["text"]):
                t = [m for m in lines if m is not l and 0 < m["bbox"][0] - l["bbox"][2] < 40 and abs((m["bbox"][1] + m["bbox"][3]) / 2 - (l["bbox"][1] + l["bbox"][3]) / 2) < 8
                     and re.search(r"[A-Z]{4}", m["text"])]
                if t:
                    titles.append((l["text"], l, t[0]))
        for l in lines:
            if any(l is t[1] or l is t[2] for t in titles) or l["text"].startswith("SCALE"):
                continue
            below = [t for t in titles if t[1]["bbox"][1] > l["bbox"][3] and -300 < l["bbox"][0] - t[1]["bbox"][0] < 900]
            if not below:
                continue
            num = min(below, key=lambda t: t[1]["bbox"][1] - l["bbox"][3])[0]
            ref = f"{num}/{sh}"
            if ref not in cut_els:
                continue
            els, T_ = cut_els[ref], l["text"].upper()
            hits = []
            sz = next((sizes.norm(w) for w in re.findall(r"\*?(?:W|HSS)\d[\dX/.]*", T_) if sizes.norm(w)), None)
            if sz:
                hits += [n for n in els if info[n]["section"] == sz["norm"]]
                if f"TYPE:{sz['norm']}" in R.nodes:
                    hits.append(f"TYPE:{sz['norm']}")
            m0 = re.match(r"^\*?([A-Z]{1,3}-?\d+(?:\.\d)?)\b", T_) or re.search(r"\b([A-Z]{2}-\d+)\b", T_)
            if m0:
                mk = m0.group(1)
                hits += [n for n in els if n in marks.get(mk, ()) or n in marks.get(mk.replace("-", ""), ())]
                for tid in (f"TYPE:{mk}", f"TYPE:{mk[0]}-{mk[1:]}"):
                    if tid in R.nodes and any(k[0] in els and k[1] == tid for k in R.rels):
                        hits.append(tid)
            if "DECK" in T_:
                hits += [n for n in els if info[n]["type"] == "deck"]
            lk = level_key(T_) if re.search(r"\bLEVEL\s*\d|\bROOF\b", T_) else None
            if lk and f"LEVEL:{lk}" in R.nodes:
                hits.append(f"LEVEL:{lk}")
            hits += [m for m in governs(T_, R)["materials"] if governs(T_, R)["why"][m] == "designation" or "STUD" in T_]
            for nid in dict.fromkeys(hits):
                docc(nid, s, l["bbox"], "section_cut", l["text"], f"label in section view {ref} names it (among what the cut crosses)", "inferred")
                stats["section view labels resolved"] += 1


def _lines_of(page) -> list[dict]:
    out = []
    for b in page.get_text("dict")["blocks"]:
        for ln in b.get("lines", []):
            t = " ".join(s["text"] for s in ln["spans"]).strip()
            if t:
                out.append({"text": re.sub(r"\s+", " ", t), "bbox": list(ln["bbox"]), "dir": ln["dir"], "block": b["number"]})
    return out


def _elevations(R, doc, plans, info, grid, docc, stats, tag_of) -> list[dict]:
    """Frame elevations: each view (title "... FRAME - LINE A") is registered to the model by its grid
    bubbles (along the line) and level markers (height); returns the views with their transforms."""
    views = []
    title_rx = re.compile(r"^((?:[A-Z-]+ ){0,3}[A-Z-]*FRAME)\s*-\s*LINE\s+([A-Z0-9.]+)$")
    lvl_rx = re.compile(r"^(LEVEL\s*\d+|ROOF)\s+EL\.\s*(-?\d+)'\s*-\s*(\d+)\"")
    for s in plans["sheets"]:
        page = doc[s["page"] - 1]
        lines = _lines_of(page)
        titles = []
        for ln in lines:
            m = title_rx.match(ln["text"])
            if m and ln["bbox"][0] < s["cutoff"]:
                titles.append((ln, m.group(1), m.group(2)))
        if not titles:
            continue
        titles.sort(key=lambda t: t[0]["bbox"][1])
        words = page.get_text("words")
        top = 40.0
        for ln, sysname, line in titles:
            y0, y1 = top, ln["bbox"][1]
            top = ln["bbox"][3] + 4
            abbr = "".join(w[0] for w in re.split(r"[\s-]+", sysname) if w)
            fid = f"FRAME:{abbr}-{line}"
            R.node(fid, "element", "frame", sysname.title() + f" line {line}")
            docc(fid, s, ln["bbox"], "elevation_tag", ln["text"], "frame elevation title", "exact")
            if line not in grid:
                continue
            perp_axis = grid[line]["axis"]          # the line's own axis position is fixed
            along_axis = "y" if perp_axis == "x" else "x"
            # bubbles: grid labels of the other family inside the view
            g = profiles_grid_label(words, y0, y1, s["cutoff"])
            pairs = [((b[0] + b[2]) / 2, grid[b[4]]["pos"]) for b in g if b[4] in grid and grid[b[4]]["axis"] == along_axis]
            for b in g:
                if f"GRID:{b[4]}" in R.nodes:
                    docc(f"GRID:{b[4]}", s, b[:4], "grid_bubble", b[4], "grid bubble in a frame elevation", "exact")
            lv = []
            for l2 in lines:
                if not (y0 <= l2["bbox"][1] <= y1):
                    continue
                # a level marker: "LEVEL 2 EL. 14'-0\"" on one line, or the name over the elevation (two lines)
                below = [l3 for l3 in lines if abs(l3["bbox"][0] - l2["bbox"][0]) < 6 and 0 < l3["bbox"][1] - l2["bbox"][3] < 20]
                for txt, box in [(l2["text"], l2["bbox"])] + [(l2["text"] + " " + l3["text"], _union([l2["bbox"], l3["bbox"]])) for l3 in below]:
                    m = lvl_rx.match(txt)
                    if not m:
                        continue
                    ft = int(m.group(2)) + (int(m.group(3)) / 12) * (1 if int(m.group(2)) >= 0 else -1)
                    lv.append(((box[1] + box[3]) / 2, ft * 0.3048, m.group(1)))
                    lk = level_key(m.group(1))
                    if lk:
                        R.level_elev = getattr(R, "level_elev", {}) | {lk: ft}
                    if lk and f"LEVEL:{lk}" in R.nodes:
                        docc(f"LEVEL:{lk}", s, box, "elevation_tag", txt, "level marker in an elevation", "exact")
                    break
            ta, tz = _fit(pairs), _fit([(y, z) for y, z, _ in lv])
            if not ta or not tz:
                continue

            def to3d(x, y, ta=ta, tz=tz, line=line, perp_axis=perp_axis):
                a, z = ta[0] * x + ta[1], tz[0] * y + tz[1]
                return (grid[line]["pos"], a, z) if perp_axis == "x" else (a, grid[line]["pos"], z)
            views.append({"sheet": s, "y0": y0, "y1": y1, "to3d": to3d, "frame": fid})
            for el in plans["elements"]:
                if el["sheet"] != s["sheet"] or el["mark"] or not el["size_norm"]:
                    continue
                cx, cy = (el["bbox"][0] + el["bbox"][2]) / 2, (el["bbox"][1] + el["bbox"][3]) / 2
                if not (y0 <= cy <= y1):
                    continue
                pt = to3d(cx, cy)
                cands = [n for n, x in info.items() if x["section"] == el["size_norm"] and x["type"] in ("beam", "girder", "column", "brace")]
                best = _nearest(pt, cands, info)
                nid, conf = _conf(best, 1.5)
                bbox = _tag_box(words, el)
                tid = f"TYPE:{el['size_norm']}"
                R.node(tid, "type", "section", el["size_norm"])
                docc(tid, s, bbox, "elevation_tag", el["text"], "size text on an elevation", "exact")
                if nid:
                    tag_of[el["id"]] = nid
                    docc(nid, s, bbox, "elevation_tag", el["text"], "elevation tag -> 3D point (view bubbles + level markers) -> nearest member with that section", conf)
                    R.rel(nid, fid, "member-of", "member tagged in the frame's elevation", "inferred")
                    stats["elevation tags resolved"] += 1
                else:
                    stats["elevation tags unresolved"] += 1
    return views


def profiles_grid_label(words, y0, y1, cutoff):
    """Grid bubble labels (16-26 pt tall, grid-label text) inside a view band."""
    rx = re.compile(r"^(\d{1,2}(?:\.\d)?|[A-H](?:\.\d)?)$")
    return [w for w in words if rx.match(w[4]) and y0 <= w[1] <= y1 and w[2] < cutoff and 15 <= w[3] - w[1] <= 26]


def _rows_of(words, tol=3.0):
    ws = sorted(words, key=lambda w: (w[1] + w[3]) / 2)
    rows, cur, cy = [], [], None
    for w in ws:
        c = (w[1] + w[3]) / 2
        if cur and abs(c - cy) > tol:
            rows.append(sorted(cur, key=lambda w: w[0]))
            cur = []
        if not cur:
            cy = c
        cur.append(w)
    if cur:
        rows.append(sorted(cur, key=lambda w: w[0]))
    return rows


def _schedules(R, doc, plans, info, grid, marks, docc, stats, pf):
    gl = re.compile(r"^(\d{1,2})/([A-Z])$|^([A-Z])-?(\d{1,2})$")
    for s in plans["sheets"]:
        if s["kind"] in ("details", "notes"):
            continue
        page = doc[s["page"] - 1]
        words = [w for w in page.get_text("words") if w[2] < (s["cutoff"] if s["kind"] in ("framing",)
                                                              else pf.drawings.title_block.x_min.at(page.rect.width))]
        rows = _rows_of(words)
        # (a) grid-keyed schedule: a header row of >= 4 grid intersection labels; each text line below sits in
        #     the column whose header it is centred under, down to the table's end (a 60 pt gap)
        lines = [l for l in _lines_of(page) if l["dir"][0] > 0.99]
        for row in rows:
            heads = [w for w in row if gl.match(w[4]) and all(x in grid for x in gl.match(w[4]).groups() if x)]
            if len(heads) < 4:
                continue
            hy = max(h[3] for h in heads)
            x_lo, x_hi = min(h[0] for h in heads) - 40, max(h[2] for h in heads) + 40
            body = sorted((l for l in lines if l["bbox"][1] > hy and x_lo <= l["bbox"][0] <= x_hi), key=lambda l: l["bbox"][1])
            last_y = hy
            for l in body:
                if l["bbox"][1] - last_y > 60:
                    break
                last_y = max(last_y, l["bbox"][3])
                lc = (l["bbox"][0] + l["bbox"][2]) / 2
                col = min(heads, key=lambda h: abs((h[0] + h[2]) / 2 - lc))
                if abs((col[0] + col[2]) / 2 - lc) > 30:
                    continue
                m = gl.match(col[4])
                ga, gb = (m.group(1), m.group(2)) if m.group(1) else (m.group(4), m.group(3))
                if ga not in grid or gb not in grid:
                    continue
                gx = grid[ga]["pos"] if grid[ga]["axis"] == "x" else grid[gb]["pos"]
                gy = grid[gb]["pos"] if grid[gb]["axis"] == "y" else grid[ga]["pos"]
                t = l["text"].strip()
                for fm in re.finditer(r"\b(" + "|".join(_SYS) + r")\s+([A-Z0-9]{1,2})\b", t):
                    fid = f"FRAME:{fm.group(1)}-{fm.group(2)}"
                    if fid in R.nodes:
                        docc(fid, s, l["bbox"], "schedule_row", t, f"system cell under {col[4]} names the frame", "exact")
                info_sz = sizes.norm(t)
                if info_sz and info_sz["kind"] == "steel":
                    want = ("column",)
                    tid = f"TYPE:{info_sz['norm']}"
                    R.node(tid, "type", "section", info_sz["norm"])
                    docc(tid, s, l["bbox"], "schedule_row", t, "size in a grid-keyed schedule", "exact")
                elif _MARK.fullmatch(t) or re.fullmatch(r"[A-Z]{1,2}\d+(?:\.\d)?", t):
                    want = {"F": ("footing",), "P": ("pier",), "B": ("connection",)}.get(t[0], ())
                else:
                    continue
                cands = [n for n, x in info.items() if x["type"] in want and x["min"]]
                best = sorted((math.hypot((info[n]["min"][0] + info[n]["max"][0]) / 2 - gx, (info[n]["min"][1] + info[n]["max"][1]) / 2 - gy), n)
                              for n in cands)
                if best and best[0][0] <= 0.6:
                    docc(best[0][1], s, l["bbox"], "schedule_row", t, f"grid-keyed schedule cell under {col[4]} -> element at that intersection", "exact")
                    stats["schedule cells resolved"] += 1
        # (b) type-mark schedule rows: a row segment (words split at 60 pt gaps) led by a printed mark that has
        #     instances; kept only where >= 2 such segments line up (a table), so a lone label is not a schedule
        cand = []
        for row in rows:
            segs, cur = [], [row[0]]
            for w in row[1:]:
                if w[0] - cur[-1][2] > 60:
                    segs.append(cur)
                    cur = [w]
                else:
                    cur.append(w)
            segs.append(cur)
            for seg in segs:
                key = seg[0][4]
                gm = gl.match(key)
                is_grid = bool(gm) and all(x in grid for x in gm.groups() if x)   # "1/A" / "A-1" of THIS grid
                if len(seg) < 3 or is_grid or (key not in marks and f"DETAIL:{key}" not in R.nodes):
                    continue
                cand.append(seg)
        for seg in cand:
            if not any(o is not seg and abs(o[0][0] - seg[0][0]) <= 3 and 0 < abs(o[0][1] - seg[0][1]) <= 40 for o in cand):
                continue
            key = seg[0][4]
            bbox, text = _union([w[:4] for w in seg]), " ".join(w[4] for w in seg)
            for nid in sorted(marks.get(key, ())):
                docc(nid, s, bbox, "schedule_row", text, "type-mark schedule row -> every instance with that mark", "exact")
                stats["schedule rows -> instances"] += 1
            for tid in (f"DETAIL:{key}", f"TYPE:{key[0]}-{key[1:]}" if re.fullmatch(r"[A-Z]\d+", key) else None):
                if tid and tid in R.nodes:
                    docc(tid, s, bbox, "schedule_row", text, "type-mark schedule row", "exact")


def _paragraphs(lines: list[dict]) -> list[list[dict]]:
    """Note paragraphs: lines of one text block, split where a numbered / lettered note starts or the
    vertical gap opens past a third of a line height (table rows, separate notes)."""
    out = []
    for lns in _by_block(lines).values():
        lns.sort(key=lambda l: (l["bbox"][1], l["bbox"][0]))
        cur = []
        for l in lns:
            if cur:
                h = cur[-1]["bbox"][3] - cur[-1]["bbox"][1]
                if re.match(r"^(\d{1,2}|[A-Z])\.\s", l["text"]) or l["bbox"][1] - cur[-1]["bbox"][3] > max(3.0, h / 3):
                    out.append(cur)
                    cur = []
            cur.append(l)
        if cur:
            out.append(cur)
    return out


def _by_block(lines):
    d = defaultdict(list)
    for l in lines:
        d[l["block"]].append(l)
    return d


def _notes(R, doc, plans, info, docc, stats, pf):
    el_rx = re.compile(r"\bEL\.?\s*(-?\d+)'\s*-\s*(\d+)\"")
    for s in plans["sheets"]:
        if s["kind"] == "details":
            continue
        page = doc[s["page"] - 1]
        tb = pf.drawings.title_block.x_min.at(page.rect.width)
        nx = pf.drawings.notes_column.x_min.at(page.rect.width)
        lines = [ln for ln in _lines_of(page) if ln["dir"][0] > 0.99 and ln["bbox"][2] <= tb
                 and (s["kind"] == "notes" or ln["bbox"][0] >= min(nx, s["cutoff"]))]
        for lns in _paragraphs(lines):
            text = " ".join(l["text"] for l in lns)
            if len(text) < 12:
                continue
            g = governs(text, R)
            hits = g["materials"] + g["details"] + g["frames"] + g["decks"]
            for m in el_rx.finditer(text.upper()):     # an elevation that is a level's elevation names the level
                ft = int(m.group(1)) + int(m.group(2)) / 12 * (1 if int(m.group(1)) >= 0 else -1)
                for lk, z in getattr(R, "level_elev", {}).items():
                    if abs(z - ft) < 0.01 and f"LEVEL:{lk}" not in hits:
                        hits.append(f"LEVEL:{lk}")
                        g["why"][f"LEVEL:{lk}"] = "designation: level elevation"
            if not hits:
                continue
            bbox = _union([l["bbox"] for l in lns])
            for nid in hits:
                docc(nid, s, bbox, "note", text[:200], "note text names it (vocabulary: " + g["why"].get(nid, "") + ")",
                     "exact" if g["why"].get(nid, "").startswith(("designation", "detail mark", "frame id")) else "inferred")
                stats["note occurrences"] += 1


# =============================================================================== vocabulary

def governs(text: str, R: Registry) -> dict:
    """What a paragraph of text names: materials (by designation), section types, detail types (marks,
    ranges, title nouns), frames (system phrase + lines), decks, pier types. Returns ids that exist."""
    T = " " + re.sub(r"\s+", " ", text.upper()) + " "
    why: dict[str, str] = {}
    mats = []
    for mid, (_, rx, generic) in MATERIALS.items():
        if re.search(rx, T):
            mats.append(mid)
            why[mid] = "designation"
        elif generic and re.search(generic, T) and mid in R.nodes:
            mats.append(mid)
            why[mid] = "material noun"
    types = []
    for tok in re.findall(r"\b(?:W|HSS)\d[\dX/.]*", T):
        info = sizes.norm(tok.rstrip(".,"))
        if info and f"TYPE:{info['norm']}" in R.nodes:
            types.append(f"TYPE:{info['norm']}")
            why[types[-1]] = "size"
    dets = set()
    for m in _RANGE.finditer(T):
        for n in range(int(m.group(2)), int(m.group(3)) + 1):
            dets.add(f"DETAIL:{m.group(1)}-{n}")
    for m in _MARK.finditer(T):
        dets.add(f"DETAIL:{m.group(0)}")
    dets = {d for d in dets if d in R.nodes}
    for d in dets:
        why[d] = "detail mark"
    # detail families by the noun phrase of their titles ("COLUMN BASE PLATE BP-1" -> BASE PLATE)
    for nid, n in R.nodes.items():
        if n["kind"] != "detail" or nid in dets:
            continue
        mk = nid.split(":")[1]
        title = (n["name"] or "").upper()
        if mk not in title:
            continue
        words = [w for w in re.sub(r"\(.*?\)", "", title.split(mk)[0]).split() if w.isalpha()]
        fam = mk.split("-")[0]
        if any(d.split(":")[1].split("-")[0] == fam for d in dets if d in why and why[d] == "detail mark"):
            continue      # the text names a specific member of this family ("BP-3"): no family-wide reading
        aliases = re.findall(r"\(([A-Z]{2,6})\)", title.split(mk, 1)[1] if mk in title else "")
        keys = ([" ".join(words[-2:])] if len(words) >= 2 else []) + \
               ([words[-1]] if words and words[-1] not in _GENERIC_NOUNS else []) + aliases
        for phrase in keys:
            if re.search(r"\b" + re.escape(phrase) + r"S?\b", T):
                dets.add(nid)
                why[nid] = f"detail title noun '{phrase}'"
                break
    frames = []
    ids = {nid for nid, n in R.nodes.items() if n["type"] == "frame" and re.search(r"\b" + re.escape(nid.split(":")[1]) + r"\b", T)}
    for nid in sorted(ids):
        frames.append(nid)
        why[nid] = "frame id"
    for nid, n in R.nodes.items():
        if n["type"] != "frame" or ids:
            continue
        sysab, line = nid.split(":")[1].rsplit("-", 1)
        phrase = _SYS.get(sysab, "")
        named = phrase and re.search(r"\b" + re.escape(phrase) + r"S?\b", T) or re.search(rf"\b{sysab}\b", T)
        if not named:
            continue
        lines = re.findall(r"\bLINES?\s+((?:[A-Z0-9]{1,2}(?:,\s*|\s+AND\s+|\s*))+)", T)
        listed = {x for grp in lines for x in re.split(r",\s*|\s+AND\s+|\s+", grp.strip()) if x}
        if not listed or line in listed:
            frames.append(nid)
            why[nid] = "frame system phrase" + (" + line" if listed else "")
    if re.search(r"SEISMIC FORCE-RESISTING SYSTEM|\bSFRS\b", T) and not frames:
        for nid, n in R.nodes.items():
            if n["type"] == "frame":
                frames.append(nid)
                why[nid] = "SFRS = every frame"
    decks = []
    if re.search(r"\bDECK", T):
        roof = bool(re.search(r"\bROOF DECK|\bROOF\b", T))
        floor = bool(re.search(r"\bFLOOR|\bCOMPOSITE|\bFILL\b|LEVEL \d", T))
        for nid, n in R.nodes.items():
            if n["type"] != "deck":
                continue
            is_roof = level_key(n["attrs"].get("storey", "")) == "RF"
            if (roof and is_roof) or (floor and not is_roof) or (not roof and not floor):
                decks.append(nid)
                why[nid] = "deck phrase"
    piers = []
    if re.search(r"\bPIERS?\b", T):
        for nid, n in R.nodes.items():
            if n["kind"] == "type" and n["type"] == "pier":
                piers.append(nid)
                why[nid] = "pier noun"
    return {"materials": mats, "types": types, "details": sorted(dets), "frames": frames, "decks": decks, "piers": piers,
            "why": why}


# =============================================================================== specs

def ingest_specs(R: Registry, path: str) -> dict:
    sp = spec_ingest.read_specs(path)
    for p in sp["paragraphs"]:
        R.node(p["id"], "spec", "spec_paragraph", p["title"], {k: p[k] for k in ("section", "section_title", "article", "paragraph", "text")})
        occ = lambda c, rule, conf: {"doc": "specs", "how": "spec_article", "section": p["section"], "article": p["article"],  # noqa: E731
                                     "paragraph": p["paragraph"], "page": c["page"], "bbox": c["bbox"], "text": p["text"][:200],
                                     "spec": p["id"], "rule": rule, "confidence": conf}
        for c in p["chunks"]:
            R.occ(p["id"], occ(c, p["rule"], "exact"))
        g = governs(p["text"], R)
        _category_material(R, p, g)
        for nid in g["materials"] + g["types"] + g["details"] + g["frames"] + g["decks"] + g["piers"]:
            conf = "exact" if g["why"][nid] in ("designation", "size", "detail mark") else "inferred"
            R.rel(nid, p["id"], "specified-by", f"spec paragraph names it ({g['why'][nid]})", conf)
            for c in p["chunks"]:
                R.occ(nid, occ(c, f"spec paragraph names it ({g['why'][nid]})", conf))
    return {"sections": len(sp["sections"]), "paragraphs": len(sp["paragraphs"])}


_CATEGORY_NOUNS = {"footing": r"\bFOOTINGS?\b", "grade_beam": r"\bGRADE BEAMS?\b", "deck": r"\bDECK\b", "pier": r"\bPIERS?\b"}


def _category_material(R: Registry, p: dict, g: dict):
    """A product paragraph that cites ONE material by designation and names element categories
    ("Footings, piers and grade beams: f'c = 4,000 psi") makes the untyped elements of those categories
    instances of that material (elements that already have a section / type mark keep their type)."""
    des = [m for m in g["materials"] if g["why"][m] == "designation"]
    if len(des) != 1 or p.get("part") != "2":
        return
    T = p["text"].upper()
    typed = {s for (s, d, k) in R.rels if k == "instance-of"}
    for cat, rx in _CATEGORY_NOUNS.items():
        if re.search(rx, T):
            for nid, n in R.nodes.items():
                if n["kind"] == "element" and n["type"] == cat and nid not in typed:
                    R.rel(nid, des[0], "instance-of", f"product paragraph {p['id']} names the category and one material", "inferred")


def ensure_materials(R: Registry, texts: list[str]):
    """Material nodes exist where a document cites the designation (spec book or drawing notes)."""
    T = " ".join(texts).upper()
    for mid, (name, rx, _) in MATERIALS.items():
        if re.search(rx, T):
            R.node(mid, "material", "material", name)


# =============================================================================== calcs

def ingest_calcs(R: Registry, path: str, pf) -> dict:
    pk = calcpkg_ingest.read_package(path, "calcs", profile=pf)
    known = {}
    for nid, n in R.nodes.items():
        if n["kind"] == "element" and n["type"] not in ("level", "grid"):
            known[nid.split(":", 1)[1] if nid.startswith("FRAME:") else nid] = nid
        elif n["kind"] == "detail":
            known[nid.split(":", 1)[1]] = nid
    res = calc_rows.read_records(pk["pages"], known, pf.calcs.boilerplate_rx, pf.calcs.title.description_prefix)
    by_subject = defaultdict(list)
    for r in res["records"]:
        R.node(r["id"], "record", "calc_record", r["title"], {"sheet": r["sheet"], "software": r["software"], "anchor": r["anchor"],
                                                             "subject": r["subject"], "mentions": r["mentions"]})
        occ = {"doc": "calcs", "how": r["how"], "record": r["id"], "page": r["page"], "bbox": r["bbox"], "sheet": r["sheet"],
               "text": r["text"], "text_layer": True, "rule": r["rule"], "confidence": "exact"}
        R.occ(r["id"], occ)
        if r["subject"]:
            R.occ(r["subject"], dict(occ, rule="calc record names it as its subject"))
            R.rel(r["subject"], r["id"], "designed-by", "calc record's leading identifier names its subject")
            by_subject[r["subject"]].append(r["id"])
    for r in res["records"]:
        subj = R.nodes.get(r["subject"] or "", {})
        for m in r["mentions"]:
            # a connection is designed for the SUPPORTED member's end reaction (load path rule below); the
            # support it also names ("To" column) does not feed it, so a connection record takes only the
            # typical detail it names from its mentions
            if subj.get("type") == "connection" and R.nodes.get(m, {}).get("kind") == "element":
                continue
            for src in by_subject.get(m, []):
                if src != r["id"]:
                    R.rel(src, r["id"], "feeds", "record mentions an element / detail designed by another record", "inferred")
    # load path -> calc dependency: the record designing a supported member feeds the record designing its
    # support (the reaction is a load on it) and the record designing the connection between them
    for (s, d, k), rel in list(R.rels.items()):
        if k not in ("frames-into", "bears-on") or R.nodes[s]["type"] == "deck":
            continue
        for rs in by_subject.get(s, []):
            for rd in by_subject.get(d, []) + by_subject.get(rel.get("via") or "", []):
                R.rel(rs, rd, "feeds", "load path: the supported member's design reaction loads its support / connection", "inferred")
    return {"records": len(res["records"]), "unreadable_pages": res["unreadable_pages"], "stats": res["stats"],
            "software": {p["sheet_id"]: p["software"] for p in pk["pages"]}}


# =============================================================================== build

def counts(nodes: list[dict], rels: list[dict]) -> dict:
    by_kind, by_type, occ, rk = defaultdict(int), defaultdict(int), defaultdict(int), defaultdict(int)
    for n in nodes:
        by_kind[n["kind"]] += 1
        by_type[f"{n['kind']}:{n['type']}"] += 1
        for o in n["occurrences"]:
            occ[o["doc"]] += 1
    for r in rels:
        rk[r["kind"]] += 1
    return {"nodes": len(nodes), "nodes_by_kind": dict(sorted(by_kind.items())), "nodes_by_type": dict(sorted(by_type.items())),
            "occurrences": sum(occ.values()), "occurrences_by_doc": dict(sorted(occ.items())), "relations": len(rels),
            "relations_by_kind": dict(sorted(rk.items()))}


def build(paths: dict) -> dict:
    R = Registry()
    meta = {"inputs": {k: v.split("/")[-1] for k, v in paths.items()}}
    ifc = ingest_ifc(R, paths["ifc"])
    meta["ifc"] = {"elements": len(ifc["elements"]), "grid_lines": len(ifc["grid"])}
    texts = []
    if paths.get("specs"):
        texts += [p["text"] for p in spec_ingest.read_specs(paths["specs"])["paragraphs"]]
    pf = profiles.resolve(None, paths.get("drawings"), paths.get("calcs"))
    if paths.get("drawings"):
        texts += [pymupdf.open(paths["drawings"])[i].get_text() for i in range(pymupdf.open(paths["drawings"]).page_count)]
    ensure_materials(R, texts)
    if paths.get("drawings"):
        meta["drawings"] = ingest_drawings(R, paths["drawings"], ifc, pf)
        meta["drawings"].pop("sheets", None)
    if paths.get("specs"):
        meta["specs"] = ingest_specs(R, paths["specs"])
    if paths.get("calcs"):
        meta["calcs"] = ingest_calcs(R, paths["calcs"], pf)
    meta["profile"] = pf.id
    nodes = sorted(R.nodes.values(), key=lambda n: n["id"])
    for n in nodes:
        n["occurrences"].sort(key=lambda o: (o["doc"], o.get("page") or 0, o.get("bbox") or [], o.get("how", "")))
    rels = sorted(R.rels.values(), key=lambda r: (r["kind"], r["src"], r["dst"]))
    return {"schema": SCHEMA, "source": "ingested", "meta": meta, "nodes": nodes, "relations": rels, "counts": counts(nodes, rels)}
