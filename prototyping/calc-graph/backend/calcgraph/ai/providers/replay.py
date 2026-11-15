"""Deterministic replay provider: answers from recorded fixtures keyed by ``inputs_key``.

Never calls a network. A missing fixture raises ``ReplayMiss`` naming the key and the
path to write, so a fixture can be authored by hand (or recorded from an approved real
run) and the pipeline replays it byte-for-byte forever after.

Fixture file: ``<root>/<task>/<inputs_key>.json`` =
``{"output": {...}, "model_id": "<model that produced it, or 'hand-authored'>"}``.
Default root ``<store>/ai_fixtures`` (store_root.py, CALCGRAPH_STORE; gitignored); override ``CALCGRAPH_AI_FIXTURES``.
Fixtures derived from copyrighted documents must stay in gitignored dirs.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Mapping

from ...store_root import store_path
from ..cache import canonical_json
from ..types import Usage
from .base import Provider, ProviderRequest, ProviderResponse


class ReplayMiss(LookupError):
    pass


def default_fixture_root() -> Path:
    env = os.environ.get("CALCGRAPH_AI_FIXTURES")
    return Path(env) if env else Path(store_path("ai_fixtures"))   # THE store root (store_root.py)


class ReplayProvider(Provider):
    name = "replay"
    model_id = "replay"

    def __init__(self, root: Path | str | None = None, fixtures: Mapping[str, dict] | None = None):
        self.root = Path(root) if root is not None else default_fixture_root()
        self.fixtures = dict(fixtures or {})  # inputs_key -> fixture, checked before disk
        self.calls = 0

    def fixture_path(self, task: str, inputs_key: str) -> Path:
        return self.root / task / f"{inputs_key}.json"

    def estimate(self, req: ProviderRequest) -> Usage:
        return Usage(input_tokens=0, output_tokens=0, cost_usd=0.0)

    def complete(self, req: ProviderRequest) -> ProviderResponse:
        self.calls += 1
        fx = self.fixtures.get(req.inputs_key)
        if fx is None:
            p = self.fixture_path(req.task.name, req.inputs_key)
            if not p.exists():
                raise ReplayMiss(f"no replay fixture for task {req.task.name!r} inputs_key "
                                 f"{req.inputs_key}; write {p}")
            fx = json.loads(p.read_text("utf-8"))
        if "output" not in fx:
            raise ReplayMiss(f"fixture for {req.inputs_key} has no 'output'")
        recorded = str(fx.get("model_id") or "hand-authored")
        return ProviderResponse(raw_json=canonical_json(fx["output"]), usage=Usage(),
                                model_id=f"replay:{recorded}")
