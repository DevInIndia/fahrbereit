"""Session state, held server side and keyed by session id.

Milestone 1 keeps this in memory behind an interface a persistent implementation can
satisfy later, so M-7's durability requirement is a swap rather than a refactor.

LangGraph's checkpointer handles conversation continuity, the message history. This
holds the interview record and the derived artifacts, which are ours: the checkpointer
knows nothing about slot provenance or the invalidation map.
"""

from __future__ import annotations

import threading
from contextvars import ContextVar
from typing import Any, Optional, Protocol

from agent.state import InterviewState

# The tools the model calls are registered once at import time, so they cannot close
# over a session. The current session id is carried per request instead.
CURRENT_SESSION: ContextVar[str] = ContextVar("fahrbereit_session", default="default")


class SessionStore(Protocol):
    def load(self, session_id: str) -> InterviewState: ...
    def save(self, state: InterviewState) -> None: ...
    def artifact(self, session_id: str, key: str) -> Any: ...
    def set_artifact(self, session_id: str, key: str, value: Any) -> None: ...
    def clear(self, session_id: str) -> None: ...


class InMemorySessionStore:
    """Milestone 1. Survives a page reload, not a process restart."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._states: dict[str, InterviewState] = {}
        self._artifacts: dict[str, dict[str, Any]] = {}

    def load(self, session_id: str) -> InterviewState:
        with self._lock:
            state = self._states.get(session_id)
            if state is None:
                state = InterviewState(session_id=session_id)
                self._states[session_id] = state
            return state

    def save(self, state: InterviewState) -> None:
        with self._lock:
            self._states[state.session_id] = state

    def artifact(self, session_id: str, key: str) -> Any:
        with self._lock:
            return self._artifacts.get(session_id, {}).get(key)

    def set_artifact(self, session_id: str, key: str, value: Any) -> None:
        with self._lock:
            self._artifacts.setdefault(session_id, {})[key] = value

    def clear(self, session_id: str) -> None:
        with self._lock:
            self._states.pop(session_id, None)
            self._artifacts.pop(session_id, None)


STORE: SessionStore = InMemorySessionStore()


def current_state() -> InterviewState:
    return STORE.load(CURRENT_SESSION.get())


def save_state(state: InterviewState) -> None:
    STORE.save(state)
