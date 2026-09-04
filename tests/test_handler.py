from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

from botocore.exceptions import ClientError

from changelog.handler import process_event


class FakeNotes:
    def __init__(self):
        self.items: dict[str, dict[str, Any]] = {}

    def get_item(self, Key):
        item = self.items.get(Key["sha"])
        return {"Item": item} if item else {}

    def put_item(self, Item, ConditionExpression=None):
        sha = Item["sha"]
        if ConditionExpression and sha in self.items:
            raise ClientError(
                {"Error": {"Code": "ConditionalCheckFailedException", "Message": "exists"}},
                "PutItem",
            )
        self.items[sha] = Item

    def update_item(self, Key, UpdateExpression=None, ExpressionAttributeValues=None):
        sha = Key["sha"]
        self.items.setdefault(sha, {"sha": sha})
        if ExpressionAttributeValues and ":t" in ExpressionAttributeValues:
            self.items[sha]["notified"] = ExpressionAttributeValues[":t"]


class FakeRepos:
    def __init__(self, items: dict[str, dict[str, Any]] | None = None):
        self.items = items or {}

    def get_item(self, Key):
        item = self.items.get(Key["repo"])
        return {"Item": item} if item else {}

    def put_item(self, Item):
        self.items[Item["repo"]] = Item

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

    def try_add_repo(self, full_name: str, *, muted: bool = False, free_tier_limit: int = 5) -> bool:
        if self.get_repo(full_name) is not None:
            return True
        if self.count_active_repos() >= free_tier_limit:
            return False
        self.repos.put_item(Item={"repo": full_name, "muted": muted})
        return True

    def get_note(self, sha: str):
        return self.notes.get_item(Key={"sha": sha}).get("Item")

    def put_note_if_new(self, sha: str, payload: dict[str, Any]) -> bool:
        try:
            self.notes.put_item(
                Item={"sha": sha, "notified": False, **payload},
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
            ExpressionAttributeValues={":t": True},
        )


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
        headers={"X-GitHub-Event": "pull_request", "X-Hub-Signature-256": _signed(body, secret)},
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
        headers={"X-GitHub-Event": "pull_request", "X-Hub-Signature-256": _signed(body, secret)},
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
    headers = {"X-GitHub-Event": "pull_request", "X-Hub-Signature-256": _signed(body, secret)}
    first = process_event(headers=headers, body=body, store=store, secrets=secrets, free_tier_limit=5)
    second = process_event(headers=headers, body=body, store=store, secrets=secrets, free_tier_limit=5)
    assert json.loads(first["body"])["shipped"] == "abc"
    assert json.loads(second["body"])["skipped"] == "duplicate_sha"
    assert len(posted) == 1


def test_slack_failure_returns_502_and_retries(monkeypatch):
    calls = {"n": 0}

    def boom(*_a, **_k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("slack down")

    monkeypatch.setattr("changelog.handler.post_shipped", boom)
    secret = "whsec"
    body = _merged_body(sha="retryme")
    store = FakeStore(repos={"deenski/changelog": {"repo": "deenski/changelog", "muted": False}})
    secrets = {"github_webhook_secret": secret, "slack_bot_token": "xoxb-t"}
    headers = {"X-GitHub-Event": "pull_request", "X-Hub-Signature-256": _signed(body, secret)}
    first = process_event(headers=headers, body=body, store=store, secrets=secrets, free_tier_limit=5)
    assert first["statusCode"] == 502
    assert store.get_note("retryme")["notified"] is False
    second = process_event(headers=headers, body=body, store=store, secrets=secrets, free_tier_limit=5)
    assert second["statusCode"] == 200
    assert json.loads(second["body"])["shipped"] == "retryme"
    assert store.get_note("retryme")["notified"] is True


def test_overfilled_table_does_not_silence_allowlisted(monkeypatch):
    posted = []
    monkeypatch.setattr("changelog.handler.post_shipped", lambda *a, **k: posted.append(k))
    secret = "whsec"
    body = _merged_body(sha="stillships")
    repos = {f"org/r{i}": {"repo": f"org/r{i}", "muted": False} for i in range(6)}
    repos["deenski/changelog"] = {"repo": "deenski/changelog", "muted": False}
    store = FakeStore(repos=repos)
    resp = process_event(
        headers={"X-GitHub-Event": "pull_request", "X-Hub-Signature-256": _signed(body, secret)},
        body=body,
        store=store,
        secrets={"github_webhook_secret": secret, "slack_bot_token": "xoxb-t"},
        free_tier_limit=5,
    )
    assert json.loads(resp["body"]).get("shipped") == "stillships"
    assert len(posted) == 1


def test_try_add_repo_enforces_free_tier():
    store = FakeStore(repos={f"org/r{i}": {"repo": f"org/r{i}", "muted": False} for i in range(5)})
    assert store.try_add_repo("org/new", free_tier_limit=5) is False
    assert store.get_repo("org/new") is None


def test_bad_signature_401(monkeypatch):
    monkeypatch.setattr("changelog.handler.post_shipped", lambda *a, **k: None)
    body = _merged_body()
    store = FakeStore(repos={"deenski/changelog": {"repo": "deenski/changelog", "muted": False}})
    resp = process_event(
        headers={"X-GitHub-Event": "pull_request", "X-Hub-Signature-256": "sha256=deadbeef"},
        body=body,
        store=store,
        secrets={"github_webhook_secret": "whsec", "slack_bot_token": "xoxb-t"},
        free_tier_limit=5,
    )
    assert resp["statusCode"] == 401
    assert json.loads(resp["body"])["error"] == "bad_signature"
