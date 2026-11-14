"""Budget caps for the AI step, per call and per run.

The default run cost cap is $0.00: a provider that bills anything is refused before
the call unless the caller passes a Budget, or sets ``CALCGRAPH_AI_MAX_RUN_USD``. The
replay provider costs nothing, so it always fits. Cache hits are never charged.
"""
from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field

from .types import Usage


class BudgetExceeded(RuntimeError):
    pass


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    return default if raw in (None, "") else float(raw)


@dataclass
class Budget:
    max_calls: int = 200
    max_input_tokens_per_call: int = 200_000
    max_output_tokens_per_call: int = 8_000
    max_cost_usd_per_call: float = 0.50
    max_cost_usd_per_run: float = 0.0

    @classmethod
    def from_env(cls) -> "Budget":
        return cls(
            max_calls=int(_env_float("CALCGRAPH_AI_MAX_CALLS", 200)),
            max_cost_usd_per_call=_env_float("CALCGRAPH_AI_MAX_CALL_USD", 0.50),
            max_cost_usd_per_run=_env_float("CALCGRAPH_AI_MAX_RUN_USD", 0.0),
        )


@dataclass
class Run:
    """Spend ledger for one run (one pipeline invocation). Thread-safe."""

    budget: Budget = field(default_factory=Budget.from_env)
    calls: int = 0
    cache_hits: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def precheck(self, estimate: Usage, *, label: str) -> None:
        b = self.budget
        with self._lock:
            problems = []
            if self.calls + 1 > b.max_calls:
                problems.append(f"calls {self.calls + 1} > max_calls {b.max_calls}")
            if estimate.input_tokens > b.max_input_tokens_per_call:
                problems.append(f"est. input tokens {estimate.input_tokens} > {b.max_input_tokens_per_call}")
            if estimate.output_tokens > b.max_output_tokens_per_call:
                problems.append(f"output tokens {estimate.output_tokens} > {b.max_output_tokens_per_call}")
            if estimate.cost_usd > b.max_cost_usd_per_call:
                problems.append(f"est. cost ${estimate.cost_usd:.4f} > per-call cap ${b.max_cost_usd_per_call:.4f}")
            if self.cost_usd + estimate.cost_usd > b.max_cost_usd_per_run:
                problems.append(
                    f"run cost ${self.cost_usd:.4f} + est. ${estimate.cost_usd:.4f} > run cap "
                    f"${b.max_cost_usd_per_run:.4f}")
            if problems:
                raise BudgetExceeded(f"{label}: refused before calling the provider: " + "; ".join(problems))
            self.calls += 1  # reserve the call slot

    def record(self, actual: Usage, *, label: str) -> None:
        with self._lock:
            self.input_tokens += actual.input_tokens
            self.output_tokens += actual.output_tokens
            self.cost_usd += actual.cost_usd
            over = self.cost_usd > self.budget.max_cost_usd_per_run
        if over:
            # The call already happened; fail loudly so the run stops spending.
            raise BudgetExceeded(
                f"{label}: actual run cost ${self.cost_usd:.4f} exceeded the run cap "
                f"${self.budget.max_cost_usd_per_run:.4f} (estimate was low)")

    def hit(self) -> None:
        with self._lock:
            self.cache_hits += 1

    def summary(self) -> dict:
        return {"calls": self.calls, "cache_hits": self.cache_hits, "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens, "cost_usd": round(self.cost_usd, 6)}
