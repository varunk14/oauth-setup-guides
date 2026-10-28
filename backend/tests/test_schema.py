import copy
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.schema import EvidenceLabel, Guide


def test_sample_guide_is_valid(sample_guide: dict[str, Any]) -> None:
    guide = Guide.model_validate(sample_guide)
    assert guide.app.slug == "example-app"
    labels = {ev.label for ev in guide.all_evidence()}
    assert labels == set(EvidenceLabel)


def mutate(base: dict[str, Any], path: list[Any], value: Any) -> dict[str, Any]:
    data = copy.deepcopy(base)
    target = data
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    return data


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        (
            ["difficulty", "evidence"],
            {"label": "TESTED"},
            "TESTED evidence must reference at least one probe",
        ),
        (
            ["difficulty", "evidence"],
            {"label": "SOURCED"},
            "SOURCED evidence must reference at least one source",
        ),
        (
            ["difficulty", "evidence"],
            {"label": "SOURCED", "source_ids": ["nope"]},
            "unknown sources",
        ),
        (
            ["difficulty", "evidence"],
            {"label": "TESTED", "probe_ids": ["nope"]},
            "unknown probes",
        ),
        (["steps", 1, "order"], 3, "steps must be numbered 1..n"),
        (["meta", "sources_count"], 5, "sources_count"),
        (["time", "hands_on_minutes_min"], 99, "hands_on_minutes_min"),
        (["difficulty", "level"], "Trivial", "Input should be"),
        (["app", "slug"], "Bad Slug", "String should match pattern"),
        (["unexpected_field"], "x", "Extra inputs are not permitted"),
        (["agent_vs_human", "human_must"], [], "at least 1 item"),
    ],
)
def test_invalid_guides_rejected(
    sample_guide: dict[str, Any], path: list[Any], value: Any, message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        Guide.model_validate(mutate(sample_guide, path, value))


def test_tested_requires_successful_probe(sample_guide: dict[str, Any]) -> None:
    data = mutate(sample_guide, ["probes", 0, "ok"], False)
    with pytest.raises(ValidationError, match="at least one successful probe"):
        Guide.model_validate(data)


def test_committed_json_schema_is_current() -> None:
    script = Path(__file__).resolve().parents[1] / "scripts" / "export_schema.py"
    result = subprocess.run(
        [sys.executable, str(script), "--check"],
        capture_output=True,
        text=True,
        cwd=script.parents[1],
        env={"PYTHONPATH": str(script.parents[1])},
    )
    assert result.returncode == 0, result.stdout + result.stderr
