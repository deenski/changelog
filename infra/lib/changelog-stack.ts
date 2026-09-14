import * as path from "path";
import * as cdk from "aws-cdk-lib";
import { Duration, RemovalPolicy } from "aws-cdk-lib";
import * as apigwv2 from "aws-cdk-lib/aws-apigatewayv2";
import { HttpLambdaIntegration } from "aws-cdk-lib/aws-apigatewayv2-integrations";
import * as dynamodb from "aws-cdk-lib/aws-dynamodb";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as secretsmanager from "aws-cdk-lib/aws-secretsmanager";
import { Construct } from "constructs";

export interface ChangelogIngestStackProps extends cdk.StackProps {
  secretsArn: string;
  freeTierRepoLimit?: number;
}

/** Repo root (parent of infra/). */
const ROOT = path.join(__dirname, "..", "..");

export class ChangelogIngestStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: ChangelogIngestStackProps) {
    super(scope, id, props);

    const freeTierRepoLimit = props.freeTierRepoLimit ?? 5;

    const notes = new dynamodb.Table(this, "Notes", {
      partitionKey: { name: "sha", type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: RemovalPolicy.DESTROY,
    });
    notes.addGlobalSecondaryIndex({
      indexName: "repo-index",
      partitionKey: { name: "repo", type: dynamodb.AttributeType.STRING },
      projectionType: dynamodb.ProjectionType.ALL,
    });

    const repos = new dynamodb.Table(this, "Repos", {
      partitionKey: { name: "repo", type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: RemovalPolicy.DESTROY,
    });

    const metrics = new dynamodb.Table(this, "Metrics", {
      partitionKey: { name: "metric", type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: RemovalPolicy.DESTROY,
    });

    const secret = secretsmanager.Secret.fromSecretCompleteArn(
      this,
      "AppSecrets",
      props.secretsArn,
    );

    const fn = new lambda.Function(this, "IngestFn", {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: "changelog.handler.lambda_handler",
      code: lambda.Code.fromAsset(path.join(ROOT, "src")),
      timeout: Duration.seconds(30),
      memorySize: 256,
      architecture: lambda.Architecture.ARM_64,
      environment: {
        NOTES_TABLE: notes.tableName,
        REPOS_TABLE: repos.tableName,
        METRICS_TABLE: metrics.tableName,
        SECRETS_ARN: props.secretsArn,
        FREE_TIER_REPO_LIMIT: String(freeTierRepoLimit),
      },
    });
    notes.grantReadWriteData(fn);
    repos.grantReadWriteData(fn);
    metrics.grantReadWriteData(fn);
    secret.grantRead(fn);

    const httpApi = new apigwv2.HttpApi(this, "WebhookApi", {
      corsPreflight: {
        allowMethods: [apigwv2.CorsHttpMethod.GET, apigwv2.CorsHttpMethod.POST],
        allowOrigins: ["*"],
      },
    });
    const integration = new HttpLambdaIntegration("IngestIntegration", fn);
    httpApi.addRoutes({
      path: "/webhook",
      methods: [apigwv2.HttpMethod.POST],
      integration,
    });
    httpApi.addRoutes({
      path: "/changelog",
      methods: [apigwv2.HttpMethod.GET],
      integration,
    });
    httpApi.addRoutes({
      path: "/changelog/{owner}/{repo}",
      methods: [apigwv2.HttpMethod.GET],
      integration,
    });
    httpApi.addRoutes({
      path: "/metrics",
      methods: [apigwv2.HttpMethod.GET],
      integration,
    });
    httpApi.addRoutes({
      path: "/",
      methods: [apigwv2.HttpMethod.GET],
      integration,
    });

    new cdk.CfnOutput(this, "WebhookUrl", {
      value: `${httpApi.apiEndpoint}/webhook`,
    });
    new cdk.CfnOutput(this, "PublicChangelogUrl", {
      value: `${httpApi.apiEndpoint}/changelog`,
    });
    new cdk.CfnOutput(this, "InstallLandingUrl", {
      value: `${httpApi.apiEndpoint}/`,
    });
    new cdk.CfnOutput(this, "MetricsUrl", {
      value: `${httpApi.apiEndpoint}/metrics`,
    });
    new cdk.CfnOutput(this, "NotesTableName", { value: notes.tableName });
    new cdk.CfnOutput(this, "ReposTableName", { value: repos.tableName });
    new cdk.CfnOutput(this, "MetricsTableName", { value: metrics.tableName });
  }
}
