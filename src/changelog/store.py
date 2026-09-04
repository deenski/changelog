from __future__ import annotations

from typing import Any

import boto3
from botocore.exceptions import ClientError


class Store:
    def __init__(self, notes_table: str, repos_table: str, dynamodb: Any | None = None):
        self._db = dynamodb or boto3.resource("dynamodb")
        self.notes = self._db.Table(notes_table)
        self.repos = self._db.Table(repos_table)

    def get_repo(self, full_name: str) -> dict[str, Any] | None:
        item = self.repos.get_item(Key={"repo": full_name}).get("Item")
        return item

    def count_active_repos(self) -> int:
        # v0: small free-tier table; full scan is fine.
        count = 0
        scan_kwargs: dict[str, Any] = {}
        while True:
            resp = self.repos.scan(**scan_kwargs)
            for item in resp.get("Items", []):
                if not item.get("muted", False):
                    count += 1
            if "LastEvaluatedKey" not in resp:
                break
            scan_kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
        return count

    def put_note_if_new(self, sha: str, payload: dict[str, Any]) -> bool:
        """Return True if this SHA was newly recorded (caller should Slack)."""
        item = {"sha": sha, **payload}
        try:
            self.notes.put_item(
                Item=item,
                ConditionExpression="attribute_not_exists(sha)",
            )
            return True
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return False
            raise
