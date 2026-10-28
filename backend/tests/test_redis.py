"""Redis-backed store and run gate, with an in-memory fake Redis (no network)."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
import pytest

from app.agent.limits import LimitExceeded, RedisRunGate
from app.agent.redis import RedisError, UpstashRedis
from app.agent.store import RedisStore
from app.schema import Guide


class FakeRedis:
    def __init__(self) -> None:
        self.data: dict[str, Any] = {}

    def command(self, *args: str | int) -> Any:
        name, *rest = [str(a) for a in args]
        name = name.upper()
        if name == "GET":
            return self.data.get(rest[0])
        if name == "SET":
            key, value, *opts = rest
            if "NX" in opts and key in self.data:
                return None
            self.data[key] = value
            return "OK"
        if name == "DEL":
            return int(self.data.pop(rest[0], None) is not None)
        if name == "INCR":
            self.data[rest[0]] = str(int(self.data.get(rest[0], 0)) + 1)
            return int(self.data[rest[0]])
        if name == "EXPIRE":
            return 1
        if name == "SADD":
            self.data.setdefault(rest[0], set()).add(rest[1])
            return 1
        if name == "SMEMBERS":
            return sorted(self.data.get(rest[0], set()))
        raise AssertionError(f"unexpected command {name}")


def test_redis_store_round_trip(sample_guide: dict[str, Any]) -> None:
    store = RedisStore(FakeRedis())
    guide = Guide.model_validate(sample_guide)
    assert store.get("example-app") is None
    store.put(guide, ["example-app", "Example.COM"])
    assert store.get("example-app") == guide
    assert store.find("example.com") == guide
    assert [g.app.slug for g in store.all()] == ["example-app"]


def test_redis_gate_limits_and_lock() -> None:
    redis = FakeRedis()
    gate = RedisRunGate(redis, per_ip_per_hour=2, per_day=3, lock_seconds=300)

    async def scenario() -> list[str]:
        codes = []
        async with gate.acquire("1.1.1.1"):
            # A second run while the first holds the lock is refused.
            try:
                async with gate.acquire("2.2.2.2"):
                    codes.append("entered")
            except LimitExceeded as exc:
                codes.append(exc.code)
        async with gate.acquire("1.1.1.1"):
            pass
        for ip in ("1.1.1.1", "3.3.3.3"):
            try:
                async with gate.acquire(ip):
                    codes.append(f"ran {ip}")
            except LimitExceeded as exc:
                codes.append(exc.code)
        try:
            async with gate.acquire("4.4.4.4"):
                codes.append("ran 4.4.4.4")
        except LimitExceeded as exc:
            codes.append(exc.code)
        return codes

    assert asyncio.run(scenario()) == ["busy", "rate_limited", "ran 3.3.3.3", "daily_limit"]
    assert not any(k.endswith("lock:run") for k in redis.data), "lock must be released"


def test_redis_gate_releases_lock_when_run_fails() -> None:
    redis = FakeRedis()
    gate = RedisRunGate(redis, per_ip_per_hour=5, per_day=5, lock_seconds=300)

    async def scenario() -> None:
        with pytest.raises(RuntimeError):
            async with gate.acquire("1.1.1.1"):
                raise RuntimeError("run crashed")

    asyncio.run(scenario())
    assert not any(k.endswith("lock:run") for k in redis.data)


def test_upstash_client_sends_command_and_reads_result() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.read())
        return httpx.Response(200, json={"result": "OK"})

    client = httpx.Client(
        transport=httpx.MockTransport(handler), headers={"Authorization": "Bearer t0ken"}
    )
    redis = UpstashRedis("https://example.upstash.io/", "t0ken", client=client)
    assert redis.command("SET", "k", "v", "NX", "EX", 300) == "OK"
    assert seen["body"] == ["SET", "k", "v", "NX", "EX", "300"]
    assert seen["auth"] == "Bearer t0ken"


def test_upstash_client_raises_on_error() -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(400, json={"error": "ERR bad"}))
    )
    with pytest.raises(RedisError, match="ERR bad"):
        UpstashRedis("https://example.upstash.io", "t", client=client).command("GET", "k")
