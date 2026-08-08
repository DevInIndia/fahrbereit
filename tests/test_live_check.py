"""Tests for the isolated live market check module and endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient

from agent.live_check import perform_live_market_check
from agent.server import app


def test_perform_live_market_check_fallback_on_error():
    """Verify perform_live_market_check fails gracefully without raising exceptions."""
    result = perform_live_market_check(
        marke="Kia",
        modell="Carnival",
        variante="Style",
        baujahr=2025,
        kilometerstand_km=20000,
        preis_eur=25000,
    )
    assert isinstance(result, dict)
    assert result["preis_eur"] == 25000
    assert result["status"] in ("ok", "unavailable")


def test_live_market_check_endpoint():
    """Verify /api/live-market-check route handles requests cleanly."""
    client = TestClient(app)
    response = client.post(
        "/api/live-market-check",
        json={
            "marke": "Kia",
            "modell": "Carnival",
            "variante": "Style",
            "baujahr": 2025,
            "kilometerstand_km": 20000,
            "preis_eur": 25000,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["preis_eur"] == 25000
