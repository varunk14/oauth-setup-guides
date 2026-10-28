"""The /api/generate endpoint: streaming, cache first, then limits and the run lock."""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.agent.limits import LimitExceeded, RunGate
from app.agent.pipeline import Deps
from app.agent.providers import ProviderChain
from app.agent.settings import load_settings
from app.agent.store import GeneratedStore
from app.main import Agent, app, get_agent, get_generated
from app.store import DEFAULT_GUIDES_DIR, GuideStore
from tests.agent_fakes import FakeProvider, fake_probe_runner


def events(response_text: str) -> list[dict[str, object]]:
    return [
        json.loads(line[len("data: ") :])
        for line in response_text.splitlines()
        if line.startswith("data: ")
    ]


@pytest.fixture
def agent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Agent]:
    monkeypatch.setenv("OPENAI_API_KEY", "test-not-a-real-key")
    monkeypatch.delenv("ENV_FILE", raising=False)
    settings = replace(load_settings(), generated_dir=tmp_path)
    generated = GeneratedStore(tmp_path)
    provider = FakeProvider("primary")
    deps = Deps(
        chain_factory=lambda notify: ProviderChain(provider, None, notify),
        probe_runner=fake_probe_runner,
        generated=generated,
        library=GuideStore.from_directory(DEFAULT_GUIDES_DIR),
    )
    agent = Agent(settings, RunGate(per_ip_per_hour=2, per_day=3), deps)
    app.dependency_overrides[get_agent] = lambda: agent
    app.dependency_overrides[get_generated] = lambda: generated
    yield agent
    app.dependency_overrides.clear()


def post(query: str, refresh: bool = False, ip: str = "1.2.3.4") -> list[dict[str, object]]:
    client = TestClient(app)
    response = client.post(
        "/api/generate", json={"query": query, "refresh": refresh}, headers={"x-forwarded-for": ip}
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    return events(response.text)


def test_live_run_streams_progress_and_guide_is_served(agent: Agent) -> None:
    stream = post("Acme Chat")
    assert stream[0]["type"] == "step"
    assert stream[-1] == {"type": "done", "slug": "acme-chat", "cached": False, "from": "generated"}
    client = TestClient(app)
    assert client.get("/api/guides/acme-chat").json()["meta"]["generated_by"] == "live_agent"
    listed = [g["slug"] for g in client.get("/api/guides").json()]
    assert "acme-chat" in listed and "github" in listed


def test_library_answers_are_free_and_skip_limits(agent: Agent) -> None:
    for _ in range(5):
        assert post("GitHub")[-1] == {
            "type": "done",
            "slug": "github",
            "cached": True,
            "from": "library",
        }
    assert agent.gate.day.maxlen is None and len(agent.gate.day) == 0


def test_per_ip_limit_gives_clear_message(agent: Agent) -> None:
    assert post("Acme One", refresh=True)[-1]["type"] == "done"
    assert post("Acme Two", refresh=True)[-1]["type"] == "done"
    last = post("Acme Three", refresh=True)[-1]
    assert last["type"] == "error" and last["code"] == "rate_limited"
    assert "browse the library" in str(last["message"])
    # A different visitor is not blocked by someone else's hourly limit.
    assert post("Acme Four", refresh=True, ip="5.6.7.8")[-1]["type"] == "done"


def test_daily_limit(agent: Agent) -> None:
    for i, ip in enumerate(["1.1.1.1", "2.2.2.2", "3.3.3.3"]):
        assert post(f"Acme {i}", refresh=True, ip=ip)[-1]["type"] == "done"
    last = post("Acme 9", refresh=True, ip="4.4.4.4")[-1]
    assert last["code"] == "daily_limit"


def test_bad_query_is_rejected_without_a_run(agent: Agent) -> None:
    last = post("<script>")[-1]
    assert last["code"] == "bad_query"
    assert len(agent.gate.day) == 0


def test_not_configured_server(agent: Agent) -> None:
    agent.settings = replace(
        agent.settings, openai_api_key="", gemini_api_key="", tavily_api_key=""
    )
    last = post("Brand New App")[-1]
    assert last["code"] == "not_configured"


def test_gate_reports_busy_while_a_run_holds_the_lock() -> None:
    import asyncio

    async def scenario() -> str:
        gate = RunGate(per_ip_per_hour=5, per_day=5)
        async with gate.lock:
            try:
                gate.check("9.9.9.9")
            except LimitExceeded as exc:
                return exc.code
        return "no error"

    assert asyncio.run(scenario()) == "busy"


def test_live_copies_of_library_apps_are_not_listed_but_still_reachable(agent: Agent) -> None:
    from app.schema import Guide
    from tests.agent_fakes import RESEARCH

    data = {
        **RESEARCH,
        "app_name": "GitHub",
        "website": "https://github.com",
        "official_domains": ["github.com"],
    }
    agent.deps.chain_factory = lambda notify: ProviderChain(
        FakeProvider(research_data=data), None, notify
    )
    assert post("GitHub", refresh=True)[-1]["slug"] == "github-live"
    client = TestClient(app)
    slugs = [g["slug"] for g in client.get("/api/guides").json()]
    assert slugs.count("github") == 1 and "github-live" not in slugs
    assert (
        Guide.model_validate(client.get("/api/guides/github-live").json()).app.slug == "github-live"
    )
