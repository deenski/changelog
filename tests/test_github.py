import hashlib
import hmac
import json

from changelog.github import parse_merged_pull_request, verify_signature


def test_verify_signature_ok():
    secret = "s3cret"
    body = b'{"ok":true}'
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert verify_signature(secret, body, f"sha256={digest}")


def test_verify_signature_bad():
    assert not verify_signature("s3cret", b"{}", "sha256=deadbeef")


def test_parse_merged_pr():
    payload = {
        "action": "closed",
        "pull_request": {
            "merged": True,
            "merge_commit_sha": "abc123",
            "title": "Add ingest",
            "html_url": "https://github.com/deenski/changelog/pull/1",
            "number": 1,
            "user": {"login": "deenski"},
        },
        "repository": {"full_name": "deenski/changelog"},
    }
    merge = parse_merged_pull_request("pull_request", payload)
    assert merge["sha"] == "abc123"
    assert merge["repo"] == "deenski/changelog"


def test_parse_ignores_unmerged():
    payload = {"action": "closed", "pull_request": {"merged": False}}
    assert parse_merged_pull_request("pull_request", payload) is None
