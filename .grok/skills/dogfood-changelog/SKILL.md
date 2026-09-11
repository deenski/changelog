---
name: dogfood-changelog
description: Use this when dogfooding changelog after deploy — allowlist, public page, Slack #shipped, metrics.
when-to-use: dogfood, verify ship, post-deploy check, changelog smoke test
---

# Dogfood changelog

1. Confirm stack is deployed (outputs present).
2. Ensure `deenski/changelog` is in DynamoDB `repos` with `muted=false`.
3. Open `PublicChangelogUrl` / path `changelog/deenski/changelog`.
4. Invite Slack bot to `#shipped` if needed.
5. Merge a PR on an allowlisted repo → expect Slack note + public page entry.
6. Hit `/metrics` — expect `page_hits` / `landing_hits` counters to move.
7. If Slack fails after note write, expect 5xx + GitHub redelivery (by design).

Do not expand into Stripe/Pro/custom-domain work during dogfood.
