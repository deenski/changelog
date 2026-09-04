from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

from changelog.handler import process_event


class FakeNotes:
    def __init__(self):
        self.items: dict[str, dict[str, Any]] = {}

    def put_item(self, Item, ConditionExpression=None):
        sha = Item["sha"]
        if ConditionExpression and sha in self.items:
            from botocore.exceptions import ClientError

            raise ClientError(
                {"Error": {"Code": "ConditionalCheckFailedException", "Message": "exists"}},
                "PutItem",
            )
        self.items[sha] = Item


class FakeRepos:
    def __init__(self, items: dict[str, dict[str, Any]] | None = None):
        self.items = items or {}

    def get_item(self, Key):
        item = self.items.get(Key["repo"])
        return {"Item": item} if item else {}

    def scan(self, **_kwargs):
        return {"Items": list(self.items.values())}


class FakeStore:
    def __init__(self, repos: dict[str, dict[str, Any]] | None = None):
        self.notes = FakeNotes()
        self.repos = FakeRepos(repos)

    def get_repo(self, full_name: str):
        return self.repos.get_item(Key={"repo": full_name}).get("Item")

    def count_active_repos(self) -> int:
        return sum(1 for i in self.repos.items.values() if not i.get("muted", False))

    def put_note_if_new(self, sha: str, payload: dict[str, Any]) -> bool:
        try:
            self.notes.put_item(Item={"sha": sha, **payload}, ConditionExpression="attribute_not_exists(sha)")
            return True
        except Exception:
            return False


def _signed(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _merged_body(repo="deenski/changelog", sha="deadbeef"):
    return json.dumps(
        {
            "action": "closed",
            "pull_request": {
                "merged": True,
                "merge_commit_sha": sha,
                "title": "Ship it",
                "html_url": "https://github.com/deenski/changelog/pull/2",
                "number": 2,
                "user": {"login": "deenski"},
            },
            "repository": {"full_name": repo},
        }
    ).encode()


def test_not_allowlisted_noop(monkeypatch):
    posted = []
    monkeypatch.setattr("changelog.handler.post_shipped", lambda *a, **k: posted.append(k))
    secret = "whsec"
    body = _merged_body()
    store = FakeStore(repos={})
    resp = process_event(
        headers={
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": _signed(body, secret),
        },
        body=body,
        store=store,
        secrets={"github_webhook_secret": secret, "slack_bot_token": "xoxb-t"},
        free_tier_limit=5,
    )
    assert json.loads(resp["body"])["skipped"] == "not_allowlisted"
    assert posted == []


def test_mute_skips(monkeypatch):
    posted = []
    monkeypatch.setattr("changelog.handler.post_shipped", lambda *a, **k: posted.append(k))
    secret = "whsec"
    body = _merged_body()
    store = FakeStore(repos={"deenski/changelog": {"repo": "deenski/changelog", "muted": True}})
    resp = process_event(
        headers={
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": _signed(body, secret),
        },
        body=body,
        store=store,
        secrets={"github_webhook_secret": secret, "slack_bot_token": "xoxb-t"},
        free_tier_limit=5,
    )
    assert json.loads(resp["body"])["skipped"] == "muted"
    assert posted == []


def test_idempotent_no_double_slack(monkeypatch):
    posted = []
    monkeypatch.setattr("changelog.handler.post_shipped", lambda *a, **k: posted.append(k))
    secret = "whsec"
    body = _merged_body(sha="abc")
    store = FakeStore(repos={"deenski/changelog": {"repo": "deenski/changelog", "muted": False}})
    secrets = {"github_webhook_secret": secret, "slack_bot_token": "xoxb-t", "slack_channel": "#shipped"}
    headers = {
        "X-GitHub-Event": "pull_request",
        "X-Hub-Signature-256": _signed(body, secret),
    }
    first = process_event(headers=headers, body=body, store=store, secrets=secrets, free_tier_limit=5)
    second = process_event(headers=headers, body=body, store=store, secrets=secrets, free_tier_limit=5)
    assert json.loads(first["body"])["shipped"] == "abc"
    assert json.loads(second["body"])["skipped"] == "duplicate_sha"
    assert len(posted) == 1
