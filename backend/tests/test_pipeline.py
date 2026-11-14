"""CI tests (not run on the dev laptop - a hook blocks local test runners).

They run the production pipeline on the synthetic package and pin the floor the
evaluation reached on 2026-11-14 so a regression fails CI. The element graphs come from the
TypeScript packages the UI runs (scripts/build_graph.mjs -> packages/ifc-parser +
packages/element-graph), so Node >= 22.18 and the repo's `npm ci` are needed.
"""
import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))  # backend/


@pytest.fixture(scope="session")
def report(tmp_path_factory):
    data = tmp_path_factory.mktemp("synthetic")
    subprocess.run([sys.executable, "-m", "synth.generate", "--out", str(data)], check=True, cwd=ROOT)
    subprocess.run(["node", os.path.join(ROOT, "scripts", "build_graph.mjs"),
                    str(data / "model_rev1.ifc"), str(data / "model_rev1.graph.json"),
                    str(data / "model_rev2.ifc"), str(data / "model_rev2.graph.json")], check=True, cwd=ROOT)
    subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "evaluate.py"), "--data", str(data)],
                   check=True, cwd=ROOT)
    return json.load(open(os.path.join(ROOT, "data", "eval", "latest.json")))


def test_segmentation_exact(report):
    assert report["segmentation"]["exact"] == report["segmentation"]["truth_calcs"]


def test_design_mapping_floor(report):
    o = report["design_mapping"]["overall"]
    assert o["precision"] >= 0.93 and o["recall"] >= 0.99


def test_mark_tiers_are_precise(report):
    for tier in ("exact", "range", "loose", "family", "type"):
        if tier in report["design_mapping"]["per_tier"]:
            assert report["design_mapping"]["per_tier"][tier]["precision"] == 1.0, tier


def test_load_path_exact(report):
    assert report["load_path_rev1"]["precision"] == 1.0 and report["load_path_rev1"]["recall"] == 1.0
    assert report["revisions"]["load_path_rev2"]["recall"] == 1.0


def test_impact_remove_c8(report):
    im = report["impact_remove_C8"]
    assert (im["removed"], im["hit"]) == (15, 36)
    assert im["stale_calcs"] == ["K03", "K04", "K05", "K07", "K08", "K09", "K10", "K12"]


def test_revisions(report):
    rv = report["revisions"]
    assert rv["diff_removed"]["exact"] and rv["diff_changed"]["exact"]
    assert rv["decisions_carried_forward"] == {"confirm": "confirmed", "reject": "rejected"}


def test_generator_byte_stable(tmp_path):
    from synth.generate import generate, _digest
    generate(str(tmp_path / "a"), 7)
    generate(str(tmp_path / "b"), 7)
    assert _digest(str(tmp_path / "a")) == _digest(str(tmp_path / "b"))
