#!/usr/bin/env python3
from __future__ import annotations

import aws_cdk as cdk

from changelog_stack import ChangelogIngestStack

app = cdk.App()
secrets_arn = app.node.try_get_context("secretsArn")
if not secrets_arn:
    raise SystemExit("Pass -c secretsArn=arn:aws:secretsmanager:...:secret:...")

ChangelogIngestStack(
    app,
    "ChangelogIngest",
    secrets_arn=secrets_arn,
    env=cdk.Environment(
        account=app.node.try_get_context("account"),
        region=app.node.try_get_context("region") or "us-east-1",
    ),
)
app.synth()
