"""CI tests (not run on the dev laptop: a hook blocks local test runners) for values the /v2 UI reads from ONE
source, so a consumer never re-derives them:

- design scenarios: every answer-key design scenario is in GET /scenarios (the UI picker's only list);
- real ETABS runs: every saved fixture validates, its agreement summary matches its own rows, and the
  finding is worded from the run's numbers (etabs_runs.finding);
- model revisions: split by design and ordered newest first at the source (move_api._model_revs_by_design);
- change order spec articles: each carries the registry links that bring it in (spec_via / spec_links);
- ETABS send: a move that changes nothing is refused.
"""
from __future__ import annotations

import json
import os
import sys

import pytest
from fastapi import HTTPException

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path[:0] = [os.path.join(ROOT, "backend"), ROOT]

from calcgraph import etabs_runs, move_api  # noqa: E402
from calcgraph.move_model import Move  # noqa: E402
from calcgraph.platforms.change_order import estimate  # noqa: E402


# ------------------------------------------------------------------ saved real ETABS runs
def test_every_run_fixture_validates_and_is_self_consistent():
    runs = etabs_runs.runs()
    assert runs, "data/fixtures/etabs_runs has no saved run"
    for r in runs:
        rows = r["members"]["rows"]
        agg = r["members"]["agreement"]
        assert sum(a["rows"] for a in agg) == len(rows)
        assert sum(a["flagged"] for a in agg) == sum(x["flag"] for x in rows)
        for a in agg:   # within + flagged-and-scored = scored
            assert a["within"] <= a["n"] <= a["rows"]
        assert etabs_runs.label(r).startswith(f"Real ETABS {r['etabs_version']} run, ")


def test_finding_is_worded_from_the_run_numbers():
    for r in etabs_runs.runs():
        f = etabs_runs.finding(r)
        m1 = r["modes"][0]
        assert f"{m1['period_s']:.3f} s" in f["headline"]
        over = [d for d in r["drift"] if d["etabs_ratio"] > 1.0]
        assert len(f["drift_ng"]) == len(over)
        for d in over:
            assert f"{d['etabs_ratio']:.3f}" in f["headline"]
            assert f"{d['design_in'] / d['allow_in']:.3f}" in f["headline"]


def test_orig_run_finds_torsion_and_smf_drift():
    r = next((x for x in etabs_runs.runs() if x["design"] == "ORIG"), None)
    assert r is not None, "the ORIG real ETABS run fixture is missing"
    f = etabs_runs.finding(r)
    assert f["mode1"]["shape"] == "torsional"
    assert {(d["system"], d["level"]) for d in f["drift_ng"]} == {("SMF", "L3")}


def test_validate_refuses_a_run_without_an_eastern_offset():
    r = dict(etabs_runs.runs()[0], run_at="2026-11-14T17:41:47")
    with pytest.raises(etabs_runs.RunFixtureError):
        etabs_runs.validate(r)


# ------------------------------------------------------------------ design scenarios in /scenarios
def test_every_design_scenario_is_listed():
    p = os.path.join(move_api.V2, "answer_key.json")
    if not os.path.exists(p):
        pytest.skip("no answer key (data/synthetic_v2 is generated)")
    key = json.load(open(p))
    listed = {s["id"]: s for s in move_api.scenarios()}
    for s in key.get("design_scenarios", []):
        assert listed[s["id"]]["kind"] == "design"
        assert listed[s["id"]]["column"] is None
    for s in key["scenarios"]:
        assert s["id"] in listed


# ------------------------------------------------------------------ model revisions split by design
class _FakeStore:
    def __init__(self, rows):
        self.rows = rows

    def revisions(self, pid):
        return self.rows


def test_model_revisions_newest_first_and_current_design_only(monkeypatch):
    rows = [
        {"id": 1, "parent_id": None, "kind": "model", "sha256": "old"},
        {"id": 2, "parent_id": 1, "kind": "model", "sha256": "a"},
        {"id": 3, "parent_id": None, "kind": "calcs", "sha256": "c"},
        {"id": 4, "parent_id": None, "kind": "model", "sha256": "new"},
        {"id": 5, "parent_id": 4, "kind": "model", "sha256": "b"},
        {"id": 6, "parent_id": 5, "kind": "model", "sha256": "new"},   # undo: restores the base
        {"id": 7, "parent_id": 2, "kind": "model", "sha256": "a"},
    ]
    monkeypatch.setattr(move_api, "_store", lambda: _FakeStore(rows))
    monkeypatch.setattr(move_api, "_v2_project", lambda st: 1)
    monkeypatch.setattr(move_api, "_find_base_rev", lambda st, pid: 4)
    cur, earlier, base = move_api._model_revs_by_design()
    assert base == 4
    assert [r["id"] for r in cur] == [6, 5, 4]
    assert [r["id"] for r in earlier] == [7, 2, 1]


# ------------------------------------------------------------------ change order spec links
def test_spec_articles_carry_their_links():
    imp = {"elements": ["COL-X"], "spec_articles": ["SPEC:A", "SPEC:B"],
           "spec_via": {"SPEC:A": ["MAT:A992"], "SPEC:B": ["FRAME:SMF-A", "MAT:A992"]},
           "spec_links": {"MAT:A992": {"elements": ["COL-X"], "articles": ["SPEC:A", "SPEC:B"]},
                          "FRAME:SMF-A": {"elements": ["COL-X"], "articles": ["SPEC:B"]}}}
    out = estimate(imp, [], {"elements": [], "records": [], "relations": []})
    by = {s["article"]: s for s in out["spec_articles"]}
    assert by["SPEC:A"]["via"] == ["MAT:A992"]
    assert by["SPEC:B"]["via"] == ["FRAME:SMF-A", "MAT:A992"]
    assert out["spec_links"]["MAT:A992"]["articles"] == ["SPEC:A", "SPEC:B"]


# ------------------------------------------------------------------ ETABS send needs a move
def test_etabs_send_refuses_a_move_that_changes_nothing():
    with pytest.raises(HTTPException) as e:
        move_api.etabs_send(Move(column="2B", dx=0, dy=0))
    assert e.value.status_code == 400
