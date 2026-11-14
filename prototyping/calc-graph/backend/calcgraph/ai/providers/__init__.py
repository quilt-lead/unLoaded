"""Provider registry. ``CALCGRAPH_AI_PROVIDER`` picks the default (``replay``)."""
from __future__ import annotations

import os
from typing import Callable

from .anthropic_provider import AnthropicProvider
from .base import Provider, ProviderDisabled, ProviderRequest, ProviderResponse
from .replay import ReplayMiss, ReplayProvider

_FACTORIES: dict[str, Callable[[], Provider]] = {}
_INSTANCES: dict[str, Provider] = {}

DEFAULT_PROVIDER = "replay"


def register_provider(name: str, factory: Callable[[], Provider], *, replace: bool = False) -> None:
    if name in _FACTORIES and not replace:
        raise ValueError(f"provider {name!r} already registered")
    _FACTORIES[name] = factory
    _INSTANCES.pop(name, None)


def get_provider(name: str | None = None) -> Provider:
    name = name or os.environ.get("CALCGRAPH_AI_PROVIDER") or DEFAULT_PROVIDER
    if name not in _FACTORIES:
        raise KeyError(f"unknown AI provider {name!r}; registered: {sorted(_FACTORIES)}")
    if name not in _INSTANCES:
        _INSTANCES[name] = _FACTORIES[name]()
    return _INSTANCES[name]


def list_providers() -> list[str]:
    return sorted(_FACTORIES)


register_provider("replay", ReplayProvider)
register_provider("anthropic", AnthropicProvider)

__all__ = ["Provider", "ProviderDisabled", "ProviderRequest", "ProviderResponse", "ReplayMiss",
           "ReplayProvider", "AnthropicProvider", "register_provider", "get_provider",
           "list_providers", "DEFAULT_PROVIDER"]
