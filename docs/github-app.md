# GitHub App wiring (KAN-2)

**Shipped App:** [`deenski-changelog`](https://github.com/apps/deenski-changelog) (App ID `4830006`), installed on `deenski/changelog`.

Create flow (historical / recreate):

1. Open (logged in as `deenski`): Developer settings → GitHub Apps → New.
2. Or use the manifest flow: paste `github-app-manifest.json` via
   [Create GitHub App from manifest](https://docs.github.com/en/apps/sharing-github-apps/registering-a-github-app-from-a-manifest).
   Manifest `name` must be globally unique (`deenski-changelog`, not `Changelog`).
3. Webhook URL = CDK output `WebhookUrl` (live: `https://pn4i4lubz3.execute-api.us-east-1.amazonaws.com/webhook`).
4. Webhook secret → Secrets Manager `github_webhook_secret`.
5. Private key PEM → `github_private_key` (v0 receive is HMAC-only; PEM reserved for App API).
6. Install on **only** `deenski/changelog`.

## Secrets Manager JSON

Secret: `changelog/prod`

```json
{
  "github_app_id": "4830006",
  "github_private_key": "-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----",
  "github_webhook_secret": "REPLACE",
  "slack_bot_token": "xoxb-REPLACE",
  "slack_channel": "C0BUV8EDEKD"
}
```

## Slack

- Channel: `#shipped` (`C0BUV8EDEKD`).
- Bot needs `chat:write` and membership in that channel.

## Deploy order

```bash
aws secretsmanager create-secret --name changelog/prod --secret-string file://secrets.example.json

cd infra
cdk deploy -c secretsArn=$(aws secretsmanager describe-secret --secret-id changelog/prod --query ARN --output text)

# Allowlist: DynamoDB Repos item {"repo":"deenski/changelog","muted":false}
```
