"""CI tests (not run on the dev laptop - a hook blocks local test runners).

They run the production pipeline on the synthetic package and pin the floor the
evaluation reached on 2026-11-14 so a regression fails CI.
"""
import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


@pytest.fixture(scope="session")
def report(tmp_path_factory):
    data = tmp_path_factory.mktemp("synthetic")
    subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "evaluate.py"), "--data", str(data), "--regen"],
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


def test_revisions(report):
    rv = report["revisions"]
    assert rv["diff_removed"]["exact"] and rv["diff_changed"]["exact"]
    assert rv["decisions_carried_forward"] == {"confirm": "confirmed", "reject": "rejected"}


def test_generator_byte_stable(tmp_path):
    from synth.generate import generate, _digest
    generate(str(tmp_path / "a"), 7)
    generate(str(tmp_path / "b"), 7)
    assert _digest(str(tmp_path / "a")) == _digest(str(tmp_path / "b"))
