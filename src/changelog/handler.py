from __future__ import annotations

import base64
import json
import logging
from typing import Any

from changelog.config import load_secrets, load_settings
from changelog.github import loads_body, parse_merged_pull_request, verify_signature
from changelog.slack import post_shipped
from changelog.store import Store

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _response(status: int, body: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(body),
    }


def process_event(
    *,
    headers: dict[str, str],
    body: bytes,
    store: Store,
    secrets: dict[str, Any],
    free_tier_limit: int,
) -> dict[str, Any]:
    sig = headers.get("x-hub-signature-256") or headers.get("X-Hub-Signature-256")
    secret = secrets["github_webhook_secret"]
    if not verify_signature(secret, body, sig):
        return _response(401, {"ok": False, "error": "bad_signature"})

    event_name = headers.get("x-github-event") or headers.get("X-GitHub-Event") or ""
    payload = loads_body(body)
    merge = parse_merged_pull_request(event_name, payload)
    if not merge:
        return _response(200, {"ok": True, "skipped": "not_merged_pr"})

    repo = merge["repo"]
    repo_cfg = store.get_repo(repo)
    if not repo_cfg:
        return _response(200, {"ok": True, "skipped": "not_allowlisted"})
    if repo_cfg.get("muted", False):
        return _response(200, {"ok": True, "skipped": "muted"})

    active = store.count_active_repos()
    if active > free_tier_limit:
        # Config already over free tier — no-op until Pro (KAN-4).
        return _response(200, {"ok": True, "skipped": "free_tier_exceeded"})

    created = store.put_note_if_new(
        merge["sha"],
        {
            "repo": repo,
            "title": merge["title"],
            "pr_url": merge["pr_url"],
            "pr_number": merge.get("pr_number"),
            "author": merge.get("author"),
        },
    )
    if not created:
        return _response(200, {"ok": True, "skipped": "duplicate_sha"})

    channel = secrets.get("slack_channel") or "#shipped"
    post_shipped(
        secrets["slack_bot_token"],
        channel,
        repo=repo,
        sha=merge["sha"],
        title=merge["title"],
        pr_url=merge["pr_url"],
        author=merge.get("author"),
    )
    return _response(200, {"ok": True, "shipped": merge["sha"]})


def lambda_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    settings = load_settings()
    secrets = load_secrets(settings.secrets_arn)
    store = Store(settings.notes_table, settings.repos_table)

    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    # Normalize common casing after lowercasing keys
    raw_headers = event.get("headers") or {}
    for key in ("X-Hub-Signature-256", "X-GitHub-Event", "x-hub-signature-256", "x-github-event"):
        if key in raw_headers:
            headers[key] = raw_headers[key]

    body_str = event.get("body") or ""
    if event.get("isBase64Encoded"):
        body = base64.b64decode(body_str)
    else:
        body = body_str.encode("utf-8") if isinstance(body_str, str) else body_str

    return process_event(
        headers=headers,
        body=body,
        store=store,
        secrets=secrets,
        free_tier_limit=settings.free_tier_repo_limit,
    )
