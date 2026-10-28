"""Safe automated probes run by our backend code, never by the model.

A probe only sends anonymous GET requests: no accounts, no credentials, no form
submissions. Every request is checked against a domain allowlist (including each
redirect hop), must use HTTPS, must resolve to a public IP address, and is
bounded by a timeout and a response size cap.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import ipaddress
import json
import socket
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit

import httpx

from app.schema import Probe

TIMEOUT = httpx.Timeout(8.0, connect=5.0)
MAX_BYTES = 512_000
MAX_REDIRECTS = 5
MAX_CONCURRENCY = 4
USER_AGENT = "oauth-setup-guides-probe/0.1 (+https://github.com/varunk14/oauth-setup-guides)"
FAKE_CLIENT_ID = "oauth-setup-guides-probe-0000"
FAKE_REDIRECT_URI = "https://example.com/oauth/callback"

# Text that shows the provider looked at our fake client ID and rejected it.
# Only searched in the response body and in an `error` query parameter of the
# final URL, never in our own request URL (which contains "client_id").
CLIENT_REJECTION_MARKERS = (
    "invalid_client",
    "invalid client",
    "unauthorized_client",
    "invalid app id",
    "invalid_app_id",
    "application not found",
    "oauth client was not found",
    "invalid_request",
)

ProbeKind = Literal["oidc_discovery", "oauth_metadata", "authorize_endpoint", "url_reachable"]
Resolver = Callable[[str], Awaitable[list[str]]]


class ProbeBlocked(Exception):
    """The request was refused by our own safety rules before it was sent."""


@dataclass(frozen=True)
class ProbeSpec:
    id: str
    kind: ProbeKind
    url: str


@dataclass(frozen=True)
class FetchResult:
    final_url: str
    status: int
    body: bytes
    truncated: bool


class Allowlist:
    def __init__(self, domains: Iterable[str]) -> None:
        self.domains = {d.lower().strip(".") for d in domains if d}

    def allows(self, host: str) -> bool:
        host = host.lower().strip(".")
        return any(host == d or host.endswith("." + d) for d in self.domains)


async def system_resolver(host: str) -> list[str]:
    loop = asyncio.get_running_loop()
    infos = await loop.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    return [str(info[4][0]) for info in infos]


async def _check_url(url: str, allowlist: Allowlist, resolver: Resolver) -> None:
    parts = urlsplit(url)
    if parts.scheme != "https":
        raise ProbeBlocked(f"only https is allowed, got '{parts.scheme}'")
    host = parts.hostname or ""
    if not allowlist.allows(host):
        raise ProbeBlocked(f"host '{host}' is not on the allowlist")
    addresses = await resolver(host)
    if not addresses:
        raise ProbeBlocked(f"host '{host}' did not resolve")
    for address in addresses:
        if not ipaddress.ip_address(address).is_global:
            raise ProbeBlocked(f"host '{host}' resolves to a non-public address")


async def fetch(
    client: httpx.AsyncClient, url: str, allowlist: Allowlist, resolver: Resolver
) -> FetchResult:
    """GET a URL, following redirects manually so every hop is checked."""
    for _ in range(MAX_REDIRECTS + 1):
        await _check_url(url, allowlist, resolver)
        request = client.build_request("GET", url, headers={"User-Agent": USER_AGENT})
        response = await client.send(request, stream=True, follow_redirects=False)
        try:
            if response.is_redirect and "location" in response.headers:
                url = urljoin(url, response.headers["location"])
                continue
            chunks: list[bytes] = []
            size = 0
            truncated = False
            async for chunk in response.aiter_bytes():
                chunks.append(chunk)
                size += len(chunk)
                if size >= MAX_BYTES:
                    truncated = True
                    break
            return FetchResult(url, response.status_code, b"".join(chunks)[:MAX_BYTES], truncated)
        finally:
            await response.aclose()
    raise ProbeBlocked(f"more than {MAX_REDIRECTS} redirects")


def _now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _probe(
    spec: ProbeSpec,
    outcome: Literal["confirmed", "not_found", "inconclusive"],
    summary: str,
    status: int | None = None,
) -> Probe:
    return Probe.model_validate(
        {
            "id": spec.id,
            "kind": spec.kind,
            "target_url": spec.url,
            "ran_at": _now(),
            "outcome": outcome,
            "http_status": status,
            "summary": summary,
        }
    )


def _error_text_from_query(query: str) -> str:
    """Collect error-looking values from a redirect URL, decoding base64 where possible."""
    texts: list[str] = []
    for key, values in parse_qs(query).items():
        if "error" not in key.lower():
            continue
        for value in values:
            texts.append(value)
            try:
                decoded = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
            except (binascii.Error, ValueError):
                continue
            texts.append(decoded.decode("utf-8", "replace"))
    return " ".join(texts)


def _describe_metadata(data: dict[str, object]) -> str:
    parts = []
    for key in ("issuer", "authorization_endpoint", "token_endpoint"):
        if isinstance(data.get(key), str):
            parts.append(f"{key}={data[key]}")
    pkce = data.get("code_challenge_methods_supported")
    if isinstance(pkce, list):
        parts.append("PKCE methods: " + ", ".join(str(m) for m in pkce))
    else:
        parts.append("PKCE methods: not listed")
    return "; ".join(parts)


async def _run_one(
    client: httpx.AsyncClient, spec: ProbeSpec, allowlist: Allowlist, resolver: Resolver
) -> Probe:
    url = spec.url
    if spec.kind == "authorize_endpoint":
        sep = "&" if urlsplit(url).query else "?"
        url = (
            url
            + sep
            + urlencode(
                {
                    "client_id": FAKE_CLIENT_ID,
                    "response_type": "code",
                    "redirect_uri": FAKE_REDIRECT_URI,
                    "state": "probe",
                }
            )
        )
    try:
        result = await fetch(client, url, allowlist, resolver)
    except ProbeBlocked as exc:
        return _probe(spec, "inconclusive", f"Not sent: {exc}.")
    except httpx.HTTPError as exc:
        return _probe(spec, "inconclusive", f"Request failed: {type(exc).__name__}.")

    status = result.status
    final_host = urlsplit(result.final_url).hostname or ""

    if spec.kind in ("oidc_discovery", "oauth_metadata"):
        if status == 200:
            try:
                data = json.loads(result.body)
            except ValueError:
                data = None
            if isinstance(data, dict) and "authorization_endpoint" in data:
                return _probe(
                    spec, "confirmed", "Metadata found. " + _describe_metadata(data), status
                )
            return _probe(
                spec, "inconclusive", "HTTP 200 but not an OAuth metadata document.", status
            )
        if status in (400, 404, 410):
            return _probe(spec, "not_found", f"No metadata document (HTTP {status}).", status)
        return _probe(spec, "inconclusive", f"Unexpected HTTP {status}.", status)

    if spec.kind == "authorize_endpoint":
        final = urlsplit(result.final_url)
        haystack = (
            _error_text_from_query(final.query) + " " + result.body.decode("utf-8", "replace")
        ).lower()
        found = [m for m in CLIENT_REJECTION_MARKERS if m in haystack]
        if status < 500 and found:
            return _probe(
                spec,
                "confirmed",
                f"Endpoint answered HTTP {status} on {final_host} and rejected a fake client ID "
                f"(matched: {found[0]}).",
                status,
            )
        path = final.path.lower()
        if (
            status < 400
            and ("login" in path or "signin" in path)
            and FAKE_CLIENT_ID in result.final_url
        ):
            return _probe(
                spec,
                "confirmed",
                f"Endpoint is live: it sent us to a sign-in page on {final_host} that carries our "
                "fake client ID back to the authorize route. It asks users to sign in before it "
                "checks the client ID, so rejection could not be observed anonymously.",
                status,
            )
        if status == 404:
            return _probe(spec, "not_found", f"HTTP 404 on {final_host}.", status)
        return _probe(
            spec,
            "inconclusive",
            f"Endpoint answered HTTP {status} on {final_host}, but no client error was visible. "
            "The page is likely rendered by JavaScript, which this check does not run.",
            status,
        )

    # url_reachable
    if status < 400:
        note = "" if result.final_url == spec.url else f" after redirect to {final_host}"
        return _probe(spec, "confirmed", f"Page loads (HTTP {status}{note}).", status)
    if status in (404, 410):
        return _probe(spec, "not_found", f"Page not found (HTTP {status}).", status)
    return _probe(spec, "inconclusive", f"HTTP {status} on {final_host}.", status)


async def run_probes(
    specs: list[ProbeSpec],
    allowlist: Allowlist,
    *,
    resolver: Resolver = system_resolver,
    transport: httpx.AsyncBaseTransport | None = None,
) -> list[Probe]:
    semaphore = asyncio.Semaphore(MAX_CONCURRENCY)
    async with httpx.AsyncClient(timeout=TIMEOUT, transport=transport) as client:

        async def guarded(spec: ProbeSpec) -> Probe:
            async with semaphore:
                return await _run_one(client, spec, allowlist, resolver)

        return list(await asyncio.gather(*(guarded(s) for s in specs)))
