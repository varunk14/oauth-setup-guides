"""Free-tier and spend protection: one run at a time, per-IP and daily caps."""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque


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
            raise LimitExceeded(
                "busy",
                "Another live investigation is running. Try again in a minute, or browse the "
                "library.",
            )
        if len(self.day) >= self.per_day:
            raise LimitExceeded(
                "daily_limit",
                "The daily limit for live investigations is reached. Try again tomorrow, or "
                "browse the library.",
            )
        if len(hits) >= self.per_ip_per_hour:
            raise LimitExceeded(
                "rate_limited",
                "You have started several live investigations this hour. Try again later, or "
                "browse the library.",
            )

    def record(self, ip: str) -> None:
        now = self._now()
        self.by_ip[ip].append(now)
        self.day.append(now)
