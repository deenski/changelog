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
        return self.repos.get_item(Key={"repo": full_name}).get("Item")

    def count_active_repos(self) -> int:
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

    def try_add_repo(self, full_name: str, *, muted: bool = False, free_tier_limit: int = 5) -> bool:
        """Add allowlisted repo if under free-tier cap. Returns False if at limit."""
        existing = self.get_repo(full_name)
        if existing is not None:
            return True
        if self.count_active_repos() >= free_tier_limit:
            return False
        self.repos.put_item(Item={"repo": full_name, "muted": muted})
        return True

    def get_note(self, sha: str) -> dict[str, Any] | None:
        return self.notes.get_item(Key={"sha": sha}).get("Item")

    def put_note_if_new(self, sha: str, payload: dict[str, Any]) -> bool:
        """Insert pending note. True if newly created."""
        item = {"sha": sha, "notified": False, **payload}
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

    def mark_notified(self, sha: str) -> None:
        self.notes.update_item(
            Key={"sha": sha},
            UpdateExpression="SET notified = :t",
            ExpressionAttributeValues=":t",  # placeholder fixed below
        )
