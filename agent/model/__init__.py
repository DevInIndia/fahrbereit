"""The model seam.

Import `get_model` and `CallType` from here. Nothing outside this package imports a
model vendor, so changing vendor is a change to `MODEL_PROVIDER` plus one builder in
`providers.py`.
"""

from agent.model.budget import LEDGER, BudgetLedger
from agent.model.cache import install_cache_if_enabled
from agent.model.factory import (
    get_model,
    guard,
    is_rate_limit_error,
    model_name,
    provider_name,
    reset_cache,
)
from agent.model.types import CallType, ModelCall, RateLimitExceeded

__all__ = [
    "LEDGER",
    "BudgetLedger",
    "CallType",
    "ModelCall",
    "RateLimitExceeded",
    "get_model",
    "guard",
    "install_cache_if_enabled",
    "is_rate_limit_error",
    "model_name",
    "provider_name",
    "reset_cache",
]
