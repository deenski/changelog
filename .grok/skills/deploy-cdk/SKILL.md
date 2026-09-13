---
name: deploy-cdk
description: Use this when deploying or bootstrapping the changelog AWS CDK stack in infra/.
when-to-use: cdk deploy, cdk bootstrap, ship infra, deploy changelog stack
---

# Deploy changelog (CDK)

## Preconditions

- AWS credentials with deploy rights (named CLI profile / access keys configured locally — never commit keys).
- Secrets Manager secret exists; pass its ARN as `-c secretsArn=...`.
- Never invent or commit secret values; shape is `secrets.example.json`.

## Steps

1. `cd infra`
2. `python -m venv .venv && source .venv/bin/activate`
3. `pip install -r requirements.txt`
4. `cdk bootstrap` once per account/region if needed
5. `cdk deploy -c secretsArn=arn:aws:secretsmanager:REGION:ACCOUNT:secret:changelog/...`
6. Record stack outputs: `WebhookUrl`, `PublicChangelogUrl`, `InstallLandingUrl`, `MetricsUrl`

## After deploy

- Point the GitHub App webhook at `WebhookUrl` (secret must match Secrets Manager).
- Ensure allowlisted repos exist in DynamoDB `repos` with `muted=false` (≤5 free).
- Prefer the `dogfood-changelog` skill next.
