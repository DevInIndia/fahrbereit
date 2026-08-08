"""Isolated Live Market Check module using Gemini Google Search Grounding.

Strictly display-only validation. Completely decoupled from ranking, scoring,
and session state. Never alters candidate listing data or ranking scores.
Must reside in agent/model/ to respect the architectural vendor seam guardrail.
"""

from __future__ import annotations

import os
import re
from typing import Any

_CACHE: dict[str, dict[str, Any]] = {}


def perform_live_market_check(
    marke: str,
    modell: str,
    variante: str,
    baujahr: int | None,
    kilometerstand_km: int | None,
    preis_eur: int,
) -> dict[str, Any]:
    """Search for comparable real-market listings in Germany via Gemini grounding.

    Fails gracefully returning status='unavailable' on rate limit, 429 quota error,
    or network failure. Results are cached in memory per vehicle query.
    """
    key = f"{marke}:{modell}:{variante}:{baujahr}:{kilometerstand_km}:{preis_eur}"
    if key in _CACHE:
        return _CACHE[key]

    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        result = {
            "status": "unavailable",
            "hinweis": "Live check unavailable (missing API key)",
            "preis_eur": preis_eur,
        }
        _CACHE[key] = result
        return result

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        prompt = (
            f"Search for used {marke} {modell} {variante} {baujahr or ''} "
            f"with ~{kilometerstand_km or 50000} km in Germany on car marketplaces. "
            f"State the observed typical price range in EUR in format 'MIN EUR to MAX EUR'."
        )

        response = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
            ),
        )

        text = response.text or ""
        citations: list[dict[str, str]] = []

        candidates = getattr(response, "candidates", None)
        if candidates and candidates[0]:
            gm = getattr(candidates[0], "grounding_metadata", None)
            if gm and hasattr(gm, "grounding_chunks") and gm.grounding_chunks:
                for chunk in gm.grounding_chunks:
                    web = getattr(chunk, "web", None)
                    if web and getattr(web, "uri", None):
                        citations.append({
                            "titel": getattr(web, "title", "Marketplace listing") or "Marketplace listing",
                            "url": web.uri,
                        })

        # Extract numeric price values from response text
        nums = [int(n.replace(".", "").replace(",", "")) for n in re.findall(r"\b\d{1,3}(?:\.\d{3})+\b|\b\d{4,5}\b", text)]
        valid_prices = [n for n in nums if 2000 <= n <= 200000]

        if valid_prices:
            obs_min = min(valid_prices)
            obs_max = max(valid_prices)
            mid = (obs_min + obs_max) // 2
            delta = preis_eur - mid
            result = {
                "status": "ok",
                "preis_eur": preis_eur,
                "markt_min_eur": obs_min,
                "markt_max_eur": obs_max,
                "delta_eur": delta,
                "quellen": citations[:3],
                "text": text[:300],
            }
        else:
            result = {
                "status": "ok",
                "preis_eur": preis_eur,
                "quellen": citations[:3],
                "text": text[:300],
            }

        _CACHE[key] = result
        return result

    except Exception:
        # Graceful fallback: return plain unavailable state on 429 quota or API failure
        result = {
            "status": "unavailable",
            "hinweis": "Live check unavailable",
            "preis_eur": preis_eur,
        }
        _CACHE[key] = result
        return result
