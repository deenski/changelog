from __future__ import annotations

from pathlib import Path

from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
)
from aws_cdk import aws_apigatewayv2 as apigwv2
from aws_cdk import aws_apigatewayv2_integrations as apigwv2_integrations
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct

ROOT = Path(__file__).resolve().parents[1]


class ChangelogIngestStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        secrets_arn: str,
        free_tier_repo_limit: int = 5,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        notes = dynamodb.Table(
            self,
            "Notes",
            partition_key=dynamodb.Attribute(name="sha", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )
        notes.add_global_secondary_index(
            index_name="repo-index",
            partition_key=dynamodb.Attribute(name="repo", type=dynamodb.AttributeType.STRING),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        repos = dynamodb.Table(
            self,
            "Repos",
            partition_key=dynamodb.Attribute(name="repo", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )

        metrics = dynamodb.Table(
            self,
            "Metrics",
            partition_key=dynamodb.Attribute(name="metric", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )

        secret = secretsmanager.Secret.from_secret_complete_arn(self, "AppSecrets", secrets_arn)

        fn = lambda_.Function(
            self,
            "IngestFn",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="changelog.handler.lambda_handler",
            code=lambda_.Code.from_asset(str(ROOT / "src")),
            timeout=Duration.seconds(30),
            memory_size=256,
            architecture=lambda_.Architecture.ARM_64,
            environment={
                "NOTES_TABLE": notes.table_name,
                "REPOS_TABLE": repos.table_name,
                "METRICS_TABLE": metrics.table_name,
                "SECRETS_ARN": secrets_arn,
                "FREE_TIER_REPO_LIMIT": str(free_tier_repo_limit),
            },
        )
        notes.grant_read_write_data(fn)
        repos.grant_read_write_data(fn)
        metrics.grant_read_write_data(fn)
        secret.grant_read(fn)

        http_api = apigwv2.HttpApi(
            self,
            "WebhookApi",
            cors_preflight=apigwv2.CorsPreflightOptions(
                allow_methods=[apigwv2.CorsHttpMethod.GET, apigwv2.CorsHttpMethod.POST],
                allow_origins=["*"],
            ),
        )
        integration = apigwv2_integrations.HttpLambdaIntegration("IngestIntegration", fn)
        http_api.add_routes(
            path="/webhook",
            methods=[apigwv2.HttpMethod.POST],
            integration=integration,
        )
        http_api.add_routes(
            path="/changelog",
            methods=[apigwv2.HttpMethod.GET],
            integration=integration,
        )
        http_api.add_routes(
            path="/changelog/{owner}/{repo}",
            methods=[apigwv2.HttpMethod.GET],
            integration=integration,
        )
        http_api.add_routes(
            path="/metrics",
            methods=[apigwv2.HttpMethod.GET],
            integration=integration,
        )
        http_api.add_routes(
            path="/",
            methods=[apigwv2.HttpMethod.GET],
            integration=integration,
        )

        CfnOutput(self, "WebhookUrl", value=f"{http_api.api_endpoint}/webhook")
        CfnOutput(self, "PublicChangelogUrl", value=f"{http_api.api_endpoint}/changelog")
        CfnOutput(self, "InstallLandingUrl", value=f"{http_api.api_endpoint}/")
        CfnOutput(self, "MetricsUrl", value=f"{http_api.api_endpoint}/metrics")
        CfnOutput(self, "NotesTableName", value=notes.table_name)
        CfnOutput(self, "ReposTableName", value=repos.table_name)
        CfnOutput(self, "MetricsTableName", value=metrics.table_name)
