"""Every source data file the code reads has a declared producer that evaluate_all runs on a fresh checkout.

data/synthetic_v2 is gitignored. CI (2ef4e4e, run 43668049528) failed evaluate_all with a FileNotFoundError
traceback on data/synthetic_v2/answer_key.json: evaluate_all generated the source data with synth.v2.generate
only, while answer_key.json comes from synth.v2.scenarios, so every fresh checkout lacked it and only dev
machines (where someone had run scenarios by hand) passed. Now calcgraph.store_root.SOURCE_PRODUCERS declares
every source artifact and the command that writes it, evaluate_all runs each producer with a missing
artifact, and these tests fail on a read of an undeclared source file or a producer evaluate_all skips.
(CI only - not run on the dev Mac.)"""
from __future__ import annotations

import ast
import importlib.util
import os
import re
import subprocess
from types import SimpleNamespace

import pytest

from calcgraph import store_root as sr

ROOT = sr.ROOT
SCANNED = ("backend/calcgraph", "scripts", "synth")
SOURCE_DIR_NAMES = {"V2", "V2_DIR", "SYNTH_V2_DIR"}   # the names the code binds data/synthetic_v2 to
LITERAL = re.compile(r"data/synthetic_v2/([A-Za-z0-9_.\-]+)")
# literals naming a source path that is gone on purpose (documentation of a retirement, not a read)
NOT_READS = {"revisions"}   # recalc.py's one-time data/synthetic_v2/revisions migration, deleted in 3a58f59
DECLARED = {n for _mod, names in sr.SOURCE_PRODUCERS for n in names}


def _py_files():
    for top in SCANNED:
        for dp, dns, fns in os.walk(os.path.join(ROOT, top)):
            dns[:] = [d for d in dns if d not in ("__pycache__", "node_modules", "generated")]
            for fn in fns:
                if fn.endswith(".py"):
                    yield os.path.join(dp, fn)


def _is_source_dir(node: ast.AST) -> bool:
    return ((isinstance(node, ast.Name) and node.id in SOURCE_DIR_NAMES)
            or (isinstance(node, ast.Attribute) and node.attr in SOURCE_DIR_NAMES))


def _referenced_source_names() -> dict[str, list[str]]:
    """{first path component under data/synthetic_v2: [file:line, ...]} for every literal the code names."""
    out: dict[str, list[str]] = {}
    for path in _py_files():
        rel = os.path.relpath(path, ROOT)
        tree = ast.parse(open(path, encoding="utf-8").read(), filename=rel)
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Call) and node.args:
                f = node.func
                fname = f.attr if isinstance(f, ast.Attribute) else f.id if isinstance(f, ast.Name) else ""
                first = node.args[1] if fname == "join" and len(node.args) > 1 and _is_source_dir(node.args[0]) else (
                    node.args[0] if fname == "source_file" else None)
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    names.append(first.value.split("/", 1)[0])
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                names += LITERAL.findall(node.value)
            for n in names:
                n = n.rstrip(".")
                if n and n not in NOT_READS:
                    out.setdefault(n, []).append(f"{rel}:{getattr(node, 'lineno', '?')}")
    return out


def test_every_source_file_the_code_names_has_a_declared_producer():
    refs = _referenced_source_names()
    assert {"design.json", "answer_key.json"} <= refs.keys(), "the scan no longer sees the known readers"
    undeclared = {n: where[:3] for n, where in refs.items() if n not in DECLARED}
    assert not undeclared, (
        "source files read but not in calcgraph.store_root.SOURCE_PRODUCERS (evaluate_all would never generate "
        f"them on a fresh checkout): {undeclared} - declare the producer, or write it under derived_path")


def test_every_producer_is_a_real_module():
    for mod, _names in sr.SOURCE_PRODUCERS:
        assert importlib.util.find_spec(mod) is not None, mod


def test_a_missing_source_file_names_its_producer(tmp_path):
    with pytest.raises(sr.SourceDataMissing, match=r"source data not generated: .*answer_key\.json is missing - "
                                                   r"run `uv run python -m synth\.v2\.scenarios`"):
        sr.source_file("answer_key.json", source_dir=str(tmp_path))
    with pytest.raises(FileNotFoundError):   # existing `except FileNotFoundError` callers still catch it
        sr.source_file("scenarios", "S01.json", source_dir=str(tmp_path))
    (tmp_path / "design.json").write_text("{}")
    assert sr.source_file("design.json", source_dir=str(tmp_path)) == str(tmp_path / "design.json")
    assert "design.json" not in sr.missing_sources(str(tmp_path))
    assert sr.source_producer("scenarios/ORIG.e2k") == "synth.v2.scenarios"


def _evaluate_all():
    spec = importlib.util.spec_from_file_location("evaluate_all_under_test", os.path.join(ROOT, "scripts", "evaluate_all.py"))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_evaluate_all_runs_every_producer_on_an_empty_source_dir(tmp_path, monkeypatch):
    ea = _evaluate_all()
    calls: list[list[str]] = []
    monkeypatch.setattr(ea, "V2", str(tmp_path))
    monkeypatch.setattr(ea, "run", lambda cmd, timeout=1800: calls.append(cmd) or subprocess.CompletedProcess(cmd, 0, "", ""))
    err = ea._ensure_v2(SimpleNamespace(regen_v2=False))
    assert [c[2] for c in calls] == [mod for mod, _ in sr.SOURCE_PRODUCERS]
    # the stub wrote nothing, so the source data is still incomplete and evaluate_all says what to run
    assert err and "source data not generated" in err and "synth.v2.scenarios" in err


def test_evaluate_all_reruns_only_the_producer_whose_artifact_is_missing(tmp_path, monkeypatch):
    ea = _evaluate_all()
    for mod, names in sr.SOURCE_PRODUCERS:
        for n in names:
            (tmp_path / n).write_text("{}")
    os.remove(tmp_path / "answer_key.json")
    calls: list[list[str]] = []
    monkeypatch.setattr(ea, "V2", str(tmp_path))
    monkeypatch.setattr(ea, "run", lambda cmd, timeout=1800: calls.append(cmd) or subprocess.CompletedProcess(cmd, 1, "", "boom"))
    err = ea._ensure_v2(SimpleNamespace(regen_v2=False))
    assert [c[2] for c in calls] == ["synth.v2.scenarios"]
    assert err and err.startswith("source data not generated: synth.v2.scenarios exit 1")
