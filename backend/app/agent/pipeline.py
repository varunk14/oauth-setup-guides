"""The live investigation: research, probes, source checks, write, enforce, save.

Our code drives the steps; the model only researches and writes. Progress is
reported as small event dicts that the API streams to the browser.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError

from app.agent.assemble import (
    Draft,
    assemble,
    build_sources,
    composio_sources,
    draft_schema,
    host_of,
    is_http_url,
    normalize_draft,
    registrable_domain,
    slugify,
)
from app.agent.prompts import RESEARCH_SYSTEM, WRITE_SYSTEM
from app.agent.providers import ProviderChain, ProviderError
from app.agent.store import GeneratedStore
from app.probes import Allowlist, ProbeSpec
from app.schema import Guide, Probe, Source
from app.store import GuideStore

log = logging.getLogger("agent")

Event = dict[str, Any]
ProbeRunner = Callable[[list[ProbeSpec], Allowlist], Awaitable[list[Probe]]]
ChainFactory = Callable[[Callable[[str], Awaitable[None]]], ProviderChain]

QUERY_RE = re.compile(r"^[\w .,&'()+:/-]{1,100}$", re.UNICODE)


class InvestigationError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class Deps:
    chain_factory: ChainFactory
    probe_runner: ProbeRunner
    generated: GeneratedStore
    library: GuideStore
    timeout_s: float = 240


def clean_query(raw: str) -> str:
    query = " ".join(raw.split())
    if not query or not QUERY_RE.match(query):
        raise InvestigationError(
            "bad_query", "Enter an app name or website, for example Zoom or zoom.us."
        )
    return query


def query_keys(query: str) -> list[str]:
    keys = [slugify(query)]
    candidate = query if "://" in query else f"https://{query}"
    host = host_of(candidate)
    if "." in host and " " not in query:
        keys.append(registrable_domain(host))
    return keys


def library_match(library: GuideStore, keys: list[str], query: str) -> Guide | None:
    wanted = {k.lower() for k in keys} | {query.lower()}
    for summary in library.summaries():
        names = {
            summary.slug,
            summary.name.lower(),
            summary.name.lower().split(" (")[0],
            registrable_domain(host_of(summary.website)),
        }
        if names & wanted:
            return library.get(summary.slug)
    return None


def plan_probes(research: dict[str, Any], official: set[str]) -> list[ProbeSpec]:
    website = str(research.get("website", ""))
    authorize = str(research.get("authorize_endpoint", "")).strip()
    if not (is_http_url(authorize) and registrable_domain(host_of(authorize)) in official):
        authorize = ""
    auth_host = host_of(authorize) or host_of(website)
    specs: list[ProbeSpec] = []
    if auth_host:
        specs.append(
            ProbeSpec(
                "oidc", "oidc_discovery", f"https://{auth_host}/.well-known/openid-configuration"
            )
        )
        specs.append(
            ProbeSpec(
                "oauth-meta",
                "oauth_metadata",
                f"https://{auth_host}/.well-known/oauth-authorization-server",
            )
        )
    if authorize:
        specs.append(ProbeSpec("authorize", "authorize_endpoint", authorize))
    console = str(research.get("developer_console_url", "")).strip()
    if is_http_url(console) and registrable_domain(host_of(console)) in official:
        specs.append(ProbeSpec("console", "url_reachable", console))
    docs = [
        u
        for u in research.get("docs_urls", [])
        if is_http_url(u) and registrable_domain(host_of(u)) in official
    ]
    if docs:
        specs.append(ProbeSpec("docs", "url_reachable", docs[0]))
    return specs


async def check_sources(sources: list[Source], runner: ProbeRunner) -> list[Source]:
    """Drop sources whose page does not exist or that our safety rules refuse."""
    if not sources:
        return []
    specs = [ProbeSpec(f"c{i}", "url_reachable", str(s.url)) for i, s in enumerate(sources)]
    allow = Allowlist({registrable_domain(host_of(str(s.url))) for s in sources})
    results = await runner(specs, allow)
    keep = []
    for source, probe in zip(sources, results, strict=True):
        if probe.outcome == "not_found" or probe.summary.startswith("Not sent"):
            continue
        keep.append(source)
    return keep


def writer_prompt(
    query: str, research: dict[str, Any], sources: list[Source], probes: list[Probe]
) -> str:
    source_lines = "\n".join(f"{s.id}: {s.url} ({s.kind})" for s in sources) or "(none)"
    probe_lines = (
        "\n".join(f"{p.id}: {p.kind} {p.target_url} -> {p.outcome}: {p.summary}" for p in probes)
        or "(none)"
    )
    return (
        f"App: {query}\nToday: {datetime.now(UTC).date()}\n\n"
        f"RESEARCH FINDINGS (JSON):\n{json.dumps(research, indent=1)}\n\n"
        f"SOURCES (cite by id; only these exist):\n{source_lines}\n\n"
        f"CHECKS (our automated probes; cite by id for TESTED):\n{probe_lines}\n\n"
        "Write the guide as JSON matching the schema."
    )


def _keep_failed(deps: Deps, run_id: str, name: str, raw: object, exc: ValidationError) -> None:
    """Log why a draft failed and keep it (git-ignored) so the cause can be fixed."""
    problems = [f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()[:15]]
    log.warning(json.dumps({"event": "invalid_draft", "run_id": run_id, "errors": problems}))
    folder = deps.generated.directory / "_failed"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{run_id}-{name}.json").write_text(
        json.dumps({"errors": problems, "raw": raw}, indent=1, default=str)
    )


def find_cached(query: str, deps: Deps) -> Event | None:
    """A free answer from the library or an earlier run, if there is one."""
    keys = query_keys(query)
    found = library_match(deps.library, keys, query)
    if found:
        return {"type": "done", "slug": found.app.slug, "cached": True, "from": "library"}
    for key in keys:
        cached = deps.generated.find(key)
        if cached:
            return {"type": "done", "slug": cached.app.slug, "cached": True, "from": "generated"}
    return None


async def _run(
    query: str, refresh: bool, deps: Deps, emit: Callable[[Event], Awaitable[None]]
) -> None:
    started = time.monotonic()
    run_id = uuid.uuid4().hex[:8]
    keys = query_keys(query)

    async def notice(message: str) -> None:
        await emit({"type": "notice", "message": message})

    chain = deps.chain_factory(notice)
    outcome = "error"
    try:
        await emit(
            {
                "type": "step",
                "step": "research",
                "status": "running",
                "message": "Searching the provider's official developer docs...",
            }
        )
        research = await chain.research(
            RESEARCH_SYSTEM, f"App: {query}\nToday: {datetime.now(UTC).date()}"
        )
        data = research.data
        website = str(data.get("website", "")).strip()
        official = {registrable_domain(d) for d in data.get("official_domains", []) if d}
        if is_http_url(website):
            official.add(registrable_domain(host_of(website)))
        if not data.get("is_real_app") or not official or not is_http_url(website):
            raise InvestigationError(
                "unknown_app",
                f"We could not identify an app called '{query}' with official developer docs. "
                "Check the spelling, or try its website (for example zoom.us).",
            )
        findings = data.get("findings", [])
        await emit(
            {
                "type": "step",
                "step": "research",
                "status": "done",
                "message": f"Identified {data.get('app_name')} ({website}). "
                f"{len(findings)} facts from {len(research.consulted_urls)} pages.",
            }
        )
        if data.get("oauth_supported") == "no":
            other = data.get("other_auth") or "another method"
            outcome = "no_oauth"
            await emit(
                {
                    "type": "no_oauth",
                    "message": f"{data.get('app_name')} does not appear to offer OAuth for "
                    f"third-party apps. It uses {other}. No OAuth app setup is needed, so we did "
                    "not write a guide.",
                }
            )
            return

        if not refresh:
            for domain in sorted(official):
                cached = deps.generated.find(domain)
                if cached:
                    outcome = "cached"
                    await emit(
                        {
                            "type": "done",
                            "slug": cached.app.slug,
                            "cached": True,
                            "from": "generated",
                        }
                    )
                    return

        await emit(
            {
                "type": "step",
                "step": "probes",
                "status": "running",
                "message": "Running safe checks on the provider's OAuth endpoints...",
            }
        )
        specs = plan_probes(data, official)
        probes = await deps.probe_runner(specs, Allowlist(official)) if specs else []
        conclusive = sum(p.outcome != "inconclusive" for p in probes)
        for p in probes:
            await emit(
                {
                    "type": "probe",
                    "id": p.id,
                    "target": str(p.target_url),
                    "outcome": p.outcome,
                    "summary": p.summary,
                }
            )
        await emit(
            {
                "type": "step",
                "step": "probes",
                "status": "done",
                "message": f"{conclusive} of {len(probes)} checks were conclusive.",
            }
        )

        await emit(
            {
                "type": "step",
                "step": "sources",
                "status": "running",
                "message": "Checking that every cited page exists...",
            }
        )
        today = datetime.now(UTC).date()
        candidates = build_sources(data, research.consulted_urls, official, today)
        sources = await check_sources(candidates, deps.probe_runner)
        await emit(
            {
                "type": "step",
                "step": "sources",
                "status": "done",
                "message": f"{len(sources)} of {len(candidates)} sources checked and kept "
                f"({sum(s.kind == 'official' for s in sources)} official).",
            }
        )

        await emit(
            {
                "type": "step",
                "step": "write",
                "status": "running",
                "message": "Writing the guide and labelling every claim...",
            }
        )
        prompt = writer_prompt(query, data, [*sources, *composio_sources()], probes)
        schema = draft_schema()
        raw = await chain.write_json(WRITE_SYSTEM, prompt, schema)
        try:
            draft = Draft.model_validate(normalize_draft(raw))
        except ValidationError as exc:
            _keep_failed(deps, run_id, "draft1", raw, exc)
            await emit(
                {
                    "type": "notice",
                    "message": "The draft did not match the format; asking for one repair.",
                }
            )
            raw = await chain.write_json(
                WRITE_SYSTEM,
                prompt
                + "\n\nYour previous JSON was invalid. Fix these errors and return the full "
                + f"JSON:\n{exc}"
                + f"\n\nPREVIOUS JSON:\n{json.dumps(raw)[:20000]}",
                schema,
            )
            try:
                draft = Draft.model_validate(normalize_draft(raw))
            except ValidationError as exc2:
                _keep_failed(deps, run_id, "draft2", raw, exc2)
                raise InvestigationError(
                    "invalid_output", "The model could not produce a valid guide. Please try again."
                ) from exc2
        await emit({"type": "step", "step": "write", "status": "done", "message": "Draft written."})

        await emit(
            {
                "type": "step",
                "step": "validate",
                "status": "running",
                "message": "Enforcing evidence rules and validating...",
            }
        )
        slug = slugify(str(data.get("app_name") or query))
        if deps.library.get(slug):
            slug = f"{slug}-live"
        try:
            guide = assemble(
                slug=slug,
                draft=draft,
                research=data,
                sources=sources,
                probes=probes,
                searches=chain.usage.searches,
                provider=chain.describe(),
                run_seconds=time.monotonic() - started,
            )
        except ValidationError as exc:
            raise InvestigationError(
                "invalid_output", "The guide failed validation. Please try again."
            ) from exc
        deps.generated.put(guide, [*keys, *official, slug])
        await emit(
            {
                "type": "step",
                "step": "validate",
                "status": "done",
                "message": f"Valid guide with {guide.meta.sources_count} sources.",
            }
        )
        outcome = "done"
        await emit({"type": "done", "slug": guide.app.slug, "cached": False, "from": "generated"})
    finally:
        log.info(
            json.dumps(
                {
                    "event": "run",
                    "run_id": run_id,
                    "query": query,
                    "outcome": outcome,
                    "provider": chain.describe() if chain.providers else None,
                    "searches": chain.usage.searches,
                    "input_tokens": chain.usage.input_tokens,
                    "output_tokens": chain.usage.output_tokens,
                    "seconds": round(time.monotonic() - started, 1),
                }
            )
        )


async def investigate(query: str, refresh: bool, deps: Deps) -> AsyncIterator[Event]:
    """Run an investigation and yield progress events; always ends with done/error/no_oauth."""
    queue: asyncio.Queue[Event | None] = asyncio.Queue()

    async def emit(event: Event) -> None:
        await queue.put(event)

    async def runner() -> None:
        try:
            async with asyncio.timeout(deps.timeout_s):
                await _run(query, refresh, deps, emit)
        except InvestigationError as exc:
            await emit({"type": "error", "code": exc.code, "message": exc.message})
        except ProviderError as exc:
            await emit(
                {
                    "type": "error",
                    "code": "provider",
                    "message": f"The model providers are unavailable right now ({exc.message}). "
                    "Try again later, or browse the library.",
                }
            )
        except TimeoutError:
            await emit(
                {
                    "type": "error",
                    "code": "timeout",
                    "message": "The investigation took too long and was stopped. Try again, "
                    "or browse the library.",
                }
            )
        except Exception:
            log.exception("investigation failed")
            await emit(
                {
                    "type": "error",
                    "code": "internal",
                    "message": "Something went wrong on our side. Please try again.",
                }
            )
        finally:
            await queue.put(None)

    task = asyncio.create_task(runner())
    try:
        while (event := await queue.get()) is not None:
            yield event
    finally:
        if not task.done():
            task.cancel()
