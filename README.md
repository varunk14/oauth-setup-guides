# OAuth Setup Guides

Know before you start how hard it is to create an OAuth app with a provider and get it
approved: the steps, the time including review waits, the requirements that can block you,
and what an agent can do for you versus what you must do yourself.

- **Library**: curated guides for apps with very different setup challenges.
- **Live generation**: submit any app name or website and watch an agent research it and
  write a shareable guide.
- **Evidence labels**: every claim is marked TESTED, SOURCED, INFERRED or UNVERIFIED.

Status: early development. The full README (live link, decisions, evidence model,
verification, limitations) comes with the first release.

## Run locally

Requirements: Python 3.13 with [uv](https://docs.astral.sh/uv/), Node 24.

```bash
# Backend (http://127.0.0.1:8000)
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8000

# Frontend (http://127.0.0.1:5173), in a second terminal
cd frontend
npm install
npm run dev
```

Configuration: copy `.env.example` to `.env` and fill in values. Keys are used by the
backend only and never reach the browser.

## Checks

```bash
cd backend && uv run ruff format --check . && uv run ruff check . && uv run mypy app scripts tests && uv run pytest
cd frontend && npm run lint && npm run format:check && npm run typecheck && npm test && npm run build && npm run e2e
./scripts/check_bundle.sh frontend/dist
```

## Layout

- `backend/` FastAPI app, guide schema (`app/schema.py`), tests
- `frontend/` React + TypeScript + Vite
- `schema/guide.schema.json` JSON Schema generated from the backend models
- `data/guides/` curated library guides (one JSON file per app)
