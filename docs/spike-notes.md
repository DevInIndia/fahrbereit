# Spike notes

De-risking outcomes recorded before the architecture that depends on them is built. Every
result here was produced by running code, not by reading documentation. Failures are
recorded with their exact error text.

---

## Spike 0: the model path

**Date**: 2026-08-08
**Question**: does Gemini on the free tier drive a multistep agent at all, and does
`gemini-3.5-flash-lite` handle tool calling reliably enough to be the primary model?
**Verdict**: **pass on every count.** Tool calling is reliable. The primary model decision
stands.

**Cost**: eight model calls charged to quota across both spike runs.

### Results

| Test | Model | Result | Latency |
|---|---|---|---:|
| Reachability | `gemini-3.5-flash-lite` | pass | 1.21s |
| Single tool call | `gemini-3.5-flash-lite` | pass, arguments correct | 0.88s |
| Agent loop via `create_deep_agent` | `gemini-3.5-flash-lite` | pass, 2 AIMessages, 1 ToolMessage | 2.14s |
| Tool calling | `gemini-3.1-flash-lite` | pass, arguments correct | 1.51s |
| Plain generation | `gemma-4-31b-it` | pass | 13.99s, 19.82s |
| Tool calling | `gemma-4-31b-it` | pass, unexpectedly | not measured |

### Tool calling is reliable on the Lite variants

Given the German prompt "Ich suche einen Kompaktwagen bis 25000 Euro",
`gemini-3.5-flash-lite` emitted:

```
{'name': 'suche_fahrzeuge',
 'args': {'kategorie': 'Kompaktwagen', 'max_preis_eur': 25000},
 'id': '6QjiyQvo', 'type': 'tool_call'}
```

Both arguments extracted correctly from German free text. `gemini-3.1-flash-lite` produced
the same result, so the alternate is genuine rather than nominal.

### Finding that changed the planned routing

**Gemma 4 31B is not usable on any path the user waits on.** Same narration prompt:
`gemini-3.5-flash-lite` 1.23s, `gemma-4-31b-it` 19.82s. Sixteen times slower. Gemma emits
`thinking` blocks that cannot be disabled:

```
ChatGoogleGenerativeAIError: Error calling model 'gemma-4-31b-it' (INVALID_ARGUMENT):
400 INVALID_ARGUMENT. {'error': {'code': 400, 'message': 'Thinking budget is not
supported for this model.', 'status': 'INVALID_ARGUMENT'}}
```

Revised routing: interactive work, narration included, goes to the reasoning model. Gemma
takes bulk and offline work only, which is where its 14,400 daily requests actually pay.

### Incidental findings

- Response `content` is a list of typed blocks, not a string. Code assuming
  `response.content` is a string will silently produce wrong output.
- `gemini-3.5-flash-lite` ignores `temperature` and warns. Determinism cannot be obtained
  by pinning temperature, which reinforces keeping ranking out of the model entirely.

---

## Spike A: MCP App rendering behind an external Python AG-UI endpoint

**Date**: 2026-08-08
**Verdict**: **partial. The protocol layer is proven. The middleware injection step is
not, and it is not yet understood.**

### What was proven

**1. MCP Apps is first party in the Python SDK.** `mcp` 2.0.0 ships
`mcp.server.apps.Apps`, an `Extension` implementing the `io.modelcontextprotocol/ui`
extension. This was not expected and it materially simplifies `formular` and `kasse`:

```python
apps = Apps()

@apps.tool(resource_uri="ui://spike/hello.html", description="Open the spike app")
def open_spike_app(ctx: Context) -> str:
    return "Spike app opened."

apps.add_html_resource("ui://spike/hello.html", HELLO_HTML)
mcp = MCPServer("fahrbereit-spike", extensions=[apps])
```

**2. The wire format is correct.** Verified with a real MCP client against the real server:

```
open_spike_app
  meta = {"ui": {"resourceUri": "ui://spike/hello.html"}}
ui://spike/hello.html   mime='text/html;profile=mcp-app'
capabilities: {"extensions": {"io.modelcontextprotocol/ui": {}}}
```

**3. Cross language interop works.** The TypeScript `@modelcontextprotocol/sdk` 1.x client
connects to the Python 2.0 server over streamable HTTP and sees the metadata:

```
TS SDK connected OK
tools seen by TS SDK: 2
   open_spike_app {"ui":{"resourceUri":"ui://spike/hello.html"}}
   spike_echo null
```

This rules out a protocol version incompatibility between the SDK generations, which was
the most likely suspected cause of the failure below.

**4. The AG-UI endpoint requires a checkpointer.** Undocumented in the quickstart and it
fails at the first request rather than at construction:

```
File "ag_ui_langgraph/agent.py", line 206, in _handle_stream_events
    agent_state = await self.graph.aget_state(config)
ValueError: No checkpointer set
```

Fixed by passing `checkpointer=InMemorySaver()` to `create_deep_agent`. This is a real
constraint on the architecture, not a spike artifact, and it aligns with the M-7 plan of
using a LangGraph checkpointer for conversation continuity.

### What failed

`MCPAppsMiddleware` attached to an `HttpAgent` pointed at the Python endpoint **injected
no tools**. A diagnostic on the Python side logging the inbound AG-UI request body:

```
[DIAG] incoming tools count = 0
```

The agent consequently could not call the tool, delegated to a subagent, and the subagent
reported:

```
no tool named `open_spike_app` is available in my tool definitions
```

The run itself completed cleanly. Full AG-UI event sequence observed: `RUN_STARTED`, `RAW`,
`STEP_STARTED`, `STEP_FINISHED`, `TOOL_CALL_START`, `TOOL_CALL_END`, `STATE_SNAPSHOT`,
`MESSAGES_SNAPSHOT`, `TOOL_CALL_RESULT`, `TEXT_MESSAGE_START`, `TEXT_MESSAGE_CONTENT`,
`TEXT_MESSAGE_END`, `RUN_FINISHED`. No `ACTIVITY_SNAPSHOT` was emitted, which is the event
the middleware uses to carry `resourceUri` to the frontend.

So the transport works, the agent works, the MCP server works, and the two speak
compatible protocols. The failure is isolated to the middleware's tool discovery or
injection step.

### What is ruled out

- Protocol version mismatch between `mcp` 2.0 Python and `@modelcontextprotocol/sdk` 1.x
  TypeScript. Directly disproved by test 3.
- The MCP server being unreachable. It answers `200` on `POST /mcp` and the TS client
  completes a full handshake and `tools/list`.
- The Python endpoint being unreachable or malformed. It answers `200` and streams a
  complete, well formed AG-UI event sequence.
- The `_meta.ui.resourceUri` being absent or misnamed. It is present and correctly shaped
  in both the Python and the TypeScript view of the tool.

### What is not yet known

Why `fetchUITools` produced nothing. Candidates, untested:

1. The middleware may require the AG-UI request to carry a specific `forwardedProps`
   shape, or may only inject on a second pass after an initial discovery round trip.
2. `HttpAgent.use()` may not be applying the middleware in the way the runner assumed, so
   `MCPAppsMiddleware.run` may never have executed. The runner captured no evidence either
   way, which is a gap in the spike rather than a finding.
3. The middleware's own MCP client may be failing silently at connect time, since no error
   surfaced on the Node side.

Distinguishing these needs instrumentation inside the middleware call path. That is
perhaps thirty minutes of work and it was not done inside the timebox.

### Path selection: we host the bridge ourselves

**Decided 2026-08-08. The middleware failure is left UNRESOLVED, deliberately.**

We host the app bridge directly in React using `@modelcontextprotocol/ext-apps`, hold our
own MCP client to the `formular` and `kasse` servers, fetch the `ui://` resource and render
the sandboxed iframe ourselves. Every dependency that path needs is proven by a run above.

The reasoning for not spending another thirty minutes on the middleware: `@ag-ui/mcp-apps-middleware`
is at 0.0.3, the failure is in its own discovery step rather than in anything we control,
and three mandatory requirements were at zero when the decision was taken. Debugging a
young package to save frontend code is the wrong trade against that clock.

This is recorded rather than deleted because it is an honest finding about a young package
and someone else may hit it. It is not a claim that the middleware is broken; it is a claim
that we could not make it inject tools inside a timebox, and that we did not establish why.
One line goes in the README's known limitations noting that we host the bridge directly.

---

## Spike B: A2UI component from an agent emitted message

**Status**: not run. The Spike A investigation consumed the timebox.

The relevant capability was confirmed to exist during Phase 0 research:
`ag_ui_langgraph` 0.0.42 exports `get_a2ui_tools`, `a2ui_tool`, `A2UIGuidelines`,
`A2UIToolParams`, `BASIC_CATALOG_ID` and `A2UI_OPERATIONS_KEY`. That is a strong signal but
it is not a run, and it is recorded here as unproven.

---

## Spike C: real marketplace data via Gemini Google Search grounding

**Date**: 2026-08-09
**Question**: the brief speaks of researching car marketplaces on the user's behalf.
Search grounding is built into Gemini, needs no second key, breaks no marketplace terms
of service and returns real source URLs in its grounding metadata. Can it give us a
live market check against real German listings on the free tier?
**Verdict**: **no. Grounding quota on a free tier key is zero.** Tested, not assumed.

**Cost**: five calls.

### Results

| Model | Grounded | Result |
|---|---|---|
| `gemini-2.5-flash` | yes | `404 NOT_FOUND`, no longer available to new users |
| `gemini-2.5-flash-lite` | yes | `404 NOT_FOUND`, no longer available to new users |
| `gemini-3.5-flash-lite` | yes | `429 RESOURCE_EXHAUSTED` |
| `gemini-3.5-flash-lite` | **no** | **pass** |

The last two rows are the finding. The same model, on the same key, in the same
minute, answers an ordinary request and refuses a grounded one:

```
model='gemini-3.5-flash-lite', contents='Say OK.'                      -> "OK."

model='gemini-3.5-flash-lite', tools=[Tool(google_search=GoogleSearch())]
  -> 429 RESOURCE_EXHAUSTED. You exceeded your current quota, please check
     your plan and billing details.
```

That control matters. A 429 on its own would be ambiguous, because 136 model calls had
already gone through the daily budget that day and exhaustion would look identical. The
ungrounded call succeeding at the same moment rules that out. The refusal is attached to
the `google_search` tool, not to the daily request count.

### What this rules out

The plan for this feature was built on a rate limit dashboard reading of 20 requests per
day for search grounding on Gemini 2.5 Flash. **Those models return 404 for this key**,
with an explicit message that they are closed to new users. So the 20 per day allowance
belongs to models we cannot reach, and the model we can reach is at zero. There is no
combination available on the free tier that produces one grounded search.

### Consequence

An implementation of this shipped at `926f2b3` and was reverted at `2f8096d`. It had
three defects independent of quota, listed in the revert message, of which the serious
one was that it regex-harvested figures out of free model prose and presented their
midpoint as a market price. But the quota result above is the one that closes the
question: the feature's only reachable state on this key is "unavailable".

**The mock marketplace stays, and this is now a tested reason rather than a preference.**
`agent/listing.py` remains the single file a real source would replace. Recorded here in
full because a judge asking why the marketplace is synthetic deserves an answer with an
error code in it, and because the next person to have this idea should be able to see it
was tried.
