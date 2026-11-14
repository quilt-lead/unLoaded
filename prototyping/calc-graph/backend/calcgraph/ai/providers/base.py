"""Provider interface. A provider turns a ProviderRequest into raw JSON text plus
usage; parsing and validation against the task schema happen in ``step.py`` for every
provider alike, so replay and real outputs go through the same structured path."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from ..tasks import TaskSpec
from ..types import AIInputs, AIOutput, Usage


class ProviderDisabled(RuntimeError):
    pass


@dataclass(frozen=True)
class ProviderRequest:
    task: TaskSpec
    inputs: AIInputs
    output_schema: type[AIOutput]
    json_schema: dict[str, Any]
    inputs_key: str
    max_output_tokens: int


@dataclass(frozen=True)
class ProviderResponse:
    raw_json: str
    usage: Usage
    model_id: str  # the model that actually answered (replay: the recorded one)


class Provider(ABC):
    name: str = ""
    model_id: str = ""

    def enabled(self) -> tuple[bool, str]:
        """(enabled, reason). A disabled provider must refuse ``complete``."""
        return True, "always on"

    @abstractmethod
    def estimate(self, req: ProviderRequest) -> Usage:
        """Upper-bound-ish usage estimate, checked against the budget BEFORE the call."""

    @abstractmethod
    def complete(self, req: ProviderRequest) -> ProviderResponse:
        ...
