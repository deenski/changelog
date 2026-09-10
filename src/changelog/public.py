from __future__ import annotations

import html
from typing import Any


APP_INSTALL_URL = "https://github.com/apps/deenski-changelog"


def _esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def render_landing(*, changelog_path: str = "/changelog") -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Changelog — free install</title>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 40rem; margin: 2rem auto; padding: 0 1rem; line-height: 1.5; color: #111; }}
    a {{ color: #0969da; }}
    ol {{ padding-left: 1.25rem; }}
    code {{ background: #f6f8fa; padding: 0.1rem 0.35rem; border-radius: 4px; }}
  </style>
</head>
<body>
  <h1>Changelog (free)</h1>
  <p>Merged PRs become short notes in Slack. Free tier is ≤5 allowlisted repos. No paywall.</p>
  <ol>
    <li>Install the GitHub App: <a href="{_esc(APP_INSTALL_URL)}">deenski-changelog</a> on up to 5 repos.</li>
    <li><strong>v0:</strong> App install alone is not enough — ops must add each repo to the DynamoDB allowlist (<code>muted=false</code>). Cap enforced via <code>try_add_repo</code>.</li>
    <li>Invite the Slack bot to <code>#shipped</code> (or your channel).</li>
    <li>Merge a PR — a note lands in Slack and on the <a href="{_esc(changelog_path)}">public changelog</a>.</li>
  </ol>
  <p>Full walkthrough (incl. ops allowlist): see <code>docs/install.md</code> in the repo.</p>
</body>
</html>
"""


def render_repo_index(repos: list[str]) -> str:
    if not repos:
        items = "<li><em>No allowlisted repos yet.</em></li>"
    else:
        items = "\n".join(
            f'<li><a href="/changelog/{_esc(r)}">{_esc(r)}</a></li>' for r in repos
        )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Public changelogs</title>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 40rem; margin: 2rem auto; padding: 0 1rem; line-height: 1.5; }}
    a {{ color: #0969da; }}
  </style>
</head>
<body>
  <p><a href="/">← Install</a></p>
  <h1>Public changelogs</h1>
  <p>Allowlisted free repos (muted repos are hidden).</p>
  <ul>
    {items}
  </ul>
</body>
</html>
"""


def render_repo_changelog(full_name: str, notes: list[dict[str, Any]]) -> str:
    rows: list[str] = []
    for n in notes:
        sha = _esc((n.get("sha") or "")[:7])
        title = _esc(n.get("title"))
        author = _esc(n.get("author") or "")
        merged = _esc(n.get("merged_at") or "")
        pr_url = _esc(n.get("pr_url") or "#")
        rows.append(
            f'<li><code>{sha}</code> '
            f'<a href="{pr_url}">{title}</a>'
            f'{" · @" + author if author else ""}'
            f'{" · " + merged if merged else ""}'
            f"</li>"
        )
    body = "\n".join(rows) if rows else "<li><em>No notes yet.</em></li>"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{_esc(full_name)} changelog</title>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 48rem; margin: 2rem auto; padding: 0 1rem; line-height: 1.5; }}
    a {{ color: #0969da; }}
    code {{ background: #f6f8fa; padding: 0.1rem 0.35rem; border-radius: 4px; }}
    li {{ margin: 0.4rem 0; }}
  </style>
</head>
<body>
  <p><a href="/changelog">← All repos</a></p>
  <h1>{_esc(full_name)}</h1>
  <ul>
    {body}
  </ul>
</body>
</html>
"""
