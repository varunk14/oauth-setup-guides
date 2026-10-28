"""Unit tests for draft normalisation and the writer schema."""

from typing import Any

from app.agent.assemble import (
    composio_status,
    draft_schema,
    normalize_draft,
    registrable_domain,
    short_category,
)
from tests.agent_fakes import draft


def test_schema_keeps_fields_named_like_schema_keywords() -> None:
    schema = draft_schema()
    step = schema["properties"]["steps"]["items"]["properties"]
    assert "title" in step, "the step 'title' field must survive keyword stripping"
    requirement = schema["properties"]["requirements"]["items"]
    assert "required" not in requirement["properties"]
    assert set(requirement["properties"]["is_required"]["enum"]) == {"yes", "no", "conditional"}
    assert "is_required" in requirement["required"]
    assert "$ref" not in str(schema) and "$defs" not in schema
    assert "pattern" not in str(schema)


def test_normalize_maps_booleans_and_case_for_required() -> None:
    raw: dict[str, Any] = draft()
    raw["requirements"][0]["required"] = True
    raw["requirements"][1]["required"] = "No"
    raw["review_process"]["required"] = False
    out = normalize_draft(raw)
    assert [r["required"] for r in out["requirements"]][:2] == ["yes", "no"]
    assert out["review_process"]["required"] == "no"


def test_normalize_maps_is_required_back_and_defaults_missing() -> None:
    raw: dict[str, Any] = draft()
    raw["requirements"][0] = {**raw["requirements"][0], "is_required": "yes"}
    raw["requirements"][0].pop("required")
    raw["requirements"][1].pop("required")
    out = normalize_draft(raw)
    assert out["requirements"][0]["required"] == "yes"
    assert "is_required" not in out["requirements"][0]
    assert out["requirements"][1]["required"] == "conditional"


def test_normalize_moves_long_time_labels_to_detail() -> None:
    raw: dict[str, Any] = draft()
    raw["time"]["approval_wait"] = "Between two and six weeks depending on the review queue"
    out = normalize_draft(raw)
    assert len(out["time"]["approval_wait"]) <= 40
    assert "review queue" in out["time"]["detail"]


def test_registrable_domain() -> None:
    assert registrable_domain("developer.calendly.com") == "calendly.com"
    assert registrable_domain("www.xero.com") == "xero.com"
    assert registrable_domain("api.example.co.uk") == "example.co.uk"


def test_composio_status_from_snapshot() -> None:
    assert composio_status("Calendly", "https://calendly.com") == "yes"
    assert composio_status("Xero", "https://www.xero.com") == "no"
    assert composio_status("Totally Unknown Tool", "https://unknown.example") == "unknown"


def test_short_category() -> None:
    assert short_category("Video conferencing and communications platform") == "Video conferencing"
    assert short_category("Cloud storage and file collaboration") == "Cloud storage"
    assert short_category("CRM") == "CRM"
    assert short_category("") == "Other"
