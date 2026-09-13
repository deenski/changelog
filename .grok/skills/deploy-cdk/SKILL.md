---
name: deploy-cdk
description: Use this when deploying or bootstrapping the changelog AWS CDK stack in infra/.
when-to-use: cdk deploy, cdk bootstrap, ship infra, deploy changelog stack
---

# Deploy changelog (CDK / TypeScript)

## Preconditions

- AWS credentials with deploy rights (named CLI profile / access keys configured locally — never commit keys).
- Secrets Manager secret exists; pass its ARN as `-c secretsArn=...`.
- Never invent or commit secret values; shape is `secrets.example.json`.
- IaC is **TypeScript CDK** under `infra/` (KAN-12). Lambda runtime stays Python 3.12.

## Steps

1. `cd infra`
2. `npm ci`
3. `npx cdk bootstrap` once per account/region if needed
4. `export SECRETS_ARN=arn:aws:secretsmanager:REGION:ACCOUNT:secret:changelog/...`
5. `npx cdk deploy -c secretsArn="$SECRETS_ARN"`
6. Record stack outputs: `WebhookUrl`, `PublicChangelogUrl`, `InstallLandingUrl`, `MetricsUrl`

## After deploy

- Point the GitHub App webhook at `WebhookUrl` (secret must match Secrets Manager).
- Ensure allowlisted repos exist in DynamoDB `repos` with `muted=false` (≤5 free).
- Prefer the `dogfood-changelog` skill next.
