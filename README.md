# Changelog

Merge notes → Slack `#shipped`, plus a **free** public read-only changelog page.

**v0 (KAN-2):** GitHub App → idempotent note-per-SHA → Slack. Free: ≤5 allowlisted repos.

**KAN-6:** Public `/changelog` pages + install landing + basic adoption metrics. No Stripe.

Out of scope: Stripe (KAN-3), Pro >5 (KAN-4), custom domain (KAN-5).

## Stack (AWS GA only)

- API Gateway HTTP API
- Lambda (Python 3.12)
- DynamoDB (`notes` by SHA + `repo-index` GSI, `repos` allowlist/mute, `metrics` counters)
- Secrets Manager (GitHub App + Slack bot token)
- **IaC: AWS CDK (Python)**

## Stranger install

See [docs/install.md](docs/install.md). Short path:

1. Install [deenski-changelog](https://github.com/apps/deenski-changelog) on ≤5 repos.
2. Invite the Slack bot to `#shipped`.
3. Merge a PR → Slack note + public page entry.

## Layout

```
src/changelog/   # Lambda package
infra/           # CDK app + stack
docs/            # install / adoption
tests/           # unit tests (no AWS)
```

## Local tests

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q
```

## Deploy (after secrets exist)

```bash
cd infra
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cdk bootstrap   # once per account/region
cdk deploy -c secretsArn=arn:aws:secretsmanager:...:secret:changelog/...
```

Stack outputs: `WebhookUrl`, `PublicChangelogUrl`, `InstallLandingUrl`, `MetricsUrl`.

## GitHub App

1. Create a GitHub App with `pull_request` events; Contents read, Pull requests read.
2. Webhook URL = stack `WebhookUrl`; secret matches Secrets Manager.
3. Install on allowlisted repos (DynamoDB `repos` table still gates ingest).
4. Secrets Manager JSON:

```json
{
  "github_app_id": "123",
  "github_private_key": "-----BEGIN RSA PRIVATE KEY-----\n...",
  "github_webhook_secret": "...",
  "slack_bot_token": "xoxb-...",
  "slack_channel": "#shipped"
}
```

`github_app_id` / private key are reserved for future App API calls. **Receive path is HMAC webhook verify only.**

## Allowlist (free)

| repo (S) | muted (BOOL) |
|----------|--------------|
| `owner/repo` | `false` |

Muted or missing → no-op. Free-tier ≤5 is enforced when **adding** a repo (`Store.try_add_repo`), not on every ingest.

## Failure / retry

Notes are written `notified=false`, Slack runs, then `notified=true`. If Slack fails, the handler returns **5xx** and GitHub redelivers.

## Dogfood

1. Deploy via CDK.
2. Ensure `deenski/changelog` is in `repos` with `muted=false`.
3. Open `PublicChangelogUrl` / `changelog/deenski/changelog`.
4. Merge a PR → Slack + public page; `/metrics` shows `page_hits` / `landing_hits`.
