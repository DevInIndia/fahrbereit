/**
 * Host for an MCP App surface.
 *
 * We hold the bridge ourselves rather than delegating to the AG-UI MCP Apps
 * middleware, per the Path 2 decision in docs/spike-notes.md. The surface HTML comes
 * from a `ui://` resource served by the MCP server; we render it in a sandboxed
 * iframe and relay `window.mcp.callTool` over postMessage to the server's tools.
 *
 * The sandbox grants scripts and nothing else. No same-origin, so the surface cannot
 * reach this document, its storage, or its cookies. Everything it can do, it does
 * through the bridge, which only accepts named tools.
 */

import { useEffect, useRef, useState } from "react";
import { type Lang, t } from "./i18n";

const BRIDGE_SHIM = `
<script>
(() => {
  const pending = new Map();
  let seq = 0;
  window.mcp = {
    callTool(tool, args) {
      const id = "c" + (++seq);
      return new Promise((resolve, reject) => {
        pending.set(id, { resolve, reject });
        parent.postMessage({ __mcpBridge: true, id, tool, args }, "*");
      });
    },
  };
  window.addEventListener("message", (event) => {
    const data = event.data;
    if (!data || !data.__mcpBridgeReply) return;
    const entry = pending.get(data.id);
    if (!entry) return;
    pending.delete(data.id);
    data.error ? entry.reject(data.error) : entry.resolve(data.result);
  });
  const post = () => parent.postMessage(
    { __mcpBridgeHeight: true, height: document.documentElement.scrollHeight }, "*");
  new ResizeObserver(post).observe(document.documentElement);
  setTimeout(post, 40);
})();
<\/script>
`;

type Props = {
  endpoint: string;
  title: string;
  lang: Lang;
  onToolResult?: (tool: string, result: string) => void;
};

export function AppFrame({ endpoint, title, lang, onToolResult }: Props) {
  const [html, setHtml] = useState<string | null>(null);
  const [meta, setMeta] = useState<{ resourceUri: string; mimeType: string } | null>(null);
  const [height, setHeight] = useState(420);
  const [error, setError] = useState<string | null>(null);
  const frameRef = useRef<HTMLIFrameElement>(null);

  useEffect(() => {
    let cancelled = false;
    setHtml(null);
    setError(null);
    fetch(endpoint)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((data) => {
        if (cancelled) return;
        setMeta({ resourceUri: data.resourceUri, mimeType: data.mimeType });
        setHtml(String(data.html).replace("</head>", `${BRIDGE_SHIM}</head>`));
      })
      .catch((e) => !cancelled && setError(String(e)));
    return () => {
      cancelled = true;
    };
  }, [endpoint]);

  useEffect(() => {
    async function onMessage(event: MessageEvent) {
      const data = event.data;
      if (data?.__mcpBridgeHeight) {
        setHeight(Math.max(240, Math.min(1400, data.height + 24)));
        return;
      }
      if (!data?.__mcpBridge) return;
      const target = frameRef.current?.contentWindow;
      try {
        const res = await fetch("/api/app/bridge", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ tool: data.tool, args: data.args ?? {} }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const payload = await res.json();
        onToolResult?.(data.tool, payload.result);
        target?.postMessage(
          { __mcpBridgeReply: true, id: data.id, result: payload.result }, "*");
      } catch (e) {
        target?.postMessage(
          { __mcpBridgeReply: true, id: data.id, error: String(e) }, "*");
      }
    }
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, [onToolResult]);

  return (
    <section className="panel appframe">
      <div className="eyebrow">
        MCP App · {title}
        {meta ? <span className="dim"> · {meta.resourceUri}</span> : null}
      </div>
      {error ? (
        <p className="err">{t("ladenFehlgeschlagen", lang)}: {error}</p>
      ) : null}
      {html === null && !error ? <p className="dim">{t("wirdGeladen", lang)}</p> : null}
      {html !== null && (
        <iframe
          ref={frameRef}
          title={title}
          srcDoc={html}
          sandbox="allow-scripts"
          style={{ width: "100%", height, border: "1px solid var(--rule)" }}
        />
      )}
    </section>
  );
}
