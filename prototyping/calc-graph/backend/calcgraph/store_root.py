"""THE store root: where every runtime writer puts what it writes.

`CALCGRAPH_STORE` (default data/store under the repo) - read here and nowhere else. The revision store,
inbox state, calc revisions (re-runs and their undo / redo), the heat cache and the AI result cache all
take their paths from `store_path(...)`, so pointing CALCGRAPH_STORE at a copy (a smoke run, a parity
check) leaves the real store untouched. No imports beyond the standard library, so any module can use it.

scripts/check_platform_contracts.py (check I) fails on a backend module that builds a data/store,
data/cache or revisions path itself, or reads CALCGRAPH_STORE outside this file.

Three roots, three owners:
- SOURCE data, `SYNTH_V2_DIR` (data/synthetic_v2): the Harbor View documents. Written ONLY by the generator
  (synth/v2/generate.py, synth/v2/scenarios.py) inside `allow_source_writes()`; everything else reads it.
- the STORE, `store_path(...)` (CALCGRAPH_STORE, default data/store): runtime state the app writes.
- DERIVED outputs, `derived_path(...)` (CALCGRAPH_DERIVED, default data/eval, gitignored): what scripts
  compute FROM the source data - evaluation results (move_eval, registry_eval, the scorecard), the
  registry rebuilt from the documents, platforms.json, the ETABS .e2k export. `derived_for(source_dir)`
  is the per-source folder (data/eval/synthetic_v2 for the Harbor View building).

The source-write guard (`install_source_write_guard`, installed by `import calcgraph`) is a Python audit
hook: any write, create, rename, delete or truncate whose path is under a source data dir raises
PermissionError unless the caller is inside `allow_source_writes()`. Writes from C code (ifcopenshell,
PyMuPDF save) do not raise audit events, so scripts/evaluate_all.py and CI also fingerprint the source dir
before and after (`source_fingerprint`) and fail on any change.
"""
from __future__ import annotations

import contextlib
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEFAULT_STORE = os.path.join(ROOT, "data", "store")


def store_dir() -> str:
    """The store root (read at call time, so a caller that sets CALCGRAPH_STORE first is honoured)."""
    return os.environ.get("CALCGRAPH_STORE") or DEFAULT_STORE


def store_path(*parts: str) -> str:
    """A path under the store root."""
    return os.path.join(store_dir(), *parts)


def is_default_store() -> bool:
    return os.path.abspath(store_dir()) == DEFAULT_STORE


# ----------------------------------------------------------------------------- source data + derived outputs
SYNTH_V2_DIR = os.path.join(ROOT, "data", "synthetic_v2")   # the Harbor View building (generator-owned)
SOURCE_DIRS = (SYNTH_V2_DIR,)
DEFAULT_DERIVED = os.path.join(ROOT, "data", "eval")


def derived_dir() -> str:
    """The derived-outputs root (read at call time, like store_dir)."""
    return os.environ.get("CALCGRAPH_DERIVED") or DEFAULT_DERIVED


def derived_path(*parts: str) -> str:
    """A path under the derived-outputs root."""
    return os.path.join(derived_dir(), *parts)


def derived_for(source_dir: str, *parts: str) -> str:
    """Where outputs computed from `source_dir` go: <derived>/<basename of source_dir>/..."""
    return derived_path(os.path.basename(os.path.normpath(source_dir)), *parts)


_allow_depth = 0
_guard_installed = False
_source_real = tuple(os.path.realpath(d) for d in SOURCE_DIRS)
_WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC
# audit event -> indices of its path arguments that get written (CPython audit events table)
_WRITTEN_ARGS = {"os.rename": (0, 1),       # os.rename and os.replace: moving out of a source dir deletes there
                 "shutil.move": (0, 1), "shutil.copyfile": (1,), "shutil.copytree": (1,),
                 "os.symlink": (1,), "os.link": (1,),
                 "os.mkdir": (0,), "os.remove": (0,), "os.rmdir": (0,), "os.truncate": (0,), "os.utime": (0,),
                 "os.chmod": (0,), "os.chown": (0,), "shutil.rmtree": (0,)}


@contextlib.contextmanager
def allow_source_writes():
    """The generator's licence to write the source data dirs (process-wide while the block runs)."""
    global _allow_depth
    _allow_depth += 1
    try:
        yield
    finally:
        _allow_depth -= 1


def under_source(path) -> bool:
    """True when `path` (str / bytes / PathLike; an int fd is never) is a source data dir or inside one."""
    if path is None or isinstance(path, int):
        return False
    try:
        p = os.path.realpath(os.fsdecode(os.fspath(path)))
    except (TypeError, ValueError):
        return False
    return any(p == d or p.startswith(d + os.sep) for d in _source_real)


def _guard(event: str, args: tuple) -> None:
    if _allow_depth:
        return
    if event == "open":
        path, mode, flags = args
        writes = (any(c in mode for c in "wax+") if isinstance(mode, str)
                  else bool(isinstance(flags, int) and flags & _WRITE_FLAGS))
        paths = (path,) if writes else ()
    elif event in _WRITTEN_ARGS:
        paths = tuple(args[i] for i in _WRITTEN_ARGS[event] if i < len(args))
    else:
        return
    for p in paths:
        if under_source(p):
            raise PermissionError(
                f"refusing to write {os.fsdecode(os.fspath(p))!r}: it is under the source data dir. Only the "
                f"generator (synth/v2, inside store_root.allow_source_writes()) writes there; put derived / eval "
                f"output under store_root.derived_path(...) and runtime state under store_root.store_path(...)")


def install_source_write_guard() -> None:
    """Install the audit hook once per process (audit hooks cannot be removed)."""
    global _guard_installed
    if not _guard_installed:
        sys.addaudithook(_guard)
        _guard_installed = True


def source_fingerprint(source_dir: str = SYNTH_V2_DIR) -> dict[str, tuple[int, int]]:
    """{relative path: (size, mtime_ns)} of every file under `source_dir` (empty when it is absent); two
    fingerprints differ when anything was written, created, replaced or deleted in between."""
    out: dict[str, tuple[int, int]] = {}
    for dp, _dns, fns in os.walk(source_dir):
        for fn in fns:
            full = os.path.join(dp, fn)
            try:
                st = os.stat(full)
            except FileNotFoundError:
                continue
            out[os.path.relpath(full, source_dir)] = (st.st_size, st.st_mtime_ns)
    return out


def fingerprint_diff(before: dict, after: dict) -> list[str]:
    """Human-readable changes between two source fingerprints."""
    return ([f"added {k}" for k in sorted(after.keys() - before.keys())]
            + [f"removed {k}" for k in sorted(before.keys() - after.keys())]
            + [f"changed {k}" for k in sorted(before.keys() & after.keys()) if before[k] != after[k]])
