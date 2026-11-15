"""Disk cache for the v2 heat view (GET /api/v2/health): move_impact.heat() re-runs ~80 probe impacts
(4 probes x every column), tens of seconds cold, so a server restart must not recompute it.

The result is stored under <store>/cache/heat/<key>.json (store_root.py; gitignored), where key is a sha256 over EVERY
input heat() reads - traced, not guessed:

  design      the bytes of data/synthetic_v2/design.json (heat(exp) reads elements, relations, records,
              occurrences from it; nothing else from disk except the AISC table below)
  probe       the probe distance
  platform    construction_status(column) for every column: the only thing heat() asks the platform
              adapters (health_of -> platform_status(column)); hashing the answers covers mock vs live,
              a login, and any change in live records
  code        move_impact.py (the engine), synth/v2/aisc.py + its CSV (the section table _shape and
              _phi_mn read), and the PyNite / NetworkX versions it solves with

so a restart serves the stored result instantly and only a real input change recomputes. Writes are
atomic (tmp + os.replace); one computation per key runs at a time and concurrent callers wait for it.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from datetime import datetime
from importlib import metadata
from zoneinfo import ZoneInfo

from .store_root import store_path

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
def _cache_dir() -> str:
    """cache/heat under THE store root (store_root.py: CALCGRAPH_STORE)."""
    return store_path("cache", "heat")
_HERE = os.path.dirname(__file__)
CODE_FILES = (os.path.join(_HERE, "move_impact.py"),
              os.path.join(ROOT, "synth", "v2", "aisc.py"),
              os.path.join(ROOT, "synth", "v2", "data", "aisc_v16_subset.csv"))
_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()


def _sha_file(p: str) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _version(dist: str) -> str:
    try:
        return metadata.version(dist)
    except metadata.PackageNotFoundError:
        return "?"


def inputs(design_sha: str, design: dict, probe: float, platform_status) -> dict:
    """The fingerprint of every input (see module doc), each as a short hash."""
    cols = sorted(e["id"] for e in design["elements"] if e["type"] == "column")
    if platform_status is None:
        plat = "none"
    else:
        h = hashlib.sha256()
        for c in cols:
            h.update(json.dumps([c, platform_status(c)], sort_keys=True, default=str).encode())
        plat = h.hexdigest()
    code = hashlib.sha256()
    for p in CODE_FILES:
        code.update(os.path.basename(p).encode() + _sha_file(p).encode())
    code.update(f"PyNiteFEA={_version('PyNiteFEA')};networkx={_version('networkx')}".encode())
    return {"design": design_sha[:16], "probe": float(probe), "platform": plat[:16], "code": code.hexdigest()[:16]}


def key_of(inp: dict) -> str:
    return hashlib.sha256(json.dumps(inp, sort_keys=True).encode()).hexdigest()[:24]


def _path(key: str) -> str:
    return os.path.join(_cache_dir(), f"{key}.json")


def load(key: str) -> dict | None:
    try:
        with open(_path(key)) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def get_or_compute(inp: dict, compute) -> tuple[dict, str, dict]:
    """(heat, "hit" | "computed", meta). `compute()` returns the JSON-safe heat dict."""
    key = key_of(inp)
    doc = load(key)
    if doc is not None:
        return doc["heat"], "hit", doc["meta"]
    with _LOCKS_GUARD:
        lock = _LOCKS.setdefault(key, threading.Lock())
    with lock:
        doc = load(key)            # another caller computed it while we waited
        if doc is not None:
            return doc["heat"], "hit", doc["meta"]
        t = time.time()
        heat = compute()
        meta = {"key": key, "inputs": inp, "seconds": round(time.time() - t, 1),
                "computed_at": datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M:%S ET")}
        os.makedirs(_cache_dir(), exist_ok=True)
        tmp = _path(key) + f".tmp{os.getpid()}.{threading.get_ident()}"
        with open(tmp, "w") as fh:
            json.dump({"meta": meta, "heat": heat}, fh)
        os.replace(tmp, _path(key))
        return heat, "computed", meta
