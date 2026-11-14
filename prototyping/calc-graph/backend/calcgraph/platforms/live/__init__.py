"""LIVE construction-platform adapters (Procore, Autodesk Build / ACC, Autodesk Forma) behind the existing
PlatformAdapter interface, config-selected, falling back to the synthetic mock, every record source-labelled.

Selection (per platform, default "mock" - nothing touches the network unless asked):

    CALCGRAPH_PLATFORM_PROCORE=live      Procore Developer Sandbox (PROCORE_ENV=sandbox | monthly)
    CALCGRAPH_PLATFORM_ACC=live          Autodesk Build (ACC) project via APS
    CALCGRAPH_PLATFORM_FORMA=live        Autodesk Forma proposals/elements via APS (beta API)

    from calcgraph.platforms.live import wrap_selected
    adapters = [wrap_selected(mock, state) for mock in get_adapters(design)]   # the one registration edit

`SourcedAdapter` serves the live adapter when selected AND it builds; on any failure (not signed in, ids
not configured, HTTP error, rate limit exhausted) it serves the mock and says why. Every NormalizedRecord
then carries:

    fields["source"]        "live" | "mock"
    fields["source_label"]  e.g. "Procore sandbox (live)" or "synthetic mock (live unavailable: not signed in ...)"

and describe() reports {"synthetic", "source", "fallback_reason", "selected"}.
"""
from __future__ import annotations

import logging
import os

from ..base import NormalizedRecord, PlatformAdapter
from .transport import Recorded

log = logging.getLogger("calcgraph.platforms.live")
MODE_ENV = {"procore": "CALCGRAPH_PLATFORM_PROCORE", "autodesk_build": "CALCGRAPH_PLATFORM_ACC",
            "forma": "CALCGRAPH_PLATFORM_FORMA"}


def selected_mode(name: str) -> str:
    v = (os.environ.get(MODE_ENV.get(name, ""), "") or "mock").strip().lower()
    return "live" if v == "live" else "mock"


def live_class(name: str):
    if name == "procore":
        from .procore_live import ProcoreLiveAdapter
        return ProcoreLiveAdapter
    if name == "autodesk_build":
        from .acc_live import AccLiveAdapter
        return AccLiveAdapter
    if name == "forma":
        from .forma_live import FormaLiveAdapter
        return FormaLiveAdapter
    raise KeyError(name)


class SourcedAdapter(PlatformAdapter):
    """One platform: live when selected and reachable, else the mock. Same surface as any adapter."""

    def __init__(self, mock: PlatformAdapter, state=None, mode: str | None = None, recorded: Recorded | None = None,
                 live_config: dict | None = None):
        super().__init__()
        self.mock = mock
        self.name = mock.name
        self.selected = mode or selected_mode(mock.name)
        self._state = state if state is not None else getattr(mock, "state", None)
        self._recorded = recorded
        self._live_config = live_config
        self.live: PlatformAdapter | None = None
        self.source = "mock"
        self.fallback_reason: str | None = None if self.selected == "live" else "mock selected (default)"
        self.label = mock.label
        self.capabilities = mock.capabilities
        self.doc_urls = mock.doc_urls

    # status.py / change_order.py read `.state` (the synthetic construction state) when present: a live
    # source has none, so the engine falls back to the records themselves.
    @property
    def state(self):
        self._records()
        return self._state if self.source == "mock" else None

    def _build(self) -> dict[str, list[NormalizedRecord]]:
        if self.selected == "live":
            try:
                self.live = live_class(self.name)(self._state, recorded=self._recorded, config=self._live_config)
                built = self.live._build()
                self.live._cache = built
                self.source, self.fallback_reason = "live", None
                self.label, self.capabilities, self.doc_urls = self.live.label, self.live.capabilities, self.live.doc_urls
                return self._label(built, "live", f"{self.live.label}")
            except Exception as e:   # noqa: BLE001 - any live failure falls back, with the reason shown
                from .secrets import redact
                self.fallback_reason = f"live unavailable: {type(e).__name__}: {redact(e)[:300]}"
                log.warning("%s: %s; serving the synthetic mock", self.name, self.fallback_reason)
        self.source = "mock"
        self.label, self.capabilities, self.doc_urls = self.mock.label, self.mock.capabilities, self.mock.doc_urls
        return self._label(self.mock._records(), "mock", f"synthetic mock ({self.fallback_reason})")

    @staticmethod
    def _label(recs: dict[str, list[NormalizedRecord]], source: str, label: str) -> dict[str, list[NormalizedRecord]]:
        for rs in recs.values():
            for r in rs:
                r.fields["source"] = source
                r.fields["source_label"] = label
        return recs

    def deep_link(self, record_type: str, id: str) -> str:
        self._records()
        return (self.live if self.source == "live" else self.mock).deep_link(record_type, id)

    def describe(self) -> dict:
        self._records()
        d = (self.live if self.source == "live" else self.mock).describe()
        d.update(name=self.name, synthetic=self.source == "mock", source=self.source, selected=self.selected,
                 fallback_reason=self.fallback_reason, label=self.label)
        return d


def wrap_selected(mock: PlatformAdapter, state=None) -> PlatformAdapter:
    """Registration hook: wrap a synthetic adapter so config can swap in its live counterpart."""
    return SourcedAdapter(mock, state)


__all__ = ["SourcedAdapter", "wrap_selected", "selected_mode", "live_class", "MODE_ENV"]
