"""Probe tests use httpx.MockTransport and a fake resolver: no real network."""

import asyncio
import json

import httpx
import pytest

from app.probes import FAKE_CLIENT_ID, MAX_BYTES, Allowlist, ProbeSpec, run_probes

ALLOW = Allowlist(["example.com"])


async def public_resolver(host: str) -> list[str]:
    return ["93.184.215.14"]


async def private_resolver(host: str) -> list[str]:
    return ["127.0.0.1"]


def run(spec: ProbeSpec, handler, resolver=public_resolver, allowlist=ALLOW):  # type: ignore[no-untyped-def]
    probes = asyncio.run(
        run_probes([spec], allowlist, resolver=resolver, transport=httpx.MockTransport(handler))
    )
    return probes[0]


def test_discovery_confirmed_reports_endpoints_and_pkce() -> None:
    doc = {
        "issuer": "https://example.com",
        "authorization_endpoint": "https://example.com/authorize",
        "token_endpoint": "https://example.com/token",
        "code_challenge_methods_supported": ["S256"],
    }
    probe = run(
        ProbeSpec("p1", "oidc_discovery", "https://example.com/.well-known/openid-configuration"),
        lambda req: httpx.Response(200, json=doc),
    )
    assert probe.outcome == "confirmed"
    assert "authorization_endpoint=https://example.com/authorize" in probe.summary
    assert "PKCE methods: S256" in probe.summary
    assert probe.http_status == 200


def test_discovery_missing_is_not_found() -> None:
    probe = run(
        ProbeSpec("p1", "oidc_discovery", "https://example.com/.well-known/openid-configuration"),
        lambda req: httpx.Response(404),
    )
    assert probe.outcome == "not_found"


def test_discovery_non_json_is_inconclusive() -> None:
    probe = run(
        ProbeSpec("p1", "oauth_metadata", "https://example.com/.well-known/x"),
        lambda req: httpx.Response(200, text="<html>hi</html>"),
    )
    assert probe.outcome == "inconclusive"


def test_authorize_sends_fake_client_and_detects_rejection() -> None:
    seen: list[httpx.URL] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req.url)
        return httpx.Response(400, text='{"error":"invalid_client"}')

    probe = run(ProbeSpec("p1", "authorize_endpoint", "https://example.com/authorize"), handler)
    assert probe.outcome == "confirmed"
    assert "invalid_client" in probe.summary
    assert seen[0].params["client_id"] == FAKE_CLIENT_ID
    assert seen[0].params["response_type"] == "code"


def test_authorize_without_client_error_is_inconclusive() -> None:
    probe = run(
        ProbeSpec("p1", "authorize_endpoint", "https://example.com/authorize"),
        lambda req: httpx.Response(200, text="<html>Welcome</html>"),
    )
    assert probe.outcome == "inconclusive"


def test_authorize_error_in_redirect_counts() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/authorize":
            return httpx.Response(
                302, headers={"location": "https://example.com/error?error=invalid_client"}
            )
        return httpx.Response(200, text="Something went wrong")

    probe = run(ProbeSpec("p1", "authorize_endpoint", "https://example.com/authorize"), handler)
    assert probe.outcome == "confirmed"


def test_authorize_base64_error_in_redirect_counts() -> None:
    encoded = "Cg5pbnZhbGlkX2NsaWVudBIfVGhlIE9BdXRoIGNsaWVudCB3YXMgbm90IGZvdW5kLiCRAw"

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/authorize":
            location = f"https://example.com/signin/oauth/error?authError={encoded}"
            return httpx.Response(302, headers={"location": location})
        return httpx.Response(200, text="<html>Access blocked</html>")

    probe = run(ProbeSpec("p1", "authorize_endpoint", "https://example.com/authorize"), handler)
    assert probe.outcome == "confirmed"
    assert "rejected a fake client ID" in probe.summary


def test_authorize_login_redirect_proves_endpoint_is_live() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/authorize":
            location = f"https://example.com/login?client_id={FAKE_CLIENT_ID}&return_to=x"
            return httpx.Response(302, headers={"location": location})
        return httpx.Response(200, text="<html>Sign in</html>")

    probe = run(ProbeSpec("p1", "authorize_endpoint", "https://example.com/authorize"), handler)
    assert probe.outcome == "confirmed"
    assert "sign-in page" in probe.summary


def test_redirects_within_allowlist_are_followed() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/apps":
            return httpx.Response(302, headers={"location": "https://login.example.com/signin"})
        return httpx.Response(200, text="Sign in")

    probe = run(ProbeSpec("p1", "url_reachable", "https://example.com/apps"), handler)
    assert probe.outcome == "confirmed"
    assert "login.example.com" in probe.summary


def test_soft_404_page_is_inconclusive() -> None:
    page = "<html><head><title>Page Not Found - Example</title></head><body></body></html>"
    probe = run(
        ProbeSpec("p1", "url_reachable", "https://example.com/apps"),
        lambda req: httpx.Response(200, text=page),
    )
    assert probe.outcome == "inconclusive"
    assert "Page Not Found" in probe.summary


def test_normal_page_title_is_confirmed() -> None:
    page = "<html><head><title>Developer Apps</title></head><body>404 errors docs</body></html>"
    probe = run(
        ProbeSpec("p1", "url_reachable", "https://example.com/apps"),
        lambda req: httpx.Response(200, text=page),
    )
    assert probe.outcome == "confirmed"


def test_redirect_off_allowlist_is_blocked() -> None:
    calls: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(str(req.url))
        return httpx.Response(302, headers={"location": "https://evil.test/steal"})

    probe = run(ProbeSpec("p1", "url_reachable", "https://example.com/apps"), handler)
    assert probe.outcome == "inconclusive"
    assert "not on the allowlist" in probe.summary
    assert calls == ["https://example.com/apps"]


@pytest.mark.parametrize(
    ("url", "message"),
    [
        ("http://example.com/apps", "only https"),
        ("https://other.test/apps", "not on the allowlist"),
        ("https://notexample.com/apps", "not on the allowlist"),
    ],
)
def test_unsafe_urls_are_never_sent(url: str, message: str) -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        raise AssertionError("request must not be sent")

    probe = run(ProbeSpec("p1", "url_reachable", url), handler)
    assert probe.outcome == "inconclusive"
    assert message in probe.summary


def test_private_addresses_are_blocked() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        raise AssertionError("request must not be sent")

    probe = run(
        ProbeSpec("p1", "url_reachable", "https://example.com/apps"),
        handler,
        resolver=private_resolver,
    )
    assert probe.outcome == "inconclusive"
    assert "non-public address" in probe.summary


def test_large_bodies_are_capped() -> None:
    big = b"x" * (MAX_BYTES * 3)
    probe = run(
        ProbeSpec("p1", "url_reachable", "https://example.com/big"),
        lambda req: httpx.Response(200, content=big),
    )
    assert probe.outcome == "confirmed"


def test_network_errors_are_inconclusive() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out")

    probe = run(ProbeSpec("p1", "url_reachable", "https://example.com/apps"), handler)
    assert probe.outcome == "inconclusive"
    assert "ConnectTimeout" in probe.summary


def test_probe_result_is_valid_json() -> None:
    probe = run(
        ProbeSpec("p1", "url_reachable", "https://example.com/"),
        lambda req: httpx.Response(200),
    )
    assert json.loads(probe.model_dump_json())["outcome"] == "confirmed"
