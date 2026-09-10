# Install Changelog (free)

No paywall. Free tier: **≤5 allowlisted repos**. Slack notes + public read-only changelog page.

## Important (v0)

**Installing the GitHub App does not auto-allowlist repos.** Ingest still gates on the DynamoDB `repos` table. After App install, an operator must add each repo (`muted=false`) via `Store.try_add_repo` (or a direct put). Self-serve install→allowlist sync is out of scope for KAN-6.

## 1. Install the GitHub App

1. Open [deenski-changelog](https://github.com/apps/deenski-changelog).
2. Install on your account or org.
3. Select **up to 5 repositories** you want notes for (you can change later).

Permissions used: Contents (read), Pull requests (read). Event: `pull_request`.

## 2. Ops: Dynamo allowlist (required)

| repo | muted |
|------|-------|
| `owner/name` | `false` |

- Missing or `muted=true` → webhook no-ops (and public page 404s).
- Adding a 6th active repo via `Store.try_add_repo` is rejected (free cap).
- Already-allowlisted repos keep shipping even if the table was overfilled.

Dogfood: put `deenski/changelog` with `muted=false`.

## 3. Slack

1. Invite the Changelog bot to `#shipped` (or the channel configured in Secrets Manager).
2. Merge a PR on an allowlisted repo → one short note per merge SHA.

## 4. Public page

After deploy, stack outputs:

- `InstallLandingUrl` — stranger-facing install blurb (`/`)
- `PublicChangelogUrl` — list of allowlisted repos (`/changelog`)
- Per-repo page: `/changelog/{owner}/{repo}` (dogfood: `/changelog/deenski/changelog`)
- `MetricsUrl` — basic adoption counters (`page_hits`, `landing_hits`)

AWS API Gateway URL is fine for v0 (custom domain is KAN-5, out of scope).

## 5. What this is not

- No Stripe / Pro gate (KAN-3) — paused until free adoption is proven.
- No Pro >5 repos public page (KAN-4).
- No custom domain (KAN-5).
- No automatic App-install → Dynamo allowlist sync (manual ops for v0).
