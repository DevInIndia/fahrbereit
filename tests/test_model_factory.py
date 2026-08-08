"""The model seam. These tests need no API key and make no network call."""

from __future__ import annotations

import re

from pathlib import Path

import pytest
from langchain_core.language_models.chat_models import BaseChatModel

from agent.model import (
    LEDGER,
    CallType,
    RateLimitExceeded,
    get_model,
    guard,
    is_rate_limit_error,
    model_name,
    provider_name,
    reset_cache,
)
from agent.model.budget import BudgetLedger
from agent.model.types import ModelCall

REPO = Path(__file__).resolve().parents[1]

# Every vendor package that must not be imported outside agent/model/.
VENDOR_MODULES = [
    "langchain_google_genai",
    "langchain_openai",
    "langchain_anthropic",
    "google.generativeai",
    "google.genai",
    "openai",
    "anthropic",
]


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for var in (
        "MODEL_PROVIDER",
        "MODEL_REASONING",
        "MODEL_CHEAP",
        "GOOGLE_API_KEY",
        "OPENAI_COMPATIBLE_API_KEY",
        "OPENAI_COMPATIBLE_BASE_URL",
    ):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key-not-real")
    reset_cache()
    LEDGER.reset()
    yield
    reset_cache()


# ------------------------------------------------------------------ resolution


def test_defaults_to_the_verified_free_tier_models():
    """The reasoning default must be a model with a usable daily ceiling.

    The full Flash models sit at 20 requests per day, which is about three user
    turns. Defaulting to one would make the system unusable out of the box.
    """
    assert provider_name() == "gemini"
    assert model_name(CallType.REASONING) == "gemini-3.5-flash-lite"
    assert model_name(CallType.CHEAP) == "gemma-4-31b-it"


def test_configuration_overrides_the_default(monkeypatch):
    monkeypatch.setenv("MODEL_REASONING", "gemini-3.1-flash-lite")
    assert model_name(CallType.REASONING) == "gemini-3.1-flash-lite"


def test_get_model_returns_a_base_chat_model():
    """create_deep_agent accepts str or BaseChatModel. A RunnableBinding is neither."""
    llm = get_model(CallType.REASONING)
    assert isinstance(llm, BaseChatModel)


def test_reasoning_and_cheap_resolve_to_different_models():
    assert get_model(CallType.REASONING).model != get_model(CallType.CHEAP).model


def test_unknown_provider_fails_legibly(monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "definitely-not-a-provider")
    with pytest.raises(RuntimeError) as excinfo:
        get_model()
    message = str(excinfo.value)
    assert "definitely-not-a-provider" in message
    assert "gemini" in message  # names the valid options rather than just refusing


def test_missing_credential_names_the_variable(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    reset_cache()
    with pytest.raises(RuntimeError) as excinfo:
        get_model()
    assert "GOOGLE_API_KEY" in str(excinfo.value)


# ------------------------------------------------------------------ the seam


def test_no_vendor_import_outside_the_model_package():
    """This is the assertion that actually keeps the seam honest.

    Everything else can be satisfied while someone quietly imports a vendor in the
    session or a tool. A grep cannot be argued with.
    """
    # Walk the working tree rather than asking git, because untracked files are
    # exactly the ones a seam breach would arrive in.
    skip_dirs = {".venv", "venv", "node_modules", ".git", "__pycache__", "dist", "build"}
    sources = [
        p.relative_to(REPO)
        for p in REPO.rglob("*.py")
        if not skip_dirs.intersection(p.relative_to(REPO).parts)
    ]
    assert sources, "found no Python sources to scan, the check would be vacuous"

    pattern = re.compile(
        r"^\s*(?:from|import)\s+(" + "|".join(re.escape(v) for v in VENDOR_MODULES) + r")\b",
        re.MULTILINE,
    )

    offenders = []
    for rel in sources:
        if rel.parts[:2] == ("agent", "model"):
            continue
        if rel.parts[0] == "tests":
            continue
        text = (REPO / rel).read_text(encoding="utf-8", errors="replace")
        for match in pattern.finditer(text):
            line = text[: match.start()].count("\n") + 1
            offenders.append(f"{rel}:{line} imports {match.group(1)}")

    assert not offenders, "vendor imported outside agent/model/:\n" + "\n".join(offenders)


# ------------------------------------------------------------------ throttling


@pytest.mark.parametrize(
    "exc",
    [
        RuntimeError("429 Too Many Requests"),
        RuntimeError("RESOURCE_EXHAUSTED: quota exceeded"),
        RuntimeError("rate limit reached for this model"),
    ],
)
def test_rate_limit_detected_across_provider_shapes(exc):
    assert is_rate_limit_error(exc)


def test_non_rate_limit_errors_are_not_misread():
    assert not is_rate_limit_error(RuntimeError("400 INVALID_ARGUMENT"))
    assert not is_rate_limit_error(ValueError("no such model"))


def test_status_code_attribute_is_detected():
    exc = RuntimeError("upstream refused")
    exc.status_code = 429
    assert is_rate_limit_error(exc)


def test_guard_translates_a_throttle_into_a_renderable_state():
    """FR-044: a throttle must arrive as a named state, not as a provider stack trace."""
    with pytest.raises(RateLimitExceeded) as excinfo:
        with guard(CallType.REASONING):
            raise RuntimeError("429 Too Many Requests")
    assert excinfo.value.model == "gemini-3.5-flash-lite"
    assert excinfo.value.call_type is CallType.REASONING


def test_guard_leaves_unrelated_errors_alone():
    with pytest.raises(ValueError):
        with guard():
            raise ValueError("a real bug, not a throttle")


# ------------------------------------------------------------------ budget


def test_ledger_counts_billable_calls_and_discounts_cache_hits():
    ledger = BudgetLedger()
    ledger.record(ModelCall.now(CallType.REASONING, "gemini-3.5-flash-lite"))
    ledger.record(ModelCall.now(CallType.REASONING, "gemini-3.5-flash-lite"))
    assert ledger.billable_total() == 2

    ledger.record_cache_hit(CallType.REASONING, "gemini-3.5-flash-lite")
    assert ledger.billable_total() == 1
    assert ledger.cache_hits() == 1


def test_ledger_report_names_the_daily_ceiling():
    ledger = BudgetLedger()
    ledger.record(ModelCall.now(CallType.REASONING, "gemini-3.5-flash-lite"))
    assert "500 daily" in ledger.report()


def test_ledger_report_is_safe_when_empty():
    assert "no billable" in BudgetLedger().report()
