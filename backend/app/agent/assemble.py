"""Turn research + probe results + the model's draft into a valid Guide.

Our code, not the model, has the last word on evidence:
- TESTED must cite a conclusive probe that we actually ran.
- SOURCED must cite a source we found and checked; community-only becomes INFERRED.
- Steps that involve signing in, submitting, paying or accepting terms are "human".
- The Composio note, sources, probes, "what the agent did" and metadata are filled
  in by code.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field

from app.schema import (
    Blocker,
    Difficulty,
    Evidence,
    EvidenceLabel,
    Guide,
    Nuance,
    Probe,
    Requirement,
    ReviewProcess,
    ScopeInfo,
    Source,
    Step,
    TimeEstimate,
)

DATA_DIR = Path(__file__).resolve().parents[3] / "data"
COMPOSIO_SOURCE_ID = "composio-dir"
COMPOSIO_DIRECTORY_URL = "https://docs.composio.dev/toolkits/managed-auth"
COMPOSIO_AUTH_SOURCE_ID = "composio-auth"
COMPOSIO_AUTH_URL = "https://docs.composio.dev/docs/auth-configuration/custom-auth-configs"


def composio_sources() -> list[Source]:
    """Pre-checked Composio pages that every live guide may cite."""
    checked = json.loads((DATA_DIR / "composio_managed_auth.json").read_text())["snapshot_date"]
    return [
        Source.model_validate(
            {
                "id": COMPOSIO_AUTH_SOURCE_ID,
                "url": COMPOSIO_AUTH_URL,
                "title": "Composio custom auth configs (bring your own OAuth app)",
                "kind": "official",
                "checked_on": checked,
            }
        ),
        Source.model_validate(
            {
                "id": COMPOSIO_SOURCE_ID,
                "url": COMPOSIO_DIRECTORY_URL,
                "title": "Composio managed OAuth apps directory",
                "kind": "official",
                "checked_on": checked,
            }
        ),
    ]


ENDPOINT_PROBES = ("oidc_discovery", "oauth_metadata", "authorize_endpoint")
MAX_SOURCES = 14

HUMAN_ONLY = re.compile(
    r"\b(sign(s|ing)? in|log(s|ging)? in|login to|create an account|sign up|submit|pay|"
    r"payment|accept (the )?terms|agree to|click allow|approve the consent|consent screen "
    r"and approve|record a|upload a|verify your (identity|business))\b",
    re.IGNORECASE,
)

MULTI_PART_SUFFIXES = {"co.uk", "com.au", "co.jp", "co.in", "com.br", "co.nz", "co.za"}


def registrable_domain(host: str) -> str:
    host = host.lower().strip(".")
    if host.startswith("www."):
        host = host[4:]
    parts = host.split(".")
    if len(parts) >= 3 and ".".join(parts[-2:]) in MULTI_PART_SUFFIXES:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def host_of(url: str) -> str:
    try:
        return (urlsplit(url).hostname or "").lower()
    except ValueError:
        return ""


def is_http_url(url: str) -> bool:
    parts = urlsplit(url)
    return parts.scheme in ("http", "https") and bool(parts.hostname)


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:60] or "app"


# ------------------------------------------------------------------ draft


class Strict(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)


class DraftApp(Strict):
    name: str
    category: str = "Other"


class Draft(Strict):
    """What we ask the model to write. Everything else is filled in by code."""

    app: DraftApp
    summary: str
    difficulty: Difficulty
    time: TimeEstimate
    requirements: list[Requirement] = Field(default_factory=list)
    scopes: list[ScopeInfo] = Field(default_factory=list)
    steps: list[Step] = Field(min_length=1)
    review_process: ReviewProcess
    blockers: list[Blocker] = Field(default_factory=list)
    agent_can: list[str] = Field(default_factory=list)
    human_must: list[str] = Field(default_factory=list)
    nuances: list[Nuance] = Field(default_factory=list)
    unverified: list[str] = Field(default_factory=list)


DROP_KEYS = {"title", "default", "pattern", "format", "minLength", "maxLength", "examples"}


def _inline(node: Any, defs: dict[str, Any]) -> Any:
    if isinstance(node, dict):
        if "$ref" in node:
            return _inline(defs[node["$ref"].split("/")[-1]], defs)
        out: dict[str, Any] = {}
        for key, value in node.items():
            if key in DROP_KEYS or key == "$defs":
                continue
            if key == "properties" and isinstance(value, dict):
                # Field names are data, not schema keywords: keep "title", "required", ...
                out[key] = {name: _inline(sub, defs) for name, sub in value.items()}
            else:
                out[key] = _inline(value, defs)
        return out
    if isinstance(node, list):
        return [_inline(v, defs) for v in node]
    return node


MODEL_REQUIRED_FIELD = "is_required"


def _rename_required(node: Any) -> None:
    """Models confuse a data field named "required" with the JSON Schema keyword.

    The schema the model sees calls it "is_required"; normalize_draft maps it back.
    """
    if isinstance(node, dict):
        props = node.get("properties")
        if isinstance(props, dict) and "required" in props:
            props[MODEL_REQUIRED_FIELD] = props.pop("required")
            if isinstance(node.get("required"), list):
                node["required"] = [
                    MODEL_REQUIRED_FIELD if k == "required" else k for k in node["required"]
                ]
        for value in node.values():
            _rename_required(value)
    elif isinstance(node, list):
        for value in node:
            _rename_required(value)


def draft_schema() -> dict[str, Any]:
    """The Draft JSON schema, inlined and trimmed so both providers accept it."""
    raw = Draft.model_json_schema()
    result: dict[str, Any] = _inline(raw, raw.get("$defs", {}))
    _rename_required(result)
    return result


def normalize_draft(raw: dict[str, Any]) -> dict[str, Any]:
    """Fix small, mechanical slips before validation (order of ranges, long labels)."""
    data: dict[str, Any] = json.loads(json.dumps(raw))
    time = data.get("time")
    if isinstance(time, dict):
        for lo_key, hi_key in (
            ("hands_on_minutes_min", "hands_on_minutes_max"),
            ("approval_wait_days_min", "approval_wait_days_max"),
        ):
            lo, hi = time.get(lo_key), time.get(hi_key)
            if isinstance(lo, int) and isinstance(hi, int) and lo > hi:
                time[lo_key], time[hi_key] = hi, lo
        extra = []
        for key in ("hands_on", "approval_wait"):
            label = time.get(key)
            if isinstance(label, str) and len(label) > 40:
                extra.append(label)
                time[key] = label[:37].rstrip() + "..."
        if extra:
            time["detail"] = " ".join(filter(None, [time.get("detail"), *extra]))
    yes_no = {
        True: "yes",
        False: "no",
        "true": "yes",
        "false": "no",
        "required": "yes",
        "optional": "conditional",
        "sometimes": "conditional",
    }
    targets = [*(data.get("requirements") or []), data.get("review_process")]
    for item in targets:
        if not isinstance(item, dict):
            continue
        if MODEL_REQUIRED_FIELD in item:
            item["required"] = item.pop(MODEL_REQUIRED_FIELD)
        # Missing entirely: "conditional" (it depends) is the neutral, non-committal value.
        item.setdefault("required", "conditional")
        if "required" in item:
            value = item["required"]
            key = value.strip().lower() if isinstance(value, str) else value
            if key in ("yes", "no", "conditional"):
                item["required"] = key
            elif key in yes_no:
                item["required"] = yes_no[key]
    steps = data.get("steps")
    if isinstance(steps, list):
        for i, step in enumerate(steps, start=1):
            if isinstance(step, dict):
                step["order"] = i
                if step.get("who") not in ("agent", "human", "either"):
                    step["who"] = "human"
    return data


# ------------------------------------------------------------- composio


def composio_status(app_name: str, website: str) -> str:
    """Return 'yes', 'no' or 'unknown' from the dated directory snapshot."""
    snapshot = json.loads((DATA_DIR / "composio_managed_auth.json").read_text())
    managed, byo = set(snapshot["managed"]), set(snapshot["byo"])
    base = registrable_domain(host_of(website)).split(".")[0] if website else ""
    candidates = {
        re.sub(r"[^a-z0-9]", "", app_name.lower()),
        slugify(app_name).replace("-", "_"),
        slugify(app_name),
        base,
    }
    candidates.discard("")
    if candidates & managed:
        return "yes"
    if candidates & byo:
        return "no"
    return "unknown"


def composio_note(status: str) -> dict[str, Any]:
    snapshot = json.loads((DATA_DIR / "composio_managed_auth.json").read_text())
    if status == "yes":
        detail = (
            "Composio lists a managed OAuth app for this toolkit, so you can start without "
            "registering your own. You need your own app for your own name on the consent "
            "screen, custom scopes, a dedicated rate limit quota or faster polling triggers."
        )
        label = EvidenceLabel.SOURCED
    elif status == "no":
        detail = (
            "Composio lists this toolkit under 'Bring your own OAuth app', so you need to "
            "register your own app with the provider, as described below."
        )
        label = EvidenceLabel.SOURCED
    else:
        detail = (
            "We could not match this app to a toolkit in Composio's managed OAuth directory "
            "snapshot. Check the directory before you start."
        )
        label = EvidenceLabel.UNVERIFIED
    evidence: dict[str, Any] = {"label": label.value}
    if label is EvidenceLabel.SOURCED:
        evidence["source_ids"] = [COMPOSIO_SOURCE_ID]
    return {
        "managed_oauth": status,
        "detail": detail,
        "snapshot_date": snapshot["snapshot_date"],
        "evidence": evidence,
    }


# --------------------------------------------------------------- sources


def build_sources(
    research: dict[str, Any], consulted: list[str], official: set[str], today: date
) -> list[Source]:
    """Number every URL the research relied on; official vs community decided by domain."""
    urls: list[str] = []
    for url in [f.get("source_url", "") for f in research.get("findings", [])] + list(
        research.get("docs_urls", [])
    ):
        url = str(url).strip()
        if is_http_url(url) and url not in urls:
            urls.append(url)
    for url in consulted:
        if is_http_url(url) and url not in urls and len(urls) < MAX_SOURCES:
            urls.append(url)
    sources = []
    for i, url in enumerate(urls[:MAX_SOURCES], start=1):
        kind = "official" if registrable_domain(host_of(url)) in official else "community"
        title = next(
            (
                f.get("fact", "")[:80]
                for f in research.get("findings", [])
                if f.get("source_url") == url
            ),
            "",
        )
        sources.append(
            Source.model_validate(
                {
                    "id": f"s{i}",
                    "url": url,
                    "title": title or host_of(url) + urlsplit(url).path,
                    "kind": kind,
                    "checked_on": today,
                }
            )
        )
    return sources


# ------------------------------------------------------------- evidence


def sanitize(ev: Evidence, sources: dict[str, Source], probes: dict[str, Probe]) -> Evidence:
    source_ids = [s for s in ev.source_ids if s in sources]
    probe_ids = [p for p in ev.probe_ids if p in probes]
    conclusive = [p for p in probe_ids if probes[p].outcome != "inconclusive"]
    label = ev.label
    note = ev.note
    corrected = False
    if label is EvidenceLabel.TESTED and not conclusive:
        label = EvidenceLabel.SOURCED if source_ids else EvidenceLabel.UNVERIFIED
        corrected = True
    if label is EvidenceLabel.SOURCED:
        if not source_ids:
            label, corrected = EvidenceLabel.UNVERIFIED, True
        elif all(sources[s].kind != "official" for s in source_ids):
            label, corrected = EvidenceLabel.INFERRED, True
            note = (note + " " if note else "") + "Based on a non-official source."
    if corrected:
        note = (note + " " if note else "") + "Label set by our checks."
    if label is EvidenceLabel.TESTED:
        probe_ids = conclusive
    return Evidence(label=label, source_ids=source_ids, probe_ids=probe_ids, note=note)


def judgement(evidence: dict[str, Any]) -> dict[str, Any]:
    """A difficulty level is our judgement from the sources, never a sourced fact."""
    if evidence["label"] in ("SOURCED", "TESTED"):
        evidence = {
            **evidence,
            "label": "INFERRED",
            "probe_ids": [],
            "note": " ".join(
                filter(
                    None,
                    [evidence.get("note"), "The level is our judgement from the cited sources."],
                )
            ),
        }
    return evidence


def _short(text: str, limit: int = 40) -> str:
    return text if len(text) <= limit else text[: limit - 3].rstrip() + "..."


def fix_time(time: TimeEstimate) -> TimeEstimate:
    data = time.model_dump()
    lo, hi = sorted((data["hands_on_minutes_min"], data["hands_on_minutes_max"]))
    wlo, whi = sorted((data["approval_wait_days_min"], data["approval_wait_days_max"]))
    data.update(
        hands_on_minutes_min=lo,
        hands_on_minutes_max=hi,
        approval_wait_days_min=wlo,
        approval_wait_days_max=whi,
    )
    return TimeEstimate.model_validate(data)


# -------------------------------------------------------------- assemble


def agent_did(
    probes: list[Probe], searches: int, sources: list[Source], provider: str
) -> list[str]:
    lines = [
        f"Researched the official docs with {provider} ({searches} web searches) and kept "
        f"{len(sources)} sources, each checked to load."
    ]
    for p in probes:
        lines.append(f"Checked {p.target_url}: {p.outcome.replace('_', ' ')}. {p.summary}")
    return lines


def assemble(
    *,
    slug: str,
    draft: Draft,
    research: dict[str, Any],
    sources: list[Source],
    probes: list[Probe],
    searches: int,
    provider: str,
    run_seconds: float,
    now: datetime | None = None,
) -> Guide:
    now = (now or datetime.now(UTC)).replace(microsecond=0)
    website = str(research.get("website", "")).strip()
    status = composio_status(draft.app.name, website)
    all_sources = [*sources, *composio_sources()]
    by_id = {s.id: s for s in all_sources}
    probe_by_id = {p.id: p for p in probes}

    def ev(e: Evidence) -> dict[str, Any]:
        return sanitize(e, by_id, probe_by_id).model_dump(mode="json")

    def items(group: list[Any]) -> list[dict[str, Any]]:
        out = []
        for entry in group:
            data = entry.model_dump(mode="json")
            data["evidence"] = ev(entry.evidence)
            out.append(data)
        return out

    steps = items(draft.steps)
    for i, step in enumerate(steps, start=1):
        step["order"] = i
        if step["who"] != "human" and HUMAN_ONLY.search(step["action"] + " " + step["title"]):
            step["who"] = "human"

    time = fix_time(draft.time).model_dump(mode="json")
    time["evidence"] = ev(draft.time.evidence)
    if len(time["hands_on"]) > 40 or len(time["approval_wait"]) > 40:
        time["detail"] = (
            time.get("detail") or ""
        ) + f" {time['hands_on']}; {time['approval_wait']}"
        time["hands_on"] = _short(time["hands_on"])
        time["approval_wait"] = _short(time["approval_wait"])

    docs = [u for u in research.get("docs_urls", []) if is_http_url(u)] or [website]
    console = str(research.get("developer_console_url", "")).strip()

    unverified = list(dict.fromkeys([*draft.unverified, *research.get("unknowns", [])]))
    unverified += [f"Sources disagree: {c}" for c in research.get("conflicts", [])]

    guide: dict[str, Any] = {
        "app": {
            "name": draft.app.name,
            "slug": slug,
            "website": website,
            "category": draft.app.category or "Other",
            "docs_urls": docs[:5],
            "developer_console_url": console if is_http_url(console) else None,
        },
        "summary": draft.summary,
        "difficulty": {
            **draft.difficulty.model_dump(mode="json"),
            "evidence": judgement(ev(draft.difficulty.evidence)),
        },
        "time": time,
        "requirements": items(draft.requirements),
        "scopes": items(draft.scopes),
        "steps": steps,
        "review_process": {
            **draft.review_process.model_dump(mode="json"),
            "evidence": ev(draft.review_process.evidence),
        },
        "blockers": items(draft.blockers),
        "agent_vs_human": {
            "agent_did": agent_did(probes, searches, sources, provider),
            "agent_can": draft.agent_can,
            "human_must": draft.human_must
            or ["Sign in to the provider's developer console and register the app."],
        },
        "nuances": items(draft.nuances),
        "unverified": unverified,
        "composio_note": composio_note(status),
        "sources": [],
        "probes": [json.loads(p.model_dump_json()) for p in probes],
        "meta": {
            "schema_version": "1",
            "generated_at": now.isoformat(),
            "generated_by": "live_agent",
            "model": provider,
            "sources_count": 0,
            "run_seconds": round(run_seconds, 1),
        },
    }
    # Conclusive endpoint checks the writer did not use become their own TESTED notes.
    used = {
        pid
        for group in ("requirements", "scopes", "steps", "blockers", "nuances")
        for entry in guide[group]
        for pid in entry["evidence"].get("probe_ids", [])
    }
    for p in probes:
        if p.kind in ENDPOINT_PROBES and p.outcome != "inconclusive" and p.id not in used:
            guide["nuances"].append(
                {
                    "topic": "other",
                    "detail": f"Automated check of {p.target_url}: {p.summary}",
                    "evidence": {"label": "TESTED", "source_ids": [], "probe_ids": [p.id]},
                }
            )
    # Keep only sources that something cites (the Composio directory is always cited
    # when its status is known).
    cited: set[str] = set()
    for group in ("requirements", "scopes", "steps", "blockers", "nuances"):
        for entry in guide[group]:
            cited.update(entry["evidence"].get("source_ids", []))
    for key in ("difficulty", "time", "review_process", "composio_note"):
        cited.update(guide[key]["evidence"].get("source_ids", []))
    kept = [s for s in all_sources if s.id in cited]
    guide["sources"] = [json.loads(s.model_dump_json()) for s in kept]
    guide["meta"]["sources_count"] = len(kept)
    return Guide.model_validate(guide)
