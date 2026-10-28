"""Live agent tests with fakes only."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from app.agent.pipeline import Deps, find_cached, investigate
from app.agent.providers import ProviderChain, ProviderError
from app.agent.store import GeneratedStore
from app.schema import EvidenceLabel
from app.store import DEFAULT_GUIDES_DIR, GuideStore
from tests.agent_fakes import RESEARCH, FakeProvider, draft, ev, fake_probe_runner

LIBRARY = GuideStore.from_directory(DEFAULT_GUIDES_DIR)


def make_deps(
    tmp_path: Path,
    primary: FakeProvider | None,
    backup: FakeProvider | None = None,
    timeout: float = 30,
) -> Deps:
    return Deps(
        chain_factory=lambda notify: ProviderChain(primary, backup, notify),
        probe_runner=fake_probe_runner,
        generated=GeneratedStore(tmp_path),
        library=LIBRARY,
        timeout_s=timeout,
    )


def run(query: str, deps: Deps, refresh: bool = False) -> list[dict[str, Any]]:
    async def collect() -> list[dict[str, Any]]:
        return [e async for e in investigate(query, refresh, deps)]

    return asyncio.run(collect())


def test_happy_path_saves_guide_and_enforces_evidence(tmp_path: Path) -> None:
    sourced_difficulty = draft()
    sourced_difficulty["difficulty"]["evidence"] = ev("SOURCED", ["s1"])
    provider = FakeProvider("primary", write_errors=[sourced_difficulty])
    deps = make_deps(tmp_path, provider)
    events = run("Acme Chat", deps)
    assert events[-1] == {"type": "done", "slug": "acme-chat", "cached": False, "from": "generated"}
    steps = [(e["step"], e["status"]) for e in events if e["type"] == "step"]
    assert ("research", "done") in steps and ("validate", "done") in steps
    assert any(e["type"] == "probe" and e["id"] == "authorize" for e in events)

    guide = deps.generated.get("acme-chat")
    assert guide is not None
    reqs = {r.name: r.evidence for r in guide.requirements}
    # TESTED citing a probe that never ran is corrected.
    assert reqs["Fake test"].label is EvidenceLabel.UNVERIFIED
    # A claim backed only by a community source cannot be SOURCED.
    assert reqs["Blog claim"].label is EvidenceLabel.INFERRED
    # Real probe citations stay TESTED.
    assert guide.nuances[0].evidence.label is EvidenceLabel.TESTED
    # Steps renumbered, and signing in is always a human step.
    assert [s.order for s in guide.steps] == [1, 2]
    assert guide.steps[0].who == "human"
    # Time ranges are ordered by code.
    assert guide.time.hands_on_minutes_min == 30 and guide.time.hands_on_minutes_max == 60
    # The page that does not exist was dropped from sources.
    assert all(not str(s.url).endswith("/missing") for s in guide.sources)
    # The difficulty level is always a judgement.
    assert guide.difficulty.evidence.label is EvidenceLabel.INFERRED
    # Code-owned fields.
    assert guide.meta.generated_by == "live_agent"
    assert guide.meta.model == "primary:fake-model"
    assert guide.composio_note.managed_oauth == "unknown"
    assert any("authorize" in line for line in guide.agent_vs_human.agent_did)
    assert any("Sources disagree" in u for u in guide.unverified)
    # A conclusive endpoint check the writer ignored is added as a TESTED note by code.
    auto = [n for n in guide.nuances if n.evidence.probe_ids == ["oauth-meta"]]
    assert auto and auto[0].evidence.label is EvidenceLabel.TESTED
    # Composio's own docs are offered to the writer as citable, checked sources.
    assert (
        "composio-auth: https://docs.composio.dev/docs/auth-configuration"
        in provider.last_write_prompt
    )


@pytest.mark.parametrize("kind", ["auth", "quota", "server", "timeout", "config", "bad_output"])
def test_research_failure_switches_to_backup(tmp_path: Path, kind: str) -> None:
    primary = FakeProvider("openai", research_error=ProviderError(kind, f"{kind} problem"))  # type: ignore[arg-type]
    backup = FakeProvider("gemini+tavily")
    deps = make_deps(tmp_path, primary, backup)
    events = run("Acme Chat", deps)
    notices = [e["message"] for e in events if e["type"] == "notice"]
    assert any("switched to the backup (gemini+tavily)" in n for n in notices)
    assert events[-1]["type"] == "done"
    guide = deps.generated.get("acme-chat")
    assert guide is not None and guide.meta.model == "gemini+tavily:fake-model"
    assert backup.research_calls == 1


def test_write_failure_switches_and_reuses_research(tmp_path: Path) -> None:
    primary = FakeProvider("openai", write_errors=[ProviderError("quota", "out of credit")])
    backup = FakeProvider("gemini+tavily")
    deps = make_deps(tmp_path, primary, backup)
    events = run("Acme Chat", deps)
    assert events[-1]["type"] == "done"
    assert primary.research_calls == 1 and backup.research_calls == 0
    assert backup.write_calls == 1


def test_rate_limit_retries_once_without_switching(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def no_sleep(_: float) -> None:
        return None

    monkeypatch.setattr("app.agent.providers.asyncio.sleep", no_sleep)
    primary = FakeProvider("openai", write_errors=[ProviderError("rate_limit", "slow down")])
    backup = FakeProvider("gemini+tavily")
    events = run("Acme Chat", make_deps(tmp_path, primary, backup))
    assert events[-1]["type"] == "done"
    assert not [e for e in events if e["type"] == "notice"]
    assert backup.write_calls == 0 and primary.write_calls == 2


def test_both_providers_failing_is_an_honest_error(tmp_path: Path) -> None:
    primary = FakeProvider("openai", research_error=ProviderError("quota", "out of credit"))
    backup = FakeProvider("gemini+tavily", research_error=ProviderError("auth", "bad key"))
    events = run("Acme Chat", make_deps(tmp_path, primary, backup))
    assert events[-1]["type"] == "error" and events[-1]["code"] == "provider"
    assert "browse the library" in events[-1]["message"]


def test_unknown_app(tmp_path: Path) -> None:
    data = {**RESEARCH, "is_real_app": False, "official_domains": [], "website": ""}
    events = run("Zzqx Nonexistent", make_deps(tmp_path, FakeProvider(research_data=data)))
    assert events[-1]["type"] == "error" and events[-1]["code"] == "unknown_app"


def test_app_without_oauth_says_so_and_saves_nothing(tmp_path: Path) -> None:
    data = {**RESEARCH, "oauth_supported": "no", "other_auth": "API keys"}
    deps = make_deps(tmp_path, FakeProvider(research_data=data))
    events = run("Acme Chat", deps)
    assert events[-1]["type"] == "no_oauth"
    assert "API keys" in events[-1]["message"]
    assert deps.generated.all() == []


def test_invalid_draft_is_repaired_once(tmp_path: Path) -> None:
    provider = FakeProvider(write_errors=[{"summary": "missing everything"}])
    events = run("Acme Chat", make_deps(tmp_path, provider))
    assert events[-1]["type"] == "done"
    assert provider.write_calls == 2


def test_still_invalid_after_repair_fails_honestly(tmp_path: Path) -> None:
    provider = FakeProvider(write_errors=[{"bad": 1}, {"bad": 2}])
    events = run("Acme Chat", make_deps(tmp_path, provider))
    assert events[-1]["type"] == "error" and events[-1]["code"] == "invalid_output"


def test_timeout_stops_the_run(tmp_path: Path) -> None:
    events = run("Acme Chat", make_deps(tmp_path, FakeProvider(delay=5), timeout=0.2))
    assert events[-1]["type"] == "error" and events[-1]["code"] == "timeout"


def test_cache_finds_library_and_generated_guides(tmp_path: Path) -> None:
    deps = make_deps(tmp_path, FakeProvider())
    assert find_cached("GitHub", deps) == {
        "type": "done",
        "slug": "github",
        "cached": True,
        "from": "library",
    }
    assert find_cached("slack.com", deps)["slug"] == "slack"  # type: ignore[index]
    assert find_cached("Acme Chat", deps) is None
    run("Acme Chat", deps)
    assert find_cached("Acme Chat", deps)["slug"] == "acme-chat"  # type: ignore[index]
    assert find_cached("acme.example", deps)["slug"] == "acme-chat"  # type: ignore[index]


def test_library_app_regenerated_live_gets_its_own_slug(tmp_path: Path) -> None:
    data = {
        **RESEARCH,
        "app_name": "GitHub",
        "website": "https://github.com",
        "official_domains": ["github.com"],
    }
    provider = FakeProvider(
        research_data=data,
        write_errors=[{**draft(), "app": {"name": "GitHub", "category": "Developer tools"}}],
    )
    deps = make_deps(tmp_path, provider)
    events = run("GitHub", deps, refresh=True)
    assert events[-1]["slug"] == "github-live"
    guide = deps.generated.get("github-live")
    assert guide is not None and guide.composio_note.managed_oauth == "yes"
