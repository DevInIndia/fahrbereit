"""Counting model calls, because the daily ceiling is 500 and it is easy to spend.

The free tier limits verified on 2026-08-08 are 15 requests per minute and 500 per
day for the reasoning model. A single user turn costs several calls, so usage has to
be observable rather than guessed at.
"""

from __future__ import annotations

import logging
import os
import threading
from collections import Counter

from agent.model.types import CallType, ModelCall

log = logging.getLogger("fahrbereit.model")

# Verified against this project's key on 2026-08-08 from the AI Studio dashboard.
# Used only to report headroom, never to gate a call. The provider is the authority.
DAILY_LIMITS: dict[str, int] = {
    "gemini-3.5-flash-lite": 500,
    "gemini-3.1-flash-lite": 500,
    "gemini-2.5-flash-lite": 20,
    "gemini-2.5-flash": 20,
    "gemini-3.5-flash": 20,
    "gemma-4-31b-it": 14_400,
    "gemma-4-26b-a4b-it": 14_400,
}


class BudgetLedger:
    """Every model call this process has made, grouped for reporting."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._calls: list[ModelCall] = []

    def record(self, call: ModelCall) -> None:
        with self._lock:
            self._calls.append(call)
        if os.environ.get("MODEL_CALL_LOG", "1") == "1":
            served = "cache" if call.cached else "network"
            log.info(
                "model call type=%s model=%s served=%s total=%d",
                call.call_type.value,
                call.model,
                served,
                self.billable_total(),
            )

    def billable_total(self) -> int:
        """Calls that actually reached a provider, so cache hits are subtracted.

        Dispatches are counted by the callback handler, which fires before the cache
        is consulted. Hits are counted by the cache itself, which is the only place
        that knows a hit occurred. Billable usage is therefore the difference.
        """
        with self._lock:
            dispatched = sum(1 for c in self._calls if not c.cached)
            hits = sum(1 for c in self._calls if c.cached)
        return max(dispatched - hits, 0)

    def record_cache_hit(self, call_type: CallType, model: str) -> None:
        """Recorded by the cache layer, which is the only place a hit is observable."""
        self.record(ModelCall.now(call_type, model, cached=True))

    def by_model(self) -> Counter:
        with self._lock:
            return Counter(c.model for c in self._calls if not c.cached)

    def by_call_type(self) -> Counter:
        with self._lock:
            return Counter(c.call_type.value for c in self._calls if not c.cached)

    def cache_hits(self) -> int:
        with self._lock:
            return sum(1 for c in self._calls if c.cached)

    def report(self) -> str:
        """A short human readable usage summary, for logs and for the progress surface."""
        per_model = self.by_model()
        if not per_model:
            return "no billable model calls yet"
        lines = []
        for model, n in per_model.most_common():
            limit = DAILY_LIMITS.get(model)
            if limit:
                lines.append(f"{model}: {n} of {limit} daily")
            else:
                lines.append(f"{model}: {n}")
        hits = self.cache_hits()
        if hits:
            lines.append(f"{hits} served from cache, costing no quota")
        return "; ".join(lines)

    def reset(self) -> None:
        with self._lock:
            self._calls.clear()


LEDGER = BudgetLedger()
