"""Platform adapter interface + the vendor-neutral record the impact engine consumes.

Every adapter (Procore, Autodesk Construction Cloud Build, Autodesk Forma, and later a
real connector) exposes the same small surface:

- `list(record_type)` / the `list_*` helpers -> `NormalizedRecord`s (vendor-neutral),
- `list_raw(record_type)` -> objects shaped like that platform's public API responses,
- `get(record_type, id)` -> one raw object, `deep_link(record_type, id)` -> a URL.

The impact engine, the change-order estimator and the health meter only ever read
`NormalizedRecord`s, so swapping the synthetic adapter for a live one changes nothing
downstream. Everything served today is SYNTHETIC (see synthetic.py) and every deep link
is a `mock://` URL, never a real tenant.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import Any

# record types an adapter may serve; `capabilities` says which ones it actually does
SUBMITTALS = "submittals"
RFIS = "rfis"
CHANGE_EVENTS = "change_events"
CHANGE_ORDERS = "change_orders"
BUDGET_LINES = "budget_lines"
COST_CODES = "cost_codes"
SCHEDULE_ACTIVITIES = "schedule_activities"
SHEETS = "sheets"
ISSUES = "issues"
ELEMENTS = "elements"
PROPOSALS = "proposals"
RECORD_TYPES = (SUBMITTALS, RFIS, CHANGE_EVENTS, CHANGE_ORDERS, BUDGET_LINES, COST_CODES,
                SCHEDULE_ACTIVITIES, SHEETS, ISSUES, ELEMENTS, PROPOSALS)

# normalized construction stage of an element / package, in order of how hard it is to change
STAGES = ("design", "submitted", "approved", "fabricated", "delivered", "erected")


def stage_rank(stage: str) -> int:
    return STAGES.index(stage) if stage in STAGES else 0


@dataclass
class NormalizedRecord:
    """One platform record in vendor-neutral form.

    kind        submittal | rfi | change_event | change_order | budget_line | cost_code |
                schedule_activity | sheet | issue | element | proposal
    id          the platform's own id for the record (string), usable with get()/deep_link()
    ref         the synthetic project's canonical id for the same real-world record
                (e.g. "SUB-05-L2-S1"), identical across platforms -> use it to de-duplicate
    platform    adapter name ("procore", "autodesk_build", "forma")
    number      the human number shown in the platform UI ("05 12 00-003", "RFI-004")
    title       one-line title
    status      normalized status:
                submittal: draft | submitted | revise_resubmit | approved | fabricated | delivered | erected
                rfi: draft | open | answered | closed
                change_event / change_order: draft | pending | approved | rejected | void
                schedule_activity: not_started | in_progress | complete
                budget_line / cost_code / sheet / element / proposal: active
    element_ids registry element ids (design.json `elements[].id`) the record concerns
    dates       ISO dates, keys per kind (due, submitted, approved, start, finish, ...)
    links       {"self": mock deep link, ...}
    fields      kind-specific normalized values (stage, spec_section, amount_usd, float_days,
                predecessors, package_ref, ...) - documented per kind in synthetic.py
    raw         the platform-shaped object exactly as list_raw() returns it
    """
    kind: str
    id: str
    ref: str
    platform: str
    number: str
    title: str
    status: str
    element_ids: list[str] = field(default_factory=list)
    dates: dict[str, str | None] = field(default_factory=dict)
    links: dict[str, str] = field(default_factory=dict)
    fields: dict[str, Any] = field(default_factory=dict)
    raw: dict = field(default_factory=dict)

    def to_dict(self, include_raw: bool = True) -> dict:
        d = asdict(self)
        if not include_raw:
            d.pop("raw")
        return d


class PlatformAdapter(ABC):
    """A construction platform as the prototype sees it.

    Subclasses implement `_build()` (raw + normalized records per record type) and
    `deep_link()`. A live adapter would implement the same two against the vendor API;
    nothing else in the package needs to change.
    """
    name: str = ""
    label: str = ""
    capabilities: frozenset[str] = frozenset()
    doc_urls: dict[str, str] = {}

    def __init__(self) -> None:
        self._cache: dict[str, list[NormalizedRecord]] | None = None

    # ------------------------------------------------------------------ to implement
    @abstractmethod
    def _build(self) -> dict[str, list[NormalizedRecord]]:
        """Return {record_type: [NormalizedRecord (with .raw filled)]} for every capability."""

    @abstractmethod
    def deep_link(self, record_type: str, id: str) -> str:
        """URL of the record in the platform UI. Synthetic adapters return mock:// URLs."""

    # ------------------------------------------------------------------ public surface
    def _records(self) -> dict[str, list[NormalizedRecord]]:
        if self._cache is None:
            self._cache = self._build()
        return self._cache

    def supports(self, record_type: str) -> bool:
        return record_type in self.capabilities

    def list(self, record_type: str) -> list[NormalizedRecord]:
        if record_type not in RECORD_TYPES:
            raise KeyError(f"unknown record type {record_type!r}; one of {RECORD_TYPES}")
        return list(self._records().get(record_type, []))

    def list_raw(self, record_type: str) -> list[dict]:
        return [r.raw for r in self.list(record_type)]

    def get(self, record_type: str, id: str) -> dict | None:
        r = self.get_normalized(record_type, id)
        return r.raw if r else None

    def get_normalized(self, record_type: str, id: str) -> NormalizedRecord | None:
        sid = str(id)
        for r in self.list(record_type):
            if r.id == sid or r.ref == sid:
                return r
        return None

    def records_for_element(self, element_id: str, record_types: tuple[str, ...] | None = None) -> list[NormalizedRecord]:
        out = []
        for rt in record_types or tuple(sorted(self.capabilities)):
            out += [r for r in self.list(rt) if element_id in r.element_ids]
        return out

    def counts(self) -> dict[str, dict[str, int]]:
        out: dict[str, dict[str, int]] = {}
        for rt in RECORD_TYPES:
            recs = self.list(rt)
            if not recs:
                continue
            by: dict[str, int] = {}
            for r in recs:
                by[r.status] = by.get(r.status, 0) + 1
            out[rt] = {"total": len(recs), **dict(sorted(by.items()))}
        return out

    # convenience wrappers (the methods the lead's API routes call)
    def list_submittals(self) -> list[NormalizedRecord]:
        return self.list(SUBMITTALS)

    def list_rfis(self) -> list[NormalizedRecord]:
        return self.list(RFIS)

    def list_change_events(self) -> list[NormalizedRecord]:
        return self.list(CHANGE_EVENTS)

    def list_change_orders(self) -> list[NormalizedRecord]:
        return self.list(CHANGE_ORDERS)

    def list_budget_lines(self) -> list[NormalizedRecord]:
        return self.list(BUDGET_LINES)

    def list_cost_codes(self) -> list[NormalizedRecord]:
        return self.list(COST_CODES)

    def list_schedule_activities(self) -> list[NormalizedRecord]:
        return self.list(SCHEDULE_ACTIVITIES)

    def list_sheets(self) -> list[NormalizedRecord]:
        return self.list(SHEETS)

    def list_elements(self) -> list[NormalizedRecord]:
        return self.list(ELEMENTS)

    def list_proposals(self) -> list[NormalizedRecord]:
        return self.list(PROPOSALS)

    def describe(self) -> dict:
        return {"name": self.name, "label": self.label, "capabilities": sorted(self.capabilities),
                "doc_urls": self.doc_urls, "synthetic": True}
