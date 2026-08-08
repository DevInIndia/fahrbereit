"""A development response cache keyed on the prompt.

Re-running the same test conversation twenty times must not cost twenty times the
quota. Backed by SQLite so it survives a process restart, which is the whole point
during development.

This is a `langchain_core` interface, not a vendor interface, so importing it here
does not breach the provider seam.
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
import threading
from pathlib import Path
from typing import Any, Optional, Sequence

from langchain_core.caches import BaseCache
from langchain_core.load import dumps, loads
from langchain_core.outputs import Generation

DEFAULT_PATH = "state/model_cache.sqlite"


def _key(prompt: str, llm_string: str) -> str:
    return hashlib.sha256(f"{llm_string}\x00{prompt}".encode("utf-8")).hexdigest()


class SqliteResponseCache(BaseCache):
    """Prompt hash to serialised generations.

    Deliberately minimal. It stores what a prompt produced and hands it back, so a
    repeated development run is free. It is not a semantic cache and makes no attempt
    to match similar prompts.
    """

    def __init__(self, path: str | Path = DEFAULT_PATH) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=10, isolation_level=None)

    def _init_db(self) -> None:
        with self._lock, self._connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute(
                "CREATE TABLE IF NOT EXISTS response_cache ("
                "  key TEXT PRIMARY KEY,"
                "  generations TEXT NOT NULL"
                ")"
            )

    def lookup(self, prompt: str, llm_string: str) -> Optional[Sequence[Generation]]:
        with self._lock, self._connect() as db:
            row = db.execute(
                "SELECT generations FROM response_cache WHERE key = ?",
                (_key(prompt, llm_string),),
            ).fetchone()
        if row is None:
            return None
        try:
            return [loads(g) for g in loads(row[0])]
        except Exception:
            # A cache that cannot be read is a cache miss, never an error.
            return None

    def update(self, prompt: str, llm_string: str, return_val: Sequence[Generation]) -> None:
        try:
            payload = dumps([dumps(g) for g in return_val])
        except Exception:
            return
        with self._lock, self._connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO response_cache (key, generations) VALUES (?, ?)",
                (_key(prompt, llm_string), payload),
            )

    def clear(self, **kwargs: Any) -> None:
        with self._lock, self._connect() as db:
            db.execute("DELETE FROM response_cache")


def install_cache_if_enabled() -> bool:
    """Turn the cache on when MODEL_CACHE is set. Returns whether it was installed.

    Off by default for a demonstration, because a cached answer to a question the
    user did not ask is worse than a slow one.
    """
    if os.environ.get("MODEL_CACHE", "0") != "1":
        return False
    from langchain_core.globals import set_llm_cache

    set_llm_cache(SqliteResponseCache(os.environ.get("MODEL_CACHE_PATH", DEFAULT_PATH)))
    return True
