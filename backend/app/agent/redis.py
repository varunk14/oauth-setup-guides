"""A tiny client for Upstash Redis over its HTTPS REST API (no extra dependency)."""

from __future__ import annotations

from typing import Any, Protocol

import httpx


class RedisError(Exception):
    pass


class Redis(Protocol):
    def command(self, *args: str | int) -> Any: ...


class UpstashRedis:
    def __init__(self, url: str, token: str, client: httpx.Client | None = None) -> None:
        self.url = url.rstrip("/")
        self.client = client or httpx.Client(
            timeout=httpx.Timeout(5.0), headers={"Authorization": f"Bearer {token}"}
        )

    def command(self, *args: str | int) -> Any:
        try:
            response = self.client.post(self.url, json=[str(a) for a in args])
        except httpx.HTTPError as exc:
            raise RedisError(f"Redis request failed: {type(exc).__name__}") from exc
        try:
            body = response.json()
        except ValueError as exc:
            raise RedisError(f"Redis answered HTTP {response.status_code}") from exc
        if "error" in body:
            raise RedisError(str(body["error"]))
        return body.get("result")
