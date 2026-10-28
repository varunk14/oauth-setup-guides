import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.main import app, get_store
from app.schema import Guide
from app.store import GuideStore


@pytest.fixture
def client(sample_guide: dict[str, Any]) -> Iterator[TestClient]:
    guide = Guide.model_validate(sample_guide)
    store = GuideStore({guide.app.slug: guide})
    app.dependency_overrides[get_store] = lambda: store
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_list_guides_returns_summaries(client: TestClient) -> None:
    response = client.get("/api/guides")
    assert response.status_code == 200
    [item] = response.json()
    assert item["slug"] == "example-app"
    assert item["difficulty"] == "Easy"
    assert item["hands_on"] == "10-20 min"
    assert item["managed_oauth"] == "unknown"


def test_get_guide_returns_full_guide(client: TestClient) -> None:
    response = client.get("/api/guides/example-app")
    assert response.status_code == 200
    body = response.json()
    assert body["app"]["name"] == "Example App"
    assert body["probes"][0]["outcome"] == "confirmed"


def test_unknown_guide_is_404(client: TestClient) -> None:
    response = client.get("/api/guides/nope")
    assert response.status_code == 404
    assert "nope" in response.json()["detail"]


def test_markdown_export(client: TestClient) -> None:
    response = client.get("/api/guides/example-app/markdown")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    text = response.text
    assert text.startswith("# OAuth app setup guide: Example App")
    assert "**Difficulty: Easy.**" in text
    assert "`TESTED` probe:p1" in text
    assert "`SOURCED` [1]" in text
    assert "## What we could not verify" in text
    assert "Shareable link: http://testserver/guides/example-app" in text


def test_store_rejects_slug_file_mismatch(tmp_path: Path, sample_guide: dict[str, Any]) -> None:
    (tmp_path / "wrong-name.json").write_text(json.dumps(sample_guide))
    with pytest.raises(Exception, match="must match file name"):
        GuideStore.from_directory(tmp_path)


def test_store_rejects_invalid_guide(tmp_path: Path, sample_guide: dict[str, Any]) -> None:
    sample_guide["difficulty"]["level"] = "Trivial"
    (tmp_path / "example-app.json").write_text(json.dumps(sample_guide))
    with pytest.raises(Exception, match="not a valid guide"):
        GuideStore.from_directory(tmp_path)


def test_summaries_sorted_by_difficulty(sample_guide: dict[str, Any]) -> None:
    hard = json.loads(json.dumps(sample_guide))
    hard["app"]["slug"] = "a-hard-app"
    hard["app"]["name"] = "A Hard App"
    hard["difficulty"]["level"] = "Hard"
    store = GuideStore(
        {
            "a-hard-app": Guide.model_validate(hard),
            "example-app": Guide.model_validate(sample_guide),
        }
    )
    assert [s.slug for s in store.summaries()] == ["example-app", "a-hard-app"]
