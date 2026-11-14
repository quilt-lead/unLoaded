"""Real provider stub: Anthropic Claude. DISABLED BY DEFAULT. Never exercised.

Three independent gates, all required before any request leaves this machine:
1. ``CALCGRAPH_AI_ENABLE_REAL=1``  (an explicit opt-in; Issy approves API spend)
2. ``ANTHROPIC_API_KEY`` set
3. a run budget with ``max_cost_usd_per_run`` > 0 (the default cap is $0.00, so the
   budget pre-check in ``step.extract`` refuses the call otherwise)

The ``anthropic`` SDK is imported lazily inside ``complete`` (it is not a project
dependency; ``uv add anthropic`` when spend is approved). This module is the ONLY
place an LLM SDK may be imported - ``scripts/check_llm_imports.py`` enforces that.

The call shape (``client.messages.parse(..., output_format=<pydantic model>)``) is
written from the Anthropic Python SDK docs but has NOT been run: treat the first
approved call as the smoke test.
"""
from __future__ import annotations

import base64
import os
from pathlib import Path

from ..cache import canonical_json
from ..types import Usage
from .base import Provider, ProviderDisabled, ProviderRequest, ProviderResponse

DEFAULT_MODEL = "claude-opus-5-5"

# USD per 1M tokens (input, output), first-party API rates as of 2026-11.
PRICING_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
}

# Rough image token cost for a full calc page render; deliberately generous.
_TOKENS_PER_IMAGE = 2500


class AnthropicProvider(Provider):
    name = "anthropic"

    def __init__(self, model_id: str | None = None):
        self.model_id = model_id or os.environ.get("CALCGRAPH_AI_MODEL", DEFAULT_MODEL)
        if self.model_id not in PRICING_PER_MTOK:
            raise ValueError(f"no pricing for {self.model_id!r}; add it to PRICING_PER_MTOK "
                             "so budgets can be enforced")

    def enabled(self) -> tuple[bool, str]:
        if os.environ.get("CALCGRAPH_AI_ENABLE_REAL") != "1":
            return False, "CALCGRAPH_AI_ENABLE_REAL is not '1' (real LLM calls need Issy's spend approval)"
        if not os.environ.get("ANTHROPIC_API_KEY"):
            return False, "ANTHROPIC_API_KEY is not set"
        return True, "enabled by env flag + key"

    def _cost(self, input_tokens: int, output_tokens: int) -> float:
        pin, pout = PRICING_PER_MTOK[self.model_id]
        return input_tokens * pin / 1e6 + output_tokens * pout / 1e6

    def estimate(self, req: ProviderRequest) -> Usage:
        text = req.task.instructions + canonical_json(req.inputs.key_material()) + canonical_json(req.json_schema)
        tin = len(text) // 3 + _TOKENS_PER_IMAGE * len(req.inputs.images) + 500
        tout = req.max_output_tokens
        return Usage(input_tokens=tin, output_tokens=tout, cost_usd=self._cost(tin, tout))

    def complete(self, req: ProviderRequest) -> ProviderResponse:  # pragma: no cover - never run
        ok, why = self.enabled()
        if not ok:
            raise ProviderDisabled(f"anthropic provider disabled: {why}")
        import anthropic  # lazy: only reachable past the gates above

        content: list[dict] = []
        for im in req.inputs.images:
            if not im.path:
                raise ValueError(f"image {im.evidence_id} has no local path to send")
            data = Path(im.path).read_bytes()
            content.append({"type": "image", "source": {
                "type": "base64", "media_type": im.media_type,
                "data": base64.standard_b64encode(data).decode("ascii")}})
        content.append({"type": "text", "text": "Inputs (JSON):\n" + canonical_json(req.inputs.key_material())})

        client = anthropic.Anthropic()
        resp = client.messages.parse(
            model=self.model_id,
            max_tokens=req.max_output_tokens,
            system=req.task.instructions,
            messages=[{"role": "user", "content": content}],
            output_format=req.output_schema,
        )
        if resp.stop_reason == "refusal":
            raise RuntimeError(f"model refused: {getattr(resp, 'stop_details', None)}")
        parsed = resp.parsed_output
        if parsed is None:
            raise RuntimeError(f"no structured output (stop_reason={resp.stop_reason})")
        tin, tout = resp.usage.input_tokens, resp.usage.output_tokens
        return ProviderResponse(raw_json=parsed.model_dump_json(),
                                usage=Usage(input_tokens=tin, output_tokens=tout, cost_usd=self._cost(tin, tout)),
                                model_id=resp.model)
