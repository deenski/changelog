from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import boto3


@dataclass(frozen=True)
class Settings:
    notes_table: str
    repos_table: str
    secrets_arn: str
    free_tier_repo_limit: int


def load_settings() -> Settings:
    return Settings(
        notes_table=os.environ["NOTES_TABLE"],
        repos_table=os.environ["REPOS_TABLE"],
        secrets_arn=os.environ["SECRETS_ARN"],
        free_tier_repo_limit=int(os.environ.get("FREE_TIER_REPO_LIMIT", "5")),
    )


@lru_cache(maxsize=1)
def load_secrets(secrets_arn: str) -> dict[str, Any]:
    client = boto3.client("secretsmanager")
    raw = client.get_secret_value(SecretId=secrets_arn)["SecretString"]
    return json.loads(raw)
