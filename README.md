# Changelog

MRR experiment (KAN-1): turn merged PRs into short Slack `#shipped` notes.

**v0 (KAN-2):** GitHub App → idempotent note-per-SHA → Slack. Free: ≤5 allowlisted repos.

Out of scope here: public page, Stripe (KAN-3/KAN-4), Jira.

## Stack (AWS GA only)

- API Gateway HTTP API
- Lambda (Python 3.12)
- DynamoDB (`notes` by SHA, `repos` allowlist/mute)
- Secrets Manager (GitHub App + Slack bot token)
- **IaC: AWS CDK (Python)**

## Layout

```
src/changelog/   # Lambda package
infra/           # CDK app + stack
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

Webhook URL is a stack output (`WebhookUrl`).

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

`github_app_id` / private key are reserved for future App API calls. **v0 receive path is HMAC webhook verify only.**

## Allowlist (v0)

| repo (S) | muted (BOOL) |
|----------|--------------|
| `owner/repo` | `false` |

Muted or missing → no-op. Free-tier ≤5 is enforced when **adding** a repo (`Store.try_add_repo`), not on every ingest — overfilling the table must not silence the first five.

## Failure / retry

Notes are written `notified=false`, Slack runs, then `notified=true`. If Slack fails, the handler returns **5xx** and GitHub redelivers; pending notes retry Slack without being stuck as silent duplicates.

## Dogfood

1. Deploy via CDK.
2. `try_add_repo` / put `deenski/changelog` in `repos`.
3. Merge a PR → one Slack note per merge SHA; redeliver → no duplicate after notified.
