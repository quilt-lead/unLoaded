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

import os

from .base import OBJECT_KINDS, SOURCE_DETAIL, AnalysisAdapter, AnalysisObject, ResultSource, tag_source

ADAPTERS = ("etabs", "bhom_etabs", "risa", "ram")
# which adapter answers "etabs": the mock (default) or the real one through the Windows bridge
# (bhom_etabs - BHoM / CSI OAPI routes, with its own mock fallback). Select with
# CALCGRAPH_ETABS_ADAPTER=bhom_etabs once ETABS is installed on the desk.
ETABS_ADAPTER_ENV = "CALCGRAPH_ETABS_ADAPTER"


def etabs_adapter_name() -> str:
    v = (os.environ.get(ETABS_ADAPTER_ENV) or "etabs").strip().lower()
    return v if v in ("etabs", "bhom_etabs") else "etabs"


def get_adapter(name: str, design=None) -> AnalysisAdapter:
    """Adapter by name ("etabs" | "bhom_etabs" | "risa" | "ram"); `design` = design.json dict/path
    or None. "etabs" resolves to the configured ETABS adapter (etabs_adapter_name())."""
    key = (name or "").strip().lower()
    if key == "etabs":
        key = etabs_adapter_name()
    if key == "bhom_etabs":
        from .bhom_etabs import BhomEtabsAdapter
        return BhomEtabsAdapter(design)
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


__all__ = ["get_adapter", "etabs_adapter_name", "AnalysisAdapter", "AnalysisObject", "OBJECT_KINDS", "ADAPTERS",
           "ResultSource", "SOURCE_DETAIL", "tag_source"]
