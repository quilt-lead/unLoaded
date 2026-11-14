"""calcgraph.ai - the ONE place AI-assisted extraction/matching happens.

Interface::

    from calcgraph import ai
    res = ai.extract("fuzzy_element_calc_match", inputs, run=ai.Run(budget=ai.Budget(...)))
    res.output       # validated Pydantic object (task's schema)
    res.provenance   # AIProvenance: method="ai", provider, model_id, confidence,
                     # evidence[] resolved from the inputs, rule id/version, keys
    res.to_record()  # {"task", "value", "provenance"} for the store / schema adapters

Guarantees:
* Structured output only: every result is ``schema.model_validate_json``-ed; free text
  never leaves this package.
* Content-hash cache (``cache.py``): same task + version + instructions + schema +
  inputs + provider + model -> same answer, no call, no spend.
* Every fact is marked ``method="ai"`` with model id, confidence and evidence; cited
  evidence must be from the inputs, nested boxes must lie inside it.
* Budget caps per call and per run (``budget.py``); the default run cap is $0.00.
* Provider registry (``providers/``): ``replay`` (default, deterministic fixtures, no
  network) and ``anthropic`` (stub, disabled unless ``CALCGRAPH_AI_ENABLE_REAL=1`` AND
  ``ANTHROPIC_API_KEY`` AND a nonzero run budget; never exercised to date).
* ``scripts/check_llm_imports.py`` fails if any module outside ``calcgraph/ai/``
  imports an LLM SDK.

Intended for exactly two places (both declared in ``tasks.py``):
1. ``scanned_calc_page`` - calc pages with no text layer (scanned hand calcs), which
   the deterministic PyMuPDF text path cannot read and the matcher never maps.
2. ``fuzzy_element_calc_match`` - element <-> calc pairs the deterministic matcher
   tiers leave unresolved or ambiguous; the AI may only choose among the candidates
   the deterministic tiers proposed, or decline.
Nothing in the pipeline calls this yet; wiring it in is a separate, approved step.
"""
from __future__ import annotations

from .budget import Budget, BudgetExceeded, Run
from .cache import ResultCache
from .providers import (AnthropicProvider, Provider, ProviderDisabled, ReplayMiss, ReplayProvider,
                        get_provider, list_providers, register_provider)
from .step import AIEvidenceError, AIOutputInvalid, Result, extract
from .tasks import (FuzzyMatchDecision, ScannedCalcPageReading, TaskSpec, get_task, list_tasks,
                    register_task)
from .types import AI_ENGINE_VERSION, AIInputs, AIOutput, AIProvenance, Evidence, ImageInput, Usage

__all__ = [
    "extract", "Result", "AIInputs", "AIOutput", "AIProvenance", "Evidence", "ImageInput", "Usage",
    "Budget", "BudgetExceeded", "Run", "ResultCache", "AIEvidenceError", "AIOutputInvalid",
    "Provider", "ProviderDisabled", "ReplayMiss", "ReplayProvider", "AnthropicProvider",
    "get_provider", "list_providers", "register_provider",
    "TaskSpec", "get_task", "list_tasks", "register_task",
    "ScannedCalcPageReading", "FuzzyMatchDecision", "AI_ENGINE_VERSION",
]
