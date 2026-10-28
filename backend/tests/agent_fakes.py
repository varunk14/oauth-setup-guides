"""Fakes for agent tests: no real model, search or website calls."""

from __future__ import annotations

import asyncio
import copy
from datetime import UTC, datetime
from typing import Any

from app.agent.providers import ProviderError, Research, Usage
from app.probes import Allowlist, ProbeSpec
from app.schema import Probe

RESEARCH: dict[str, Any] = {
    "app_name": "Acme Chat",
    "website": "https://acme.example",
    "category": "Communication",
    "is_real_app": True,
    "oauth_supported": "yes",
    "other_auth": "",
    "official_domains": ["acme.example"],
    "authorize_endpoint": "https://auth.acme.example/oauth/authorize",
    "token_endpoint": "https://auth.acme.example/oauth/token",
    "developer_console_url": "https://acme.example/developers/apps",
    "docs_urls": ["https://acme.example/docs/oauth"],
    "findings": [
        {
            "topic": "setup",
            "fact": "Apps are created in the developer console.",
            "source_url": "https://acme.example/docs/oauth",
            "quote": "Create an app",
        },
        {
            "topic": "review",
            "fact": "Public apps need review.",
            "source_url": "https://acme.example/docs/review",
            "quote": "Review takes 5 days",
        },
        {
            "topic": "other",
            "fact": "A blog says review is slow.",
            "source_url": "https://blog.other.test/acme",
            "quote": "slow",
        },
        {
            "topic": "other",
            "fact": "A page that does not exist.",
            "source_url": "https://acme.example/missing",
            "quote": "x",
        },
    ],
    "conflicts": ["Review time: docs say 5 days, a blog says weeks."],
    "unknowns": ["Rate limits are not documented."],
}


def ev(
    label: str, sources: list[str] | None = None, probes: list[str] | None = None
) -> dict[str, Any]:
    return {"label": label, "source_ids": sources or [], "probe_ids": probes or []}


def draft() -> dict[str, Any]:
    return {
        "app": {"name": "Acme Chat", "category": "Communication"},
        "summary": "Self-serve app creation; public apps need a short review.",
        "difficulty": {
            "level": "Medium",
            "reason": "Review for public apps.",
            "evidence": ev("INFERRED", ["s1"]),
        },
        "time": {
            "hands_on": "30-60 min",
            "hands_on_minutes_min": 60,
            "hands_on_minutes_max": 30,
            "approval_wait": "About 5 days",
            "approval_wait_days_min": 3,
            "approval_wait_days_max": 7,
            "detail": "Review takes about 5 days.",
            "evidence": ev("SOURCED", ["s2"]),
        },
        "requirements": [
            {
                "name": "Account",
                "required": "yes",
                "detail": "A free account.",
                "evidence": ev("SOURCED", ["s1"]),
            },
            # Cites a probe that does not exist: must be corrected.
            {
                "name": "Fake test",
                "required": "no",
                "detail": "x",
                "evidence": ev("TESTED", [], ["nope"]),
            },
            # Only a community source: SOURCED must become INFERRED.
            {
                "name": "Blog claim",
                "required": "no",
                "detail": "slow",
                "evidence": ev("SOURCED", ["s3"]),
            },
        ],
        "scopes": [],
        "steps": [
            {
                "order": 5,
                "title": "Create the app",
                "action": "Sign in to the developer console and click New app.",
                "where_url": "https://acme.example/developers/apps",
                "who": "agent",
                "expected_result": "A client ID.",
                "evidence": ev("SOURCED", ["s1"]),
            },
            {
                "order": 9,
                "title": "Check the endpoint",
                "action": "Confirm the authorize endpoint answers.",
                "who": "agent",
                "expected_result": "It rejects a fake client.",
                "evidence": ev("TESTED", [], ["authorize"]),
            },
        ],
        "review_process": {
            "required": "conditional",
            "trigger": "Public distribution.",
            "typical_wait": "5 days",
            "evidence": ev("SOURCED", ["s2"]),
        },
        "blockers": [],
        "agent_can": ["Draft scope justifications."],
        "human_must": ["Sign in and create the app."],
        "nuances": [
            {
                "topic": "pkce",
                "detail": "PKCE S256 supported.",
                "evidence": ev("TESTED", [], ["oidc"]),
            }
        ],
        "unverified": ["Exact review time."],
    }


class FakeProvider:
    def __init__(
        self,
        name: str = "fake",
        *,
        research_error: ProviderError | None = None,
        write_errors: list[ProviderError | dict[str, Any]] | None = None,
        research_data: dict[str, Any] | None = None,
        delay: float = 0,
    ) -> None:
        self.name = name
        self.model = "fake-model"
        self.research_error = research_error
        self.write_queue = list(write_errors or [])
        self.research_data = research_data
        self.delay = delay
        self.research_calls = 0
        self.write_calls = 0
        self.last_write_prompt = ""

    async def research(self, system: str, prompt: str) -> Research:
        self.research_calls += 1
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.research_error:
            raise self.research_error
        data = copy.deepcopy(self.research_data or RESEARCH)
        return Research(data, ["https://acme.example/docs/oauth"], Usage(100, 50, 3))

    async def write_json(
        self, system: str, prompt: str, schema: dict[str, Any]
    ) -> tuple[dict[str, Any], Usage]:
        self.write_calls += 1
        self.last_write_prompt = prompt
        if self.write_queue:
            item = self.write_queue.pop(0)
            if isinstance(item, ProviderError):
                raise item
            return item, Usage(10, 10)
        return draft(), Usage(200, 400)


async def fake_probe_runner(specs: list[ProbeSpec], allowlist: Allowlist) -> list[Probe]:
    out = []
    for s in specs:
        outcome = "confirmed"
        summary = "Page loads (HTTP 200)."
        if s.url.endswith("/missing"):
            outcome, summary = "not_found", "Page not found (HTTP 404)."
        if s.kind == "oauth_metadata":
            outcome, summary = "not_found", "No metadata document (HTTP 404)."
        if s.kind == "oidc_discovery":
            summary = "Metadata found. PKCE methods: S256"
        out.append(
            Probe.model_validate(
                {
                    "id": s.id,
                    "kind": s.kind,
                    "target_url": s.url,
                    "outcome": outcome,
                    "http_status": 200,
                    "summary": summary,
                    "ran_at": datetime(2026, 10, 28, tzinfo=UTC),
                }
            )
        )
    return out
