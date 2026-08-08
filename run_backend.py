"""Start the backend with .env loaded.

uvicorn does not read .env, so the API key and the model configuration would be absent
if the server were started directly. This is the entry point the README documents and
the container uses.
"""

from __future__ import annotations

import os
import pathlib


def load_env(path: str = ".env") -> list[str]:
    """Load .env into the process. Existing variables win, so the shell can override."""
    file = pathlib.Path(path)
    if not file.exists():
        return []
    loaded = []
    for line in file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if key and key not in os.environ:
            os.environ[key] = value
            loaded.append(key)
    return loaded


if __name__ == "__main__":
    import uvicorn

    keys = load_env()
    print(f"loaded from .env: {', '.join(keys) if keys else 'nothing'}")
    if not os.environ.get("GOOGLE_API_KEY"):
        print(
            "warning: GOOGLE_API_KEY is not set. The chat will fail; the persona "
            "shortcuts will still work, because they call no model."
        )
    uvicorn.run(
        "agent.server:app",
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8000")),
        log_level="info",
    )
