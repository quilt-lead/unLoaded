"""How a REAL platform record is linked back to registry elements.

Real platforms have no "registry element id" field, so the seeding script writes a short machine-readable
marker into a free-text field the vendor API documents as writable, and the live adapters read it back:

    [calc-graph SUB-05-L2-S1]                      the synthetic record's canonical ref
    [calc-graph RFI-004 el=COL-2B,CONN-2B-L2-N]    optional explicit element list

Where it is written (per vendor field, all confirmed in the specs / reference pages):
  Procore RFI          `reference` (string) gets "calc-graph RFI-004"; the marker also ends the question body
  Procore submittal    `description` (string)
  Procore change event `external_data.origin_id` = "calc-graph:CE-002" and the marker in `description`
  ACC RFI (v3)         `reference` (max 20 chars) = "CG:RFI-004"; marker at the end of `question`
  ACC submittal        `description` (optional free text in the create body)
  ACC change order     `externalId` = "calc-graph:CE-002", `externalSystem` = "calc-graph"
  ACC issue            marker at the end of `description`

Element ids are resolved from the marker's `el=` list when present, else from the synthetic construction
state by ref (the seed derives every record from that state, so the ref is a stable key). A record with
no marker stays a REAL record with no element links (`element_ids=[]`), never a guessed link.
"""
from __future__ import annotations

import re

MARK = re.compile(r"\[calc-graph\s+([A-Z0-9][A-Z0-9._-]*)(?:\s+el=([A-Za-z0-9_.,:-]+))?\]")
SHORT = re.compile(r"\b(?:calc-graph[: ]|CG:)([A-Z0-9][A-Z0-9._-]*)")


def marker(ref: str, element_ids: list[str] | None = None, max_len: int = 900) -> str:
    m = f"[calc-graph {ref}"
    if element_ids:
        el = ",".join(element_ids)
        if len(m) + len(el) + 5 <= max_len:
            m += f" el={el}"
    return m + "]"


def short(ref: str, limit: int = 20) -> str:
    s = f"CG:{ref}"
    if len(s) > limit:
        raise ValueError(f"short marker {s!r} exceeds {limit} chars")
    return s


def parse(*texts) -> tuple[str | None, list[str]]:
    """First marker found in any of the texts -> (ref, explicit element ids)."""
    for t in texts:
        if not t or not isinstance(t, str):
            continue
        m = MARK.search(t)
        if m:
            return m.group(1), (m.group(2).split(",") if m.group(2) else [])
    for t in texts:
        if isinstance(t, str):
            m = SHORT.search(t)
            if m:
                return m.group(1), []
    return None, []


class Resolver:
    """ref -> element ids, from the synthetic construction state (the seed's source of truth)."""

    def __init__(self, state=None):
        self.by_ref: dict[str, list[str]] = {}
        if state is not None:
            for coll in ("submittals", "rfis", "change_events", "change_orders", "budget_lines", "activities", "sheets"):
                for rec in getattr(state, coll, None) or []:
                    if isinstance(rec, dict) and rec.get("ref"):
                        self.by_ref[rec["ref"]] = list(rec.get("element_ids") or [])

    def elements(self, ref: str | None, explicit: list[str]) -> list[str]:
        if explicit:
            return explicit
        return list(self.by_ref.get(ref or "", []))
