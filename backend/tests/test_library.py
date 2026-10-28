"""Integrity checks for the curated library in data/guides/."""

import json
from pathlib import Path

import pytest

from app.schema import EvidenceLabel, Guide
from app.store import DEFAULT_GUIDES_DIR, GuideStore

PROBES_DIR = DEFAULT_GUIDES_DIR.parent / "probes"
GUIDE_FILES = sorted(DEFAULT_GUIDES_DIR.glob("*.json"))


def test_library_loads() -> None:
    store = GuideStore.from_directory(DEFAULT_GUIDES_DIR)
    assert len(store.summaries()) == len(GUIDE_FILES)


@pytest.mark.parametrize("path", GUIDE_FILES, ids=lambda p: p.stem)
def test_library_guide_rules(path: Path) -> None:
    guide = Guide.model_validate_json(path.read_text())
    assert guide.meta.generated_by == "library"
    # Probes must be exactly what our probe runner recorded; never hand-edited.
    recorded = json.loads((PROBES_DIR / f"{guide.app.slug}.json").read_text())
    assert [json.loads(p.model_dump_json()) for p in guide.probes] == recorded
    # Every source is cited somewhere, and evidence is not all one label.
    cited = {sid for ev in guide.all_evidence() for sid in ev.source_ids}
    assert cited == {s.id for s in guide.sources}
    assert len({ev.label for ev in guide.all_evidence()}) >= 2
    assert any(s.who == "human" for s in guide.steps)
    tested = [ev for ev in guide.all_evidence() if ev.label is EvidenceLabel.TESTED]
    assert all(ev.probe_ids for ev in tested)
