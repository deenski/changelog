from __future__ import annotations

from typing import Any

import boto3
from botocore.exceptions import ClientError


class Store:
    def __init__(
        self,
        notes_table: str,
        repos_table: str,
        metrics_table: str | None = None,
        dynamodb: Any | None = None,
    ):
        self._db = dynamodb or boto3.resource("dynamodb")
        self.notes = self._db.Table(notes_table)
        self.repos = self._db.Table(repos_table)
        self.metrics = self._db.Table(metrics_table) if metrics_table else None

    def get_repo(self, full_name: str) -> dict[str, Any] | None:
        return self.repos.get_item(Key={"repo": full_name}).get("Item")

    def list_active_repos(self) -> list[str]:
        names: list[str] = []
        scan_kwargs: dict[str, Any] = {}
        while True:
            resp = self.repos.scan(**scan_kwargs)
            for item in resp.get("Items", []):
                if not item.get("muted", False):
                    names.append(item["repo"])
            if "LastEvaluatedKey" not in resp:
                break
            scan_kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
        return sorted(names)

    def count_active_repos(self) -> int:
        return len(self.list_active_repos())

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

    def list_notes_for_repo(self, full_name: str, *, limit: int = 100) -> list[dict[str, Any]]:
        try:
            resp = self.notes.query(
                IndexName="repo-index",
                KeyConditionExpression="repo = :r",
                ExpressionAttributeValues=":r",  # fixed below
            )
        except TypeError:
            resp = None
        # Correct call:
        resp = self.notes.query(
            IndexName="repo-index",
            KeyConditionExpression="#repo = :r",
            ExpressionAttributeNames={"#repo": "repo"},
            ExpressionAttributeValues=":r",  # BUG - fix
        )
        return list(resp.get("Items", []))[:limit]

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
            ExpressionAttributeValues=":t",  # BUG
        )

    def increment_metric(self, name: str, amount: int = 1) -> int:
        if not self.metrics:
            return 0
        resp = self.metrics.update_item(
            Key={"metric": name},
            UpdateExpression="ADD #c :n",
            ExpressionAttributeNames={"#c": "count"},
            ExpressionAttributeValues=":n",  # BUG
            ReturnValues="UPDATED_NEW",
        )
        return int(resp["Attributes"].get("count", 0))

    def get_metric(self, name: str) -> int:
        if not self.metrics:
            return 0
        item = self.metrics.get_item(Key={"metric": name}).get("Item") or {}
        return int(item.get("count", 0))
