# OAuth App Setup Guides

Before your AI agent's users can connect an app (Gmail, Slack, HubSpot...), you often need your
own OAuth app with that provider, and sometimes weeks of review. This tool tells you, before
you start, how hard that will be: the difficulty, the hands-on time, the approval wait, the
exact steps, what can block you, and what an agent can do for you versus what you must do
yourself. Every claim says how we know it.

**Live:** LIVE_URL_PLACEHOLDER

- **Library.** Six checked guides for apps with very different setup paths: GitHub (Easy),
  HubSpot and Slack (Medium), Salesforce and Instagram (Hard), Gmail (Very hard).
- **Investigate any app.** Type an app name or website and watch an agent research its
  official docs live (about 1-3 minutes), run safe checks on its OAuth endpoints and write a
  guide in the same format, with its own shareable link.
- **Share.** Every guide has a link and a Copy as Markdown button.
- **Evidence labels.** Every claim is TESTED, SOURCED, INFERRED or UNVERIFIED, and each guide
  ends with what we could not verify.

## The problem, as we understood it

A provider OAuth app is a registration (client ID, secret, redirect URI, scopes) that decides
whose name your users see on the consent screen and what you may access. On Composio, an
**auth config** holds that app's credentials for one toolkit, and each of your users gets a
**connected account** with their own tokens under it.

Composio already runs approved OAuth apps for about 124 toolkits ("managed auth"), so most
developers start without any provider paperwork. The hard moment comes later: you need your
own app for your own branding on the consent screen, custom scopes, a dedicated rate limit or
faster triggers, and 258 toolkits have no managed app at all. That is when developers meet
unfamiliar consoles, reviews with unclear waits and rules that are easy to miss. Every guide
therefore starts with "Do you need your own OAuth app?" and then maps the road to it.

## Key decisions and why

| Decision | Why |
|---|---|
| Six library apps chosen for contrast, not popularity | Each shows a different kind of difficulty: self-serve (GitHub), install caps until listed (HubSpot), rate limits until listed (Slack), org and packaging rules (Salesforce), per-permission review and business verification (Instagram), restricted scopes with a yearly security assessment (Gmail) |
| One strict guide format for library and live guides | A developer reads every guide the same way, and code can validate it. The format is a pydantic model; the frontend types are generated from it |
| Our code drives the agent; the model only researches and writes | Predictable, testable with fakes, cheap, and it lets code decide what counts as evidence |
| Only our own probes can produce TESTED | Models sometimes claim checks they did not run. A TESTED label must cite a probe that actually ran and was conclusive |
| Difficulty is always INFERRED | It is our judgement from the sources, never something a provider states |
| Primary model OpenAI `gpt-6-luna` with its built-in web search; automatic fallback to Gemini + Tavily | Reliable for a live demo at about $0.07 per guide; if OpenAI fails for any reason the run switches mid-run without user action |
| Cache first, then limits | Library apps and earlier results open instantly and free. New runs: one at a time, 3 per person per hour, 25 per day, capped at 8 searches and 4 minutes |
| One Vercel project, Redis for shared state | FastAPI serves both the API and the built site. Serverless instances share nothing, so generated guides and limits live in Upstash Redis |

## How the agent works

```
app name or URL
  -> cache: library or earlier run?  yes -> open it (free)
  -> limits and run lock
  -> research   model + web search: official docs first; every fact with its URL and a quote
  -> probes     our code: discovery documents, authorize endpoint with a fake client ID,
                console and docs pages (anonymous GET only)
  -> sources    our code: every cited page must load; missing or unsafe pages are dropped
  -> write      model: guide draft with evidence labels
  -> enforce    our code: fix labels it cannot back, mark sign-in steps as yours, fill in
                sources, probes, the Composio note and what the agent did
  -> validate   strict schema; one repair attempt if invalid
  -> save       shareable link; progress streamed to the browser the whole time
```

The agent never signs in, creates accounts, submits forms or enters credentials. Those steps
are always marked as yours.

It fails honestly: an unknown app gets "we could not identify", an app without OAuth gets
"no OAuth app needed, it uses ...", and limits or provider outages get a clear message with a
link back to the library.

**Safe probes.** HTTPS only, a domain allowlist checked on every redirect, public IP addresses
only, an 8-second timeout and a 512 KB size cap. Pages that are rendered by JavaScript, or
that answer 200 with a "not found" title, are reported as inconclusive rather than as proof.

## Evidence model

| Label | Meaning |
|---|---|
| TESTED | Our code observed it: a probe result with its time and outcome |
| SOURCED | An official page states it; the source is listed with the date it was checked |
| INFERRED | Our reasoning from the sources, or a community source (marked as such) |
| UNVERIFIED | We could not confirm it; also listed under "What we could not verify" |

Each label links to its sources or probe results, and notes explain anything unusual.

## Verification

Full report: [docs/verification.md](docs/verification.md). In short:

- **Fact-check.** Each library guide was audited claim by claim against official provider and
  Composio pages. 52 problems were found and fixed, for example Composio's managed Slack app
  still awaiting Marketplace review, Salesforce now blocking uninstalled connected apps, and
  Google's rule that Gmail data may not train general AI models.
- **Links.** All 93 URLs in the guides load.
- **Real setup.** A GitHub OAuth app was created by hand following our guide. Nine claims
  were confirmed, a docs conflict about expiring tokens was settled, and one label was
  corrected (the form now says "Redirect URI").
- **Live vs checked.** The live agent re-investigated GitHub and Slack. GitHub matched with no
  wrong facts. Slack first missed the rate limit for unlisted commercial apps; the research
  step was fixed and the re-run found it. Verification also caught three mistakes in our own
  probes and a source check that dropped pages redirecting to another official domain.

## Limitations

- **The live agent can miss policy traps.** It was reliable on the facts it stated, but it
  missed one important rule in a first run. The checked library matters for the most used
  apps; live guides say they were researched automatically.
- **The backup provider is less thorough.** Guides made by Gemini + Tavily read fewer pages and
  say so on the page.
- **No account-level checks.** We never sign in, so console details behind a login are taken
  from docs (except where the real setup attempt checked them).
- **Point in time.** Guides record the date they were checked; provider rules change. There is
  no automatic refresh yet.
- **Cost guards are simple.** Per-person limits use the client IP, and a determined user could
  use several addresses; the daily cap bounds the total.

## What I would do next

1. **Scale the library to 100 apps with the agent first.** Generate drafts for Composio's
   toolkits, starting with the 258 that have no managed app, then review the highest-traffic
   ones by hand with the same fact-check checklist.
2. **Keep guides fresh.** Re-run probes weekly and re-research when a source page changes;
   flag guides older than 90 days.
3. **Feedback from real setups.** A "this step was different" button on each step, feeding a
   review queue.
4. **Deeper checks without accounts.** Use a headless browser for authorize pages that are
   rendered by JavaScript, so more of them become TESTED.
5. **Composio integration.** Read managed-auth status from Composio's toolkit API instead of a
   dated snapshot, and link each guide to the matching toolkit and auth-config docs.

## Run locally

Requirements: Python 3.13 with [uv](https://docs.astral.sh/uv/), Node 24.

```bash
# Backend (http://127.0.0.1:8000)
cd backend
uv sync
ENV_FILE=../.env uv run uvicorn app.main:app --reload --port 8000

# Frontend (http://127.0.0.1:5173), in a second terminal
cd frontend
npm install
npm run dev
```

Configuration: copy `.env.example` to `.env` and fill in the keys you have. Keys are used by
the backend only and never reach the browser. Without keys the library still works and live
generation answers "not configured". Values in `ENV_FILE` take priority over variables already
exported in your shell.

| Variable | Needed for |
|---|---|
| `OPENAI_API_KEY`, `OPENAI_MODEL` | Primary research and writing (OpenAI web search) |
| `GEMINI_API_KEY`, `GEMINI_MODEL_FAST`, `TAVILY_API_KEY` | Automatic backup (Gemini writes, Tavily searches) |
| `UPSTASH_REDIS_REST_URL`, `UPSTASH_REDIS_REST_TOKEN` (or Vercel's `KV_REST_API_URL`, `KV_REST_API_TOKEN`) | Shared storage and limits when hosted; optional locally |
| `AGENT_MAX_SEARCHES`, `AGENT_RUN_TIMEOUT_S`, `AGENT_RUNS_PER_IP_PER_HOUR`, `AGENT_RUNS_PER_DAY` | Optional limits (defaults 8, 240, 3, 25) |

## Deploy (Vercel)

Import the repository as one project with the FastAPI preset and the root directory `./`.
`vercel.json` builds the frontend and allows 300 seconds per request; `index.py` exposes the
app. Add the environment variables above, then add Upstash for Redis from the project's
Storage tab and redeploy.

## Checks

```bash
cd backend && uv run ruff format --check . && uv run ruff check . && uv run mypy app scripts tests && uv run pytest
cd frontend && npm run lint && npm run format:check && npm run typecheck && npm test && npm run build && npm run e2e
./scripts/check_bundle.sh frontend/dist
```

Tests never call a real model, search API or website: providers, probes and Redis are faked,
and the browser tests fake the agent endpoint and run against their own servers. CI runs all
of the above on every pull request.

## Layout

- `backend/app/` FastAPI app: guide schema (`schema.py`), probes, library store, Markdown export
- `backend/app/agent/` live agent: providers and fallback, pipeline, evidence enforcement, limits, stores
- `frontend/` React + TypeScript + Vite: library, guide and investigate pages
- `data/guides/` the checked library guides; `data/probes/` their recorded probe results
- `data/composio_managed_auth.json` dated snapshot of Composio's managed OAuth directory
- `schema/guide.schema.json` JSON Schema generated from the backend models
- `docs/verification.md` what was tested, corrected and could not be verified
- `index.py`, `vercel.json`, `requirements.txt` deployment
