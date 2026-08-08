"""Payment seam. Import `get_payment_provider`, never a provider class.

The provider is selected by configuration, so connecting a real gateway later means
adding one class here and one value in `PAYMENT_PROVIDER`. Nothing outside this
package learns which provider is in use.
"""

from __future__ import annotations

import functools
import os

from agent.payment.mock import MockPaymentProvider
from agent.payment.protocol import (
    MWST_SATZ,
    SIMULATION_BIC,
    SIMULATION_IBAN,
    SIMULATION_TOKEN,
    LineItem,
    PaymentError,
    PaymentIntent,
    PaymentProvider,
    PaymentResult,
    PaymentStatus,
    split_mwst,
)

# The only implementation that exists in this repository. A real gateway would be
# added here as another entry, never by importing it at a call site.
PROVIDERS = {
    "mock": MockPaymentProvider,
}


@functools.lru_cache(maxsize=4)
def _build(name: str) -> PaymentProvider:
    try:
        factory = PROVIDERS[name]
    except KeyError:
        raise RuntimeError(
            f"PAYMENT_PROVIDER={name!r} is not a provider this project knows. "
            f"Choose one of: {', '.join(sorted(PROVIDERS))}. "
            f"This repository ships no real payment gateway."
        ) from None
    return factory()


def get_payment_provider() -> PaymentProvider:
    """The one way anything in this project obtains a payment provider."""
    return _build(os.environ.get("PAYMENT_PROVIDER", "mock").strip().lower())


def reset_cache() -> None:
    _build.cache_clear()


__all__ = [
    "MWST_SATZ",
    "SIMULATION_BIC",
    "SIMULATION_IBAN",
    "SIMULATION_TOKEN",
    "LineItem",
    "MockPaymentProvider",
    "PaymentError",
    "PaymentIntent",
    "PaymentProvider",
    "PaymentResult",
    "PaymentStatus",
    "get_payment_provider",
    "reset_cache",
    "split_mwst",
]
