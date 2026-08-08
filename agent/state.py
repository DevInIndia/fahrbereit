"""Interview state: typed slots that remember where their values came from.

The provenance wrapper is the point. An interface that cannot distinguish what the
user said from what the agent worked out cannot show its inferences, and an agent
that cannot show its inferences cannot be corrected. Everything else here follows
from that.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Generic, Iterable, Optional, TypeVar

from pydantic import BaseModel, Field

from agent.listing import KATEGORIEN

T = TypeVar("T")


class Provenance(str, Enum):
    STATED = "stated"      # the user said it
    INFERRED = "inferred"  # the agent worked it out and must show its working
    DEFAULT = "default"    # nobody chose it, we assumed it


class Phase(str, Enum):
    INTERVIEW = "interview"
    SUCHE = "suche"
    BEWERTUNG = "bewertung"
    EMPFEHLUNG = "empfehlung"
    FORMULAR = "formular"
    KASSE = "kasse"
    ABGESCHLOSSEN = "abgeschlossen"


class Intent(str, Enum):
    KAUF = "kauf"
    MIETE = "miete"
    UNENTSCHIEDEN = "unentschieden"


class UseCaseTag(str, Enum):
    PENDELN = "pendeln"
    FAMILIE = "familie"
    STADTVERKEHR = "stadtverkehr"
    LANGSTRECKE = "langstrecke"
    UMZUG = "umzug"
    WOCHENENDE = "wochenende"
    GEWERBLICH = "gewerblich"


class Dimension(str, Enum):
    """The scoring dimensions. Named because the user sees these names."""

    PREIS_SPIELRAUM = "preis_spielraum"
    GESAMTKOSTEN = "gesamtkosten"
    ALTER_LAUFLEISTUNG = "alter_laufleistung"
    EINSATZZWECK = "einsatzzweck"
    ZUSTAND = "zustand"
    ENTFERNUNG = "entfernung"


class Slot(BaseModel, Generic[T]):
    """One answer, plus how we came to believe it."""

    value: Optional[T] = None
    provenance: Optional[Provenance] = None
    confidence: float = 1.0
    confirmed: bool = False
    source: Optional[str] = None
    updated_at: Optional[datetime] = None

    @property
    def is_set(self) -> bool:
        return self.value is not None

    @property
    def needs_confirmation(self) -> bool:
        """An inference the user has not yet seen and accepted."""
        return self.is_set and self.provenance is Provenance.INFERRED and not self.confirmed

    def state(self, value: T, source: str | None = None) -> "Slot[T]":
        return Slot[T](
            value=value,
            provenance=Provenance.STATED,
            confidence=1.0,
            confirmed=True,
            source=source,
            updated_at=datetime.now(timezone.utc),
        )

    def infer(self, value: T, confidence: float = 0.7, source: str | None = None) -> "Slot[T]":
        """Never overwrites a stated value. An inference cannot outrank a statement."""
        if self.provenance is Provenance.STATED:
            return self
        return Slot[T](
            value=value,
            provenance=Provenance.INFERRED,
            confidence=confidence,
            confirmed=False,
            source=source,
            updated_at=datetime.now(timezone.utc),
        )

    def confirm(self) -> "Slot[T]":
        return self.model_copy(update={"confirmed": True, "updated_at": datetime.now(timezone.utc)})


class Budget(BaseModel):
    max_kaufpreis_eur: Optional[int] = None
    max_monatsrate_eur: Optional[int] = None
    max_tagessatz_eur: Optional[int] = None
    max_gesamtmiete_eur: Optional[int] = None

    def ceiling_for(self, intent: Intent) -> Optional[int]:
        if intent is Intent.MIETE:
            return self.max_tagessatz_eur
        return self.max_kaufpreis_eur


class HardConstraints(BaseModel):
    """Boolean requirements. A listing either satisfies these or it is excluded."""

    getriebe: Optional[str] = None
    kraftstoff: Optional[list[str]] = None
    min_sitzplaetze: Optional[int] = None
    min_kofferraum_liter: Optional[int] = None
    umweltplakette: Optional[str] = None
    max_kilometerstand: Optional[int] = None
    unfallfrei_erforderlich: bool = False
    max_entfernung_km: Optional[int] = None


class Location(BaseModel):
    plz: Optional[str] = None
    ort: Optional[str] = None
    max_entfernung_km: Optional[int] = None


# Which artifacts a slot feeds. Revising a slot invalidates exactly these and
# nothing else. A table rather than logic, because it has to be readable.
INVALIDATION_MAP: dict[str, tuple[str, ...]] = {
    "intent": ("filter_report", "ranking", "selection", "booking", "order"),
    "budget": ("filter_report", "ranking", "selection"),
    "constraints_hard": ("filter_report", "ranking", "selection"),
    "location": ("filter_report", "ranking", "selection"),
    "category_preference": ("filter_report", "ranking", "selection"),
    "jahresfahrleistung_km": ("tco", "ranking"),
    "preferences_soft": ("ranking",),
    "use_case_tags": ("ranking",),
    "target_date": ("availability", "ranking", "order"),
    "use_case_text": (),
}

# Weight presets per use case tag, merged and normalised. Chosen so the emphasis is
# defensible out loud: a commuter cares about running cost, a family about fit.
TAG_WEIGHTS: dict[UseCaseTag, dict[Dimension, float]] = {
    UseCaseTag.PENDELN: {Dimension.GESAMTKOSTEN: 0.35, Dimension.PREIS_SPIELRAUM: 0.20},
    UseCaseTag.FAMILIE: {Dimension.EINSATZZWECK: 0.30, Dimension.ZUSTAND: 0.20},
    UseCaseTag.STADTVERKEHR: {Dimension.EINSATZZWECK: 0.25, Dimension.GESAMTKOSTEN: 0.25},
    UseCaseTag.LANGSTRECKE: {Dimension.GESAMTKOSTEN: 0.30, Dimension.ZUSTAND: 0.25},
    UseCaseTag.UMZUG: {Dimension.EINSATZZWECK: 0.35},
    UseCaseTag.WOCHENENDE: {Dimension.PREIS_SPIELRAUM: 0.30},
    UseCaseTag.GEWERBLICH: {Dimension.GESAMTKOSTEN: 0.30, Dimension.ZUSTAND: 0.25},
}

BASE_WEIGHTS: dict[Dimension, float] = {
    Dimension.PREIS_SPIELRAUM: 0.20,
    Dimension.GESAMTKOSTEN: 0.25,
    Dimension.ALTER_LAUFLEISTUNG: 0.20,
    Dimension.EINSATZZWECK: 0.15,
    Dimension.ZUSTAND: 0.15,
    Dimension.ENTFERNUNG: 0.05,
}


class InterviewState(BaseModel):
    """Everything the agent knows about what this person needs."""

    session_id: str = "local"
    phase: Phase = Phase.INTERVIEW

    intent: Slot[Intent] = Field(default_factory=lambda: Slot[Intent]())
    use_case_text: Slot[str] = Field(default_factory=lambda: Slot[str]())
    use_case_tags: Slot[list[UseCaseTag]] = Field(default_factory=lambda: Slot[list[UseCaseTag]]())
    category_preference: Slot[list[str]] = Field(default_factory=lambda: Slot[list[str]]())
    budget: Slot[Budget] = Field(default_factory=lambda: Slot[Budget]())
    target_date: Slot[date] = Field(default_factory=lambda: Slot[date]())
    date_flexibility_days: Slot[int] = Field(default_factory=lambda: Slot[int]())
    jahresfahrleistung_km: Slot[int] = Field(default_factory=lambda: Slot[int]())
    constraints_hard: Slot[HardConstraints] = Field(
        default_factory=lambda: Slot[HardConstraints]()
    )
    preferences_soft: Slot[dict[str, float]] = Field(
        default_factory=lambda: Slot[dict[str, float]]()
    )
    location: Slot[Location] = Field(default_factory=lambda: Slot[Location]())

    # Derived artifacts, cleared by revision rather than recomputed eagerly.
    invalidated: list[str] = Field(default_factory=list)

    # ------------------------------------------------------------------ slots

    SLOT_NAMES: tuple[str, ...] = ()

    @classmethod
    def slot_names(cls) -> tuple[str, ...]:
        return tuple(INVALIDATION_MAP.keys())

    def slot(self, name: str) -> Slot:
        return getattr(self, name)

    def filled_slots(self) -> dict[str, Slot]:
        return {n: self.slot(n) for n in self.slot_names() if self.slot(n).is_set}

    def missing_slots(self) -> tuple[str, ...]:
        return tuple(n for n in self.slot_names() if not self.slot(n).is_set)

    def unconfirmed_inferences(self) -> dict[str, Slot]:
        return {n: s for n, s in self.filled_slots().items() if s.needs_confirmation}

    def knows(self, name: str) -> bool:
        """The no re-ask rule in one call. Never ask for something already known."""
        return self.slot(name).is_set

    # ------------------------------------------------------------------ revision

    def revise(self, name: str, value: Any, source: str | None = None) -> list[str]:
        """Apply a correction and report exactly what it invalidated.

        A budget change must not discard the interview, and a weight change must not
        re-run the hard filter. That asymmetry is the whole reason this exists.
        """
        if name not in INVALIDATION_MAP:
            raise KeyError(f"{name!r} is not a slot. Known slots: {', '.join(self.slot_names())}")
        current: Slot = self.slot(name)
        setattr(self, name, current.state(value, source=source))
        killed = list(INVALIDATION_MAP[name])
        for artifact in killed:
            if artifact not in self.invalidated:
                self.invalidated.append(artifact)
        return killed

    def clear_invalidation(self, artifact: str) -> None:
        if artifact in self.invalidated:
            self.invalidated.remove(artifact)

    # ------------------------------------------------------------------ weights

    def weights(self) -> dict[Dimension, float]:
        """Weights derived from the interview, normalised to sum to one.

        Shown to the user and adjustable. An explicit preferences_soft overrides the
        derivation entirely, because a stated preference outranks an inferred one
        here for the same reason it does in a slot.
        """
        explicit = self.preferences_soft.value
        if explicit:
            weights = {Dimension(k): float(v) for k, v in explicit.items()}
        else:
            weights = dict(BASE_WEIGHTS)
            for tag in self.use_case_tags.value or []:
                for dimension, bump in TAG_WEIGHTS.get(tag, {}).items():
                    weights[dimension] = weights.get(dimension, 0.0) + bump
        total = sum(weights.values()) or 1.0
        return {d: weights.get(d, 0.0) / total for d in Dimension}

    # ------------------------------------------------------------------ helpers

    def effective_categories(self) -> tuple[str, ...]:
        chosen = self.category_preference.value
        return tuple(chosen) if chosen else KATEGORIEN

    def effective_intent(self) -> Intent:
        return self.intent.value or Intent.KAUF


def tags_from_text(text: str) -> list[UseCaseTag]:
    """Cheap keyword inference over the user's own words.

    Deliberately conservative and deterministic. Everything it produces is marked
    inferred and shown for confirmation, so a wrong guess costs a correction rather
    than a bad recommendation. The model may add to this; it does not replace it.
    """
    lowered = text.lower()
    rules: list[tuple[UseCaseTag, tuple[str, ...]]] = [
        (UseCaseTag.FAMILIE, ("kind", "kinder", "familie", "nachwuchs", "schule", "baby")),
        (UseCaseTag.PENDELN, ("pendeln", "arbeitsweg", "taeglich", "buero", "arbeit")),
        (UseCaseTag.STADTVERKEHR, ("stadt", "innenstadt", "parken", "city", "urban")),
        (UseCaseTag.LANGSTRECKE, ("langstrecke", "autobahn", "weite", "fernreise", "km am stueck")),
        (UseCaseTag.UMZUG, ("umzug", "transport", "sperrig", "anhaenger", "laden")),
        (UseCaseTag.WOCHENENDE, ("wochenende", "freizeit", "ausflug", "hobby")),
        (UseCaseTag.GEWERBLICH, ("firma", "gewerblich", "geschaeft", "betrieb", "dienstwagen")),
    ]
    found = [tag for tag, needles in rules if any(n in lowered for n in needles)]
    return found
