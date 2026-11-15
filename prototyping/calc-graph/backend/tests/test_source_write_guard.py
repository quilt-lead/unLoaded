"""The source data dir (data/synthetic_v2) is generator-only: calcgraph.store_root's audit hook refuses
every other write, and derived / runtime outputs resolve outside it. (CI only - not run on the dev Mac.)
Every probe aims at a name that does not exist, so even a broken guard cannot move or delete real source
files; a blocked call raises before the syscall, and the allowed-path probe hits a missing subfolder so the
OS answers FileNotFoundError."""
import os
import shutil
import tempfile

import pytest

import calcgraph  # noqa: F401 - importing the package installs the guard
from calcgraph import store_root as sr
from calcgraph.analysis import etabs

SRC = sr.SYNTH_V2_DIR
PROBE = os.path.join(SRC, ".guard-probe")


def test_importing_calcgraph_installs_the_guard():
    assert sr._guard_installed


@pytest.mark.parametrize("write", [
    lambda: open(PROBE, "w"),
    lambda: open(PROBE, "ab"),
    lambda: open(PROBE, "r+"),
    lambda: os.open(PROBE, os.O_CREAT | os.O_WRONLY),
    lambda: tempfile.mkstemp(dir=SRC),
    lambda: os.makedirs(os.path.join(SRC, ".guard-probe-dir", "x")),
    lambda: os.replace(os.path.join(SRC, ".no-such-file"), os.path.join(tempfile.gettempdir(), "x.json")),
    lambda: os.replace(os.path.join(tempfile.gettempdir(), "x.json"), PROBE),
    lambda: os.remove(PROBE),
    lambda: shutil.copyfile(__file__, PROBE),
    lambda: shutil.rmtree(os.path.join(SRC, ".no-such-dir")),
], ids=["open-w", "open-ab", "open-r+", "os.open-creat", "mkstemp", "makedirs", "replace-out", "replace-in",
        "remove", "copyfile", "rmtree"])
def test_any_write_under_the_source_dir_is_refused(write):
    with pytest.raises(PermissionError, match="source data dir"):
        write()


def test_reads_are_not_refused(tmp_path):
    # opening for read reaches the OS (FileNotFoundError when absent), never the guard
    try:
        open(os.path.join(SRC, "design.json")).close()
    except FileNotFoundError:
        pass
    p = tmp_path / "elsewhere.json"
    p.write_text("{}")   # writes outside the source dir are untouched
    assert p.read_text() == "{}"


def test_the_generator_licence_lets_writes_reach_the_os():
    missing = os.path.join(SRC, ".no-such-dir", "x.json")
    with sr.allow_source_writes():
        with pytest.raises(FileNotFoundError):
            open(missing, "w")
    with pytest.raises(PermissionError):   # the licence ends with the block
        open(missing, "w")


def test_derived_and_runtime_outputs_resolve_outside_the_source_dir(monkeypatch, tmp_path):
    for name in ("move_eval.json", "move_eval_ingested.json", "registry_eval.json", "registry_ingested.json",
                 "platforms.json", "model.e2k"):
        assert not sr.under_source(sr.derived_for(SRC, name)), name
    assert not sr.under_source(sr.derived_path("scorecard.json"))
    assert not sr.under_source(etabs.jobs_dir())
    monkeypatch.setenv("CALCGRAPH_DERIVED", str(tmp_path / "d"))
    assert sr.derived_for(SRC, "move_eval.json") == str(tmp_path / "d" / "synthetic_v2" / "move_eval.json")


def test_fingerprint_sees_every_kind_of_change(tmp_path):
    (tmp_path / "a.json").write_text("1")
    (tmp_path / "b.json").write_text("2")
    before = sr.source_fingerprint(str(tmp_path))
    (tmp_path / "a.json").write_text("11")
    (tmp_path / "b.json").unlink()
    (tmp_path / "c.json").write_text("3")
    diff = sr.fingerprint_diff(before, sr.source_fingerprint(str(tmp_path)))
    assert diff == ["added c.json", "removed b.json", "changed a.json"]
