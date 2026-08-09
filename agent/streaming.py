"""Streaming one agent turn, so progress is live rather than a summary afterwards.

The requirement is live agent progress. Emitting tool badges after the turn finishes
does not meet it: by then there is nothing to watch.

What is streamed is the agent's own structure, not model tokens. Phases, tool calls
and filter counts are already known server side at the moment they happen and cost
nothing extra to publish, so this adds no model calls and spends no quota. Token
streaming would be the expensive option and is not what the requirement needs.

Mechanism: the agent runs on a worker thread with a LangChain callback handler that
drops events onto a queue. The request handler drains that queue and yields server
sent events until the worker signals it is done.
"""

from __future__ import annotations

import json
import logging
import queue
import threading
from typing import Any, Iterator, Optional

from langchain_core.callbacks import BaseCallbackHandler

from agent import i18n, observability
from agent.i18n import DEFAULT_LANG, Lang
from agent.model import CallType, RateLimitExceeded, guard
from agent.session import build_agent
from agent.state import Phase
from agent.store import CURRENT_SESSION, STORE, current_state
from agent.surfaces import fortschritt as fs
from agent.surfaces.katalog import build_messages

log = logging.getLogger("fahrbereit.streaming")

DONE = object()


class ProgressCallback(BaseCallbackHandler):
    """Turns LangChain's tool lifecycle into progress events on a queue."""

    def __init__(self, out: "queue.Queue[Any]", lang: Lang) -> None:
        self.out = out
        self.lang = lang
        self.schritte: list[dict[str, Any]] = []
        self.phase = Phase.INTERVIEW

    def _emit(self, event: str, data: dict[str, Any]) -> None:
        self.out.put({"event": event, "data": data})

    def _set_phase(self, phase: Phase) -> None:
        if phase is not self.phase:
            self.phase = phase
            self._emit("a2ui", {"messages": [fs.phase_message(phase, self.lang)]})

    def on_tool_start(self, serialized: Any, input_str: str, **kwargs: Any) -> None:
        name = (serialized or {}).get("name") or kwargs.get("name") or "werkzeug"
        self._set_phase(fs.TOOL_PHASE.get(name, self.phase))

        self.schritte.append(
            {"werkzeug": name, "label": fs.tool_label(name, self.lang), "status": "laeuft"}
        )
        self._emit("a2ui", {"messages": [fs.strom_message(self.schritte, self.lang)]})
        self._emit("werkzeug", {"name": name, "status": "start"})

        if name == "empfehlungen_erstellen":
            self._emit("a2ui", {"messages": [fs.suche_message(None, self.lang, laeuft=True)]})

    def on_tool_end(self, output: Any, **kwargs: Any) -> None:
        name = kwargs.get("name")
        for schritt in reversed(self.schritte):
            if schritt["status"] == "laeuft" and (name is None or schritt["werkzeug"] == name):
                schritt["status"] = "fertig"
                name = schritt["werkzeug"]
                break

        messages = [fs.strom_message(self.schritte, self.lang)]

        # The interview record may have changed, so refresh the checklist. Only that
        # component is sent, not the whole surface.
        if name in ("interview_merken", "interview_stand"):
            # Runs on the worker thread, which holds the session context variable.
            messages.append(fs.slots_message(current_state(), self.lang))

        if name == "empfehlungen_erstellen":
            result = STORE.artifact(CURRENT_SESSION.get(), "ranking")
            report = getattr(result, "report", None)
            messages.append(fs.suche_message(report, self.lang, laeuft=False))
            if report is not None:
                self._emit(
                    "filter",
                    {"gesamt": report.gesamt, "uebrig": report.uebrig},
                )
            self._set_phase(Phase.EMPFEHLUNG)

        self._emit("a2ui", {"messages": messages})
        self._emit("werkzeug", {"name": name, "status": "fertig"})

    def on_tool_error(self, error: BaseException, **kwargs: Any) -> None:
        for schritt in reversed(self.schritte):
            if schritt["status"] == "laeuft":
                schritt["status"] = "fehler"
                break
        self._emit("a2ui", {"messages": [fs.strom_message(self.schritte, self.lang)]})


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


def stream_turn(session_id: str, nachricht: str, lang: str = DEFAULT_LANG) -> Iterator[str]:
    """Run one turn, yielding server sent events as it goes."""
    normalised = i18n.normalise(lang)
    STORE.set_artifact(session_id, "lang", normalised)

    events: "queue.Queue[Any]" = queue.Queue()
    handler = ProgressCallback(events, normalised)
    ergebnis: dict[str, Any] = {}

    def arbeiten() -> None:
        # The context variable is thread local, so the worker sets it for itself.
        token = CURRENT_SESSION.set(session_id)
        try:
            from agent.model import LEDGER

            before = LEDGER.billable_total()
            agent = build_agent(normalised)
            try:
                with observability.turn_span(
                    session_id, nachricht, normalised
                ), guard(CallType.REASONING):
                    out = agent.invoke(
                        {"messages": [{"role": "user", "content": nachricht}]},
                        config={
                            "configurable": {"thread_id": session_id},
                            "callbacks": [handler],
                        },
                    )
                ergebnis["out"] = out
            except RateLimitExceeded as exc:
                ergebnis["gedrosselt"] = True
                ergebnis["fehler"] = str(exc)
            ergebnis["modellaufrufe"] = LEDGER.billable_total() - before
        except Exception as exc:  # noqa: BLE001
            log.exception("turn failed")
            ergebnis["fehler"] = str(exc)
        finally:
            CURRENT_SESSION.reset(token)
            events.put(DONE)

    worker = threading.Thread(target=arbeiten, daemon=True)

    # No context variable is held across a yield. Starlette drives a sync generator
    # from a thread pool and successive next() calls can land in different contexts,
    # so a token set before a yield cannot be reset after one:
    #   ValueError: <Token ...> was created in a different Context
    # The worker thread sets its own, which is where the tools actually read it.
    def _in_session(fn):
        token = CURRENT_SESSION.set(session_id)
        try:
            return fn()
        finally:
            CURRENT_SESSION.reset(token)

    try:
        state = _in_session(current_state)
        yield _sse("a2ui", {"messages": fs.initial_messages(state, normalised)})
        yield _sse("phase", {"phase": Phase.INTERVIEW.value})

        worker.start()
        while True:
            item = events.get()
            if item is DONE:
                break
            yield _sse(item["event"], item["data"])

        worker.join(timeout=5)

        # The turn is over: send the reply and, if one was produced, the catalogue.
        from agent.session import _text_of

        antwort = ""
        out = ergebnis.get("out")
        if out:
            messages = out.get("messages", [])
            letzte_frage = max(
                (
                    i
                    for i, m in enumerate(messages)
                    if m.__class__.__name__ == "HumanMessage"
                ),
                default=-1,
            )
            for message in reversed(messages[letzte_frage + 1 :] or messages):
                if message.__class__.__name__ == "AIMessage":
                    antwort = _text_of(message)
                    if antwort:
                        break

        if ergebnis.get("gedrosselt"):
            antwort = (
                "Das Kontingent des Modells ist für den Moment erschöpft. Die "
                "Personen-Schaltflächen links funktionieren weiterhin."
                if normalised == "de"
                else "The model quota is exhausted for the moment. The persona buttons "
                "on the left still work."
            )

        result = STORE.artifact(session_id, "ranking")
        if result is not None:
            top_rec = result.empfehlungen[0] if result.empfehlungen else None
            yield _sse(
                "katalog",
                {
                    "messages": build_messages(result, lang=normalised),
                    "top_listing_id": top_rec.listing.id if top_rec else "FB-00001",
                    "top_listing_title": top_rec.listing.bezeichnung if top_rec else "",
                },
            )


        yield _sse(
            "fertig",
            {
                "antwort": antwort or ergebnis.get("fehler", ""),
                "modellaufrufe": ergebnis.get("modellaufrufe", 0),
                "gedrosselt": bool(ergebnis.get("gedrosselt")),
                "werkzeuge": [s["werkzeug"] for s in handler.schritte],
            },
        )
    except Exception as exc:  # noqa: BLE001
        # A failure here would otherwise close the stream with no terminal event and
        # leave the interface waiting forever.
        log.exception("stream failed")
        yield _sse("fertig", {"antwort": str(exc), "modellaufrufe": 0, "werkzeuge": []})
