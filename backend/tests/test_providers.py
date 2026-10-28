"""Provider error mapping and the Tavily client, with fakes (no network)."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import httpx
import httpx2
import openai
import pytest

from app.agent.providers import GeminiTavilyProvider, OpenAIProvider, ProviderError


def _status_error(
    cls: type[openai.APIStatusError], status: int, code: str | None = None
) -> Exception:
    request = httpx2.Request("POST", "https://api.openai.com/v1/responses")
    body = {"code": code} if code else None
    return cls("error", response=httpx2.Response(status, request=request), body=body)


class FakeResponses:
    def __init__(self, exc: Exception) -> None:
        self.exc = exc

    async def create(self, **_: Any) -> Any:
        raise self.exc


@pytest.mark.parametrize(
    ("exc", "kind"),
    [
        (_status_error(openai.AuthenticationError, 401), "auth"),
        (_status_error(openai.RateLimitError, 429, "insufficient_quota"), "quota"),
        (
            openai.RateLimitError(
                "error",
                response=httpx2.Response(429, request=httpx2.Request("POST", "https://x")),
                body={"error": {"code": "insufficient_quota"}},
            ),
            "quota",
        ),
        (_status_error(openai.RateLimitError, 429, "rate_limit_exceeded"), "rate_limit"),
        (_status_error(openai.InternalServerError, 500), "server"),
        (openai.APITimeoutError(httpx2.Request("POST", "https://api.openai.com")), "timeout"),
    ],
)
def test_openai_errors_map_to_kinds(exc: Exception, kind: str) -> None:
    provider = OpenAIProvider("k", "m", 3, client=SimpleNamespace(responses=FakeResponses(exc)))
    with pytest.raises(ProviderError) as info:
        asyncio.run(provider.research("s", "p"))
    assert info.value.kind == kind


def test_openai_research_collects_consulted_sources() -> None:
    call = SimpleNamespace(
        type="web_search_call",
        action=SimpleNamespace(sources=[SimpleNamespace(url="https://a.example/x")]),
    )
    response = SimpleNamespace(
        status="completed",
        output=[call, SimpleNamespace(type="message")],
        output_text='{"app_name": "A"}',
        usage=SimpleNamespace(input_tokens=10, output_tokens=5),
    )

    class Ok:
        async def create(self, **kwargs: Any) -> Any:
            assert kwargs["max_tool_calls"] == 3
            assert kwargs["tools"][0]["type"] == "web_search"
            return response

    provider = OpenAIProvider("k", "m", 3, client=SimpleNamespace(responses=Ok()))
    result = asyncio.run(provider.research("s", "p"))
    assert result.data == {"app_name": "A"}
    assert result.consulted_urls == ["https://a.example/x"]
    assert result.usage.searches == 1 and result.usage.input_tokens == 10


def test_openai_non_json_output_is_bad_output() -> None:
    response = SimpleNamespace(status="completed", output=[], output_text="not json", usage=None)

    class Ok:
        async def create(self, **_: Any) -> Any:
            return response

    provider = OpenAIProvider("k", "m", 3, client=SimpleNamespace(responses=Ok()))
    with pytest.raises(ProviderError) as info:
        asyncio.run(provider.write_json("s", "p", {}))
    assert info.value.kind == "bad_output"


@pytest.mark.parametrize(
    ("status", "kind"), [(401, "auth"), (432, "quota"), (429, "quota"), (500, "server")]
)
def test_tavily_errors_map_to_kinds(status: int, kind: str) -> None:
    async def scenario() -> None:
        http = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(status)))
        provider = GeminiTavilyProvider("g", "m", "t", client=object(), http=http)
        await provider.search("acme oauth")

    with pytest.raises(ProviderError) as info:
        asyncio.run(scenario())
    assert info.value.kind == kind


def test_tavily_search_sends_key_and_trims_pages() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers["authorization"]
        seen["body"] = request.read()
        return httpx.Response(
            200,
            json={
                "results": [{"url": "https://a.example", "title": "A", "raw_content": "x" * 9000}]
            },
        )

    async def scenario() -> list[dict[str, str]]:
        http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        provider = GeminiTavilyProvider("g", "m", "tvly-test", client=object(), http=http)
        return await provider.search("acme oauth")

    pages = asyncio.run(scenario())
    assert seen["auth"] == "Bearer tvly-test"
    assert b'"search_depth":"basic"' in seen["body"].replace(b" ", b"")
    assert len(pages[0]["text"]) == 5000


def test_missing_tavily_key_is_a_config_error() -> None:
    provider = GeminiTavilyProvider("g", "m", "", client=object())
    with pytest.raises(ProviderError) as info:
        asyncio.run(provider.search("x"))
    assert info.value.kind == "config"
