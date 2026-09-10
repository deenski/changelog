from __future__ import annotations

import base64
import json
import logging
from typing import Any
from urllib.parse import unquote

from changelog.config import load_secrets, load_settings
from changelog.github import loads_body, parse_merged_pull_request, verify_signature
from changelog.public import render_landing, render_repo_changelog, render_repo_index
from changelog.slack import post_shipped
from changelog.store import Store

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _json(status: int, body: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(body),
    }


def _html(status: int, body: str) -> dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {"content-type": "text/html; charset=utf-8"},
        "body": body,
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
        return _json(401, {"ok": False, "error": "bad_signature"})

    event_name = headers.get("x-github-event") or headers.get("X-GitHub-Event") or ""
    payload = loads_body(body)
    merge = parse_merged_pull_request(event_name, payload)
    if not merge:
        return _json(200, {"ok": True, "skipped": "not_merged_pr"})

    repo = merge["repo"]
    repo_cfg = store.get_repo(repo)
    if not repo_cfg:
        return _json(200, {"ok": True, "skipped": "not_allowlisted"})
    if repo_cfg.get("muted", False):
        return _json(200, {"ok": True, "skipped": "muted"})

    # Free-tier is enforced on allowlist *add* (try_add_repo), not ingest.
    _ = free_tier_limit

    created = store.put_note_if_new(
        merge["sha"],
        {
            "repo": repo,
            "title": merge["title"],
            "pr_url": merge["pr_url"],
            "pr_number": merge.get("pr_number"),
            "author": merge.get("author"),
            "merged_at": merge.get("merged_at") or "",
        },
    )
    if not created:
        existing = store.get_note(merge["sha"])
        if existing and existing.get("notified"):
            return _json(200, {"ok": True, "skipped": "duplicate_sha"})
        # pending note: fall through and retry Slack

    channel = secrets.get("slack_channel") or "#shipped"
    try:
        post_shipped(
            secrets["slack_bot_token"],
            channel,
            repo=repo,
            sha=merge["sha"],
            title=merge["title"],
            pr_url=merge["pr_url"],
            author=merge.get("author"),
        )
    except Exception as exc:
        logger.exception("slack_failed sha=%s", merge["sha"])
        return _json(502, {"ok": False, "error": "slack_failed", "detail": str(exc)})

    store.mark_notified(merge["sha"])
    return _json(200, {"ok": True, "shipped": merge["sha"]})


def _route_path(event: dict[str, Any]) -> str:
    ctx = event.get("requestContext") or {}
    http = ctx.get("http") or {}
    path = http.get("path") or event.get("rawPath") or event.get("path") or "/"
    return path.rstrip("/") or "/"


def _route_method(event: dict[str, Any]) -> str:
    ctx = event.get("requestContext") or {}
    http = ctx.get("http") or {}
    return (http.get("method") or event.get("httpMethod") or "GET").upper()


def handle_public_get(path: str, store: Store) -> dict[str, Any]:
    if path == "/":
        store.increment_metric("landing_hits")
        return _html(200, render_landing())

    if path == "/changelog":
        store.increment_metric("page_hits")
        repos = store.list_active_repos()
        return _html(200, render_repo_index(repos))

    if path == "/metrics":
        return _json(
            200,
            {
                "ok": True,
                "page_hits": store.get_metric("page_hits"),
                "landing_hits": store.get_metric("landing_hits"),
                "active_repos": store.count_active_repos(),
            },
        )

    prefix = "/changelog/"
    if path.startswith(prefix):
        rest = unquote(path[len(prefix) :])
        parts = [p for p in rest.split("/") if p]
        if len(parts) != 2:
            return _html(404, "<h1>Not found</h1>")
        full_name = f"{parts[0]}/{parts[1]}"
        cfg = store.get_repo(full_name)
        if not cfg or cfg.get("muted", False):
            return _html(404, "<h1>Not found</h1><p>Repo not allowlisted (or muted).</p>")
        store.increment_metric("page_hits")
        notes = store.list_notes_for_repo(full_name)
        return _html(200, render_repo_changelog(full_name, notes))

    return _html(404, "<h1>Not found</h1>")


def lambda_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    settings = load_settings()
    store = Store(
        settings.notes_table,
        settings.repos_table,
        metrics_table=settings.metrics_table or None,
    )

    method = _route_method(event)
    path = _route_path(event)

    if method == "GET":
        # Public pages never touch Secrets Manager.
        return handle_public_get(path, store)

    if method == "POST" and path.endswith("/webhook"):
        secrets = load_secrets(settings.secrets_arn)
        headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
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

    return _json(405, {"ok": False, "error": "method_not_allowed"})
