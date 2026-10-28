# Verification: what we tested, corrected and could not verify

Checked on 2026-10-28. Provider rules change; every guide links its sources and the date
they were checked.

The goal of this page is to show how much the guides can be trusted, where they were wrong,
and what is still open. It covers five checks:

1. Automated probes (what the app tests by itself).
2. An independent fact-check of all six library guides against official pages.
3. A link check of every URL in the guides.
4. A real setup attempt (creating a GitHub OAuth app by following our guide).
5. The live agent compared with the checked library guides.

## Evidence labels

| Label | Meaning | Who can assign it |
|---|---|---|
| TESTED | Our own code observed it (a probe result with time and outcome) | Only code: it must cite a probe that ran and was conclusive |
| SOURCED | An official page states it | Must cite a source that exists and was checked to load |
| INFERRED | Reasoned from sources, or from a community source | Estimates, difficulty levels, community reports |
| UNVERIFIED | Not confirmed | Listed again in each guide's "What we could not verify" |

For live guides these rules are enforced in code after the model writes its draft: a TESTED
label without a conclusive probe, or a SOURCED label without a checked official source, is
corrected, and the correction is noted on the claim.

## 1. Automated probes

Probes are anonymous GET requests only: HTTPS, a domain allowlist checked on every redirect,
public IP addresses only, a timeout and a size cap. No accounts, logins or forms.

| App | Discovery document | Authorize endpoint with a fake client ID |
|---|---|---|
| Google (Gmail) | Found; PKCE plain and S256 | Rejected the fake client (`invalid_client`) |
| Salesforce | Found; PKCE S256 | Rejected the fake client (`invalid_client`) |
| GitHub | None (HTTP 404) | Live; asks users to sign in before it checks the client |
| Slack | Found, for Sign in with Slack only | Inconclusive: the page is rendered by JavaScript |
| Meta / Instagram | Found, for Facebook Login only | Inconclusive: the page is rendered by JavaScript |
| HubSpot | Found at api.hubapi.com, but it belongs to HubSpot's MCP server | Inconclusive: the page is rendered by JavaScript |

Inconclusive results are shown but never used as TESTED evidence.

Mistakes in the probes themselves, found and fixed (each with a test that fails without the fix):

- The authorize check searched its own request URL for the word "client_id", so every
  endpoint looked like it rejected the fake client. It now only reads the response.
- Google returns its error in an encoded `authError` value in a redirect. The check now
  decodes such values.
- `developers.facebook.com/apps` returns HTTP 200 with the title "Page Not Found" to
  signed-out visitors. The page check had called it "loads"; pages titled "not found" are now
  inconclusive.

## 2. Independent fact-check of the six library guides

Three reviewers each audited two guides claim by claim against official provider and
Composio pages. They found 52 problems. All were fixed, and the most consequential ones were
re-checked on the live pages before the fix was accepted.

| Guide | Most important corrections |
|---|---|
| Slack | Composio's managed Slack app is still in Slack Marketplace review, so it gets the same limits as an unlisted app (the guide had implied it avoids them). Scopes rewritten as user scopes for Composio's "slack" toolkit (the "slackbot" toolkit uses bot scopes). The rate limit for unlisted commercial apps covers all installs of apps created after 2025-05-29, not only new installs |
| GitHub | Composio accepts GitHub App credentials as well as OAuth apps (had been listed as unverified). Org access restrictions are on by default only for new organizations and only block private resources and privileged writes |
| Gmail | Branding, Audience and Data Access pages in the Google console were mixed up; steps split and fixed. Added Google's Limited Use rule: Gmail data may not be used to train general AI models. The brand check takes minutes when automated, 2-3 business days if reviewed by hand |
| HubSpot | The 60-day listing review is counted from when feedback is shared. Super Admin is needed only for account-level apps. AI connectors must use user-level access from the start |
| Salesforce | Since September 2025 Salesforce blocks new users from authorizing uninstalled connected apps, including Composio's managed app; a customer admin may need to install or approve it. Group and Essentials editions have no API access |
| Instagram | Composio's managed Instagram app currently lacks the comment permission. Business Verification is needed to publish and for Advanced Access, not in development mode |
| All six | Difficulty levels relabelled from SOURCED to INFERRED (they are our judgement). Steps that need signing in or giving consent are always "you". Composio's warning about the old v1 callback URL added |

Earlier research notes that the official pages corrected while drafting:

| Research note | Official page | Result |
|---|---|---|
| Meta App Review takes about 20 days (from a blog) | Meta's submission guide: you "should receive a decision within a week" | Corrected |
| Google restricted-scope verification takes "several weeks" | Google's unverified-apps page: it "might require several months" | Range widened |
| `gmail.send` is a restricted scope | Gmail scopes page: it is sensitive | Corrected |
| HubSpot caps unlisted installs at 25 | HubSpot changelog, enforced 2025-09-22 | Confirmed |
| New GitHub OAuth apps issue expiring tokens by default | "Creating an OAuth app" says so; the comparison page still says tokens are long-lived | Confirmed; the conflict is noted in the guide |

## 3. Link check

All URLs in the six guides were fetched: 93 links, all HTTP 200. Page titles were checked for
"not found" pages that answer 200; the only one found is described in section 1.

## 4. Real setup attempt

A GitHub OAuth app was created by hand, following the library guide's steps exactly, to see
whether the screens match the guide. Results:

(To be filled in from the attempt.)

## 5. The live agent compared with the checked library guides

The live agent investigated GitHub and Slack from scratch. The results were saved separately
so the checked guides were not touched, then compared claim by claim.

| | GitHub | Slack (first run) | Slack (after fixes) |
|---|---|---|---|
| Difficulty (checked guide) | Easy (Easy) | Medium (Medium; Hard if commercial) | Hard |
| Key facts present | 7 of 9 | 8 of 10 | 9 of 10 |
| Missed | Wording only: "no review" stated as conditional; GitHub Apps described as "may be a better fit" instead of recommended | The rate limit for unlisted commercial apps (1 request per minute on message history) and the Marketplace terms; called the listing "optional" | The exact "only appropriate channel" wording (the point itself is covered) |
| Wrong facts found | None | None, but the omission is misleading for commercial agents | Review wait "up to 9 weeks" vs 10 business days preliminary plus up to 10 weeks functional in the checked guide |
| Sources kept | 11 | 13 | 11 (14 of 14 checked) |
| Run time | 113 s | 106 s | 105 s |

What this showed, and what changed:

- The agent is reliable on the facts it states: no false statements were found in these runs.
  It is weaker at noticing policy traps, which is why a checked library still matters for
  the most used apps.
- The research step now explicitly asks for restrictions that apply until an app is listed or
  approved (for example lower rate limits for unlisted apps). The next Slack run found the
  rate limit and rated Slack Hard.
- A middle run kept only 2 of 14 sources: Slack's old api.slack.com pages redirect to
  docs.slack.dev, and the source check refused the redirect. Sources may now redirect to any of
  the app's official domains, and only missing or unsafe pages are dropped.

Other live runs:

| App | Provider | Result |
|---|---|---|
| Zoom | OpenAI | Valid guide in 105 s; 5 of 5 probes conclusive (the authorize endpoint rejected a fake client); about $0.07 |
| Calendly | OpenAI | Valid guide; honest that Calendly does not say who approves scopes or how long it takes |
| Xero, with OpenAI deliberately broken | Gemini + Tavily (automatic fallback) | Switched in under a second, valid guide in 24 s. But it missed Xero's limit for new apps ("New apps default to the starter tier with 5 connections"). The backup now searches more, the research asks for connection caps, and guides made by the backup show a visible caution |

## What we could not verify

- How long Google's CASA security assessment takes and what it costs (not stated by Google).
- How long Meta Business Verification takes.
- Whether Slack's existing-install exemption from the new rate limit ended on 2026-03-03 (seen
  only in a search snippet).
- Which scopes Composio's managed apps request by default.
- Salesforce's five-active-refresh-token cap on a Salesforce page (stated by Composio).
- Anything behind a provider login, such as exact console labels after signing in, except
  where the real setup attempt checked them.

Each guide lists its own open questions under "What we could not verify".
