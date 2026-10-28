"""Model providers behind one small interface, with automatic fallback.

Primary: OpenAI with its built-in web search. Backup: Tavily search + Gemini.
Any provider failure becomes a ProviderError, and ProviderChain switches to the
backup for the rest of the run without user action.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

import httpx

ErrorKind = Literal["auth", "quota", "rate_limit", "server", "timeout", "bad_output", "config"]

RESEARCH_TOPICS = [
    "setup",
    "scopes",
    "review",
    "requirements",
    "tokens",
    "pkce",
    "redirect_uris",
    "rate_limits",
    "sandbox",
    "distribution",
    "other",
]

# Strict JSON schema for the research step (all keys required; "" or [] when unknown).
RESEARCH_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "app_name",
        "website",
        "category",
        "is_real_app",
        "oauth_supported",
        "other_auth",
        "official_domains",
        "authorize_endpoint",
        "token_endpoint",
        "developer_console_url",
        "docs_urls",
        "findings",
        "conflicts",
        "unknowns",
    ],
    "properties": {
        "app_name": {"type": "string"},
        "website": {"type": "string"},
        "category": {"type": "string"},
        "is_real_app": {"type": "boolean"},
        "oauth_supported": {"type": "string", "enum": ["yes", "no", "unclear"]},
        "other_auth": {"type": "string"},
        "official_domains": {"type": "array", "items": {"type": "string"}},
        "authorize_endpoint": {"type": "string"},
        "token_endpoint": {"type": "string"},
        "developer_console_url": {"type": "string"},
        "docs_urls": {"type": "array", "items": {"type": "string"}},
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["topic", "fact", "source_url", "quote"],
                "properties": {
                    "topic": {"type": "string", "enum": RESEARCH_TOPICS},
                    "fact": {"type": "string"},
                    "source_url": {"type": "string"},
                    "quote": {"type": "string"},
                },
            },
        },
        "conflicts": {"type": "array", "items": {"type": "string"}},
        "unknowns": {"type": "array", "items": {"type": "string"}},
    },
}


class ProviderError(Exception):
    def __init__(self, kind: ErrorKind, message: str) -> None:
        super().__init__(message)
        self.kind = kind
        self.message = message


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    searches: int = 0

    def add(self, other: Usage) -> None:
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.searches += other.searches


@dataclass
class Research:
    data: dict[str, Any]
    consulted_urls: list[str] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)


class Provider(Protocol):
    name: str
    model: str

    async def research(self, system: str, prompt: str) -> Research: ...

    async def write_json(
        self, system: str, prompt: str, schema: dict[str, Any]
    ) -> tuple[dict[str, Any], Usage]: ...


def _parse_json(text: str) -> dict[str, Any]:
    try:
        data = json.loads(text)
    except (TypeError, ValueError) as exc:
        raise ProviderError("bad_output", "The model did not return valid JSON.") from exc
    if not isinstance(data, dict):
        raise ProviderError("bad_output", "The model did not return a JSON object.")
    return data


# ---------------------------------------------------------------- OpenAI


class OpenAIProvider:
    name = "openai"

    def __init__(self, api_key: str, model: str, max_searches: int, client: Any = None) -> None:
        from openai import AsyncOpenAI

        self.model = model
        self.max_searches = max_searches
        self.client = client or AsyncOpenAI(api_key=api_key, timeout=150, max_retries=0)

    async def _create(self, **kwargs: Any) -> Any:
        import openai

        try:
            return await self.client.responses.create(model=self.model, **kwargs)
        except openai.AuthenticationError as exc:
            raise ProviderError("auth", "OpenAI rejected the API key.") from exc
        except openai.PermissionDeniedError as exc:
            raise ProviderError("auth", "OpenAI denied access to this model.") from exc
        except openai.RateLimitError as exc:
            body: dict[str, Any] = exc.body if isinstance(exc.body, dict) else {}
            error_obj = body.get("error")
            nested: dict[str, Any] = error_obj if isinstance(error_obj, dict) else {}
            codes = f"{getattr(exc, 'code', '')} {body.get('code', '')} {nested.get('code', '')}"
            kind: ErrorKind = "quota" if "quota" in codes + str(exc) else "rate_limit"
            raise ProviderError(kind, "OpenAI quota or rate limit reached.") from exc
        except openai.APITimeoutError as exc:
            raise ProviderError("timeout", "OpenAI did not answer in time.") from exc
        except openai.APIConnectionError as exc:
            raise ProviderError("server", "Could not reach OpenAI.") from exc
        except openai.APIStatusError as exc:
            raise ProviderError("server", f"OpenAI error (HTTP {exc.status_code}).") from exc

    @staticmethod
    def _usage(response: Any, searches: int = 0) -> Usage:
        usage = getattr(response, "usage", None)
        return Usage(
            input_tokens=getattr(usage, "input_tokens", 0) or 0,
            output_tokens=getattr(usage, "output_tokens", 0) or 0,
            searches=searches,
        )

    async def research(self, system: str, prompt: str) -> Research:
        response = await self._create(
            instructions=system,
            input=prompt,
            tools=[{"type": "web_search", "search_context_size": "medium"}],
            include=["web_search_call.action.sources"],
            max_tool_calls=self.max_searches,
            max_output_tokens=12000,
            text={
                "format": {
                    "type": "json_schema",
                    "name": "research",
                    "schema": RESEARCH_SCHEMA,
                    "strict": True,
                }
            },
        )
        calls = [o for o in response.output if getattr(o, "type", "") == "web_search_call"]
        consulted: list[str] = []
        for call in calls:
            for source in getattr(getattr(call, "action", None), "sources", None) or []:
                url = getattr(source, "url", None)
                if url and url not in consulted:
                    consulted.append(url)
        if getattr(response, "status", "completed") != "completed":
            raise ProviderError("bad_output", "OpenAI stopped before finishing the research.")
        data = _parse_json(response.output_text)
        return Research(data, consulted, self._usage(response, searches=len(calls)))

    async def write_json(
        self, system: str, prompt: str, schema: dict[str, Any]
    ) -> tuple[dict[str, Any], Usage]:
        response = await self._create(
            instructions=system,
            input=prompt,
            max_output_tokens=20000,
            text={
                "format": {
                    "type": "json_schema",
                    "name": "guide",
                    "schema": schema,
                    "strict": False,
                }
            },
        )
        if getattr(response, "status", "completed") != "completed":
            raise ProviderError("bad_output", "OpenAI stopped before finishing the guide.")
        return _parse_json(response.output_text), self._usage(response)


# ---------------------------------------------------------- Gemini + Tavily

TAVILY_URL = "https://api.tavily.com/search"
TAVILY_PAGE_CHARS = 5000


class GeminiTavilyProvider:
    name = "gemini+tavily"

    def __init__(
        self,
        gemini_api_key: str,
        model: str,
        tavily_api_key: str,
        *,
        client: Any = None,
        http: httpx.AsyncClient | None = None,
    ) -> None:
        self.model = model
        self.tavily_api_key = tavily_api_key
        if client is None:
            from google import genai

            # Timeout in milliseconds: the free tier can stall for minutes.
            client = genai.Client(api_key=gemini_api_key, http_options={"timeout": 120_000})
        self.client = client
        self.http = http

    async def _generate(self, system: str, prompt: str, schema: dict[str, Any]) -> Any:
        from google.genai import errors

        try:
            return await self.client.aio.models.generate_content(
                model=self.model,
                contents=prompt,
                config={
                    "system_instruction": system,
                    "response_mime_type": "application/json",
                    "response_json_schema": schema,
                    "max_output_tokens": 20000,
                },
            )
        except errors.APIError as exc:
            code = getattr(exc, "code", 0) or 0
            if code in (401, 403):
                raise ProviderError("auth", "Gemini rejected the API key.") from exc
            if code == 429:
                raise ProviderError("quota", "Gemini quota or rate limit reached.") from exc
            raise ProviderError("server", f"Gemini error (HTTP {code}).") from exc
        except (httpx.TimeoutException, TimeoutError) as exc:
            raise ProviderError("timeout", "Gemini did not answer in time.") from exc

    @staticmethod
    def _usage(response: Any, searches: int = 0) -> Usage:
        meta = getattr(response, "usage_metadata", None)
        return Usage(
            input_tokens=getattr(meta, "prompt_token_count", 0) or 0,
            output_tokens=getattr(meta, "candidates_token_count", 0) or 0,
            searches=searches,
        )

    async def search(self, query: str) -> list[dict[str, str]]:
        if not self.tavily_api_key:
            raise ProviderError("config", "Tavily search is not configured.")
        http = self.http or httpx.AsyncClient(timeout=30)
        try:
            response = await http.post(
                TAVILY_URL,
                headers={"Authorization": f"Bearer {self.tavily_api_key}"},
                json={
                    "query": query,
                    "search_depth": "basic",
                    "max_results": 5,
                    "include_raw_content": "markdown",
                },
            )
        except httpx.HTTPError as exc:
            raise ProviderError("server", "Could not reach Tavily search.") from exc
        finally:
            if self.http is None:
                await http.aclose()
        if response.status_code == 401:
            raise ProviderError("auth", "Tavily rejected the API key.")
        if response.status_code in (429, 432, 433):
            raise ProviderError("quota", "Tavily quota or rate limit reached.")
        if response.status_code >= 400:
            raise ProviderError("server", f"Tavily error (HTTP {response.status_code}).")
        results = response.json().get("results", [])
        pages = []
        for item in results:
            text = item.get("raw_content") or item.get("content") or ""
            pages.append(
                {
                    "url": str(item.get("url", "")),
                    "title": str(item.get("title", "")),
                    "text": str(text)[:TAVILY_PAGE_CHARS],
                }
            )
        return pages

    async def research(self, system: str, prompt: str) -> Research:
        app = prompt.split("\n", 1)[0].removeprefix("App: ").strip()
        queries = [
            f"{app} OAuth app register developer documentation",
            f"{app} OAuth scopes permissions app review verification",
            f"{app} OAuth authorization endpoint token refresh token",
            f"{app} API app connection limits uncertified partner program tiers",
            f"{app} app marketplace listing certification requirements",
        ]
        pages: list[dict[str, str]] = []
        for query in queries:
            for page in await self.search(query):
                if page["url"] and all(p["url"] != page["url"] for p in pages):
                    pages.append(page)
        corpus = "\n\n".join(
            f"=== PAGE {i}\nURL: {p['url']}\nTITLE: {p['title']}\n{p['text']}"
            for i, p in enumerate(pages, start=1)
        )
        response = await self._generate(
            system + "\nYou cannot browse. Use only the pages below; every source_url must be one "
            "of their URLs.",
            f"{prompt}\n\nSEARCH RESULTS:\n{corpus}",
            RESEARCH_SCHEMA,
        )
        data = _parse_json(response.text)
        return Research(
            data, [p["url"] for p in pages], self._usage(response, searches=len(queries))
        )

    async def write_json(
        self, system: str, prompt: str, schema: dict[str, Any]
    ) -> tuple[dict[str, Any], Usage]:
        response = await self._generate(system, prompt, schema)
        return _parse_json(response.text), self._usage(response)


# ------------------------------------------------------------- the chain

Notify = Callable[[str], Awaitable[None]]


class ProviderChain:
    """Use the primary provider; on any failure switch to the backup for good."""

    def __init__(self, primary: Provider | None, backup: Provider | None, notify: Notify) -> None:
        self.providers = [p for p in (primary, backup) if p is not None]
        self.index = 0
        self.notify = notify
        self.usage = Usage()

    @property
    def current(self) -> Provider:
        return self.providers[self.index]

    async def _call(self, fn: Callable[[Provider], Awaitable[Any]]) -> Any:
        if not self.providers:
            raise ProviderError("config", "No model provider is configured.")
        while True:
            provider = self.current
            try:
                try:
                    return await fn(provider)
                except ProviderError as exc:
                    if exc.kind != "rate_limit":
                        raise
                    await asyncio.sleep(2)  # one short retry on a plain rate limit
                    return await fn(provider)
            except ProviderError as exc:
                if self.index + 1 >= len(self.providers):
                    raise
                self.index += 1
                await self.notify(
                    f"{provider.name} failed ({exc.message}) - switched to the backup "
                    f"({self.current.name})."
                )

    async def research(self, system: str, prompt: str) -> Research:
        result: Research = await self._call(lambda p: p.research(system, prompt))
        self.usage.add(result.usage)
        return result

    async def write_json(self, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        data, usage = await self._call(lambda p: p.write_json(system, prompt, schema))
        self.usage.add(usage)
        return data  # type: ignore[no-any-return]

    def describe(self) -> str:
        return f"{self.current.name}:{self.current.model}"
