"""Spend protection: one run at a time, per-IP and daily caps.

RunGate keeps state in memory (one server process). RedisRunGate keeps it in Redis so the
limits hold across serverless instances. Both expose acquire(ip), an async context
manager that raises LimitExceeded before the run starts.
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from datetime import UTC, datetime
from typing import Protocol

from app.agent.redis import Redis

BUSY = (
    "busy",
    "Another live investigation is running. Try again in a minute, or browse the library.",
)
DAILY = (
    "daily_limit",
    "The daily limit for live investigations is reached. Try again tomorrow, or browse the "
    "library.",
)
HOURLY = (
    "rate_limited",
    "You have started several live investigations this hour. Try again later, or browse the "
    "library.",
)


class LimitExceeded(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class RunGate:
    def __init__(self, per_ip_per_hour: int, per_day: int, clock: object = None) -> None:
        self.per_ip_per_hour = per_ip_per_hour
        self.per_day = per_day
        self.lock = asyncio.Lock()
        self.by_ip: dict[str, deque[float]] = defaultdict(deque)
        self.day: deque[float] = deque()
        self.clock = clock or time.monotonic

    def _now(self) -> float:
        return float(self.clock())  # type: ignore[operator]

    def check(self, ip: str) -> None:
        now = self._now()
        hits = self.by_ip[ip]
        while hits and now - hits[0] > 3600:
            hits.popleft()
        while self.day and now - self.day[0] > 86400:
            self.day.popleft()
        if self.lock.locked():
            raise LimitExceeded(*BUSY)
        if len(self.day) >= self.per_day:
            raise LimitExceeded(*DAILY)
        if len(hits) >= self.per_ip_per_hour:
            raise LimitExceeded(*HOURLY)

    def record(self, ip: str) -> None:
        now = self._now()
        self.by_ip[ip].append(now)
        self.day.append(now)

    @asynccontextmanager
    async def acquire(self, ip: str) -> AsyncIterator[None]:
        # No await between the check and taking the lock, so two requests cannot both pass.
        self.check(ip)
        async with self.lock:
            self.record(ip)
            yield


class Gate(Protocol):
    def acquire(self, ip: str) -> AbstractAsyncContextManager[None]: ...


class RedisRunGate:
    """Same rules as RunGate, with the counters and the run lock in Redis."""

    def __init__(
        self,
        redis: Redis,
        per_ip_per_hour: int,
        per_day: int,
        lock_seconds: int,
        prefix: str = "osg",
    ) -> None:
        self.redis = redis
        self.per_ip_per_hour = per_ip_per_hour
        self.per_day = per_day
        self.lock_seconds = lock_seconds
        self.prefix = prefix

    def _keys(self, ip: str) -> tuple[str, str, str]:
        now = datetime.now(UTC)
        return (
            f"{self.prefix}:rl:ip:{ip}:{now:%Y%m%d%H}",
            f"{self.prefix}:rl:day:{now:%Y%m%d}",
            f"{self.prefix}:lock:run",
        )

    @asynccontextmanager
    async def acquire(self, ip: str) -> AsyncIterator[None]:
        ip_key, day_key, lock_key = self._keys(ip)
        if int(self.redis.command("GET", day_key) or 0) >= self.per_day:
            raise LimitExceeded(*DAILY)
        if int(self.redis.command("GET", ip_key) or 0) >= self.per_ip_per_hour:
            raise LimitExceeded(*HOURLY)
        # SET NX is atomic: only one run can hold the lock; it expires if a run crashes.
        if self.redis.command("SET", lock_key, "1", "NX", "EX", self.lock_seconds) != "OK":
            raise LimitExceeded(*BUSY)
        try:
            for key, ttl in ((ip_key, 3600), (day_key, 90000)):
                self.redis.command("INCR", key)
                self.redis.command("EXPIRE", key, ttl)
            yield
        finally:
            self.redis.command("DEL", lock_key)
