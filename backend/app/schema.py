"""The guide format shared by curated library guides and live agent guides.

Every claim carries an Evidence object. The validators enforce the evidence
rules in code, so a guide cannot call something TESTED unless a recorded probe
backs it, or SOURCED unless it cites a listed source.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

SCHEMA_VERSION: Literal["1"] = "1"

SLUG_PATTERN = r"^[a-z0-9][a-z0-9-]{0,62}$"
ID_PATTERN = r"^[a-z][a-z0-9-]{0,31}$"


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class EvidenceLabel(StrEnum):
    TESTED = "TESTED"
    SOURCED = "SOURCED"
    INFERRED = "INFERRED"
    UNVERIFIED = "UNVERIFIED"


class Evidence(Strict):
    label: EvidenceLabel
    source_ids: list[str] = Field(default_factory=list)
    probe_ids: list[str] = Field(default_factory=list)
    note: str | None = None

    @model_validator(mode="after")
    def label_has_backing(self) -> Evidence:
        if self.label is EvidenceLabel.TESTED and not self.probe_ids:
            raise ValueError("TESTED evidence must reference at least one probe")
        if self.label is EvidenceLabel.SOURCED and not self.source_ids:
            raise ValueError("SOURCED evidence must reference at least one source")
        return self


class Source(Strict):
    id: str = Field(pattern=ID_PATTERN)
    url: HttpUrl
    title: str = Field(min_length=1)
    kind: Literal["official", "community", "other"]
    checked_on: date


class Probe(Strict):
    """A safe automated check run by our backend code, never by the model."""

    id: str = Field(pattern=ID_PATTERN)
    kind: Literal["oidc_discovery", "oauth_metadata", "authorize_endpoint", "url_reachable"]
    target_url: HttpUrl
    ran_at: datetime
    outcome: Literal["confirmed", "not_found", "inconclusive"] = Field(
        description="confirmed: the thing exists and works; not_found: definitely absent; "
        "inconclusive: blocked, timed out or unclear (cannot back a TESTED claim)"
    )
    http_status: int | None = None
    summary: str = Field(min_length=1)


class AppInfo(Strict):
    name: str = Field(min_length=1)
    slug: str = Field(pattern=SLUG_PATTERN)
    website: HttpUrl
    category: str = Field(min_length=1)
    docs_urls: list[HttpUrl] = Field(min_length=1)
    developer_console_url: HttpUrl | None = None


DifficultyLevel = Literal["Easy", "Medium", "Hard", "Very hard"]


class Difficulty(Strict):
    level: DifficultyLevel
    reason: str = Field(min_length=1)
    evidence: Evidence


class TimeEstimate(Strict):
    hands_on: str = Field(
        min_length=1, max_length=40, description="Short label for cards, e.g. '30-60 min'"
    )
    hands_on_minutes_min: int = Field(ge=0)
    hands_on_minutes_max: int = Field(ge=0)
    approval_wait: str = Field(
        min_length=1, max_length=40, description="Short label, e.g. 'None' or '2-6 weeks'"
    )
    approval_wait_days_min: int = Field(ge=0)
    approval_wait_days_max: int = Field(ge=0)
    detail: str | None = Field(
        default=None, description="Plain explanation of the estimate and what changes it"
    )
    evidence: Evidence

    @model_validator(mode="after")
    def ranges_ordered(self) -> TimeEstimate:
        if self.hands_on_minutes_min > self.hands_on_minutes_max:
            raise ValueError("hands_on_minutes_min must be <= hands_on_minutes_max")
        if self.approval_wait_days_min > self.approval_wait_days_max:
            raise ValueError("approval_wait_days_min must be <= approval_wait_days_max")
        return self


YesNoConditional = Literal["yes", "no", "conditional"]


class Requirement(Strict):
    name: str = Field(min_length=1)
    required: YesNoConditional
    detail: str = Field(min_length=1)
    evidence: Evidence


class ScopeInfo(Strict):
    name: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    sensitivity: Literal["standard", "sensitive", "restricted"]
    triggers_review: bool
    evidence: Evidence


class Step(Strict):
    order: int = Field(ge=1)
    title: str = Field(min_length=1)
    action: str = Field(min_length=1)
    where_url: HttpUrl | None = None
    who: Literal["agent", "human", "either"]
    expected_result: str = Field(min_length=1)
    evidence: Evidence


class ReviewProcess(Strict):
    required: YesNoConditional
    trigger: str = Field(min_length=1)
    what_to_submit: list[str] = Field(default_factory=list)
    typical_wait: str = Field(min_length=1)
    common_rejections: list[str] = Field(default_factory=list)
    evidence: Evidence


class Blocker(Strict):
    blocker: str = Field(min_length=1)
    how_to_get_past: str = Field(min_length=1)
    contact: str | None = None
    evidence: Evidence


class AgentVsHuman(Strict):
    agent_did: list[str] = Field(default_factory=list)
    agent_can: list[str] = Field(default_factory=list)
    human_must: list[str] = Field(min_length=1)


class Nuance(Strict):
    topic: Literal[
        "refresh_tokens",
        "token_expiry",
        "pkce",
        "redirect_uris",
        "sandbox_vs_production",
        "rate_limits",
        "tenancy",
        "other",
    ]
    detail: str = Field(min_length=1)
    evidence: Evidence


class ComposioNote(Strict):
    managed_oauth: Literal["yes", "no", "unknown"]
    detail: str = Field(min_length=1)
    snapshot_date: date
    evidence: Evidence


class Meta(Strict):
    schema_version: Literal["1"] = SCHEMA_VERSION
    generated_at: datetime
    generated_by: Literal["library", "live_agent"]
    model: str | None = None
    sources_count: int = Field(ge=0)
    run_seconds: float | None = Field(default=None, ge=0)


class Guide(Strict):
    app: AppInfo
    summary: str = Field(min_length=1)
    difficulty: Difficulty
    time: TimeEstimate
    requirements: list[Requirement]
    scopes: list[ScopeInfo]
    steps: list[Step] = Field(min_length=1)
    review_process: ReviewProcess
    blockers: list[Blocker]
    agent_vs_human: AgentVsHuman
    nuances: list[Nuance]
    unverified: list[str] = Field(
        default_factory=list, description="What we could not verify, in plain words"
    )
    composio_note: ComposioNote
    sources: list[Source]
    probes: list[Probe]
    meta: Meta

    def all_evidence(self) -> list[Evidence]:
        items: list[Evidence] = [
            self.difficulty.evidence,
            self.time.evidence,
            self.review_process.evidence,
            self.composio_note.evidence,
        ]
        for group in (
            self.requirements,
            self.scopes,
            self.steps,
            self.blockers,
            self.nuances,
        ):
            items.extend(entry.evidence for entry in group)
        return items

    @model_validator(mode="after")
    def references_resolve(self) -> Guide:
        source_ids = [s.id for s in self.sources]
        probe_ids = [p.id for p in self.probes]
        if len(set(source_ids)) != len(source_ids):
            raise ValueError("source ids must be unique")
        if len(set(probe_ids)) != len(probe_ids):
            raise ValueError("probe ids must be unique")
        probes_by_id = {p.id: p for p in self.probes}
        for ev in self.all_evidence():
            missing_sources = set(ev.source_ids) - set(source_ids)
            if missing_sources:
                raise ValueError(f"evidence cites unknown sources: {sorted(missing_sources)}")
            missing_probes = set(ev.probe_ids) - set(probe_ids)
            if missing_probes:
                raise ValueError(f"evidence cites unknown probes: {sorted(missing_probes)}")
            if ev.label is EvidenceLabel.TESTED and all(
                probes_by_id[pid].outcome == "inconclusive" for pid in ev.probe_ids
            ):
                raise ValueError("TESTED evidence must cite at least one conclusive probe")
        orders = [s.order for s in self.steps]
        if orders != list(range(1, len(orders) + 1)):
            raise ValueError("steps must be numbered 1..n in order")
        if self.meta.sources_count != len(self.sources):
            raise ValueError("meta.sources_count must equal the number of sources")
        return self
