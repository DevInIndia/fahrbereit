# fahrbereit

A conversational agent that helps someone in Germany choose a car to buy or rent. You
describe your situation in your own words; it asks a couple of follow-up questions,
works out what it can from what you said, then filters a marketplace of 280 listings
and explains its ranking with numbers you can check. It ends with an intake form and a
checkout that are rendered inside the conversation, and the checkout is a simulation
from end to end.

The interesting part is what the model is not allowed to do. Filtering, scoring and
cost of ownership are ordinary Python, computed before anything is said. The model
reads those numbers and narrates them; it never produces them, and it is instructed to
say a figure is missing rather than supply a plausible one.

---

## Quickstart

Written for someone who has not used Docker before. Every command here has been run
from a clean clone.

### 1. Install Docker Desktop

Download it from `https://www.docker.com/products/docker-desktop/` and install it.
Start it, and wait until its whale icon stops animating. Docker Desktop must be
**running**, not just installed, or the commands below will report that they cannot
reach the Docker daemon.

Check it is working:

```bash
docker --version
```

```bash
docker compose version
```

Verified against Docker `28.3.0` and Compose `v2.38.1`. Anything from Docker 24 and
Compose v2 should work. If `docker compose version` fails but `docker-compose
--version` succeeds you have the old standalone tool; install a current Docker Desktop.

### 2. Get a free API key

Go to `https://aistudio.google.com/apikey`, sign in with a Google account, and create
an API key. It is free and needs no credit card.

The interface runs without a key. The conversation does not, so get one.

### 3. Configure

From the project folder:

```bash
cp .env.example .env
```

Open `.env` in any text editor and paste your key after `GOOGLE_API_KEY=`, so the line
reads `GOOGLE_API_KEY=AIza...`. Change nothing else. `.env` is gitignored and must
never be committed.

### 4. Start it

```bash
docker compose up --build
```

The first run downloads base images and installs dependencies, which takes a few
minutes. Later runs take seconds. Leave the terminal open; the services log to it.

### 5. Open it

**http://localhost:8080**

### What you should see

A dark, two-column page. On the left: a language toggle, three demo personas, weighting
controls, and an interview panel. On the right: a conversation box at the top, and
below it the results.

To check it is working end to end:

1. Click **Familie** in the left column. Six ranked cars appear within a second, the
   first one already expanded showing its score breakdown. This path uses no model, so
   it proves the ranking engine and the interface without spending any quota.
2. Type into the conversation box, for example *"I need a car for my family with two
   children, budget 25000 euro"*, and press **Send**. After a few seconds the agent
   replies, small badges appear under its answer naming the tools it called, and the
   ranked list below updates from its result.
3. Click **Checkout** in the left column. A simulated invoice appears with an orange
   SIMULATION banner across the top.

If all three work, everything is running.

### To stop it

Press `Ctrl+C` in the terminal, then:

```bash
docker compose down
```

### When it does not work

**"docker: command not found" or "cannot connect to the Docker daemon"**
Docker Desktop is not running. Start it and wait for the whale icon to settle.

**Port 8080 is already in use**
Something else on your machine has the port. Either stop it, or edit
`docker-compose.yml` and change the `ui` service's `ports` line from `"8080:80"` to
`"8090:80"`, then open `http://localhost:8090` instead.

**The page loads but the conversation returns an error**
Almost always a missing or wrong API key. Check with:

```bash
curl http://localhost:8080/api/health
```

You should see `"status":"ok"`. If you do, the backend is fine and the key is the
problem: confirm `GOOGLE_API_KEY=` in `.env` has a value, then `docker compose up -d
--build` to pick it up. The persona buttons keep working regardless, because they call
no model.

**The conversation says the quota is exhausted**
The free tier allows 500 model requests a day and a turn costs three or four. Use the
persona buttons, or come back tomorrow.

**Changes to the code are not showing up**
Compose caches builds. Rebuild explicitly:

```bash
docker compose up -d --build
```

---

## How the containers fit together

Four services on one Docker network. You only ever open one of them.

```
                     browser
                        |
                 http://localhost:8080
                        |
              +---------v---------+
              |        ui         |   nginx: serves the built interface,
              |   (port 80)       |   proxies /api to the backend
              +---------+---------+
                        | /api
              +---------v---------+
              |      backend      |   the agent, the ranking engine,
              |   (port 8000)     |   the app bridge
              +----+---------+----+
                   |         |
      Model Context Protocol over HTTP
                   |         |
        +----------v--+   +--v----------+
        |  formular   |   |    kasse    |   two MCP App servers, each
        | (port 3001) |   | (port 3002) |   serving a ui:// resource
        +-------------+   +-------------+
```

| Service | Port | What it does |
|---|---|---|
| `ui` | 8080 | nginx serving the built React bundle and proxying `/api` to the backend, so the browser sees a single origin |
| `backend` | 8000 | the agent loop, the interview record, the deterministic ranking engine, and the bridge the app surfaces call back through |
| `formular` | 3001 | MCP server owning the intake form surface |
| `kasse` | 3002 | MCP server owning the simulated checkout surface |

The backend reaches the two MCP servers at `MCP_FORMULAR_URL` and `MCP_KASSE_URL`,
which compose sets to their service names. They are genuinely separate processes and
every surface fetch and every bridge call crosses the protocol. `GET /api/health`
reports `"mcp":"remote"` when that is true and `"remote-degraded"` if a call has ever
had to fall back, so the claim is checkable rather than asserted.

Application state lives in a named Docker volume, `fahrbereit-state`, mounted at
`/app/state`. Ports 8000, 3001 and 3002 are published so you can inspect the backend
and the MCP servers directly, but nothing requires it.

### Running without Docker

Useful for development. Two terminals, from the project root.

```bash
python -m venv .venv && .venv/Scripts/python.exe -m pip install -e .
```

```bash
.venv/Scripts/python.exe run_backend.py
```

```bash
cd ui && npm install && npm run dev
```

Then open `http://localhost:5173`. Without `MCP_FORMULAR_URL` and `MCP_KASSE_URL` set,
the backend calls the two MCP servers in-process instead of over the network, so a
single command still gives you the whole interface. `/api/health` reports
`"mcp":"in-process"` so the difference is never hidden.

Run the tests, which need no API key and make no network call:

```bash
.venv/Scripts/python.exe -m pytest tests/ -q
```

See the ranking engine on its own, with no model and no interface:

```bash
.venv/Scripts/python.exe -m scripts.demo_ranking
```

---

## Project structure

```
agent/            the Python side
  session.py      the agent loop: create_deep_agent, checkpointer, one turn
  prompts/        system prompt, interview policy, hallucination guardrail
  tools/          what the agent may call
    interview.py    record slots, read state, ask for recommendations
    ranking.py      hard filter and weighted scoring
    tco.py          German five year cost of ownership
  listing.py      the typed listing model and the dataset loader
  state.py        typed interview record with per-slot provenance
  store.py        session state, keyed by session id
  model/          model provider seam; nothing outside imports a vendor
  payment/        payment provider seam; the mock is the only implementation
  surfaces/       ranking results translated into A2UI messages
  i18n.py         German and English
  server.py       HTTP surface and the app bridge
mcpapps/          the two MCP App servers
  formular/       intake form
  kasse/          simulated checkout
ui/               React interface, A2UI catalog, chat
data/             seeded generator and the committed marketplace
tests/            191 tests, no API key required
specs/            spec-kit artifacts: spec, plan, research, data model, tasks
docs/             spike notes and architecture
```

---

## Where the mock boundary is

- **Payment is simulated end to end.** No gateway, no bank, no card network is
  contacted in any environment. `agent/payment/mock.py` is the only implementation of
  the `PaymentProvider` interface in this repository. There is no card input anywhere
  in the codebase, not even a disabled one, and a test walks the whole tree to keep it
  that way.
- **The marketplace is synthetic**, generated by `data/generate.py` from a committed
  seed. No listing site is contacted and no real inventory is represented.
- **Dealers and rental operators are invented.** Manufacturer and model names are
  factual references to real vehicles. No BMW Group mark or asset appears anywhere.

To connect a real payment gateway later: add one class implementing `PaymentProvider`
in `agent/payment/`, register it in the `PROVIDERS` map, and set `PAYMENT_PROVIDER` to
its name. Nothing outside that package would change.

---

## Status

Built so far: the marketplace and its generator, the deterministic ranking engine with
German cost of ownership, the typed interview record, the conversational agent loop,
the A2UI catalogue surface, both MCP App surfaces, the German and English toggle, and
the containers.

Still to come: the live agent progress surface, observability, and the evaluation
harness. This section will be replaced by the full requirement traceability table and
an honest known-limitations list before submission.
