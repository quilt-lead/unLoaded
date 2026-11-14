"""Construction-platform adapters (SYNTHETIC) behind one interface.

    from calcgraph.platforms import get_adapters, load_design
    design = load_design()                      # data/synthetic_v2/design.json
    adapters = get_adapters(design)             # [ProcoreAdapter, AutodeskBuildAdapter, FormaAdapter]
    adapters[0].list_submittals()               # -> [NormalizedRecord]
    adapters[0].list_raw("submittals")          # -> Procore-shaped dicts
    estimate(impact, adapters, design)          # potential change order (change_order.py)
    construction_status("COL-2B", adapters)     # health-meter input (status.py)

No network, no credentials: every adapter reshapes the same deterministic synthetic state
(synthetic.py). A live connector would subclass PlatformAdapter and register here.
"""
from __future__ import annotations

import json
import os

from .autodesk_build import AutodeskBuildAdapter
from .base import RECORD_TYPES, STAGES, NormalizedRecord, PlatformAdapter, stage_rank
from .forma import FormaAdapter
from .procore import ProcoreAdapter
from .synthetic import ConstructionState, build_state

REGISTRY: dict[str, type[PlatformAdapter]] = {
    ProcoreAdapter.name: ProcoreAdapter,
    AutodeskBuildAdapter.name: AutodeskBuildAdapter,
    FormaAdapter.name: FormaAdapter,
}
DEFAULT_DESIGN = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "synthetic_v2", "design.json"))
_STATE_CACHE: dict[int, tuple[dict, ConstructionState]] = {}


def load_design(path: str | None = None) -> dict:
    with open(path or DEFAULT_DESIGN) as fh:
        return json.load(fh)


def get_state(design: dict) -> ConstructionState:
    """One ConstructionState per design dict (cached by identity)."""
    hit = _STATE_CACHE.get(id(design))
    if hit is None or hit[0] is not design:
        hit = (design, build_state(design))
        _STATE_CACHE.clear()
        _STATE_CACHE[id(design)] = hit
    return hit[1]


def get_adapters(design: dict, names: list[str] | None = None) -> list[PlatformAdapter]:
    state = get_state(design)
    return [REGISTRY[n](state) for n in (names or list(REGISTRY))]


def get_adapter(name: str, design: dict) -> PlatformAdapter:
    return get_adapters(design, [name])[0]


from .change_order import estimate  # noqa: E402
from .status import construction_status  # noqa: E402

__all__ = ["REGISTRY", "RECORD_TYPES", "STAGES", "NormalizedRecord", "PlatformAdapter", "ProcoreAdapter",
           "AutodeskBuildAdapter", "FormaAdapter", "ConstructionState", "build_state", "get_state", "get_adapters",
           "get_adapter", "load_design", "estimate", "construction_status", "stage_rank"]
