#!/usr/bin/env python3
"""
GitHub Actions完了後にNotion DB_CCを自動更新するスクリプト。
Issue番号からDB_CCの該当行を見つけ、ステータス・PRリンク・結果サマリーを更新する。

Usage:
    python scripts/update_notion.py --issue-number 11 --status 完了 --summary "スライド生成完了" --pr-link "https://..."
"""

import argparse
import json
import os
import sys
import urllib.request

NOTION_API_KEY = os.environ.get("NOTION_API_KEY", "")
DB_CC_ID = "33e71450-0266-80d4-a844-000b023fbd60"
NOTION_API = "https://api.notion.com/v1"


def notion_request(method, path, body=None):
    url = f"{NOTION_API}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {NOTION_API_KEY}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"Notion API error: {e.code} {e.read().decode()}", file=sys.stderr)
        return None


def find_page_by_issue_number(issue_number):
    """DB_CCからIssue番号で該当ページを検索"""
    result = notion_request("POST", f"/databases/{DB_CC_ID}/query", {
        "filter": {
            "property": "Issue番号",
            "number": {"equals": issue_number}
        }
    })
    if not result or not result.get("results"):
        return None
    return result["results"][0]["id"]


def update_page(page_id, status=None, pr_link=None, summary=None):
    """DB_CCのページを更新"""
    properties = {}

    if status:
        properties["ステータス"] = {"select": {"name": status}}

    if pr_link:
        properties["PRリンク"] = {"url": pr_link}

    if summary:
        properties["結果サマリー"] = {
            "rich_text": [{"text": {"content": summary[:2000]}}]
        }

    if not properties:
        print("Nothing to update")
        return

    result = notion_request("PATCH", f"/pages/{page_id}", {
        "properties": properties
    })

    if result:
        print(f"Updated page {page_id}: status={status}, pr_link={'set' if pr_link else 'skip'}, summary={'set' if summary else 'skip'}")
    else:
        print("Failed to update page", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Update Notion DB_CC after Claude Code completion")
    parser.add_argument("--issue-number", type=int, required=True)
    parser.add_argument("--status", default="完了")
    parser.add_argument("--pr-link", default="")
    parser.add_argument("--summary", default="")
    args = parser.parse_args()

    if not NOTION_API_KEY:
        print("NOTION_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    page_id = find_page_by_issue_number(args.issue_number)
    if not page_id:
        print(f"No page found with Issue番号={args.issue_number}", file=sys.stderr)
        sys.exit(0)  # not an error, just no matching page

    update_page(
        page_id,
        status=args.status,
        pr_link=args.pr_link or None,
        summary=args.summary or None,
    )


if __name__ == "__main__":
    main()
