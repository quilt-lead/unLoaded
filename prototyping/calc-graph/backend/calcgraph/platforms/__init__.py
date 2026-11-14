"""Construction-platform adapters (SYNTHETIC) behind one interface.

    from calcgraph.platforms import get_adapters, load_design
    design = load_design()                      # data/synthetic_v2/design.json
    adapters = get_adapters(design)             # [ProcoreAdapter, AutodeskBuildAdapter, FormaAdapter]
    adapters[0].list_submittals()               # -> [NormalizedRecord]
    adapters[0].list_raw("submittals")          # -> Procore-shaped dicts
    estimate(impact, adapters, design)          # potential change order (change_order.py)
    construction_status("COL-2B", adapters)     # health-meter input (status.py)

By default no network, no credentials: every adapter reshapes the same deterministic synthetic
state (synthetic.py). get_adapters() wraps each in live.SourcedAdapter, which serves the live
connector (live/) when CALCGRAPH_PLATFORM_<PROCORE|ACC|FORMA>=live and it builds, else the mock
with the reason; every record carries fields["source"] / ["source_label"] (docs/platforms-real.md).
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
_ASOF_CACHE: dict[tuple, tuple[dict, ConstructionState]] = {}


def load_design(path: str | None = None) -> dict:
    with open(path or DEFAULT_DESIGN) as fh:
        return json.load(fh)


def get_state(design: dict, as_of=None) -> ConstructionState:
    """One ConstructionState per design dict (cached by identity). as_of (date / ISO string): the state
    PROJECTED to close of business that day (synthetic.build_state) - the one projection every as-of
    consumer reads (as_of.py); None = today's state."""
    if as_of is not None:
        from .synthetic import as_of_date, next_workday
        k = (id(design), next_workday(as_of_date(as_of)))   # same next workday = same state
        hit = _ASOF_CACHE.get(k)
        if hit is None or hit[0] is not design:
            if len(_ASOF_CACHE) > 48:
                _ASOF_CACHE.clear()
            hit = _ASOF_CACHE[k] = (design, build_state(design, as_of=as_of))
        return hit[1]
    hit = _STATE_CACHE.get(id(design))
    if hit is None or hit[0] is not design:
        hit = (design, build_state(design))
        _STATE_CACHE.clear()
        _STATE_CACHE[id(design)] = hit
    return hit[1]


def get_mock_adapters(design: dict, names: list[str] | None = None, as_of=None) -> list[PlatformAdapter]:
    """The bare synthetic adapters (no live selection, no source labels) - what get_adapters wraps.
    For code that builds its own live.SourcedAdapter (the contract checks)."""
    state = get_state(design, as_of)
    return [REGISTRY[n](state) for n in (names or list(REGISTRY))]


def get_adapters(design: dict, names: list[str] | None = None, as_of=None) -> list[PlatformAdapter]:
    """Every platform, each wrapped so config (CALCGRAPH_PLATFORM_<NAME>=live) can swap in its live
    connector; with no env set these are the synthetic mocks, labelled source=mock. The ONLY place
    adapters are built, so every consumer (routes, health meter, change order) sees the same source."""
    from .live import wrap_selected
    state = get_state(design, as_of)
    return [wrap_selected(m, state) for m in get_mock_adapters(design, names, as_of)]


def adapters_fingerprint() -> tuple:
    """What decides which adapters get_adapters() builds, besides the design: the per-platform mode
    selected by env and, when any platform is live, the stored app credentials / tokens. A cached
    adapter list is valid only while this is unchanged, so a login made after the server started
    (scripts/platform_auth.py writes data/secrets/) is picked up without a restart."""
    from .live import MODE_ENV, selected_mode
    modes = tuple((n, selected_mode(n)) for n in sorted(MODE_ENV))
    secrets: tuple = ()
    if any(m == "live" for _, m in modes):
        from .live.secrets import secrets_dir
        d = secrets_dir()
        if os.path.isdir(d):
            secrets = tuple(sorted((f, os.stat(os.path.join(d, f)).st_mtime_ns) for f in os.listdir(d)))
    return modes + secrets


def get_adapter(name: str, design: dict) -> PlatformAdapter:
    return get_adapters(design, [name])[0]


from .change_order import estimate  # noqa: E402
from .status import construction_status  # noqa: E402

__all__ = ["REGISTRY", "RECORD_TYPES", "STAGES", "NormalizedRecord", "PlatformAdapter", "ProcoreAdapter",
           "AutodeskBuildAdapter", "FormaAdapter", "ConstructionState", "build_state", "get_state", "get_adapters",
           "get_adapter", "get_mock_adapters", "adapters_fingerprint", "load_design", "estimate", "construction_status", "stage_rank"]
