"""3D structural model FROM THE PLANS: drawing-set elements -> IFC4.

Every IFC element IS a drawing-set element: its GlobalId is uuid5 of the element id, and
its pset carries the sheet, element id, tag text, grid, level and the rule that placed it.

Coordinates
  Each plan sheet is calibrated from its own grid bubbles and the dimension strings
  between adjacent bubbles (15'-6", 20'-1" ...), not from the nominal scale. Grid lines
  get building coordinates (feet) from the cumulative dimension strings of a reference
  plan; a point on any plan maps piecewise-linearly between that sheet's own grid lines,
  so every S2.0.x sheet registers to the same grid. Residual per dimension string =
  (calibrated scale x measured points) - written dimension, reported per sheet.
  Building axes: x east from grid 6, y north from grid F, z up from the finish-floor datum.
Elevations
  Read from the drawings and cited (sheet, words, boxes). Where a value is not stated for
  the thing it is applied to, it is marked ASSUMED in the element pset and in the UI.
Placement rules
  HSS column   leader end on the plan (drawing_loadpath) -> x, y; foundation plan columns
               run top of footing -> Level 2, and on to the roof when a roof beam's drawn line
               ends within 1.5 ft of it; Level 2 plan columns run Level 2 -> roof (assumed)
  W beam       the drawn line it labels, ends registered to building coords, top of steel at
               the level elevation (slab / deck depth not deducted)
  Footing      at the column its mark belongs to, schedule L x W x T, top at top of footing
  Moment frame S3.0.1 frame elevations: bubbles give the bay grid lines; the frame line is
               the grid the SMF markers on the Level 2 plan vote for; columns at bubble lines
               finish floor -> T.O. parapet line, beams between bubbles at the level line
               they are drawn on
Never invented: a size not in aisc.py becomes a generic box flagged "profile unknown".
"""
from __future__ import annotations

import math
import re
import uuid
from collections import Counter, defaultdict

import numpy as np
import pymupdf

from . import aisc
from .ifc_common import IfcBuilder

NS = uuid.UUID("2b8f6c1e-7d3a-4f51-9a0e-5d1c3b7e9f20")
FT = 0.3048
DIM = re.compile(r"^(\d+)'\s*-\s*(\d+)(?:\s+(\d+)/(\d+))?\"$")
ELEV = re.compile(r"^([+-])?\s*(\d+)'\s*-\s*(\d+)(?:\s+(\d+)/(\d+))?\"$")


def _ft(m) -> float:
    v = int(m.group(1)) + int(m.group(2)) / 12
    if m.group(3):
        v += int(m.group(3)) / int(m.group(4)) / 12
    return v


def parse_elev(text: str) -> float | None:
    m = re.search(r"([+-])?\s*(\d+)'\s*-\s*(\d+)(?:\s+(\d+)/(\d+))?\"", text)
    if not m:
        return None
    v = int(m.group(2)) + int(m.group(3)) / 12 + (int(m.group(4)) / int(m.group(5)) / 12 if m.group(4) else 0)
    return -v if m.group(1) == "-" else v


def _lines(page):
    out = []
    for b in page.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            t = " ".join(s["text"].strip() for s in l["spans"] if s["text"].strip())
            if t:
                out.append({"text": t, "rect": [round(v, 1) for v in l["bbox"]], "dir": tuple(round(v) for v in l["dir"])})
    return out


def _r(b):
    return [round(v, 1) for v in b]


# ---------------- calibration ----------------
def calibrate(page, sheet: dict) -> dict:
    g = sheet["grid"]
    cols, rows = g["cols"], g["rows"]
    lines = [l for l in _lines(page) if DIM.match(l["text"]) and l["rect"][2] < sheet["cutoff"]]
    top_y = min(r[1] for c in cols for r in c["rects"])
    left_x = min(r[0] for c in rows for r in c["rects"])
    pairs = []
    for axis, gl in (("x", cols), ("y", rows)):
        for a, b in zip(gl, gl[1:]):
            mid = (a["pos"] + b["pos"]) / 2
            if axis == "x":
                cand = [l for l in lines if l["dir"] == (1, 0) and a["pos"] < (l["rect"][0] + l["rect"][2]) / 2 < b["pos"]
                        and top_y < (l["rect"][1] + l["rect"][3]) / 2 < top_y + 150]
                key = lambda l: abs((l["rect"][0] + l["rect"][2]) / 2 - mid)
            else:
                cand = [l for l in lines if l["dir"][0] == 0 and a["pos"] < (l["rect"][1] + l["rect"][3]) / 2 < b["pos"]
                        and left_x < (l["rect"][0] + l["rect"][2]) / 2 < left_x + 150]
                key = lambda l: abs((l["rect"][1] + l["rect"][3]) / 2 - mid)
            if not cand:
                pairs.append({"axis": axis, "a": a["label"], "b": b["label"], "dpt": b["pos"] - a["pos"], "dim": None})
                continue
            l = min(cand, key=key)
            pairs.append({"axis": axis, "a": a["label"], "b": b["label"], "dpt": b["pos"] - a["pos"],
                          "dim": _ft(DIM.match(l["text"])), "text": l["text"], "rect": l["rect"]})
    k = {}
    for axis in ("x", "y"):
        ps = [p for p in pairs if p["axis"] == axis and p["dim"]]
        k[axis] = sum(p["dim"] * p["dpt"] for p in ps) / sum(p["dpt"] ** 2 for p in ps) if ps else 1 / 9.0
    for p in pairs:
        if p["dim"]:
            p["measured_ft"] = round(k[p["axis"]] * p["dpt"], 3)
            p["residual_in"] = round((p["measured_ft"] - p["dim"]) * 12, 2)
    res = [abs(p["residual_in"]) for p in pairs if p["dim"]]
    return {"sheet": sheet["sheet"], "kx_ft_per_pt": k["x"], "ky_ft_per_pt": k["y"],
            "scale_check": f"1 ft = {1 / k['x']:.2f} pt (x), {1 / k['y']:.2f} pt (y); nominal 1/8\" = 1'-0\" is 9.00",
            "pairs": pairs, "dims_found": len(res), "dims_expected": len(pairs),
            "max_residual_in": round(max(res), 2) if res else None,
            "rms_residual_in": round(math.sqrt(sum(r * r for r in res) / len(res)), 2) if res else None}


class Frame:
    """Building coordinates (ft) of grid lines, from a reference sheet's dimension strings."""

    def __init__(self, cal: dict, sheet: dict):
        self.col_ft, self.row_ft = {}, {}
        for axis, gl, out in (("x", sheet["grid"]["cols"], self.col_ft), ("y", sheet["grid"]["rows"], self.row_ft)):
            pos = 0.0
            out[gl[0]["label"]] = 0.0
            for p in [q for q in cal["pairs"] if q["axis"] == axis]:
                pos += p["dim"] if p["dim"] else p["dpt"] * cal["k" + axis + "_ft_per_pt"]
                out[p["b"]] = pos
        self.depth = max(self.row_ft.values())  # A..F, A at the top of the sheet
        self.source = sheet["sheet"]

    def gx(self, label):
        return self.col_ft[label]

    def gy(self, label):  # north positive, F at 0
        return self.depth - self.row_ft[label]

    def mapper(self, sheet: dict, cal: dict):
        cols = [(c["pos"], self.col_ft[c["label"]]) for c in sheet["grid"]["cols"] if c["label"] in self.col_ft]
        rows = [(r["pos"], self.row_ft[r["label"]]) for r in sheet["grid"]["rows"] if r["label"] in self.row_ft]

        def interp(v, pts, k):
            pts = sorted(pts)
            if v <= pts[0][0]:
                return pts[0][1] + (v - pts[0][0]) * k
            if v >= pts[-1][0]:
                return pts[-1][1] + (v - pts[-1][0]) * k
            for (p0, f0), (p1, f1) in zip(pts, pts[1:]):
                if p0 <= v <= p1:
                    return f0 + (v - p0) / (p1 - p0) * (f1 - f0)

        return lambda x, y: (interp(x, cols, cal["kx_ft_per_pt"]), self.depth - interp(y, rows, cal["ky_ft_per_pt"]))


# ---------------- elevations ----------------
def read_elevations(doc, sheets: list[dict]) -> dict:
    """Each: {ft, text, sheet, page, rects, assumed, note}."""
    by = {s["sheet"]: s for s in sheets}
    out = {}

    def head(sheet_no, label_rx, key):
        s = by.get(sheet_no)
        if not s:
            return
        ls = _lines(doc[s["page"] - 1])
        for l in ls:
            if re.fullmatch(label_rx, l["text"]):
                below = [m for m in ls if ELEV.match(m["text"]) and 0 < m["rect"][1] - l["rect"][1] < 16
                         and abs(m["rect"][2] - l["rect"][2]) < 12]
                if below:
                    out[key] = {"ft": parse_elev(below[0]["text"]),
                                "text": f"{l['text']} {below[0]['text']}", "sheet": sheet_no, "page": s["page"],
                                "rects": [l["rect"], below[0]["rect"]], "assumed": False}
                    return

    smf = next((s["sheet"] for s in sheets if s["kind"] == "smf"), None)
    head(smf, r"LEVEL 2", "level2")
    head(smf, r"T\.O\. PARAPET", "parapet")
    # notes: datum and top of footing
    for s in sheets:
        if s["kind"] not in ("framing", "foundation"):
            continue
        for l in _lines(doc[s["page"] - 1]):
            t = l["text"]
            if "datum" not in out and re.search(r"\(DATUM\) ELEVATION 0'-0\"", t):
                out["datum"] = {"ft": 0.0, "text": t, "sheet": s["sheet"], "page": s["page"], "rects": [l["rect"]],
                                "assumed": False}
            m = re.search(r"FOOTING ELEVATION SHALL BE ([+-]?\d+'-\d+\")", t)
            if m and "tof" not in out:
                out["tof"] = {"ft": parse_elev(m.group(1).replace("'-", "' - ")),
                              "text": t + " (general note: top of all footings, typ. UNO)", "sheet": s["sheet"],
                              "page": s["page"], "rects": [l["rect"]], "assumed": False}
            m = re.match(r"^TOSL: \+(\d+)'-(\d+)\"$", t)
            if m and s["level"] == "Level 2" and "level2_tosl" not in out:
                out["level2_tosl"] = {"ft": int(m.group(1)) + int(m.group(2)) / 12, "text": t, "sheet": s["sheet"],
                                      "page": s["page"], "rects": [l["rect"]], "assumed": False}
    if "parapet" in out:
        p = out["parapet"]
        out["roof"] = {**p, "assumed": True,
                       "note": "No roof elevation is written on the plans. Roof framing is placed at the T.O. PARAPET "
                               "line, where S3.0.1 draws the roof moment-frame beams. S2.0.3 carries a local "
                               "'TOS: +30'-6\"' note (not applied)."}
    return out


# ---------------- moment frames from S3.0.1 ----------------
def frames_from_elevation(doc, sheets, elements, frame: Frame, elev: dict) -> tuple[list[dict], list[str]]:
    smf = next((s for s in sheets if s["kind"] == "smf"), None)
    if not smf:
        return [], ["no moment frame elevation sheet"]
    page = doc[smf["page"] - 1]
    words = page.get_text("words")
    bub = [w for w in words if re.fullmatch(r"\d(\.\d)?|[A-F](\.\d)?", w[4]) and 17 <= (w[3] - w[1]) <= 21 and w[2] < smf["cutoff"]]
    # (25 pt numbers are elevation view titles, not grid bubbles)
    clusters: list[list] = []
    for w in sorted(bub, key=lambda w: (round(w[1] / 10), w[0])):
        c = next((c for c in clusters if abs(c[0][1] - w[1]) < 6 and w[0] - c[-1][0] < 450), None)
        if c:
            c.append(w)
        else:
            clusters.append([w])
    ls = _lines(page)
    heads_l2 = [l for l in ls if l["text"] == "LEVEL 2"]
    heads_par = [l for l in ls if l["text"] == "T.O. PARAPET"]
    heads_ff = [l for l in ls if l["text"].startswith("BUILDING 12 FINISHED")]
    markers = [e for e in elements if e["mark"] == "SMF" and e["sheet_kind"] == "framing" and e["level"] == "Level 2"]
    out, notes = [], []
    used = set()
    used_markers: set[str] = set()
    singles = [c for c in clusters if len(c) < 2]
    if singles:
        notes.append(f"{len(singles)} lone bubble(s) on {smf['sheet']} (not a frame elevation) ignored")
    # larger frames first; each SMF marker can place one frame only
    for c in sorted((c for c in clusters if len(c) >= 2), key=lambda c: -len(c)):
        labels = [w[4] for w in sorted(c, key=lambda w: w[0])]
        bx = {w[4]: (w[0] + w[2]) / 2 for w in c}
        by_ = c[0][1]
        x1 = max(bx.values())
        near = lambda hs: min((h for h in hs if h["rect"][0] > x1 and 0 < h["rect"][1] - by_ < 700),
                              key=lambda h: h["rect"][0] - x1 + (h["rect"][1] - by_) * 0.1, default=None)
        h2, hp, hf = near(heads_l2), near(heads_par), near(heads_ff)
        if not (h2 and hp):
            notes.append(f"frame {'-'.join(labels)}: level heads not found")
            continue
        letters = labels[0][0].isalpha()
        votes = Counter()
        voters: dict[str, list[str]] = defaultdict(list)
        for m in markers:
            if m["id"] in used_markers:
                continue
            ref = m["grid"]
            if "/" not in ref:
                continue
            rp, cp = ref.split("/")
            along, perp = (rp, cp) if letters else (cp, rp)
            if "-" in perp or "beyond" in perp:
                continue
            parts = along.replace("beyond ", "").split("-")
            lo, hi = min(labels), max(labels)
            if all(p in labels or lo <= p <= hi for p in parts):
                votes[perp] += 1
                voters[perp].append(m["id"])
        if not votes:
            notes.append(f"frame {'-'.join(labels)}: no SMF marker on the Level 2 plan places it - skipped")
            continue
        line, nv = votes.most_common(1)[0]
        used_markers.update(voters[line])
        y2, yp = (h2["rect"][1] + h2["rect"][3]) / 2, (hp["rect"][1] + hp["rect"][3]) / 2
        region = (min(bx.values()) - 80, by_ - 10, x1 + 80, (hf["rect"][3] if hf else y2 + 200) + 30)
        tags = [e for e in elements if e["sheet"] == smf["sheet"] and region[0] < e["bbox"][0] < region[2]
                and region[1] < e["bbox"][1] < region[3] and e["id"] not in used]
        xy = (lambda lab: (frame.gx(line), frame.gy(lab))) if letters else (lambda lab: (frame.gx(lab), frame.gy(line)))
        for e in tags:
            cx, cy = (e["bbox"][0] + e["bbox"][2]) / 2, (e["bbox"][1] + e["bbox"][3]) / 2
            src = {"frame": f"{'-'.join(labels)} on grid {line}", "votes": nv}
            if e["vertical_text"]:
                lab = min(bx, key=lambda k: abs(bx[k] - cx))
                if abs(bx[lab] - cx) > 45:
                    continue
                out.append({"el": e, "kind": "column", "xy": xy(lab), "grid": f"{line}/{lab}" if letters else f"{lab}/{line}",
                            "z0": elev["datum"]["ft"] if "datum" in elev else 0.0, "z1": elev["parapet"]["ft"], **src})
            else:
                order = sorted(bx, key=lambda k: bx[k])
                bay = next(((a, b) for a, b in zip(order, order[1:]) if bx[a] < cx < bx[b]), None)
                if not bay:
                    continue
                lvl = "level2" if abs(cy - y2) < abs(cy - yp) else "roof"
                out.append({"el": e, "kind": "beam", "p1": xy(bay[0]), "p2": xy(bay[1]),
                            "grid": f"{line}/{bay[0]}-{bay[1]}" if letters else f"{bay[0]}-{bay[1]}/{line}",
                            "z": elev[lvl]["ft"], "level_key": lvl, **src})
            used.add(e["id"])
        notes.append(f"frame {'-'.join(labels)} placed on grid {line} ({nv} SMF marker votes)")
    return out, notes


# ---------------- build ----------------
def build(sid: str, plans_path: str, sheets: list[dict], elements: list[dict], edges: list[dict], links: list[dict],
          findings: list[dict], out_path: str) -> dict:
    doc = pymupdf.open(plans_path)
    plans = {s["sheet"]: s for s in sheets if s["kind"] in ("framing", "foundation") and s["grid"]["cols"]}
    cals = {sh: calibrate(doc[s["page"] - 1], s) for sh, s in plans.items()}
    ref_sheet = max(plans.values(), key=lambda s: (cals[s["sheet"]]["dims_found"], s["kind"] == "framing"))
    frame = Frame(cals[ref_sheet["sheet"]], ref_sheet)
    maps = {sh: frame.mapper(plans[sh], cals[sh]) for sh in plans}
    elev = read_elevations(doc, sheets)
    lv_ft = {"Level 2": elev["level2"]["ft"], "Roof": elev["roof"]["ft"]}
    lv_key = {"Level 2": "level2", "Roof": "roof"}

    B = IfcBuilder(out_path, namespace=NS, project_name="Dana Point Harbor Bldg 12 - structure from plans",
                   project_description="Built by calc-graph from the structural S-sheets (no BIM model)",
                   project_phase="permit set", building_name="Building 12",
                   storeys=[("Foundation", elev["tof"]["ft"] * FT), ("Level 1", 0.0), ("Level 2", lv_ft["Level 2"] * FT),
                            ("Roof", lv_ft["Roof"] * FT)],
                   author="calc-graph plans_to_ifc", originating_system="calc-graph plans_to_ifc")
    placed: dict[str, dict] = {}
    skipped: Counter = Counter()
    skip_of: dict[str, str] = {}
    by_id = {e["id"]: e for e in elements}
    down = defaultdict(list)
    for e in edges:
        down[e["src"]].append(e)
    linked = {l["el"] for l in links}
    mism_text = [f["text"].split("Sizes C prints")[0] for f in findings if f["kind"] == "size mismatch"]

    def elev_src(key):
        e = elev[key]
        return f"{e['text']} ({e['sheet']})" + (" ASSUMED - " + e.get("note", "") if e.get("assumed") else "")

    def profile_for(e):
        n = e["size_norm"]
        if n.startswith("W"):
            d = aisc.w_dims_m(n)
            if d:
                return B.i_profile(n, d["bf"], d["d"], d["tw"], d["tf"]), d["d"], d["source"]
        if n.startswith("HSS"):
            d = aisc.hss_dims_m(n)
            if d:
                return B.rect_hollow_profile(n, d["b"], d["h"], d["t"]), d["h"], d["source"]
        nom = float(re.match(r"[A-Z]+(\d+(?:\.\d+)?)", n).group(1)) * 0.0254 if re.match(r"[A-Z]+\d", n) else 0.3
        return B.rect_profile(nom * 0.5, nom, f"generic {n}"), nom, f"PROFILE UNKNOWN - generic box {n} (size not in the section table)"

    def emit(e, cls, pre, storey, placement, solid, rule, pos_src, z_src, assumed, prof_src, grid=None):
        key = f"dp:{sid}:{e['id']}"
        inst, gid = B.product(cls, key, e["text"], e["type"], placement, solid, storey, pre)
        if e["id"] in linked:
            status = "linked"
        elif e["size_norm"] and any(e["size_norm"] in t for t in mism_text):
            status = "size mismatch"
        else:
            status = "no calc found"
        B.psets(inst, key, {"CalcGraph_Drawing": {
            "ElementId": e["id"], "Sheet": e["sheet"], "SheetTitle": e["sheet_title"], "Tag": e["text"], "Type": e["type"],
            "Size": e["size_norm"] or e["mark"], "Grid": grid or e["grid"], "Level": e["level"] or storey,
            "PlacementRule": rule, "PositionSource": pos_src, "ElevationSource": z_src,
            "Assumed": "; ".join(assumed) if assumed else "no", "ProfileSource": prof_src, "CalcLinkStatus": status}})
        placed[e["id"]] = {"gid": gid, "rule": rule, "position": pos_src, "elevation": z_src, "assumed": assumed,
                           "profile": prof_src, "status3d": status, "grid3d": grid or e["grid"]}

    # roof beam line ends in building coords (to see which foundation columns run to the roof)
    roof_ends = []
    for e in elements:
        if e["sheet"] in plans and plans[e["sheet"]]["level"] == "Roof" and e.get("line"):
            m = maps[e["sheet"]]
            roof_ends += [(m(e["line"][0], e["line"][1]), e), (m(e["line"][2], e["line"][3]), e)]

    # columns
    for e in elements:
        if e["cat"] != "Column" or e["sheet"] not in plans:
            continue
        s = plans[e["sheet"]]
        if s["level"] == "Roof":
            skipped["roof-plan posts (above the roof, no top elevation on the plans)"] += 1
            skip_of[e["id"]] = "post above the roof - no top elevation on the plans"
            continue
        if not e.get("at"):
            skipped["column without a followable leader (position unknown)"] += 1
            skip_of[e["id"]] = "leader not followed - position unknown"
            continue
        x, y = maps[e["sheet"]](*e["at"])
        assumed = []
        if s["kind"] == "foundation":
            z0, zs0 = elev["tof"]["ft"], elev_src("tof")
            near = [(math.hypot(p[0] - x, p[1] - y), b) for p, b in roof_ends]
            near = [t for t in near if t[0] <= 1.5]
            stack = [ed for ed in edges if ed["dst"] == e["id"] and ed["rule"] == "column->column"]
            if near:
                z1, zs1 = lv_ft["Roof"], elev_src("roof") + f"; runs to the roof: roof beam {near[0][1]['text']} line ends {near[0][0]:.1f} ft away"
                assumed += [] if not elev["roof"]["assumed"] else ["roof elevation"]
            elif stack:
                z1, zs1 = lv_ft["Roof"], elev_src("roof") + "; runs to the roof: column tagged above on the Level 2 plan"
                assumed += ["roof elevation"] if elev["roof"]["assumed"] else []
            else:
                z1, zs1 = lv_ft["Level 2"], elev_src("level2")
            storey = "Foundation"
        else:
            z0, z1 = lv_ft["Level 2"], lv_ft["Roof"]
            zs0, zs1 = elev_src("level2"), elev_src("roof")
            assumed += ["height Level 2 -> roof (column tagged on the Level 2 plan, top not stated)"]
            storey = "Level 2"
        prof, _, psrc = profile_for(e)
        emit(e, "IfcColumn", "COLUMN", storey, B.ax((x * FT, y * FT, z0 * FT)), B.solid(prof, (z1 - z0) * FT),
             "column at its leader end", f"leader end on {e['sheet']} at {e['grid']} -> ({x:.2f}, {y:.2f}) ft",
             f"base {zs0}; top {zs1}", assumed, psrc)

    # beams
    for e in elements:
        if e["cat"] != "Beam" or e["family"] != "W" or e["sheet"] not in plans:
            continue
        s = plans[e["sheet"]]
        if not e.get("line"):
            skipped["beam tag not on a followed drawn line"] += 1
            skip_of[e["id"]] = "drawn line not followed"
            continue
        m = maps[e["sheet"]]
        p1, p2 = np.array(m(e["line"][0], e["line"][1])), np.array(m(e["line"][2], e["line"][3]))
        z = lv_ft[s["level"]]
        prof, depth, psrc = profile_for(e)
        d = np.array([*(p2 - p1), 0.0]) * FT
        L = float(np.linalg.norm(d))
        if L < 0.3:
            skipped["beam line too short"] += 1
            continue
        zd = d / L
        xd = np.cross([0, 0, 1.0], zd)
        origin = (p1[0] * FT, p1[1] * FT, z * FT - depth / 2)
        assumed = ["roof elevation"] if s["level"] == "Roof" and elev["roof"]["assumed"] else []
        emit(e, "IfcBeam", "BEAM", s["level"], B.ax(origin, tuple(zd), tuple(xd)), B.solid(prof, L),
             "drawn beam line", f"line ends on {e['sheet']} -> ({p1[0]:.2f}, {p1[1]:.2f}) to ({p2[0]:.2f}, {p2[1]:.2f}) ft",
             f"top of steel = {elev_src(lv_key[s['level']])} (slab / deck depth not deducted)", assumed, psrc)

    # footings
    col_of_ft = {ed["dst"]: by_id[ed["src"]] for ed in edges if ed["rule"] == "column->footing"}
    for e in elements:
        if e["cat"] != "Footing":
            continue
        c = col_of_ft.get(e["id"])
        sch = e.get("schedule")
        if not c or not c.get("at") or not sch:
            skipped["footing mark not tied to a located column / no schedule size"] += 1
            skip_of[e["id"]] = "no located column for this footing mark" if sch else "no schedule size"
            continue
        x, y = maps[c["sheet"]](*c["at"])
        top = elev["tof"]["ft"]
        prof = B.rect_profile(sch["length_ft"] * FT, sch["width_ft"] * FT)
        emit(e, "IfcFooting", "PAD_FOOTING", "Foundation", B.ax((x * FT, y * FT, (top - sch["thick_ft"]) * FT)),
             B.solid(prof, sch["thick_ft"] * FT), "footing under its column",
             f"centred on column {c['text']} ({c['id']}) at {c['grid']}", f"top {elev_src('tof')}", [],
             f"schedule: {sch['text']} ({sch['sheet']})")

    # moment frames
    mf, mf_notes = frames_from_elevation(doc, sheets, elements, frame, elev)
    for f in mf:
        e = f["el"]
        prof, depth, psrc = profile_for(e)
        if f["kind"] == "column":
            x, y = f["xy"]
            emit(e, "IfcColumn", "COLUMN", "Level 1", B.ax((x * FT, y * FT, f["z0"] * FT), (0, 0, 1), (0, 1, 0)),
                 B.solid(prof, (f["z1"] - f["z0"]) * FT), "moment frame column on its bubble line",
                 f"S3.0.1 frame {f['frame']} -> grid {f['grid']}",
                 f"base {elev_src('datum') if 'datum' in elev else 'finish floor 0'}; top {elev_src('parapet')}",
                 ["frame line from SMF marker votes", "column base at finish floor (base plate / footing not modelled)"],
                 psrc, grid=f["grid"])
        else:
            p1, p2 = np.array(f["p1"]), np.array(f["p2"])
            d = np.array([*(p2 - p1), 0.0]) * FT
            L = float(np.linalg.norm(d))
            zd = d / L
            xd = np.cross([0, 0, 1.0], zd)
            emit(e, "IfcBeam", "BEAM", "Level 2" if f["level_key"] == "level2" else "Roof",
                 B.ax((p1[0] * FT, p1[1] * FT, f["z"] * FT - depth / 2), tuple(zd), tuple(xd)), B.solid(prof, L),
                 "moment frame beam between its bubbles", f"S3.0.1 frame {f['frame']} -> bay {f['grid']}",
                 f"top of steel = {elev_src(f['level_key'])}",
                 ["frame line from SMF marker votes"] + (["roof elevation"] if f["level_key"] == "roof" else []),
                 psrc, grid=f["grid"])
    B.write(out_path)

    for e in elements:
        if e["id"] in placed:
            e["model"] = {"in3d": True, **placed[e["id"]]}
        else:
            reason = skip_of.get(e["id"])
            if not reason:
                reason = {"Pile": "piers: no position resolved (no leader, schedule only)",
                          "Frame": "SMF marker: a symbol, the frame itself is modelled from S3.0.1"}.get(e["cat"])
            if not reason and e["mark"].startswith(("TB", "GB")):
                reason = "grade / tie beam: drawn line not followed"
            if not reason and e["family"] == "Timber":
                reason = "timber trellis: optional, not modelled"
            if not reason:
                reason = f"not modelled: {e['type']} on {e['sheet']} ({e['sheet_kind']} sheet)"
            e["model"] = {"in3d": False, "reason": reason}
    counts = Counter(by_id[i]["type"] for i in placed)
    skip_counts = Counter(e["model"]["reason"] for e in elements if not e["model"]["in3d"])
    return {
        "url": f"/api/sets/{sid}/model.ifc", "elements_in_3d": len(placed), "elements_total": len(elements),
        "counts_by_type": dict(counts.most_common()), "skipped": dict(skip_counts.most_common()),
        "calibration": {sh: {k: v for k, v in c.items() if k != "pairs"} | {
            "pairs": [{k: v for k, v in p.items() if k != "rect"} for p in c["pairs"]]} for sh, c in cals.items()},
        "reference_sheet": ref_sheet["sheet"], "grid_ft": {"cols": frame.col_ft, "rows_from_A": frame.row_ft},
        "elevations": elev, "frames": mf_notes,
    }
