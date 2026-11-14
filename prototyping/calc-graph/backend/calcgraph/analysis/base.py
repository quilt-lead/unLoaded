"""Analysis-software adapters: the common interface and the normalized object.

An adapter presents an already-designed calc-graph building the way an analysis program
(ETABS, RISA, RAM) would expose it through its API, maps every analysis-program object back
to registry ids (elements and calc records), writes the program's text model, and MOCKS the
send-change / pull-results round trip by re-running calc-graph's own design (PyNite inside).
No adapter talks to real software: nothing here may imply that ETABS/RISA/RAM ran.

Shapes the API layer can rely on:

- ``AnalysisObject.to_dict()``: {kind, label, story, element_id, record_ids, props, raw}
  kind in OBJECT_KINDS; ``raw`` mimics the vendor API output for that object.
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

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DATA_DIR = os.path.join(ROOT, "data", "synthetic_v2")
DESIGN_PATH = os.path.join(DATA_DIR, "design.json")

OBJECT_KINDS = ("story", "grid", "point", "frame", "area", "section", "material", "load_pattern",
                "load_case", "combo", "story_drift", "frame_design")


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
    """Common interface for analysis-software adapters (ETABS first; RISA / RAM stubs)."""

    name: str = ""
    doc: str = ""          # occurrence doc key, e.g. "etabs"

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
    return model.Layout({c: (float(p[0]), float(p[1])) for c, p in b["columns"].items()},
                        set(b.get("removed", [])), areas, b.get("layout_label", "Base design"))


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
