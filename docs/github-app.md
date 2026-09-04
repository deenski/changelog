# GitHub App wiring (KAN-2)

Create the App after `cdk deploy` so you have `WebhookUrl` from stack outputs.

## One-click manifest

1. Open (logged in as `deenski`):
   `https://github.com/settings/apps/new?state=changelog`
2. Or use the manifest flow: paste `github-app-manifest.json` via
   [Create GitHub App from manifest](https://docs.github.com/en/apps/sharing-github-apps/registering-a-github-app-from-a-manifest).
3. Set **Webhook URL** to the CDK output `WebhookUrl` (…/webhook).
4. Generate a webhook secret; put it in Secrets Manager as `github_webhook_secret`.
5. Generate a private key; store PEM as `github_private_key` (reserved; v0 receive is HMAC-only).
6. Install the App on **only** `deenski/changelog` (dogfood).

## Secrets Manager JSON

Secret name suggestion: `changelog/prod`

```json
{
  "github_app_id": "REPLACE",
  "github_private_key": "-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----",
  "github_webhook_secret": "REPLACE",
  "slack_bot_token": "xoxb-REPLACE",
  "slack_channel": "#shipped"
}
```

## Slack

- Channel must exist: `#shipped` (create if missing).
- Bot needs `chat:write` in that channel.

## Deploy order

```bash
# 1. Create empty secret shell (values filled after App + Slack bot exist)
aws secretsmanager create-secret --name changelog/prod --secret-string file://secrets.example.json

# 2. CDK
cd infra
cdk deploy -c secretsArn=$(aws secretsmanager describe-secret --secret-id changelog/prod --query ARN --output text)

# 3. Create/update GitHub App webhook URL from stack output WebhookUrl
# 4. Allowlist repo in DynamoDB Repos table: {"repo":"deenski/changelog","muted":false}
```
