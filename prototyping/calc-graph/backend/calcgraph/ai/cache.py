"""Content-hash cache for AI step results.

Keys:
* ``inputs_key`` = sha256 of canonical JSON {task, task version, instructions sha,
  output JSON schema, inputs (images by sha256, never by path)}. Provider-independent,
  so a replay fixture recorded from any provider replays under it.
* ``cache_key``  = sha256 of {inputs_key, provider, model_id}. One result per model.

Entries live at ``<root>/<task>/<cache_key>.json``. Default root is under
``data/store/`` (already gitignored); override with ``CALCGRAPH_AI_CACHE``. A cached
entry is re-validated against the current schema on read; a stale one is a miss.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def sha256_json(obj: Any) -> str:
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


def default_cache_root() -> Path:
    env = os.environ.get("CALCGRAPH_AI_CACHE")
    return Path(env) if env else REPO_ROOT / "data" / "store" / "ai_cache"


class ResultCache:
    def __init__(self, root: Path | str | None = None):
        self.root = Path(root) if root is not None else default_cache_root()

    def _path(self, task: str, cache_key: str) -> Path:
        return self.root / task / f"{cache_key}.json"

    def get(self, task: str, cache_key: str) -> dict | None:
        p = self._path(task, cache_key)
        if not p.exists():
            return None
        return json.loads(p.read_text("utf-8"))

    def put(self, task: str, cache_key: str, entry: dict) -> Path:
        p = self._path(task, cache_key)
        p.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write: concurrent runs never see a half-written entry.
        fd, tmp = tempfile.mkstemp(dir=p.parent, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(canonical_json(entry))
        os.replace(tmp, p)
        return p
