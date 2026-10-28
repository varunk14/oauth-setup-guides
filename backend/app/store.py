"""Loads curated library guides from data/guides/*.json and validates them at startup."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from app.schema import DifficultyLevel, Guide

DEFAULT_GUIDES_DIR = Path(__file__).resolve().parents[2] / "data" / "guides"

DIFFICULTY_ORDER: dict[str, int] = {"Easy": 0, "Medium": 1, "Hard": 2, "Very hard": 3}


class GuideSummary(BaseModel):
    """What the library page needs for one card."""

    slug: str
    name: str
    category: str
    website: str
    summary: str
    difficulty: DifficultyLevel
    difficulty_reason: str
    hands_on: str
    approval_wait: str
    approval_wait_days_max: int
    review_required: Literal["yes", "no", "conditional"]
    managed_oauth: Literal["yes", "no", "unknown"]
    generated_by: Literal["library", "live_agent"]
    generated_at: datetime


def summarize(guide: Guide) -> GuideSummary:
    return GuideSummary(
        slug=guide.app.slug,
        name=guide.app.name,
        category=guide.app.category,
        website=str(guide.app.website),
        summary=guide.summary,
        difficulty=guide.difficulty.level,
        difficulty_reason=guide.difficulty.reason,
        hands_on=guide.time.hands_on,
        approval_wait=guide.time.approval_wait,
        approval_wait_days_max=guide.time.approval_wait_days_max,
        review_required=guide.review_process.required,
        managed_oauth=guide.composio_note.managed_oauth,
        generated_by=guide.meta.generated_by,
        generated_at=guide.meta.generated_at,
    )


class LibraryError(Exception):
    pass


class GuideStore:
    def __init__(self, guides: dict[str, Guide]) -> None:
        self._guides = guides

    @classmethod
    def from_directory(cls, directory: Path) -> GuideStore:
        guides: dict[str, Guide] = {}
        for path in sorted(directory.glob("*.json")):
            try:
                guide = Guide.model_validate_json(path.read_text(encoding="utf-8"))
            except ValueError as exc:
                raise LibraryError(f"{path.name} is not a valid guide: {exc}") from exc
            if guide.app.slug != path.stem:
                raise LibraryError(f"{path.name}: slug '{guide.app.slug}' must match file name")
            guides[guide.app.slug] = guide
        return cls(guides)

    def get(self, slug: str) -> Guide | None:
        return self._guides.get(slug)

    def summaries(self) -> list[GuideSummary]:
        items = [summarize(g) for g in self._guides.values()]
        return sorted(items, key=lambda s: (DIFFICULTY_ORDER[s.difficulty], s.name.lower()))


def guides_dir() -> Path:
    return Path(os.environ.get("GUIDES_DIR", DEFAULT_GUIDES_DIR))
