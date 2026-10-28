"""Run the safe probes for library apps and save results to data/probes/<slug>.json.

Usage: uv run python scripts/run_library_probes.py [slug ...]
Real network calls; never run from tests.
"""

import asyncio
import json
import sys
from pathlib import Path

from app.probes import Allowlist, ProbeSpec, run_probes

OUT = Path(__file__).resolve().parents[2] / "data" / "probes"

PLANS: dict[str, tuple[list[str], list[ProbeSpec]]] = {
    "github": (
        ["github.com"],
        [
            ProbeSpec(
                "oidc", "oidc_discovery", "https://github.com/.well-known/openid-configuration"
            ),
            ProbeSpec(
                "oauth-meta",
                "oauth_metadata",
                "https://github.com/.well-known/oauth-authorization-server",
            ),
            ProbeSpec(
                "authorize", "authorize_endpoint", "https://github.com/login/oauth/authorize"
            ),
            ProbeSpec("console", "url_reachable", "https://github.com/settings/applications/new"),
            ProbeSpec(
                "docs",
                "url_reachable",
                "https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/creating-an-oauth-app",
            ),
        ],
    ),
    "slack": (
        ["slack.com", "slack.dev"],
        [
            ProbeSpec(
                "oidc", "oidc_discovery", "https://slack.com/.well-known/openid-configuration"
            ),
            ProbeSpec("authorize", "authorize_endpoint", "https://slack.com/oauth/v2/authorize"),
            ProbeSpec("console", "url_reachable", "https://api.slack.com/apps"),
            ProbeSpec(
                "docs",
                "url_reachable",
                "https://docs.slack.dev/authentication/installing-with-oauth",
            ),
        ],
    ),
    "google-gmail": (
        ["google.com", "googleapis.com"],
        [
            ProbeSpec(
                "oidc",
                "oidc_discovery",
                "https://accounts.google.com/.well-known/openid-configuration",
            ),
            ProbeSpec(
                "authorize",
                "authorize_endpoint",
                "https://accounts.google.com/o/oauth2/v2/auth?scope=openid",
            ),
            ProbeSpec("console", "url_reachable", "https://console.cloud.google.com/auth/clients"),
            ProbeSpec(
                "docs",
                "url_reachable",
                "https://developers.google.com/identity/protocols/oauth2/production-readiness/restricted-scope-verification",
            ),
        ],
    ),
    "meta-instagram": (
        ["facebook.com", "instagram.com"],
        [
            ProbeSpec(
                "oidc",
                "oidc_discovery",
                "https://www.facebook.com/.well-known/openid-configuration",
            ),
            ProbeSpec(
                "authorize", "authorize_endpoint", "https://www.instagram.com/oauth/authorize"
            ),
            ProbeSpec("console", "url_reachable", "https://developers.facebook.com/apps"),
            ProbeSpec(
                "docs",
                "url_reachable",
                "https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/business-login",
            ),
        ],
    ),
    "salesforce": (
        ["salesforce.com"],
        [
            ProbeSpec(
                "oidc",
                "oidc_discovery",
                "https://login.salesforce.com/.well-known/openid-configuration",
            ),
            ProbeSpec(
                "authorize",
                "authorize_endpoint",
                "https://login.salesforce.com/services/oauth2/authorize",
            ),
            ProbeSpec(
                "docs",
                "url_reachable",
                "https://help.salesforce.com/s/articleView?id=xcloud.external_client_apps.htm&type=5",
            ),
        ],
    ),
    "hubspot": (
        ["hubspot.com", "hubapi.com"],
        [
            ProbeSpec(
                "oauth-meta",
                "oauth_metadata",
                "https://api.hubapi.com/.well-known/oauth-authorization-server",
            ),
            ProbeSpec("authorize", "authorize_endpoint", "https://app.hubspot.com/oauth/authorize"),
            ProbeSpec(
                "docs",
                "url_reachable",
                "https://developers.hubspot.com/docs/apps/developer-platform/build-apps/create-an-app",
            ),
        ],
    ),
}


async def main(slugs: list[str]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for slug in slugs:
        domains, specs = PLANS[slug]
        probes = await run_probes(specs, Allowlist(domains))
        data = [json.loads(p.model_dump_json()) for p in probes]
        (OUT / f"{slug}.json").write_text(json.dumps(data, indent=2) + "\n")
        for p in probes:
            print(f"{slug:15} {p.id:10} {p.outcome:12} {p.summary}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:] or list(PLANS)))
