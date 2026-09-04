from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any


def verify_signature(secret: str, body: bytes, signature_header: str | None) -> bool:
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    expected = f"sha256={digest}"
    return hmac.compare_digest(expected, signature_header)


def parse_merged_pull_request(event_name: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    """Return merge info if this is a closed+merged pull_request event."""
    if event_name != "pull_request":
        return None
    if payload.get("action") != "closed":
        return None
    pr = payload.get("pull_request") or {}
    if not pr.get("merged"):
        return None
    repo = (payload.get("repository") or {}).get("full_name")
    sha = pr.get("merge_commit_sha")
    if not repo or not sha:
        return None
    return {
        "repo": repo,
        "sha": sha,
        "title": pr.get("title") or "(no title)",
        "pr_url": pr.get("html_url") or "",
        "pr_number": pr.get("number"),
        "author": (pr.get("user") or {}).get("login"),
    }


def loads_body(raw: bytes) -> dict[str, Any]:
    return json.loads(raw.decode("utf-8"))
