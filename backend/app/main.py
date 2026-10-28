"""FastAPI entry point."""

import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel, Field

from app.agent.limits import LimitExceeded, RunGate
from app.agent.pipeline import Deps, InvestigationError, clean_query, find_cached, investigate
from app.agent.providers import GeminiTavilyProvider, OpenAIProvider, Provider, ProviderChain
from app.agent.settings import Settings, load_settings
from app.agent.store import GeneratedStore
from app.markdown import render_markdown
from app.probes import Allowlist, ProbeSpec, run_probes
from app.schema import SCHEMA_VERSION, Guide, Probe
from app.store import GuideStore, GuideSummary, guides_dir, summarize

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

app = FastAPI(title="OAuth Setup Guides", version="0.1.0")


@lru_cache(maxsize=1)
def get_store() -> GuideStore:
    return GuideStore.from_directory(guides_dir())


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()


@lru_cache(maxsize=1)
def get_generated() -> GeneratedStore:
    return GeneratedStore(get_settings().generated_dir)


@dataclass
class Agent:
    settings: Settings
    gate: RunGate
    deps: Deps


async def _probe_runner(specs: list[ProbeSpec], allowlist: Allowlist) -> list[Probe]:
    return await run_probes(specs, allowlist)


@lru_cache(maxsize=1)
def get_agent() -> Agent:
    settings = get_settings()

    def chain_factory(notify: Callable[[str], Awaitable[None]]) -> ProviderChain:
        primary: Provider | None = None
        backup: Provider | None = None
        if settings.openai_api_key:
            primary = OpenAIProvider(
                settings.openai_api_key, settings.openai_model, settings.max_searches
            )
        if settings.gemini_api_key and settings.tavily_api_key:
            backup = GeminiTavilyProvider(
                settings.gemini_api_key, settings.gemini_model, settings.tavily_api_key
            )
        return ProviderChain(primary, backup, notify)

    deps = Deps(
        chain_factory=chain_factory,
        probe_runner=_probe_runner,
        generated=get_generated(),
        library=get_store(),
        timeout_s=settings.run_timeout_s,
    )
    return Agent(settings, RunGate(settings.runs_per_ip_per_hour, settings.runs_per_day), deps)


Store = Annotated[GuideStore, Depends(get_store)]
Generated = Annotated[GeneratedStore, Depends(get_generated)]
AgentDep = Annotated[Agent, Depends(get_agent)]


@app.get("/api/health")
@app.get("/health", include_in_schema=False)
def health() -> dict[str, str]:
    return {"status": "ok", "schema_version": SCHEMA_VERSION}


@app.get("/api/guides")
def list_guides(store: Store, generated: Generated) -> list[GuideSummary]:
    live = sorted(
        (summarize(g) for g in generated.all()), key=lambda s: s.generated_at, reverse=True
    )
    return [*store.summaries(), *live]


def _find(slug: str, store: GuideStore, generated: GeneratedStore) -> Guide:
    guide = store.get(slug) or generated.get(slug)
    if guide is None:
        raise HTTPException(status_code=404, detail=f"No guide found for '{slug}'.")
    return guide


@app.get("/api/guides/{slug}")
def get_guide(slug: str, store: Store, generated: Generated) -> Guide:
    return _find(slug, store, generated)


@app.get("/api/guides/{slug}/markdown", response_class=PlainTextResponse)
def get_guide_markdown(
    slug: str, request: Request, store: Store, generated: Generated
) -> PlainTextResponse:
    guide = _find(slug, store, generated)
    share_url = str(request.base_url).rstrip("/") + f"/guides/{slug}"
    return PlainTextResponse(
        render_markdown(guide, share_url=share_url), media_type="text/markdown; charset=utf-8"
    )


class GenerateRequest(BaseModel):
    query: str = Field(max_length=200)
    refresh: bool = False


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def sse(event: dict[str, object]) -> str:
    return f"event: {event['type']}\ndata: {json.dumps(event)}\n\n"


def _error(code: str, message: str) -> str:
    return sse({"type": "error", "code": code, "message": message})


@app.post("/api/generate")
async def generate(body: GenerateRequest, request: Request, agent: AgentDep) -> StreamingResponse:
    """Stream a live investigation as Server-Sent Events within this single request.

    Order matters for cost control: cached answers first (free), then the limits and
    the one-run-at-a-time lock, and only then the investigation itself.
    """
    ip = client_ip(request)

    async def stream() -> AsyncIterator[str]:
        try:
            query = clean_query(body.query)
        except InvestigationError as exc:
            yield _error(exc.code, exc.message)
            return
        if not body.refresh:
            cached = find_cached(query, agent.deps)
            if cached:
                yield sse(cached)
                return
        if not agent.settings.configured:
            yield _error(
                "not_configured",
                "Live generation is not configured on this server. Browse the library instead.",
            )
            return
        gate = agent.gate
        try:
            gate.check(ip)
        except LimitExceeded as exc:
            yield _error(exc.code, exc.message)
            return
        # No await between the check and taking the lock, so two requests cannot both pass.
        async with gate.lock:
            gate.record(ip)
            async for event in investigate(query, body.refresh, agent.deps):
                yield sse(event)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
