"""Unit guards for the readers and estimates the perimeter-SCBF regeneration exposed (CI only).

- every AISC shape name reads back whole through the IFC profile parser (fractional HSS walls:
  "HSS6X6X1/4" once read as "HSS6X6X1")
- a calc page that prints one member in several tables is ONE record (occurrence per row), and a
  heading block ends at the next heading of the same rank
- the move engine's in-frame SCBF girder estimate reproduces the printed UC at unchanged geometry,
  and a column checked under a seismic combo takes the seismic gravity factors, not LC2
"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from calcgraph import calc_rows, move_impact  # noqa: E402
from calcgraph.ifc_ingest import norm_profile, profile_from  # noqa: E402
from calcgraph.matcher import _PROF  # noqa: E402


def test_every_aisc_shape_reads_back_whole():
    from synth.v2 import aisc
    bad = [n for n in aisc.shapes() if profile_from(n) != norm_profile(n)]
    assert not bad, f"profile parser truncates {len(bad)} AISC shape names, e.g. {bad[:5]}"
    hss = [n for n in aisc.shapes() if n.startswith("HSS") and "/" in n]
    assert hss and all(_PROF.search(n).group(0) == n for n in hss)


def _page(rows, sizes):
    """rows: [(y, [cells])]; sizes: font size per row (same order). A cell is ONE word, as
    calcpkg_ingest._rows builds them; a multi-word cell is a fixture the reader never sees."""
    assert all(" " not in c for _, cells in rows for c in cells), "cells are single words (calcpkg_ingest._rows)"
    lines, out = [], []
    for (y, cells), sz in zip(rows, sizes):
        r = [40.0, y, 500.0, y + 9]
        out.append({"cells": cells, "rect": r})
        lines.append({"text": "  ".join(cells), "size": sz, "rect": r})
    return {"page": 1, "sheet_id": "X1-1", "software": "RISA-3D", "title": "t", "height": 792.0,
            "rows": out, "lines": lines}


def test_one_record_per_subject_per_page():
    known = {f"G-{k}": f"G-{k}" for k in "ABCD"}
    rows = [(140 + 9 * k, [str(k + 1), f"G-{c}", "W36X150", "0.88"]) for k, c in enumerate("ABCD")]
    rows += [(300 + 9 * k, [str(k + 1), f"G-{c}", "F2.3", "0.88"]) for k, c in enumerate("ABC")]
    res = calc_rows.read_records([_page(rows, [6.4] * len(rows))], known)
    ids = {}
    for r in res["records"]:
        ids.setdefault(r["subject"], set()).add(r["id"])
    assert all(len(v) == 1 for v in ids.values()), ids
    assert len(res["records"]) == 7 and len({r["id"] for r in res["records"]}) == 4


def test_heading_block_stops_at_next_heading():
    known = {"SCBF-1": "FRAME:SCBF-1"}
    rows = [(100, ["Joint", "Level"]), (110, ["1", "L2"]), (377, ["SCBF-1", "Story", "Drift"]), (394, ["Story", "Ratio"]),
            (403, ["L2", "0.26"]), (453, ["Load", "Combinations"]), (470, ["Label", "Combination"]), (480, ["S1", "1.4D"])]
    res = calc_rows.read_records([_page(rows, [6.4, 6.4, 8.6, 6.4, 6.4, 8.6, 6.4, 6.4])], known)
    (rec,) = res["records"]
    assert rec["bbox"][3] < 453, rec["bbox"]


def test_scbf_girder_frame_estimate_is_identity_at_unchanged_geometry():
    g = move_impact.Graph({"elements": [{"id": "G1", "type": "girder", "size": "W36X150"}],
                           "records": [{"id": "C-BFG:G1", "kind": "scbf_girder", "uc": 0.882, "demand": 1775.8, "calc": "C5",
                                        "elements": ["G1"],
                                        "values": {"governs_combo": "F2.3", "Lb_ft": 10.0, "span_ft": 30.0, "phiMn_kft": 2112.8,
                                                   "phiPn_k": 1677.5,
                                                   "F2_3": {"Pv_unbalanced": 204.7, "M_gravity": 240.8, "Mu": 1775.8,
                                                            "P_axial": 139.3, "eq": "H1-1b"}}}],
                           "relations": [{"src": "G1", "dst": "C-BFG:G1", "kind": "designed-by"}]})
    x = move_impact._scbf_girder_frame_uc(g, "G1", {"mu_old": 320.6, "mu_new": 320.6, "span_old": 30.0, "span_new": 30.0})
    assert abs(x["uc_frame_new"] - 0.882) < 0.002
    longer = move_impact._scbf_girder_frame_uc(g, "G1", {"mu_old": 320.6, "mu_new": 377.7, "span_old": 30.0, "span_new": 33.0})
    assert longer["uc_frame_new"] > 0.95


def test_seismic_combo_column_takes_seismic_gravity_factors():
    g = move_impact.Graph({"elements": [], "relations": [],
                           "records": [{"id": "C-ELF:Y", "kind": "seismic", "calc": "C1", "elements": [],
                                        "values": {"Cs": 0.1667, "R": 6.0, "system": "Steel special concentrically braced frame"}}]})
    dv = [10.0, 10.0, 0.0]
    assert abs(move_impact._gravity_increment(g, dv, "LC2") - 28.0) < 1e-6
    assert abs(move_impact._gravity_increment(g, dv, "OM") - (1.2 + 0.2 * 1.0) * 10 - 5.0) < 0.01
