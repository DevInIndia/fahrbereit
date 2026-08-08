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

This was the specific risk, since Lite variants sometimes handle function calling worse
than their full siblings. It is not a problem here. Given the German prompt "Ich suche
einen Kompaktwagen bis 25000 Euro", `gemini-3.5-flash-lite` emitted:

```
{'name': 'suche_fahrzeuge',
 'args': {'kategorie': 'Kompaktwagen', 'max_preis_eur': 25000},
 'id': '6QjiyQvo', 'type': 'tool_call'}
```

Both arguments extracted correctly from German free text, including the numeric budget.
`gemini-3.1-flash-lite` produced the same result, so the alternate is genuine rather than
nominal.

`create_deep_agent` accepted a `ChatGoogleGenerativeAI` instance directly, confirming that
the object form of the `model` parameter works and that the provider seam is viable.

### Finding that changes the planned routing

**Gemma 4 31B is not usable on any path the user waits on.**

| | `gemini-3.5-flash-lite` | `gemma-4-31b-it` |
|---|---:|---:|
| Same narration prompt | **1.23s** | **19.82s** |

Sixteen times slower on identical work. Two compounding causes:

1. Gemma emits `thinking` content blocks before its answer, and they cannot be turned off.
   Requesting that produces a hard failure:

   ```
   ChatGoogleGenerativeAIError: Error calling model 'gemma-4-31b-it' (INVALID_ARGUMENT):
   400 INVALID_ARGUMENT. {'error': {'code': 400, 'message': 'Thinking budget is not
   supported for this model.', 'status': 'INVALID_ARGUMENT'}}
   ```

2. Those thinking blocks consume the 16,000 TPM ceiling, which is already the tightest
   token budget of any model available to us.

The original plan routed narration, status strings and formatting to Gemma. Narration and
status strings are exactly what a user watches the interface waiting for. A twenty second
pause to render "142 Treffer" would be worse than not having the surface at all.

**Revised routing**, which keeps Gemma's 14,400 daily requests genuinely useful:

- **Interactive**, anything a user waits on, including narration and status: the reasoning
  model. Its latency is around one second.
- **Bulk and offline**, where latency does not matter: Gemma. Evaluation judging, persona
  expansion, and development-time cache warming. This is where a fourteen thousand request
  ceiling actually pays, and it removes eval load from the 500 RPD budget entirely.

The seam keeps both configurable, so this is a default rather than a constraint.

### Incidental findings

- Response `content` is a list of typed blocks, not a string. Text must be extracted from
  blocks where `type == "text"`. Code that assumes `response.content` is a string will
  silently produce wrong output.
- `gemini-3.5-flash-lite` ignores `temperature` and warns about it. Determinism cannot be
  obtained by pinning temperature on this model, which reinforces keeping ranking out of
  the model entirely.

---

## Spike A: MCP App rendering behind an external Python AG-UI endpoint

**Status**: not yet run.

---

## Spike B: A2UI component from an agent emitted message

**Status**: not yet run.
