"""Task registry: each AI task declares WHAT (instructions, output schema, version,
an optional semantic validator). The engine in ``step.py`` owns HOW.

Two tasks are declared - the only two places the AI step is intended for:

* ``scanned_calc_page`` - a calc-package page with no text layer (scanned hand calc).
  The deterministic text path (PyMuPDF words) sees nothing, so ``pdf_ingest`` /
  ``segment`` never map it. Input: the page image + page-level evidence. Output: the
  calc sheet id, title, and the values it reads, each pinned to a sub-bbox of the page.
* ``fuzzy_element_calc_match`` - an element <-> calc pairing that the deterministic
  matcher tiers (exact mark ... element-type-only, see README "Matching rules") left
  unresolved or ambiguous. Input: the element's evidence + candidate calc spans.
  Output: the chosen candidate (or none) with a reason; the choice must be one of the
  candidates given.

Adding a task = one ``register_task`` call; ``step.extract`` needs no edit.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Callable

from pydantic import BaseModel, ConfigDict, Field

from .types import AIInputs, AIOutput, BBox


@dataclass(frozen=True)
class TaskSpec:
    name: str
    version: str
    instructions: str
    output_schema: type[AIOutput]
    intended_for: str
    max_output_tokens: int = 4000
    # Semantic check beyond the schema (e.g. "choice is one of the candidates").
    validate: Callable[[AIInputs, AIOutput], None] | None = field(default=None, compare=False)

    @property
    def instructions_sha256(self) -> str:
        return hashlib.sha256(self.instructions.encode("utf-8")).hexdigest()


_TASKS: dict[str, TaskSpec] = {}


class UnknownTask(KeyError):
    pass


def register_task(spec: TaskSpec) -> TaskSpec:
    if not issubclass(spec.output_schema, AIOutput):
        raise TypeError(f"task {spec.name}: output schema must subclass AIOutput")
    existing = _TASKS.get(spec.name)
    if existing is not None and existing != spec:
        raise ValueError(f"task {spec.name} already registered with a different spec")
    _TASKS[spec.name] = spec
    return spec


def get_task(name: str) -> TaskSpec:
    try:
        return _TASKS[name]
    except KeyError:
        raise UnknownTask(f"unknown AI task {name!r}; registered: {sorted(_TASKS)}") from None


def list_tasks() -> list[TaskSpec]:
    return [_TASKS[k] for k in sorted(_TASKS)]


# --------------------------------------------------------------------------- scanned page

class ReadValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, description="what the value is, e.g. 'Mu', 'beam size'")
    text: str = Field(min_length=1, description="the value exactly as written on the page")
    value: float | None = None
    unit: str | None = Field(default=None, description="unit as written, e.g. 'k-ft', 'psf'")
    member_mark: str | None = None
    evidence_ref: str
    bbox: BBox = Field(description="where on the page, inside the referenced evidence bbox")
    confidence: float = Field(ge=0.0, le=1.0)


class ScannedCalcPageReading(AIOutput):
    calc_sheet_id: str | None = None
    title: str | None = None
    values: list[ReadValue] = Field(default_factory=list)


def _validate_scanned(inputs: AIInputs, out: AIOutput) -> None:
    assert isinstance(out, ScannedCalcPageReading)
    if not inputs.images:
        raise ValueError("scanned_calc_page needs at least one page image")
    for v in out.values:
        if v.value is not None and v.unit is None:
            raise ValueError(f"value {v.label}={v.value} has no unit")


SCANNED_CALC_PAGE = register_task(TaskSpec(
    name="scanned_calc_page",
    version="1",
    intended_for="calc pages with no text layer (scanned hand calcs)",
    output_schema=ScannedCalcPageReading,
    validate=_validate_scanned,
    instructions=(
        "You read one scanned structural calculation page. Report the calc sheet id and "
        "title if written, and every design value you can read (member size, demand, "
        "capacity, unity check, load), each with the text exactly as written, its unit as "
        "written, the member mark it belongs to if written, and a bbox inside the page "
        "evidence you cite. Report only what is legible on the page; omit anything you "
        "would have to guess. Give a confidence per value and overall."
    ),
))


# --------------------------------------------------------------------------- fuzzy match

class Candidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    calc_key: str
    evidence_ref: str
    deterministic_tier: str | None = None
    deterministic_score: float | None = None


class FuzzyMatchDecision(AIOutput):
    element_id: str
    chosen_candidate_id: str | None = Field(
        description="one of payload.candidates[].candidate_id, or null when none fits")
    reason: str = Field(min_length=1)


def _validate_fuzzy(inputs: AIInputs, out: AIOutput) -> None:
    assert isinstance(out, FuzzyMatchDecision)
    payload = inputs.payload
    if out.element_id != payload.get("element_id"):
        raise ValueError(f"decision is for {out.element_id!r}, asked about {payload.get('element_id')!r}")
    cands = [Candidate.model_validate(c) for c in payload.get("candidates", [])]
    if not cands:
        raise ValueError("fuzzy_element_calc_match needs payload.candidates")
    ids = {c.candidate_id for c in cands}
    if out.chosen_candidate_id is not None and out.chosen_candidate_id not in ids:
        raise ValueError(f"chosen candidate {out.chosen_candidate_id!r} was not offered ({sorted(ids)})")
    if out.chosen_candidate_id is not None:
        chosen = next(c for c in cands if c.candidate_id == out.chosen_candidate_id)
        if chosen.evidence_ref not in out.evidence_refs:
            raise ValueError("a chosen candidate's own evidence must be cited")


FUZZY_ELEMENT_CALC_MATCH = register_task(TaskSpec(
    name="fuzzy_element_calc_match",
    version="1",
    intended_for="element<->calc pairs the deterministic matcher tiers left unresolved",
    output_schema=FuzzyMatchDecision,
    validate=_validate_fuzzy,
    max_output_tokens=1500,
    instructions=(
        "You decide which calc (if any) designs one structural element. The deterministic "
        "matcher could not decide. You get the element's drawing evidence and candidate calc "
        "spans with the tier that proposed each. Choose one candidate only when the evidence "
        "shows that calc designs this element (same member, same level, same size or a "
        "documented substitution); otherwise choose null. Cite the evidence you used, "
        "including the chosen candidate's, and give the reason in one or two sentences."
    ),
))
