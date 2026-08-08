"""The agent loop.

`create_deep_agent` with the model from the provider factory, the interview tools, and
a checkpointer wired at construction rather than added when something fails. Spike A
established that the AG-UI bridge calls `graph.aget_state`, which raises
`ValueError: No checkpointer set` on the first request and not at build time, so the
checkpointer is passed here unconditionally.

The agent is built once per language and cached. Conversation continuity comes from
the checkpointer, keyed by thread id; the interview record lives in our own store,
keyed by session id. They share the identifier.
"""

from __future__ import annotations

import functools
import logging
from typing import Any, Optional

from deepagents import create_deep_agent
from langgraph.checkpoint.memory import InMemorySaver

from agent import i18n
from agent.i18n import DEFAULT_LANG, Lang
from agent.model import CallType, RateLimitExceeded, get_model, guard
from agent.prompts.system import system_prompt
from agent.store import CURRENT_SESSION, STORE, current_state
from agent.tools.interview import AGENT_TOOLS

log = logging.getLogger("fahrbereit.session")

# One saver for the process, so a thread's history survives across requests.
CHECKPOINTER = InMemorySaver()


@functools.lru_cache(maxsize=4)
def build_agent(lang: Lang = DEFAULT_LANG):
    """The agent. Cached per language because the system prompt differs."""
    return create_deep_agent(
        model=get_model(CallType.REASONING),
        tools=AGENT_TOOLS,
        system_prompt=system_prompt(lang),
        # Wired at construction. Without it the first request fails, not the build.
        checkpointer=CHECKPOINTER,
    )


def reset_agent() -> None:
    build_agent.cache_clear()


def _text_of(message: Any) -> str:
    """Content arrives as a list of typed blocks, not a string. Spike 0 finding."""
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    parts = []
    for block in content or []:
        if isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text", ""))
        elif isinstance(block, str):
            parts.append(block)
    return " ".join(p for p in parts if p).strip()


class TurnResult:
    def __init__(
        self,
        antwort: str,
        werkzeuge: list[str],
        modellaufrufe: int,
        gedrosselt: bool = False,
    ) -> None:
        self.antwort = antwort
        self.werkzeuge = werkzeuge
        self.modellaufrufe = modellaufrufe
        self.gedrosselt = gedrosselt


def run_turn(session_id: str, nachricht: str, lang: str = DEFAULT_LANG) -> TurnResult:
    """One user turn. Returns the reply plus what the agent did to produce it."""
    normalised = i18n.normalise(lang)
    STORE.set_artifact(session_id, "lang", normalised)

    # The tools are registered once at import, so they cannot close over a session.
    # The id travels in a context variable that the tools read.
    token = CURRENT_SESSION.set(session_id)
    try:
        agent = build_agent(normalised)
        from agent.model import LEDGER

        before = LEDGER.billable_total()
        try:
            with guard(CallType.REASONING):
                out = agent.invoke(
                    {"messages": [{"role": "user", "content": nachricht}]},
                    config={"configurable": {"thread_id": session_id}},
                )
        except RateLimitExceeded as exc:
            log.warning("rate limited: %s", exc)
            return TurnResult(
                antwort=(
                    "Das Kontingent des Modells ist für den Moment erschöpft. "
                    "Die Personen-Schaltflächen links funktionieren weiterhin, sie "
                    "brauchen kein Modell."
                    if normalised == "de"
                    else "The model quota is exhausted for the moment. The persona "
                    "buttons on the left still work; they need no model."
                ),
                werkzeuge=[],
                modellaufrufe=LEDGER.billable_total() - before,
                gedrosselt=True,
            )

        messages = out.get("messages", [])

        # The checkpointer returns the whole thread, so scanning all of it would
        # report every tool call the session has ever made. Only this turn counts:
        # everything after the last human message.
        letzte_frage = max(
            (i for i, m in enumerate(messages) if m.__class__.__name__ == "HumanMessage"),
            default=-1,
        )
        dieser_zug = messages[letzte_frage + 1 :]
        werkzeuge = [
            call["name"]
            for m in dieser_zug
            for call in (getattr(m, "tool_calls", None) or [])
        ]
        antwort = ""
        for message in reversed(dieser_zug or messages):
            if message.__class__.__name__ == "AIMessage":
                antwort = _text_of(message)
                if antwort:
                    break

        return TurnResult(
            antwort=antwort or "",
            werkzeuge=werkzeuge,
            modellaufrufe=LEDGER.billable_total() - before,
        )
    finally:
        CURRENT_SESSION.reset(token)


def ranking_for(session_id: str):
    return STORE.artifact(session_id, "ranking")


def state_for(session_id: str):
    token = CURRENT_SESSION.set(session_id)
    try:
        return current_state()
    finally:
        CURRENT_SESSION.reset(token)
