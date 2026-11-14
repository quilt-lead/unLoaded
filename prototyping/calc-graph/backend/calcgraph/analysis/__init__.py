"""Analysis-software adapters (ETABS first; RISA and RAM are stubs).

    from calcgraph.analysis import get_adapter
    etabs = get_adapter("etabs")            # reads data/synthetic_v2/design.json
    objs = etabs.model_objects()            # [AnalysisObject]
    occ = etabs.occurrences()               # [{ref, doc, kind, object_type, label, story, how}]
    etabs.export_model("model.e2k")         # ETABS text model (not opened by ETABS)
    job = etabs.send_change(None, {"moved": {"2B": [5, 0]}})   # MOCK
    res = etabs.pull_results(job)           # calc-graph PyNite re-run in ETABS result shapes
"""
from __future__ import annotations

from .base import AnalysisAdapter, AnalysisObject, OBJECT_KINDS

ADAPTERS = ("etabs", "risa", "ram")


def get_adapter(name: str, design=None) -> AnalysisAdapter:
    """Adapter by name ("etabs" | "risa" | "ram"); `design` = design.json dict/path or None."""
    key = (name or "").strip().lower()
    if key == "etabs":
        from .etabs import EtabsAdapter
        return EtabsAdapter(design)
    if key == "risa":
        from .risa import RisaAdapter
        return RisaAdapter(design)
    if key == "ram":
        from .ram import RamAdapter
        return RamAdapter(design)
    raise ValueError(f"unknown analysis adapter {name!r} (known: {', '.join(ADAPTERS)})")


__all__ = ["get_adapter", "AnalysisAdapter", "AnalysisObject", "OBJECT_KINDS", "ADAPTERS"]
