"""Shared adapter machinery: document registry, evidence builders, the rejection tally and
unit handling. Adapters NEVER invent per-fact data. Where a source output lacks a provenance
field that is a property of the RULE that produced it (rule id, rule/engine version, the
rule's declared confidence), the adapter fills it from a declared rule table and lists the
field in `provenance.adapter_supplied`, so the gap is counted, not hidden. A fact with no
locatable evidence is rejected."""
from __future__ import annotations

import hashlib
import json
import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from pydantic import ValidationError

from ..frames import sheet_bbox
from ..models import Bundle, DocKind, Document, Method, PdfEvidence, Provenance, Unitless
from ..units import Quantity, canonical, unit_from_key

ADAPTER_VERSION = "schema-adapters/1.0"
_NUM = re.compile(r"^[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?$")


class Reject(Exception):
    """A fact the adapter cannot convert (reason in the message)."""


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class DocRegistry:
    """Source-output doc keys ('plans', 'calcs', ...) -> Document with a real sha256."""
    docs: dict[str, Document] = field(default_factory=dict)
    missing: dict[str, str] = field(default_factory=dict)

    def add(self, key: str, path: str | None, kind: DocKind, name: str, pages: int | None = None, role: str = "") -> None:
        if not path or not os.path.exists(path):
            self.missing[key] = f"{name}: file not found ({path}) - no sha256, evidence on it is rejected"
            return
        self.docs[key] = Document(sha256=sha256_file(path), kind=kind, name=name, pages=pages, role=role)

    def sha(self, key: str) -> str:
        d = self.docs.get(key)
        if not d:
            raise Reject(f"evidence on document '{key}' with no sha256 ({self.missing.get(key, 'unknown doc key')})")
        return d.sha256


def pdf_ev(reg: DocRegistry, doc: str, page, rects, text: str = "", note: str = "", sheet: str | None = None,
           char_span=None) -> PdfEvidence:
    """Evidence on a PDF page from the source's [x0,y0,x1,y1] rects (PDF points)."""
    if not page:
        raise Reject("evidence has no page")
    rects = [r for r in (rects or []) if r and len(r) == 4]
    if not rects:
        raise Reject("evidence has no box (no bbox / rects)")
    sha = reg.sha(doc)
    boxes = [sheet_bbox(sha, int(page), r, sheet) for r in rects]
    bb = boxes[0]
    for b in boxes[1:]:
        bb = bb.union(b)
    return PdfEvidence(doc_sha=sha, page=int(page), bbox=bb, rects=boxes if len(boxes) > 1 else [], text=text or "",
                       note=note or "", char_span=tuple(char_span) if char_span else None)


@dataclass(frozen=True)
class Rule:
    """A producing module's rule, declared once. Used only for fields the source lacks."""
    engine: str
    version: str = "unversioned"
    confidence: float | None = None
    method: Method = Method.deterministic


def prov(evidence: list, rule_id: str | None, rule: Rule, *, rule_text: str = "", confidence: float | None = None,
         rule_version: str | None = None, engine: str | None = None, at: str | None = None,
         declared_rule_id: str | None = None) -> Provenance:
    """Provenance from what the source carries; anything missing comes from `rule` and is flagged.

    rule_id: the rule the SOURCE names for this fact. declared_rule_id: the rule the adapter
    knows produced this fact kind when the source names none (flagged as supplied)."""
    supplied = []
    if not rule_id:
        if not declared_rule_id:
            raise Reject("no rule id (source names no rule and no rule is declared for this fact kind)")
        rule_id = declared_rule_id
        supplied.append("rule_id")
    if rule_version is None:
        rule_version = rule.version
        supplied.append("rule_version")
    if engine is None:
        engine = rule.engine
        supplied.append("engine")
    if confidence is None:
        if rule.confidence is None:
            raise Reject("no confidence (source carries none and the rule declares none)")
        confidence = rule.confidence
        supplied.append("confidence")
    return Provenance(evidence=evidence, rule_id=rule_id, rule_text=rule_text, rule_version=rule_version, engine=engine,
                      method=rule.method, confidence=confidence, at=at, adapter_supplied=supplied)


@dataclass
class Tally:
    """Per-source counts: attempted / converted / rejected (with reasons), adapter-supplied
    provenance fields, and unit outcomes."""
    source: str
    attempted: Counter = field(default_factory=Counter)
    converted: Counter = field(default_factory=Counter)
    rejected: dict[str, Counter] = field(default_factory=lambda: defaultdict(Counter))
    supplied: dict[str, Counter] = field(default_factory=lambda: defaultdict(Counter))
    units: dict[str, Counter] = field(default_factory=lambda: defaultdict(Counter))
    facts_without_own_units: Counter = field(default_factory=Counter)
    skipped: Counter = field(default_factory=Counter)
    notes: list[str] = field(default_factory=list)
    examples: dict[str, list] = field(default_factory=lambda: defaultdict(list))

    def summary(self) -> dict:
        return {
            "source": self.source,
            "attempted": dict(self.attempted), "converted": dict(self.converted),
            "rejected": {k: dict(v) for k, v in self.rejected.items()},
            "rejected_total": {k: sum(v.values()) for k, v in self.rejected.items()},
            "adapter_supplied_provenance": {k: dict(v) for k, v in self.supplied.items()},
            "units": {k: dict(v) for k, v in self.units.items()},
            "facts_with_unitless_numbers": dict(self.facts_without_own_units),
            "skipped": dict(self.skipped), "notes": self.notes,
            "examples": {k: v[:3] for k, v in self.examples.items()},
        }


def _reason(e: Exception) -> str:
    if isinstance(e, ValidationError):
        er = e.errors()[0]
        loc = ".".join(str(x) for x in er["loc"])
        return f"invalid: {loc}: {er['msg']}"[:160]
    return str(e)[:160]


def build(t: Tally, bundle: Bundle, entity: str, cls, src_id: str, make, strict: bool = False):
    """Run `make()` -> kwargs, validate as `cls`, append to bundle.<entity>; tally the outcome."""
    t.attempted[entity] += 1
    try:
        kw = make()
        units = kw.pop("_units", None)
        obj = cls(**kw)
        if strict and obj.provenance.adapter_supplied:
            raise Reject(f"provenance incomplete in source: {obj.provenance.adapter_supplied}")
    except (Reject, ValidationError, KeyError, TypeError, ValueError) as e:
        if strict:
            raise
        r = _reason(e)
        t.rejected[entity][r] += 1
        if len(t.examples[f"{entity}: {r}"]) < 3:
            t.examples[f"{entity}: {r}"].append(src_id)
        return None
    getattr(bundle, entity).append(obj)
    t.converted[entity] += 1
    for f in obj.provenance.adapter_supplied:
        t.supplied[entity][f] += 1
    if units:
        t.units[entity].update(units)
        if units.get("unitless"):
            t.facts_without_own_units[entity] += 1
    return obj


# ---------------- values + units ----------------
def to_values(uc: Counter, d: dict, *, label_keys: frozenset = frozenset(),
              declared: dict[str, str] | None = None, prefix: str = "", inherited: str | None = None) -> dict:
    """Flatten a source value dict into schema Values (dotted keys for nesting).

    A number becomes a Quantity only if a unit is DECLARED: by its own key / header
    (unit_from_key), by an enclosing key ("vertical_loads_k" -> its children are kip), or by
    the adapter's `declared` map (a unit the producing module states for that field, e.g.
    RISA plan coordinates are feet) - counted separately as `declared_by_adapter`.
    Otherwise it stays `Unitless` and is counted."""
    declared = declared or {}
    out: dict = {}
    for k, v in d.items():
        key = f"{prefix}{k}"
        if v is None or v == "" or v == [] or v == {}:
            continue
        if isinstance(v, dict):
            u = unit_from_key(str(k)) or inherited
            out.update(to_values(uc, v, label_keys=label_keys, declared=declared, prefix=key + ".", inherited=u))
            continue
        if str(k) in label_keys:
            out[key] = str(v)
            continue
        if isinstance(v, bool):
            out[key] = v
            continue
        num = isinstance(v, (int, float)) or (isinstance(v, str) and bool(_NUM.match(v.strip())))
        if isinstance(v, list):
            if all(isinstance(x, str) for x in v):
                out[key] = list(v)
            else:
                out[key] = Unitless(raw=json.dumps(v), note="list of numbers; source declares no unit")
                uc["unitless"] += 1
            continue
        if not num:
            out[key] = str(v)
            continue
        own = unit_from_key(str(k))
        if own:
            out[key] = Quantity(value=float(v), unit=own)
            uc["explicit_in_key_or_header"] += 1
        elif inherited:
            out[key] = Quantity(value=float(v), unit=inherited)
            uc["explicit_in_parent_key"] += 1
        elif str(k) in declared or key in declared:
            out[key] = Quantity(value=float(v), unit=canonical(declared.get(key, declared.get(str(k)))))
            uc["declared_by_adapter"] += 1
        else:
            out[key] = Unitless(raw=str(v))
            uc["unitless"] += 1
    return out


def has_unitless(values: dict) -> bool:
    return any(isinstance(v, Unitless) for v in values.values())


def hid(*parts) -> str:
    """Short stable hash id for facts the source gives no id (findings, occurrences)."""
    return hashlib.sha1(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()[:12]


def evidence_list(reg: DocRegistry, items: list[dict], sheet_key: str = "sheet") -> list:
    """Source evidence dicts {doc, page, rects|bbox, text, note} -> PdfEvidence; any bad one rejects."""
    out = []
    for ev in items or []:
        rects = ev.get("rects") or ([ev["bbox"]] if ev.get("bbox") else [])
        out.append(pdf_ev(reg, ev.get("doc"), ev.get("page"), rects, ev.get("text", ""), ev.get("note", ""),
                          ev.get(sheet_key)))
    if not out:
        raise Reject("no evidence items")
    return out
