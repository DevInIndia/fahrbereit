"""Tracing. These tests need no Langfuse account and send nothing anywhere.

The property worth pinning is that observability is optional in the strong sense:
without credentials the product behaves identically, and a tracing failure can never
take a turn down with it.
"""

from __future__ import annotations

import importlib

import pytest

from agent import observability


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    for var in (
        "LANGFUSE_PUBLIC_KEY",
        "LANGFUSE_SECRET_KEY",
        "LANGFUSE_HOST",
        "LANGFUSE_BASE_URL",
    ):
        monkeypatch.delenv(var, raising=False)
    importlib.reload(observability)
    yield
    importlib.reload(observability)


# ------------------------------------------------------------------ optional


def test_tracing_is_off_without_credentials():
    assert observability.configure() is False
    assert observability.enabled() is False
    assert "keine" in observability.status().lower() or "no" in observability.status().lower()


def test_one_missing_key_is_not_enough(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-test")
    importlib.reload(observability)
    assert observability.configure() is False


def test_recording_is_a_no_op_when_disabled():
    """A turn must not fail because tracing is off, or because it broke."""
    observability.configure()
    observability.record_ranking(object(), object(), "de")  # nonsense arguments
    observability.flush()
    assert observability.enabled() is False


def test_turn_span_is_a_working_context_manager_when_disabled():
    observability.configure()
    with observability.turn_span("s1", "hallo", "de") as span:
        assert span is None


def test_status_never_contains_a_credential(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-abcdef123456")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-secret-value-here")
    importlib.reload(observability)
    observability.configure()  # will fail to authenticate, which is fine here
    text = observability.status()
    assert "sk-lf-secret-value-here" not in text
    assert "pk-lf-abcdef123456" not in text


# ------------------------------------------------------------------ config


def test_quotes_are_stripped_from_pasted_values(monkeypatch):
    """Keys copied from a dashboard often arrive wrapped in quotes."""
    monkeypatch.setenv("LANGFUSE_HOST", '"https://cloud.langfuse.com"')
    importlib.reload(observability)
    assert observability._setting("LANGFUSE_HOST") == "https://cloud.langfuse.com"


def test_either_host_variable_is_accepted(monkeypatch):
    """The SDK names one and the dashboard documents the other."""
    monkeypatch.setenv("LANGFUSE_BASE_URL", "https://eu.cloud.langfuse.com")
    importlib.reload(observability)
    assert (
        observability._setting("LANGFUSE_HOST", "LANGFUSE_BASE_URL")
        == "https://eu.cloud.langfuse.com"
    )


def test_host_wins_over_base_url_when_both_are_set(monkeypatch):
    monkeypatch.setenv("LANGFUSE_HOST", "https://one.example")
    monkeypatch.setenv("LANGFUSE_BASE_URL", "https://two.example")
    importlib.reload(observability)
    assert observability._setting("LANGFUSE_HOST", "LANGFUSE_BASE_URL") == "https://one.example"


def test_env_loader_strips_quotes():
    """run_backend loads .env itself; an unstripped quote becomes part of the key."""
    import pathlib
    import tempfile

    from run_backend import load_env

    with tempfile.TemporaryDirectory() as tmp:
        path = pathlib.Path(tmp) / ".env"
        path.write_text('FAHRBEREIT_TEST_KEY="quoted-value"\n', encoding="utf-8")
        load_env(str(path))

    import os

    assert os.environ.get("FAHRBEREIT_TEST_KEY") == "quoted-value"
    os.environ.pop("FAHRBEREIT_TEST_KEY", None)
