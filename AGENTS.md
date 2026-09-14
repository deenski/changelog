# AGENTS.md — changelog

Project rules for Grok Build (`grok`) and other coding agents. Keep this short and specific.

## Product

- Merge notes → Slack (channel from Secrets Manager `slack_channel`, default `#shipped`) + free public `/changelog` pages.
- Free tier: ≤5 allowlisted repos. Prove free signup/adoption before Stripe.
- Out of scope unless Product tickets it: Stripe (KAN-3), Pro >5 (KAN-4), custom domain (KAN-5).
- Do not invent product scope. Coordinate with Product / Orchestrator.

## Stack (hard rules)

- AWS **GA only**: API Gateway HTTP API, Lambda (Python 3.12), DynamoDB, Secrets Manager.
- IaC: **AWS CDK (TypeScript)** in `infra/` — never Terraform. (KAN-12; Lambda app code stays Python.)
- App (Lambda) language for this repo: **Python**. Org default elsewhere: Python or TypeScript; Go OK; avoid Rust unless asked.

## Layout

- `src/changelog/` — Lambda package (Python)
- `infra/` — CDK app + stack (TypeScript)
- `docs/` — install / adoption
- `tests/` — unit tests (no AWS)
- `.grok/skills/` — optional Grok Build project skills

## Commands

Tests:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q
```

Deploy (after secrets exist in Secrets Manager):

```bash
cd infra
npm ci
npx cdk bootstrap   # once per account/region
export SECRETS_ARN=arn:aws:secretsmanager:...:secret:changelog/...
npx cdk deploy -c secretsArn="$SECRETS_ARN"
```

Stack outputs: `WebhookUrl`, `PublicChangelogUrl`, `InstallLandingUrl`, `MetricsUrl`.

## Do / Don’t

- Don’t commit secrets. Use Secrets Manager; shape is in `secrets.example.json`.
- Slack destination is configurable via Secrets Manager `slack_channel` (default `#shipped`); do not hard-code the only channel in product docs.
- Don’t add non-GA AWS services.
- Prefer small PRs. Ask before merging to main, force-pushing, or hard-to-undo ops.
- Allowlist gate: DynamoDB `repos` (`muted=false`); App install alone does not allowlist (v0).
- On Slack failure after writing a note, handler returns 5xx so GitHub redelivers.

## Grok Build

- This file is loaded automatically by `grok` (walked from cwd to repo root).
- Optional skills: `.grok/skills/<name>/SKILL.md`.
- Verify discovery: `grok inspect`.
- Headless smoke (after auth): `grok --no-auto-update -p "Explain this repo."`
