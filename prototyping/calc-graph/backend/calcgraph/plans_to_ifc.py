"""Plan-sheet dimension strings: the calibration of a plan sheet from its own grid bubbles and the
dimension strings between adjacent bubbles (15'-6", 20'-1" ...), not from the nominal scale.

    calibrate(page, sheet) -> {kx_ft_per_pt, ky_ft_per_pt, pairs (one per adjacent bubble pair, with the
                               written dimension, the measured feet and the residual), dims_found, ...}
    _lines(page)           -> text lines with their box and writing direction
    DIM / _ft              -> the dimension-string grammar and its value in feet

Used by the drawing check (drawing_verify: printed dimensions vs the model). This module used to
also build a 3D model FROM THE PLANS of a drawing set that had no BIM model; that builder was
specific to one retired permit set and is gone (tag pre-v2-cleanup has it). A drawing set's 3D view
is now the building's own IFC (set_pipeline.link_model). The module keeps its name because
drawing_verify imports it by that name.
"""
from __future__ import annotations

import math
import re

DIM = re.compile(r"^(\d+)'\s*-\s*(\d+)(?:\s+(\d+)/(\d+))?\"$")


def _ft(m) -> float:
    v = int(m.group(1)) + int(m.group(2)) / 12
    if m.group(3):
        v += int(m.group(3)) / int(m.group(4)) / 12
    return v


def _lines(page):
    out = []
    for b in page.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            t = " ".join(s["text"].strip() for s in l["spans"] if s["text"].strip())
            if t:
                out.append({"text": t, "rect": [round(v, 1) for v in l["bbox"]], "dir": tuple(round(v) for v in l["dir"])})
    return out


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
