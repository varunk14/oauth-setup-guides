"""Small store for live-generated guides (JSON files, one per slug, plus a domain index)."""

from __future__ import annotations

import json
from pathlib import Path

from app.schema import Guide


class GeneratedStore:
    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def _index_path(self) -> Path:
        return self.directory / "_index.json"

    def _index(self) -> dict[str, str]:
        try:
            data = json.loads(self._index_path().read_text())
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def get(self, slug: str) -> Guide | None:
        path = self.directory / f"{slug}.json"
        if not path.is_file():
            return None
        try:
            return Guide.model_validate_json(path.read_text())
        except ValueError:
            return None

    def find(self, key: str) -> Guide | None:
        """Look up by domain or slug."""
        slug = self._index().get(key.lower(), key.lower())
        return self.get(slug)

    def put(self, guide: Guide, keys: list[str]) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        slug = guide.app.slug
        (self.directory / f"{slug}.json").write_text(guide.model_dump_json(indent=2))
        index = self._index()
        for key in {k.lower() for k in keys if k}:
            index[key] = slug
        self._index_path().write_text(json.dumps(index, indent=2))

    def all(self) -> list[Guide]:
        guides = []
        for path in sorted(self.directory.glob("*.json")):
            if path.name.startswith("_"):
                continue
            guide = self.get(path.stem)
            if guide:
                guides.append(guide)
        return guides
