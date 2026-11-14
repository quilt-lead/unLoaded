"""Hand-labelling procedure for a drawing-set evaluation slice (the code is committed; the labels are not).

Labels are derived from copyrighted PDFs, so everything this script writes goes to the gitignored
data/labels/<sid>/ (never commit it). The procedure is deliberately independent of the pipeline's
tag logic: candidates come from a BROAD raw-word scan, a human reviews numbered tile renders, and
only the reviewed decisions become labels.

  uv run python scripts/label_slice.py candidates --page 55          # raw-word candidates + numbered tiles
  # review data/labels/<sid>/work/tiles/*.png, write data/labels/<sid>/review_<sheet>.json (format below)
  uv run python scripts/label_slice.py finalize --sheet S2.0.2        # -> data/labels/<sid>/tags_<sheet>.json
  uv run python scripts/label_slice.py links-sample --n 50            # stratified sample of pipeline links
  uv run python scripts/label_slice.py links-context                  # both sides' text, for reading
  # judge each link (reading both PDFs), write data/labels/<sid>/links_judged.json

review_<sheet>.json:
  {"sheet": "S2.0.2", "page": 55,
   "grid": {"cols": {"6": x, ...}, "rows": {"A": y, ...}},          # bubble centre lines, PDF points
   "keep": {"<cand id>": {"type": "beam|column|jamb|post|trellis|smf-marker|...", "note": ""}},
   "drop": {"<cand id>": "why (legend / note text / not a tag)"},
   "add":  [{"text": "...", "bbox": [x0,y0,x1,y1], "type": "...", "note": ""}]}

links_judged.json: {"links": [{"key": {...as sampled...}, "correct": true|false, "reason": "..."}]}
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
from collections import defaultdict

import pymupdf

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SET_DIR = os.environ.get("CALCGRAPH_SET_DIR", os.path.expanduser("~/Downloads/dana-point-bldg12-public-set"))
PLANS = "OC-DPH_PKG21-0516_Bldg12_ApprovedPlans.pdf"
CALCS = {"calcs": "OC-DPH_PKG21-0516_Bldg12_Calcs.pdf", "stair": "OC-DPH_PKG21-0516_Bldg12_StairCalcs.pdf"}

# Broad on purpose: anything that looks like a member designation, a mark or a frame marker.
CAND = re.compile(
    r"""^(?:\(?(?:W|HSS|C|MC|L|WT|S|HP|PL)\s?\d+(?:\.\d+)?[xX]\d+.*  # steel shapes
        |\d{1,2}[xX]\d{1,2}(?:[xX].*)?                               # timber / generic AxB
        |\d{3,4}[ST]\d{3}-\d{2,3}                                    # CFS 600S162-54
        |[FP]\d{1,2}(?:\.\d)?                                        # footing / pier marks
        |SMF\d*|BF\d*|MF\d*|GB\d*|TB\d*                               # frames / grade + tie beams
        )$""", re.X)


def labels_dir(sid: str) -> str:
    d = os.path.join(ROOT, "data", "labels", sid)
    os.makedirs(os.path.join(d, "work", "tiles"), exist_ok=True)
    return d


def cmd_candidates(a) -> None:
    d = labels_dir(a.sid)
    doc = pymupdf.open(os.path.join(SET_DIR, PLANS))
    page = doc[a.page - 1]
    words = page.get_text("words")
    lines = defaultdict(list)
    for w in words:
        lines[(w[5], w[6])].append(w)
    cands = []
    for w in words:
        t = w[4].strip(",;")
        if not CAND.match(t):
            continue
        ctx = " ".join(x[4] for x in lines[(w[5], w[6])])
        cands.append({"id": f"c{len(cands):03d}", "text": t, "bbox": [round(v, 1) for v in w[:4]], "line": ctx})
    json.dump({"page": a.page, "candidates": cands}, open(os.path.join(d, "work", f"candidates_p{a.page}.json"), "w"), indent=1)
    # numbered tiles: candidate boxes in red with their id, overlapping tiles so nothing sits on an edge
    X0, Y0, X1, Y1 = [float(v) for v in a.region.split(",")] if a.region else (0, 0, page.rect.width, page.rect.height)
    tw, th, ov = (X1 - X0) / a.cols, (Y1 - Y0) / a.rows, 30
    shape = page.new_shape()
    for c in cands:
        r = pymupdf.Rect(c["bbox"])
        shape.draw_rect(r)
    shape.finish(color=(1, 0, 0), width=0.8)
    shape.commit()
    for c in cands:
        x0, y0 = c["bbox"][0], c["bbox"][1]
        page.insert_text((x0, y0 - 1), c["id"][1:], fontsize=5, color=(0, 0, 1))
    for i in range(a.cols):
        for j in range(a.rows):
            clip = pymupdf.Rect(X0 + i * tw - ov, Y0 + j * th - ov, X0 + (i + 1) * tw + ov, Y0 + (j + 1) * th + ov) & page.rect
            pix = page.get_pixmap(clip=clip, dpi=a.dpi)
            pix.save(os.path.join(d, "work", "tiles", f"p{a.page}_r{j}_c{i}.png"))
    page.get_pixmap(dpi=24).save(os.path.join(d, "work", "tiles", f"p{a.page}_overview.png"))
    print(f"{len(cands)} candidates; tiles {a.cols}x{a.rows} in {os.path.join(d, 'work', 'tiles')}")


def grid_cell(x: float, y: float, grid: dict, vertical: bool) -> str:
    """Grid reference of a point: the bay between the two nearest bubble lines on each axis,
    or the line itself when within 12 pt of it."""
    def axis(v: float, lines: dict[str, float]) -> str:
        pts = sorted(lines.items(), key=lambda kv: kv[1])
        for k, p in pts:
            if abs(v - p) <= 12:
                return k
        if v < pts[0][1]:
            return f"<{pts[0][0]}"
        if v > pts[-1][1]:
            return f">{pts[-1][0]}"
        for (k1, p1), (k2, p2) in zip(pts, pts[1:]):
            if p1 < v < p2:
                return f"{k1}-{k2}"
        return "?"
    return f"{axis(y, grid['rows'])}/{axis(x, grid['cols'])}"


def cmd_finalize(a) -> None:
    d = labels_dir(a.sid)
    rv = json.load(open(os.path.join(d, f"review_{a.sheet}.json")))
    cands = {c["id"]: c for c in json.load(open(os.path.join(d, "work", f"candidates_p{rv['page']}.json")))["candidates"]}
    missing = set(cands) - set(rv["keep"]) - set(rv["drop"])
    if missing:
        sys.exit(f"unreviewed candidates: {sorted(missing)}")
    tags = []
    for cid, k in rv["keep"].items():
        c = cands[cid]
        tags.append({"text": k.get("text", c["text"]), "bbox": c["bbox"], "type": k["type"], "note": k.get("note", ""),
                     "source": "candidate+review"})
    for t in rv.get("add", []):
        tags.append({**t, "source": "added by reviewer"})
    for t in tags:
        x = (t["bbox"][0] + t["bbox"][2]) / 2
        y = (t["bbox"][1] + t["bbox"][3]) / 2
        t["grid"] = t.get("grid") or grid_cell(x, y, rv["grid"], False)
    out = {"sid": a.sid, "sheet": a.sheet, "page": rv["page"], "doc": "plans", "grid": rv["grid"],
           "procedure": "scripts/label_slice.py candidates -> human tile review -> finalize",
           "dropped": len(rv["drop"]), "type_map": rv.get("type_map", {}), "tags": tags}
    json.dump(out, open(os.path.join(d, f"tags_{a.sheet}.json"), "w"), indent=1)
    by = defaultdict(int)
    for t in tags:
        by[t["type"]] += 1
    print(f"{len(tags)} labelled tags on {a.sheet}: {dict(by)}; {len(rv['drop'])} candidates dropped")


def link_key(g: dict, l: dict) -> dict:
    els = {e["id"]: e for e in g["elements"]}
    cs = {c["id"]: c for c in g["calcs"]}
    e, c = els[l["el"]], cs[l["calc"]]
    return {"sheet": e["sheet"], "el_text": e["text"], "el_bbox": e["bbox"], "el_type": e["type"],
            "calc_doc": c["doc"], "calc_sheet": c["sheet_id"], "calc_page": c["page"], "tier": l["tier"]}


def cmd_links_sample(a) -> None:
    d = labels_dir(a.sid)
    g = json.load(open(os.path.join(ROOT, "data", "sets", a.sid, "graph.json")))
    rng = random.Random(a.seed)
    by_tier = defaultdict(list)
    for l in g["links"]:
        by_tier[l["tier"]].append(l)
    # proportional to tier size, at least 3 per tier (or all of a small tier)
    total = len(g["links"])
    picked = []
    for t, ls in sorted(by_tier.items()):
        k = min(len(ls), max(3, round(a.n * len(ls) / total)))
        picked += rng.sample(ls, k)
    out = [{"key": link_key(g, l), "rule": l["rule"], "score": l["score"],
            "el_evidence": l["evidence"]["el"]["text"], "calc_evidence": l["evidence"]["calc"]["text"]} for l in picked]
    json.dump({"seed": a.seed, "graph_built_at": g["built_at"], "links": out},
              open(os.path.join(d, "work", "links_sample.json"), "w"), indent=1)
    print(f"sampled {len(out)} links from {total}: " + ", ".join(f"{t} {len(v)}" for t, v in sorted(by_tier.items())))


def cmd_links_context(a) -> None:
    """Print, for each sampled link, the drawing words around the tag and the calc page text."""
    d = labels_dir(a.sid)
    s = json.load(open(os.path.join(d, "work", "links_sample.json")))
    plans = pymupdf.open(os.path.join(SET_DIR, PLANS))
    calcs = {k: pymupdf.open(os.path.join(SET_DIR, v)) for k, v in CALCS.items()}
    sheet_page = {}
    g = json.load(open(os.path.join(ROOT, "data", "sets", a.sid, "graph.json")))
    for sh in g["sheets"]:
        sheet_page[sh["sheet"]] = sh["page"]
    for i, l in enumerate(s["links"]):
        k = l["key"]
        pg = plans[sheet_page[k["sheet"]] - 1]
        r = pymupdf.Rect(k["el_bbox"]) + (-60, -40, 60, 40)
        near = " ".join(w[4] for w in pg.get_text("words", clip=r))
        cp = calcs[k["calc_doc"]][k["calc_page"] - 1]
        lines = [ln.strip() for ln in cp.get_text().splitlines() if ln.strip()]
        head = " | ".join(lines[: a.head])
        # lines that print the tagged size (case-insensitive, fractions dropped the way RISA truncates them)
        size = re.sub(r"[^0-9a-z]", "", k["el_text"].lower().split("/")[0])
        hits = [ln for ln in lines if size and size in re.sub(r"[^0-9a-z]", "", ln.lower())]
        print(f"=== [{i}] {k['sheet']} {k['el_text']} ({k['el_type']}) -> {k['calc_doc']}:{k['calc_sheet']} p{k['calc_page']}"
              f"  tier={k['tier']} score={l['score']}\n  rule: {l['rule']}\n  near tag: {near}\n  calc head: {head[: a.chars]}\n"
              f"  calc lines with the size ({len(hits)}): {' || '.join(hits[:6])[: a.chars]}\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sid", default="dana-point-bldg12")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("candidates")
    p.add_argument("--page", type=int, default=55)
    p.add_argument("--cols", type=int, default=6)
    p.add_argument("--rows", type=int, default=4)
    p.add_argument("--dpi", type=int, default=110)
    p.add_argument("--region", default="", help="x0,y0,x1,y1 in PDF points (default: whole page)")
    p = sub.add_parser("finalize")
    p.add_argument("--sheet", default="S2.0.2")
    p = sub.add_parser("links-sample")
    p.add_argument("--n", type=int, default=50)
    p.add_argument("--seed", type=int, default=20261114)
    p = sub.add_parser("links-context")
    p.add_argument("--chars", type=int, default=600)
    p.add_argument("--head", type=int, default=12)
    a = ap.parse_args()
    {"candidates": cmd_candidates, "finalize": cmd_finalize, "links-sample": cmd_links_sample,
     "links-context": cmd_links_context}[a.cmd](a)


if __name__ == "__main__":
    main()
