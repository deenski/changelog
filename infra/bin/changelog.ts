#!/usr/bin/env node
import * as cdk from "aws-cdk-lib";
import { ChangelogIngestStack } from "../lib/changelog-stack";

const app = new cdk.App();
const secretsArn = app.node.tryGetContext("secretsArn") as string | undefined;
if (!secretsArn) {
  throw new Error("Pass -c secretsArn=arn:aws:secretsmanager:...:secret:...");
}

new ChangelogIngestStack(app, "ChangelogIngest", {
  secretsArn,
  env: {
    account: app.node.tryGetContext("account") as string | undefined,
    region: (app.node.tryGetContext("region") as string | undefined) || "us-east-1",
  },
});
