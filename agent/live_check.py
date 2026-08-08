"""Thin bridge module delegating to agent.model.live_check."""

from __future__ import annotations

from agent.model.live_check import perform_live_market_check

__all__ = ["perform_live_market_check"]
