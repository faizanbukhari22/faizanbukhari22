#!/usr/bin/env python3
"""Refreshes the TRENDING and NEWS blocks in README.md from the GitHub Search API."""

import datetime
import json
import os
import re
import urllib.parse
import urllib.request

README_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "README.md")
API_ROOT = "https://api.github.com/search/repositories"
TOKEN = os.environ.get("GITHUB_TOKEN", "")

AI_TOPICS = [
    "mcp",
    "model-context-protocol",
    "llm-agent",
    "ai-agents",
    "agentic-ai",
    "claude-code",
    "claude-skills",
    "llm-tools",
]


def api_get(query, per_page):
    url = f"{API_ROOT}?q={urllib.parse.quote(query)}&sort=stars&order=desc&per_page={per_page}"
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def fetch_by_topics(topics, created_after, per_topic, top_n):
    # GitHub's repository search only supports implicit AND between qualifiers
    # (no boolean OR), so each topic is queried separately and merged here.
    seen = {}
    for topic in topics:
        items = api_get(f"topic:{topic} created:>{created_after.isoformat()}", per_topic)["items"]
        for repo in items:
            seen[repo["id"]] = repo
    ranked = sorted(seen.values(), key=lambda r: r["stargazers_count"], reverse=True)
    return ranked[:top_n]


def clip(text, n):
    if not text:
        return ""
    text = text.replace("|", "-").strip()
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def render_trending(items):
    lines = [
        "| # | Repository | Stars | Language | Description |",
        "|---|---|---|---|---|",
    ]
    for i, repo in enumerate(items, start=1):
        lines.append(
            f"| {i} | [{repo['full_name']}]({repo['html_url']}) | "
            f"{repo['stargazers_count']:,} | {repo.get('language') or '-'} | "
            f"{clip(repo.get('description'), 80)} |"
        )
    return "\n".join(lines)


def render_news(items):
    lines = []
    for repo in items:
        lines.append(
            f"- **[{repo['full_name']}]({repo['html_url']})** "
            f"({repo['stargazers_count']:,}★) — {clip(repo.get('description'), 100)}"
        )
    return "\n".join(lines) if lines else "- No standout new AI tooling repos this cycle."


def replace_block(content, marker, new_body):
    pattern = re.compile(
        rf"(<!-- {marker}:START -->\n)(.*?)(\n<!-- {marker}:END -->)", re.DOTALL
    )
    if not pattern.search(content):
        raise SystemExit(f"Marker block {marker} not found in README.md")
    return pattern.sub(lambda m: m.group(1) + new_body + m.group(3), content)


def main():
    today = datetime.date.today()
    week_ago = today - datetime.timedelta(days=7)
    month_ago = today - datetime.timedelta(days=30)

    trending = api_get(f"created:>{week_ago.isoformat()}", 10)["items"]
    news = fetch_by_topics(AI_TOPICS, month_ago, per_topic=5, top_n=8)

    with open(README_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    content = replace_block(content, "TRENDING", render_trending(trending))
    content = replace_block(content, "NEWS", render_news(news))
    content = re.sub(
        r"(<!-- UPDATED:START -->\n)(.*?)(\n<!-- UPDATED:END -->)",
        lambda m: m.group(1)
        + f"_Last refreshed {today.isoformat()} (UTC) · automated weekly_"
        + m.group(3),
        content,
        flags=re.DOTALL,
    )

    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(content)


if __name__ == "__main__":
    main()
