"""Shared types for the model seam.

Nothing here imports a model vendor. This module is safe to import from anywhere.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum


class CallType(str, Enum):
    """What a model call is for, which decides which model serves it.

    The split is by latency sensitivity, not by difficulty. REASONING covers
    everything a user waits on, including narration and status strings, because a
    slow status line is worse than no status line. CHEAP covers work where nobody
    is watching the clock.
    """

    REASONING = "reasoning"
    CHEAP = "cheap"


class RateLimitExceeded(RuntimeError):
    """A provider refused the call because a rate limit was reached.

    Raised so that a throttle surfaces as a named, renderable state rather than as
    an opaque provider error, a hang, or a crash. See FR-044.
    """

    def __init__(self, model: str, call_type: CallType, detail: str = "") -> None:
        self.model = model
        self.call_type = call_type
        self.detail = detail
        super().__init__(
            f"Rate limit reached for {model} on the {call_type.value} path. {detail}".strip()
        )


@dataclass(frozen=True)
class ModelCall:
    """One recorded model call, for counting usage against a daily budget."""

    at: datetime
    call_type: CallType
    model: str
    cached: bool = False

    @staticmethod
    def now(call_type: CallType, model: str, cached: bool = False) -> "ModelCall":
        return ModelCall(datetime.now(timezone.utc), call_type, model, cached)
