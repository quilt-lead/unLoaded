"""Data shapes for the AI step: inputs, structured outputs, provenance, usage.

Every fact the AI step yields carries an ``AIProvenance`` whose ``method`` is the
literal ``"ai"`` (it cannot be constructed with any other value), plus the provider,
the model id, a confidence, and evidence that is resolved from the *inputs* - a model
cannot cite evidence it was not shown.

Field names mirror the F1 schema's Provenance/Evidence (evidence[], rule id, rule
version, engine version, method, confidence) so an adapter can convert one-to-one
once ``calcgraph.schema`` lands; this module deliberately does not import it yet.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

AI_ENGINE_VERSION = "ai-step-v1.0"

BBox = tuple[float, float, float, float]  # x0, y0, x1, y1 in the evidence's named frame


class Evidence(BaseModel):
    """One located piece of input the model may cite, by ``id``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1)
    doc_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    page: int | None = Field(default=None, ge=1)  # 1-based
    frame: str = Field(min_length=1, description="named coordinate frame of bbox, e.g. 'sheet_pt'")
    bbox: BBox | None = None
    text: str | None = None
    char_span: tuple[int, int] | None = None

    @model_validator(mode="after")
    def _check(self) -> "Evidence":
        if self.bbox is not None:
            x0, y0, x1, y1 = self.bbox
            if not (x0 <= x1 and y0 <= y1):
                raise ValueError(f"evidence {self.id}: bbox not ordered {self.bbox}")
        if self.char_span is not None and not (0 <= self.char_span[0] <= self.char_span[1]):
            raise ValueError(f"evidence {self.id}: bad char_span {self.char_span}")
        return self


class ImageInput(BaseModel):
    """A page image (e.g. a scanned hand-calc page). Hashed by content sha256 only."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    evidence_id: str = Field(min_length=1, description="Evidence.id this image renders")
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    media_type: Literal["image/png", "image/jpeg"] = "image/png"
    path: str | None = Field(default=None, description="local file; excluded from the cache key")


class AIInputs(BaseModel):
    """Everything a task sees. The cache key is a hash of this (paths excluded)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    evidence: list[Evidence] = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    images: list[ImageInput] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check(self) -> "AIInputs":
        ids = [e.id for e in self.evidence]
        dup = {i for i in ids if ids.count(i) > 1}
        if dup:
            raise ValueError(f"duplicate evidence ids: {sorted(dup)}")
        missing = [im.evidence_id for im in self.images if im.evidence_id not in ids]
        if missing:
            raise ValueError(f"images reference unknown evidence ids: {missing}")
        return self

    def evidence_by_id(self) -> dict[str, Evidence]:
        return {e.id: e for e in self.evidence}

    def key_material(self) -> dict[str, Any]:
        return {
            "evidence": [e.model_dump(mode="json") for e in self.evidence],
            "payload": self.payload,
            "images": [im.model_dump(mode="json", exclude={"path"}) for im in self.images],
        }


class AIOutput(BaseModel):
    """Base for every task's structured output.

    ``evidence_refs`` (and any nested ``evidence_ref`` / ``evidence_refs`` field) must
    name ids from ``AIInputs.evidence``; a nested ``bbox`` next to an ``evidence_ref``
    must lie inside that evidence's bbox. Both are enforced by ``ai.extract``.
    """

    model_config = ConfigDict(extra="forbid")

    confidence: float = Field(ge=0.0, le=1.0)
    evidence_refs: list[str] = Field(min_length=1)


class Usage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    cost_usd: float = Field(default=0.0, ge=0.0)


class AIProvenance(BaseModel):
    """Provenance stamped on every AI-derived fact. ``method`` is always "ai"."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    method: Literal["ai"] = "ai"
    rule_id: str  # "ai:<task name>"
    rule_version: str  # task version
    engine_version: str = AI_ENGINE_VERSION
    provider: str
    model_id: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[Evidence] = Field(min_length=1)
    inputs_key: str
    cache_key: str
    instructions_sha256: str
