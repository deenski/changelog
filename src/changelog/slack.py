from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any


def post_shipped(
    token: str,
    channel: str,
    *,
    repo: str,
    sha: str,
    title: str,
    pr_url: str,
    author: str | None = None,
) -> None:
    text = f"*shipped* `{repo}` — {title}\n`{sha[:7]}`"
    if author:
        text += f" by {author}"
    text += f"\n{pr_url}"
    body = json.dumps({"channel": channel, "text": text}).encode("utf-8")
    req = urllib.request.Request(
        "https://slack.com/api/chat.postMessage",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            payload: dict[str, Any] = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Slack HTTP {exc.code}") from exc
    if not payload.get("ok"):
        raise RuntimeError(f"Slack error: {payload.get('error')}")
