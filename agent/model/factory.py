"""Resolve a model from configuration. No caller names a vendor.

Two call types, split by whether a user is waiting. The split matters because the
free tier's fast model has a small daily budget and its large budget model is about
sixteen times slower, so the naive routing of "cheap work to the cheap model" puts a
twenty second pause exactly where a user is watching. See docs/spike-notes.md.
"""

from __future__ import annotations

import functools
import logging
import os
from contextlib import contextmanager
from typing import Any, Iterator

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.language_models.chat_models import BaseChatModel

from agent.model.budget import LEDGER
from agent.model.providers import BUILDERS
from agent.model.types import CallType, ModelCall, RateLimitExceeded

log = logging.getLogger("fahrbereit.model")

DEFAULT_MODELS = {
    CallType.REASONING: "gemini-3.5-flash-lite",
    CallType.CHEAP: "gemma-4-31b-it",
}

_ENV_VAR = {
    CallType.REASONING: "MODEL_REASONING",
    CallType.CHEAP: "MODEL_CHEAP",
}


class _LedgerCallback(BaseCallbackHandler):
    """Records every dispatched call so usage against the daily ceiling is countable."""

    def __init__(self, call_type: CallType, model: str) -> None:
        self.call_type = call_type
        self.model = model

    def on_chat_model_start(self, serialized: Any, messages: Any, **kwargs: Any) -> None:
        LEDGER.record(ModelCall.now(self.call_type, self.model))

    def on_llm_start(self, serialized: Any, prompts: Any, **kwargs: Any) -> None:
        LEDGER.record(ModelCall.now(self.call_type, self.model))


def provider_name() -> str:
    return os.environ.get("MODEL_PROVIDER", "gemini").strip().lower()


def model_name(call_type: CallType) -> str:
    return os.environ.get(_ENV_VAR[call_type], "").strip() or DEFAULT_MODELS[call_type]


@functools.lru_cache(maxsize=8)
def _build(provider: str, call_type: CallType, model: str) -> BaseChatModel:
    try:
        builder = BUILDERS[provider]
    except KeyError:
        raise RuntimeError(
            f"MODEL_PROVIDER={provider!r} is not a provider this project knows. "
            f"Choose one of: {', '.join(sorted(BUILDERS))}."
        ) from None
    llm = builder(model)
    # Set callbacks on the model itself rather than via with_config, which would
    # return a RunnableBinding. create_deep_agent wants a BaseChatModel, and a
    # binding does not reliably proxy bind_tools.
    existing = list(llm.callbacks or [])
    llm.callbacks = existing + [_LedgerCallback(call_type, model)]
    log.info("resolved %s path to %s via %s", call_type.value, model, provider)
    return llm


def get_model(call_type: CallType = CallType.REASONING) -> BaseChatModel:
    """The one way anything in this project obtains a model."""
    return _build(provider_name(), call_type, model_name(call_type))


def reset_cache() -> None:
    """Drop memoised models, so a configuration change takes effect. Used by tests."""
    _build.cache_clear()


def is_rate_limit_error(exc: BaseException) -> bool:
    """Whether a provider exception is a rate limit refusal.

    Matched on the wire status rather than on an exception class, because the
    providers behind this seam raise unrelated types for the same condition.
    """
    for attr in ("status_code", "code", "http_status"):
        if getattr(exc, attr, None) in (429, "429"):
            return True
    text = str(exc).lower()
    return "429" in text or "resource_exhausted" in text or "rate limit" in text


@contextmanager
def guard(call_type: CallType = CallType.REASONING) -> Iterator[None]:
    """Translate a provider throttle into a named, renderable failure.

    Wrap the agent invocation in this so a 429 arrives at the interface as a state
    it can draw, rather than as a hang or a stack trace. See FR-044.
    """
    try:
        yield
    except RateLimitExceeded:
        raise
    except Exception as exc:
        if is_rate_limit_error(exc):
            model = model_name(call_type)
            log.warning("rate limited on %s. usage so far: %s", model, LEDGER.report())
            raise RateLimitExceeded(model, call_type, LEDGER.report()) from exc
        raise
