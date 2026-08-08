"""The only payment provider in this repository.

It moves no money, contacts no bank, and touches no card network in any environment
including production. It simulates latency and can return failures, so the failure
path is exercised rather than merely theoretical.

Every reference it generates contains the literal token SIMULATION.
"""

from __future__ import annotations

import random
import time
import uuid
from datetime import date

from agent.payment.protocol import (
    SIMULATION_BIC,
    SIMULATION_IBAN,
    SIMULATION_TOKEN,
    LineItem,
    PaymentError,
    PaymentIntent,
    PaymentResult,
    PaymentStatus,
    split_mwst,
)


class MockPaymentProvider:
    """A believable payment provider that is unmistakably not one."""

    name = "mock"

    def __init__(
        self,
        *,
        latency_seconds: tuple[float, float] = (0.4, 1.1),
        failure_rate: float = 0.0,
        seed: int | None = None,
    ) -> None:
        self.latency_seconds = latency_seconds
        self.failure_rate = failure_rate
        self._rng = random.Random(seed)
        self._intents: dict[str, PaymentIntent] = {}

    # ------------------------------------------------------------------ helpers

    def _sleep(self) -> None:
        low, high = self.latency_seconds
        if high > 0:
            time.sleep(self._rng.uniform(low, high))

    def _reference(self, praefix: str) -> str:
        """A reference that cannot be mistaken for a real one.

        The token is in the middle rather than appended, so it survives truncation in
        a narrow column and cannot be cropped off the end of a screenshot.
        """
        stamp = date.today().strftime("%Y%m%d")
        tail = f"{self._rng.randrange(16**6):06X}"
        return f"{praefix}-{SIMULATION_TOKEN}-{stamp}-{tail}"

    # ------------------------------------------------------------------ interface

    def create_intent(
        self, positionen: list[LineItem], referenz_praefix: str = "FB"
    ) -> PaymentIntent:
        brutto = sum(p.gesamt_cent for p in positionen)
        netto, mwst = split_mwst(brutto)
        intent = PaymentIntent(
            id=str(uuid.uuid4()),
            referenz=self._reference(referenz_praefix),
            betrag_brutto_cent=brutto,
            betrag_netto_cent=netto,
            mwst_cent=mwst,
            positionen=list(positionen),
        )
        self._intents[intent.id] = intent
        return intent

    def confirm(self, intent: PaymentIntent) -> PaymentResult:
        self._sleep()
        stored = self._intents.get(intent.id, intent)

        if self._rng.random() < self.failure_rate:
            fehler = self._rng.choice(list(PaymentError))
            stored.status = PaymentStatus.FEHLGESCHLAGEN
            self._intents[stored.id] = stored
            return PaymentResult(
                intent_id=stored.id,
                status=PaymentStatus.FEHLGESCHLAGEN,
                referenz=stored.referenz,
                erfolgreich=False,
                fehler=fehler,
                meldung=f"Simulierte Zahlung fehlgeschlagen: {fehler.value}.",
            )

        stored.status = PaymentStatus.BESTAETIGT
        self._intents[stored.id] = stored
        return PaymentResult(
            intent_id=stored.id,
            status=PaymentStatus.BESTAETIGT,
            referenz=stored.referenz,
            erfolgreich=True,
            meldung=(
                "SIMULATION. Es wurde kein Geld bewegt, keine Bank kontaktiert und "
                "keine Zahlung ausgelöst."
            ),
            iban=SIMULATION_IBAN,
            bic=SIMULATION_BIC,
        )

    def get_status(self, intent_id: str) -> PaymentStatus:
        intent = self._intents.get(intent_id)
        return intent.status if intent else PaymentStatus.FEHLGESCHLAGEN

    def refund(self, intent_id: str) -> PaymentResult:
        self._sleep()
        intent = self._intents.get(intent_id)
        if intent is None:
            return PaymentResult(
                intent_id=intent_id,
                status=PaymentStatus.FEHLGESCHLAGEN,
                referenz=f"UNBEKANNT-{SIMULATION_TOKEN}",
                erfolgreich=False,
                fehler=PaymentError.ABGELEHNT,
                meldung="Unbekannte Zahlung, nichts zu erstatten.",
            )
        intent.status = PaymentStatus.ERSTATTET
        return PaymentResult(
            intent_id=intent_id,
            status=PaymentStatus.ERSTATTET,
            referenz=intent.referenz,
            erfolgreich=True,
            meldung="SIMULATION. Erstattung simuliert, es wurde kein Geld bewegt.",
        )
