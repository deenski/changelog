# Changelog

MRR experiment (KAN-1): turn merged PRs into short Slack `#shipped` notes.

**v0 (KAN-2):** GitHub App → idempotent note-per-SHA → Slack. Free: ≤5 allowlisted repos.

Out of scope here: public page, Stripe (KAN-3/KAN-4), Jira.

## Stack (AWS GA only)

- API Gateway HTTP API
- Lambda (Python 3.12)
- DynamoDB (`notes` by SHA, `repos` allowlist/mute)
- Secrets Manager (GitHub App private key + Slack bot token)

## Layout

```
src/changelog/     # Lambda package
template.yaml      # SAM
tests/             # unit tests (no AWS)
```

## Local tests

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q
```

## Deploy (after secrets exist)

```bash
sam build
sam deploy --guided
```

## GitHub App

1. Create a GitHub App with `pull_request` events; permission: Contents read, Pull requests read.
2. Set webhook URL to the API Gateway `/webhook` route; secret = value in Secrets Manager.
3. Install on allowlisted repos only (or rely on DynamoDB allowlist).
4. Put App ID + private key PEM + webhook secret in Secrets Manager JSON:

```json
{
  "github_app_id": "123",
  "github_private_key": "-----BEGIN RSA PRIVATE KEY-----\n...",
  "github_webhook_secret": "...",
  "slack_bot_token": "xoxb-...",
  "slack_channel": "#shipped"
}
```

## Allowlist (v0)

Put items in the `Repos` table:

| pk (S) | muted (BOOL) |
|--------|--------------|
| `owner/repo` | `false` |

Muted or missing → no-op. Free tier: at most 5 non-muted rows; extras no-op.

## Dogfood

1. Deploy.
2. Add `deenski/changelog` (or another repo) to allowlist.
3. Merge a PR → expect one Slack note per merge commit SHA; redeliver webhook → no duplicate.
