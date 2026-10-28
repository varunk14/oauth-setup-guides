"""Stores for live-generated guides.

FileStore keeps JSON files (local development, tests). RedisStore keeps them in Upstash
Redis, which survives across serverless instances (the hosted app).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from app.agent.redis import Redis
from app.schema import Guide


class GuideRepo(Protocol):
    def get(self, slug: str) -> Guide | None: ...

    def find(self, key: str) -> Guide | None: ...

    def put(self, guide: Guide, keys: list[str]) -> None: ...

    def all(self) -> list[Guide]: ...


class GeneratedStore:
    """File-based store (one JSON file per slug plus a domain index)."""

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


class RedisStore:
    def __init__(self, redis: Redis, prefix: str = "osg") -> None:
        self.redis = redis
        self.prefix = prefix

    def _k(self, *parts: str) -> str:
        return ":".join((self.prefix, *parts))

    def get(self, slug: str) -> Guide | None:
        raw = self.redis.command("GET", self._k("guide", slug))
        if not raw:
            return None
        try:
            return Guide.model_validate_json(raw)
        except ValueError:
            return None

    def find(self, key: str) -> Guide | None:
        key = key.lower()
        slug = self.redis.command("GET", self._k("idx", key)) or key
        return self.get(str(slug))

    def put(self, guide: Guide, keys: list[str]) -> None:
        slug = guide.app.slug
        self.redis.command("SET", self._k("guide", slug), guide.model_dump_json())
        self.redis.command("SADD", self._k("guides"), slug)
        for key in {k.lower() for k in keys if k}:
            self.redis.command("SET", self._k("idx", key), slug)

    def all(self) -> list[Guide]:
        slugs = self.redis.command("SMEMBERS", self._k("guides")) or []
        guides = [self.get(str(s)) for s in sorted(slugs)]
        return [g for g in guides if g]
