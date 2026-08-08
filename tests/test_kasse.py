"""The simulated checkout. These are safety tests, not feature tests.

M-5 requires payment to be visibly, unmistakably mocked. The assertions here are the
mechanism that keeps it that way when someone edits the surface later.
"""

from __future__ import annotations

import json
import re

import pytest

from agent.payment import (
    SIMULATION_IBAN,
    SIMULATION_TOKEN,
    LineItem,
    MockPaymentProvider,
    PaymentStatus,
    get_payment_provider,
    split_mwst,
)
from mcpapps.kasse.server import build_order, kasse_bestaetigen, render_for


@pytest.fixture
def kauf_html():
    return render_for(build_order("FB-00042", "Volkswagen Golf", "kauf", 2_149_000))


@pytest.fixture
def miete_html():
    return render_for(
        build_order(
            "FB-00016", "Volkswagen Golf", "miete", 14_700,
            kaution_cent=50_000, abholort="Frankfurt am Main", zeitraum="12. bis 14. September",
        )
    )


# ------------------------------------------------------------------ no card, ever


def test_no_card_input_exists_anywhere_in_the_surface(kauf_html, miete_html):
    """The strongest guarantee in the project: the concept is absent, not disabled."""
    forbidden = [
        "card", "kreditkarte", "kartennummer", "cardnumber", "cvv", "cvc",
        "ccv", "expiry", "exp-date", "gueltig bis", "sicherheitscode",
        "autocomplete=\"cc-", "visa", "mastercard", "amex",
    ]
    for html in (kauf_html, miete_html):
        lowered = html.lower()
        for needle in forbidden:
            assert needle not in lowered, f"card concept {needle!r} present in the surface"


def test_the_only_inputs_are_not_payment_inputs(kauf_html):
    """No input element of any kind in checkout. Nothing to type a card into."""
    assert "<input" not in kauf_html.lower()


def test_the_repository_contains_no_card_field_anywhere():
    from pathlib import Path

    repo = Path(__file__).resolve().parents[1]
    skip = {".venv", "node_modules", ".git", "__pycache__", "dist", "build", "tests"}
    hits = []
    for path in list(repo.rglob("*.py")) + list(repo.rglob("*.html")):
        rel = path.relative_to(repo)
        if skip.intersection(rel.parts):
            continue
        text = path.read_text(encoding="utf-8", errors="replace").lower()
        for needle in ("kartennummer", "cardnumber", 'name="cvv"', 'name="cvc"'):
            if needle in text:
                hits.append(f"{rel}: {needle}")
    assert not hits, f"card fields found: {hits}"


# ------------------------------------------------------------------ simulation signals


def test_the_banner_is_present_on_both_flows(kauf_html, miete_html):
    for html in (kauf_html, miete_html):
        assert "sim-banner" in html
        assert SIMULATION_TOKEN in html


def test_the_confirmation_carries_a_watermark(kauf_html):
    assert "watermark" in kauf_html
    assert 'content: "SIMULATION"' in kauf_html


def test_three_independent_signals_exist(kauf_html):
    """One signal can be scrolled past. Banner, watermark and reference token."""
    assert "sim-banner" in kauf_html
    assert "watermark" in kauf_html
    assert "kein Geld bewegt" in kauf_html


def test_the_iban_is_obviously_invalid(kauf_html):
    assert SIMULATION_IBAN in kauf_html
    assert "SIMU" in SIMULATION_IBAN
    # A real IBAN can never carry check digits 00.
    assert SIMULATION_IBAN.replace(" ", "")[2:4] == "00"


def test_the_surface_explains_why_the_iban_is_invalid(kauf_html):
    assert "Prüfziffer 00" in kauf_html


# ------------------------------------------------------------------ German invoice


def test_tax_is_shown_as_its_own_line(kauf_html):
    assert "Nettobetrag" in kauf_html
    assert "19 % MwSt." in kauf_html
    assert "Gesamtbetrag" in kauf_html


def test_net_plus_tax_equals_gross():
    order = build_order("FB-1", "Test", "kauf", 2_149_000)
    assert order["netto_cent"] + order["mwst_cent"] == order["brutto_cent"]


def test_the_split_follows_the_nineteen_percent_convention():
    netto, mwst = split_mwst(11_900)
    assert netto == 10_000
    assert mwst == 1_900


def test_rental_shows_collection_terms_and_a_refundable_deposit(miete_html):
    assert "Abholung" in miete_html
    assert "Frankfurt am Main" in miete_html
    assert "Kaution, erstattbar" in miete_html


def test_purchase_does_not_show_rental_terms(kauf_html):
    assert "Kaution" not in kauf_html
    assert "Abholung" not in kauf_html


# ------------------------------------------------------------------ references


def test_every_generated_reference_contains_the_token():
    payload = json.loads(kasse_bestaetigen("FB-00042", "kauf"))
    assert SIMULATION_TOKEN in payload["vertrag_referenz"]
    assert SIMULATION_TOKEN in payload["zahlung_referenz"]


def test_purchase_and_rental_produce_different_contract_prefixes():
    kauf = json.loads(kasse_bestaetigen("FB-A", "kauf"))["vertrag_referenz"]
    miete = json.loads(kasse_bestaetigen("FB-B", "miete"))["vertrag_referenz"]
    assert kauf.startswith("FB-KV-")
    assert miete.startswith("FB-MV-")


def test_the_token_survives_truncation_in_a_narrow_column():
    """The token sits in the middle, so cropping the end cannot hide it."""
    payload = json.loads(kasse_bestaetigen("FB-00042", "kauf"))
    assert SIMULATION_TOKEN in payload["vertrag_referenz"][:24]


def test_the_confirmation_always_declares_itself_simulated():
    payload = json.loads(kasse_bestaetigen("FB-00042", "kauf"))
    assert payload["simuliert"] is True


# ------------------------------------------------------------------ the seam


def test_the_configured_provider_is_the_mock():
    assert get_payment_provider().name == "mock"


def test_an_unknown_provider_fails_legibly(monkeypatch):
    from agent import payment

    monkeypatch.setenv("PAYMENT_PROVIDER", "stripe")
    payment.reset_cache()
    with pytest.raises(RuntimeError) as excinfo:
        payment.get_payment_provider()
    assert "stripe" in str(excinfo.value)
    assert "no real payment gateway" in str(excinfo.value).lower()
    payment.reset_cache()


def test_the_provider_can_fail_so_the_failure_path_is_exercised():
    provider = MockPaymentProvider(latency_seconds=(0, 0), failure_rate=1.0, seed=1)
    intent = provider.create_intent([LineItem(bezeichnung="Test", einzelpreis_cent=1000)])
    result = provider.confirm(intent)
    assert not result.erfolgreich
    assert result.status is PaymentStatus.FEHLGESCHLAGEN
    assert result.fehler is not None


def test_a_successful_confirmation_reports_no_money_moved():
    provider = MockPaymentProvider(latency_seconds=(0, 0), seed=2)
    intent = provider.create_intent([LineItem(bezeichnung="Test", einzelpreis_cent=1000)])
    result = provider.confirm(intent)
    assert result.erfolgreich
    assert "kein Geld bewegt" in result.meldung
    assert result.ist_simulation


def test_refund_is_supported_so_the_interface_is_complete():
    provider = MockPaymentProvider(latency_seconds=(0, 0), seed=3)
    intent = provider.create_intent([LineItem(bezeichnung="Test", einzelpreis_cent=1000)])
    provider.confirm(intent)
    refund = provider.refund(intent.id)
    assert refund.erfolgreich
    assert refund.status is PaymentStatus.ERSTATTET


def test_status_is_queryable():
    provider = MockPaymentProvider(latency_seconds=(0, 0), seed=4)
    intent = provider.create_intent([LineItem(bezeichnung="Test", einzelpreis_cent=1000)])
    assert provider.get_status(intent.id) is PaymentStatus.ERSTELLT
    provider.confirm(intent)
    assert provider.get_status(intent.id) is PaymentStatus.BESTAETIGT


def test_no_module_outside_the_payment_package_names_a_gateway():
    from pathlib import Path

    repo = Path(__file__).resolve().parents[1]
    skip = {".venv", "node_modules", ".git", "__pycache__", "dist", "build", "tests"}
    vendors = ("stripe", "adyen", "braintree", "paypal", "klarna", "mollie")
    hits = []
    for path in repo.rglob("*.py"):
        rel = path.relative_to(repo)
        if skip.intersection(rel.parts) or rel.parts[:2] == ("agent", "payment"):
            continue
        text = path.read_text(encoding="utf-8", errors="replace").lower()
        for vendor in vendors:
            if re.search(rf"\b{vendor}\b", text):
                hits.append(f"{rel}: {vendor}")
    assert not hits, f"payment vendor named outside the seam: {hits}"
