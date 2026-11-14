"""Analysis-software adapters: the common interface and the normalized object.

An adapter presents an already-designed calc-graph building the way an analysis program
(ETABS, RISA, RAM) would expose it through its API, maps every analysis-program object back
to registry ids (elements and calc records), writes the program's text model, and MOCKS the
send-change / pull-results round trip by re-running calc-graph's own design (PyNite inside).
No adapter talks to real software: nothing here may imply that ETABS/RISA/RAM ran.

Shapes the API layer can rely on:

- ``AnalysisObject.to_dict()``: {kind, label, story, element_id, record_ids, props, raw}
  kind in OBJECT_KINDS; ``raw`` mimics the vendor API output for that object; props always carry
  ``source`` (a ResultSource code) + ``source_detail`` (enforced by AnalysisAdapter, see SOURCE_DETAIL).
- ``occurrences()``: [{ref, doc, kind: "<doc>-object", object_type, label, story, how}]
- ``send_change(design, change)`` -> job dict (see etabs.EtabsAdapter.send_change)
- ``pull_results(job)`` -> results dict (see etabs.EtabsAdapter.pull_results)

A *change* is ``{"moved": {"2B": [dx_ft, dy_ft]}, "removed": ["2C"]}`` (column grid keys as
in synth.v2.model.Layout.cols).
"""
from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field

from ..schema.structural import ResultSource

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DATA_DIR = os.path.join(ROOT, "data", "synthetic_v2")
DESIGN_PATH = os.path.join(DATA_DIR, "design.json")

# Where an analysis value came from - the ONE definition every adapter tags with (mock, PyNite re-run,
# real ETABS via CSI OAPI or BHoM). Every model object's props and every result row / summary an adapter
# returns carries {"source": <ResultSource value>, "source_detail": SOURCE_DETAIL[...]}, mock included,
# so the UI reads one field whichever adapter answered.
SOURCE_DETAIL = {
    ResultSource.csi_oapi: "real ETABS, read through CSI's OAPI on the Windows bridge",
    ResultSource.etabs_via_bhom: "real ETABS, read through BHoM's ETABS_Toolkit on the Windows bridge",
    ResultSource.calcgraph_pynite: "calc-graph's own design re-run (PyNite); ETABS did not run",
    ResultSource.mock: "design.json mapped to ETABS-style objects; ETABS did not run",
    ResultSource.imported_file: "read from a BHoM / Speckle JSON file someone handed us",
}


SOURCE_CODES = frozenset(s.value for s in ResultSource)
# result keys holding per-row lists (mock: story_drifts / frame_design / base_reactions; real routes add
# bar_forces / node_reactions)
RESULT_ROW_KEYS = ("story_drifts", "frame_design", "base_reactions", "bar_forces", "node_reactions")


def tag_source(row: dict, source: ResultSource, detail: str | None = None) -> dict:
    """`row` with the source contract fields set (a copy)."""
    return {**row, "source": source.value, "source_detail": detail or SOURCE_DETAIL[source]}


def ensure_source(row: dict, default: ResultSource) -> dict:
    """In place: a row that already names a source code keeps it (a real ETABS row stays csi-oapi);
    one without a code gets `default`. A prose `source` (older mock rows) is kept as source_detail."""
    src = row.get("source")
    if src in SOURCE_CODES:
        row.setdefault("source_detail", SOURCE_DETAIL[ResultSource(src)])
        return row
    if isinstance(src, str) and src.strip():
        row.setdefault("source_detail", src)
    row["source"] = default.value
    row.setdefault("source_detail", SOURCE_DETAIL[default])
    return row


def _contract_objects(fn):
    def model_objects(self, *a, **kw):
        objs = fn(self, *a, **kw)
        for o in objs:
            ensure_source(o.props, self.object_source)
        return objs
    model_objects._source_contract = True
    return model_objects


def _contract_job(fn):
    def send_change(self, *a, **kw):
        return ensure_source(fn(self, *a, **kw), self.object_source)
    send_change._source_contract = True
    return send_change


def _contract_results(fn):
    def pull_results(self, *a, **kw):
        res = fn(self, *a, **kw)
        if isinstance(res, dict):
            for k in RESULT_ROW_KEYS:
                for row in res.get(k) or []:
                    if isinstance(row, dict):
                        ensure_source(row, self.result_source)
            if isinstance(res.get("summary"), dict):
                ensure_source(res["summary"], self.result_source)
            ensure_source(res, self.result_source)
        return res
    pull_results._source_contract = True
    return pull_results


OBJECT_KINDS = ("story", "grid", "point", "frame", "area", "shell_prop", "diaphragm", "mass_source", "section",
                "material", "load_pattern", "load_case", "combo", "story_drift", "frame_design")


@dataclass
class AnalysisObject:
    """One object as the analysis program would hold it, normalized across programs.

    kind:        one of OBJECT_KINDS
    label:       the program's user-facing label ("B12", "Story2", "W18X40", "EQX")
    story:       the program's story name for story-bound objects, else None
    element_id:  registry element / type id this object represents (or None)
    record_ids:  calc record ids that this object carries values from
    props:       normalized properties (units: kip, ft unless the key says otherwise)
    raw:         the object shaped like the vendor API output (method name -> fields)
    """
    kind: str
    label: str
    element_id: str | None = None
    record_ids: list[str] = field(default_factory=list)
    props: dict = field(default_factory=dict)
    raw: dict = field(default_factory=dict)
    story: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


class AnalysisAdapter(ABC):
    """Common interface for analysis-software adapters (ETABS first; RISA / RAM stubs).

    The source contract is enforced HERE for every subclass, mock or real: model_objects() props,
    send_change() jobs and pull_results() rows / summary / result all carry `source` (a ResultSource
    code) + `source_detail`. A subclass only declares its defaults - what its objects and results are
    when it does not say otherwise - and tags explicitly when a value came from somewhere else (the
    bridge tags csi-oapi / etabs-via-bhom rows itself, and those are never overwritten)."""

    name: str = ""
    doc: str = ""          # occurrence doc key, e.g. "etabs"
    object_source: ResultSource = ResultSource.mock               # model objects: design.json in vendor shapes
    result_source: ResultSource = ResultSource.calcgraph_pynite   # results: calc-graph's own re-run

    def __init_subclass__(cls, **kw):
        super().__init_subclass__(**kw)
        for name, wrap in (("model_objects", _contract_objects), ("send_change", _contract_job),
                           ("pull_results", _contract_results)):
            fn = cls.__dict__.get(name)
            if fn is not None and not getattr(fn, "_source_contract", False) and not getattr(fn, "__isabstractmethod__", False):
                w = wrap(fn)
                w.__name__, w.__qualname__, w.__doc__ = fn.__name__, fn.__qualname__, fn.__doc__
                setattr(cls, name, w)

    @abstractmethod
    def model_objects(self) -> list[AnalysisObject]:
        """Every object of the current design, normalized (see AnalysisObject)."""

    @abstractmethod
    def occurrences(self) -> list[dict]:
        """[{ref, doc, kind, object_type, label, story, how}] - one row per (object, registry id)."""

    @abstractmethod
    def export_model(self, path: str, design: dict | None = None, change: dict | None = None,
                     redesign: bool = False) -> dict:
        """Write the program's text model of the design (or of the design with `change` applied)."""

    @abstractmethod
    def send_change(self, design: dict | None, change: dict) -> dict:
        """MOCK: stage a proposed change for the program; returns a job record."""

    @abstractmethod
    def pull_results(self, job: dict | str) -> dict:
        """MOCK: results for a job, in the program's result shapes (calc-graph re-run)."""


def load_design(design: dict | str | None = None) -> dict:
    """design.json as a dict (path, dict, or None for data/synthetic_v2/design.json). Read only."""
    if isinstance(design, dict):
        return design
    path = design or DESIGN_PATH
    if not os.path.exists(path):
        raise FileNotFoundError(f"{path} missing - run `uv run python -m synth.v2.generate` first")
    with open(path) as fh:
        return json.load(fh)


def layout_from_design(exp: dict):
    """synth.v2.model.Layout the design was generated from (columns, removed, areas)."""
    from synth.v2 import model

    b = exp.get("building") or {}
    if not b.get("columns"):
        return model.base_layout()
    areas = [model.Area(**a) for a in b.get("areas", [])] or model.default_areas()
    # the lateral system is layout input; an export written before it was recorded is the original
    # single-SCBF-on-line-3 building (the only one that existed then)
    lat = model.LateralScheme.from_dict(b["lateral"]) if b.get("lateral") else model.original_scheme()
    return model.Layout({c: (float(p[0]), float(p[1])) for c, p in b["columns"].items()},
                        set(b.get("removed", [])), areas, b.get("layout_label", "Base design"), lat)


def validate_change(change: dict | None, layout) -> dict:
    """Normalize a change dict; raise ValueError on unknown columns or bad offsets."""
    change = change or {}
    unknown = set(change) - {"moved", "removed"}
    if unknown:
        raise ValueError(f"unknown change keys {sorted(unknown)} (allowed: moved, removed)")
    moved = {}
    for c, d in (change.get("moved") or {}).items():
        if c not in layout.cols or c in layout.removed:
            raise ValueError(f"moved column {c!r} is not in the layout")
        if not (isinstance(d, (list, tuple)) and len(d) == 2):
            raise ValueError(f"moved[{c!r}] must be [dx_ft, dy_ft]")
        moved[c] = [float(d[0]), float(d[1])]
    removed = []
    for c in change.get("removed") or []:
        if c not in layout.cols or c in layout.removed:
            raise ValueError(f"removed column {c!r} is not in the layout")
        removed.append(c)
    if set(moved) & set(removed):
        raise ValueError("a column cannot be both moved and removed")
    return {"moved": moved, "removed": sorted(removed)}


def apply_change(layout, change: dict | None):
    """A copy of `layout` with the change applied (moves keep grid identity, see synth.v2.model)."""
    change = validate_change(change, layout)
    lay = layout.copy()
    for c, (dx, dy) in change["moved"].items():
        x, y = lay.cols[c]
        lay.cols[c] = (x + dx, y + dy)
    lay.removed |= set(change["removed"])
    parts = [f"move {c} by ({dx:g}, {dy:g}) ft" for c, (dx, dy) in change["moved"].items()]
    parts += [f"remove {c}" for c in change["removed"]]
    lay.label = "; ".join(parts) or layout.label
    return lay
