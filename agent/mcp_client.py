"""Our own MCP client to the formular and kasse servers.

Spike A settled the architecture: we host the app bridge ourselves rather than
delegating to the AG-UI MCP Apps middleware. This is the piece that makes that real.
The backend holds an MCP client, reads the `ui://` resource the tool's
`_meta.ui.resourceUri` points at, and proxies tool calls from inside the sandboxed
iframe back to the server that owns them.

Two modes, chosen by configuration:

  remote     MCP_FORMULAR_URL and MCP_KASSE_URL are set, as they are under compose.
             The servers are separate processes and every call crosses the protocol.
  in-process No URLs configured, as in a bare local checkout. The same server objects
             are used directly, so a single `python run_backend.py` still works.

The remote path is the real one and is what the containers run. The fallback exists so
that a reader who has not installed Docker can still see the thing work.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Optional

log = logging.getLogger("fahrbereit.mcp")

FORMULAR_URL = os.environ.get("MCP_FORMULAR_URL", "").strip()
KASSE_URL = os.environ.get("MCP_KASSE_URL", "").strip()

# Which server owns which tool. The bridge refuses anything not listed here, so a
# sandboxed surface cannot reach arbitrary server internals.
TOOL_OWNER: dict[str, str] = {
    "formular_render": "formular",
    "formular_absenden": "formular",
    "formular_daten": "formular",
    "kasse_render": "kasse",
    "kasse_bestaetigen": "kasse",
}

RESOURCE_URI = {
    "formular": "ui://formular/intake.html",
    "kasse": "ui://kasse/checkout.html",
}


def url_for(server: str) -> str:
    return {"formular": FORMULAR_URL, "kasse": KASSE_URL}.get(server, "")


def remote_enabled() -> bool:
    return bool(FORMULAR_URL and KASSE_URL)


# ------------------------------------------------------------------ remote


async def _remote_call(server: str, tool: str, args: dict[str, Any]) -> str:
    from mcp import Client

    # mcp 2.0's Client takes the URL directly and builds the streamable HTTP
    # transport itself. An earlier version of this file imported a helper that does
    # not exist in 2.0, which made every remote call fall back silently while the
    # health endpoint still reported "remote". Hence LAST_ERROR below.
    async with Client(url_for(server), raise_exceptions=True) as client:
        return _text(await client.call_tool(tool, args))


async def _remote_resource(server: str) -> str:
    from mcp import Client

    async with Client(url_for(server), raise_exceptions=True) as client:
        content = await client.read_resource(RESOURCE_URI[server])
        for item in getattr(content, "contents", []):
            text = getattr(item, "text", None)
            if text:
                return text
    return ""


def _text(result: Any) -> str:
    for block in getattr(result, "content", []) or []:
        text = getattr(block, "text", None)
        if text:
            return text
    return ""


def _run(coro):
    """Run an async MCP call from a synchronous request handler."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    # Already inside a loop: hand the work to a private one on another thread.
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


# ------------------------------------------------------------------ in-process


def _local_call(tool: str, args: dict[str, Any]) -> str:
    from mcpapps.formular import server as formular
    from mcpapps.kasse import server as kasse

    handlers = {
        "formular_render": formular.formular_render,
        "formular_absenden": formular.formular_absenden,
        "formular_daten": formular.formular_daten,
        "kasse_render": kasse.kasse_render,
        "kasse_bestaetigen": kasse.kasse_bestaetigen,
    }
    handler = handlers[tool]
    inner = getattr(handler, "fn", None) or getattr(handler, "__wrapped__", handler)
    return inner(**args)


# ------------------------------------------------------------------ public


def call_tool(tool: str, args: dict[str, Any]) -> str:
    """Call a tool on whichever server owns it."""
    server = TOOL_OWNER.get(tool)
    if server is None:
        raise KeyError(tool)

    if remote_enabled():
        try:
            return _run(_remote_call(server, tool, args))
        except Exception as exc:  # noqa: BLE001
            # A dead MCP server must not take the whole interface down mid demo, but
            # a silent fallback is worse than a loud one: it looks like the protocol
            # is working when it is not.
            global LAST_ERROR, FELL_BACK
            LAST_ERROR = f"{tool} -> {url_for(server)}: {exc}"
            FELL_BACK = True
            log.error("MCP call fell back to in-process. %s", LAST_ERROR)
            return _local_call(tool, args)
    return _local_call(tool, args)


def surface_html(server: str, args: dict[str, Any]) -> tuple[str, str]:
    """The rendered surface, plus the ui:// identifier it belongs to."""
    tool = "formular_render" if server == "formular" else "kasse_render"
    return RESOURCE_URI[server], call_tool(tool, args)


def resource_shell(server: str) -> str:
    """Read the registered ui:// resource itself, over the protocol where possible.

    Not used to render, since the surface needs per request parameters. It exists so
    the `_meta.ui.resourceUri` path can be exercised and verified rather than assumed.
    """
    if remote_enabled():
        try:
            return _run(_remote_resource(server))
        except Exception as exc:  # noqa: BLE001
            global LAST_ERROR, FELL_BACK
            LAST_ERROR = f"resource {server}: {exc}"
            FELL_BACK = True
            log.error("MCP resource read fell back. %s", LAST_ERROR)
    from mcpapps.formular import server as formular
    from mcpapps.kasse import server as kasse

    module = formular if server == "formular" else kasse
    return module.apps  # type: ignore[return-value]


# Set whenever a remote call falls back. Reported by /api/health, because a fallback
# that nothing surfaces is indistinguishable from the protocol working.
LAST_ERROR: Optional[str] = None
FELL_BACK = False


def mode() -> str:
    """What the MCP path is actually doing, not what it was configured to do."""
    if not remote_enabled():
        return "in-process"
    return "remote-degraded" if FELL_BACK else "remote"


def last_error() -> Optional[str]:
    return LAST_ERROR
