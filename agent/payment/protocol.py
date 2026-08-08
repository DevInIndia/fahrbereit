"""The payment seam.

There is no real payment gateway in this repository and there never will be. What
there is, is an interface shaped so that adding one later is a contained change: one
new class implementing `PaymentProvider`, one new value in `PAYMENT_PROVIDER`.

Nothing outside `agent/payment/` may know which provider is in use, and no provider
specific concept may leak into the agent, the MCP apps, or the interface.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Protocol, runtime_checkable

from pydantic import BaseModel, Field

# Deliberately, unmistakably invalid. An IBAN carries a mod-97 checksum in positions
# three and four; 00 can never be valid. It also spells out what it is.
SIMULATION_IBAN = "DE00 SIMU LATI ON00 0000 00"
SIMULATION_BIC = "SIMULATEXXX"
SIMULATION_TOKEN = "SIMULATION"

MWST_SATZ = 0.19


class PaymentStatus(str, Enum):
    ERSTELLT = "erstellt"
    BESTAETIGT = "bestaetigt"
    FEHLGESCHLAGEN = "fehlgeschlagen"
    ERSTATTET = "erstattet"


class PaymentError(str, Enum):
    """Failure modes a provider may return, so the failure path is exercised."""

    ABGELEHNT = "abgelehnt"
    ZEITUEBERSCHREITUNG = "zeitueberschreitung"
    UNZUREICHENDE_DECKUNG = "unzureichende_deckung"


class LineItem(BaseModel):
    bezeichnung: str
    menge: int = 1
    einzelpreis_cent: int

    @property
    def gesamt_cent(self) -> int:
        return self.menge * self.einzelpreis_cent


class PaymentIntent(BaseModel):
    """A payment that has been prepared but not completed."""

    id: str
    referenz: str  # carries SIMULATION_TOKEN
    betrag_brutto_cent: int
    betrag_netto_cent: int
    mwst_cent: int
    waehrung: str = "EUR"
    status: PaymentStatus = PaymentStatus.ERSTELLT
    positionen: list[LineItem] = Field(default_factory=list)
    erstellt_am: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    simuliert: bool = True  # never false in this repository


class PaymentResult(BaseModel):
    """The outcome of confirming or refunding. Typed, never a raw dictionary."""

    intent_id: str
    status: PaymentStatus
    referenz: str
    erfolgreich: bool
    fehler: Optional[PaymentError] = None
    meldung: str = ""
    iban: str = SIMULATION_IBAN
    bic: str = SIMULATION_BIC
    simuliert: bool = True

    @property
    def ist_simulation(self) -> bool:
        return True


@runtime_checkable
class PaymentProvider(Protocol):
    """What any payment backend must provide.

    A real gateway would implement exactly this. The only implementation that exists
    here is the mock.
    """

    name: str

    def create_intent(
        self, positionen: list[LineItem], referenz_praefix: str = "FB"
    ) -> PaymentIntent:
        """Prepare a payment. Computes net, tax at nineteen percent, and gross."""
        ...

    def confirm(self, intent: PaymentIntent) -> PaymentResult:
        """Complete a prepared payment."""
        ...

    def get_status(self, intent_id: str) -> PaymentStatus:
        """Current status of a prepared payment."""
        ...

    def refund(self, intent_id: str) -> PaymentResult:
        """Reverse a completed payment."""
        ...


def split_mwst(brutto_cent: int) -> tuple[int, int]:
    """Split a gross amount into net and nineteen percent tax.

    German invoice convention shows all three. Computed from gross because the
    listing prices are gross, which is how consumer prices are quoted in Germany.
    """
    netto = round(brutto_cent / (1 + MWST_SATZ))
    return netto, brutto_cent - netto
