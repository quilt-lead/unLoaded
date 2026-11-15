"""THE store root: where every runtime writer puts what it writes.

`CALCGRAPH_STORE` (default data/store under the repo) - read here and nowhere else. The revision store,
inbox state, calc revisions (re-runs and their undo / redo), the heat cache and the AI result cache all
take their paths from `store_path(...)`, so pointing CALCGRAPH_STORE at a copy (a smoke run, a parity
check) leaves the real store untouched. No imports beyond the standard library, so any module can use it.

scripts/check_platform_contracts.py (check I) fails on a backend module that builds a data/store,
data/cache or revisions path itself, or reads CALCGRAPH_STORE outside this file.
"""
from __future__ import annotations

import os

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
