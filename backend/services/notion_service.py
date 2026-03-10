"""
notion_agent.py
----------------
Handles all Notion API interactions:
  - Creates a "DocForge Documents" database inside your Notion page on first run
  - Pushes generated Word/Excel documents as formatted Notion pages
  - Updates existing pages when sections are refined
  - Returns the Notion page URL for display in Streamlit
"""

import os
import json
import time
import requests
import logging
from dotenv import load_dotenv
from backend.services.redis_service import redis_svc, ThrottleExceeded

log = logging.getLogger(__name__)

load_dotenv()

NOTION_TOKEN   = os.getenv("NOTION_TOKEN")
NOTION_PAGE_ID = os.getenv("NOTION_PAGE_ID")
NOTION_VERSION = "2022-06-28"

NOTION_HEADERS = {
    "Authorization":  f"Bearer {NOTION_TOKEN}",
    "Notion-Version": NOTION_VERSION,
    "Content-Type":   "application/json",
}

BASE_URL = "https://api.notion.com/v1"


def _notion_request(method: str, url: str, **kwargs) -> dict:
    """
    Central HTTP helper for all Notion API calls.
    Throttle + backoff handled by redis_svc.notion_request().
    """
    def _do_request():
        resp = getattr(requests, method)(url, headers=NOTION_HEADERS, **kwargs)

        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", 1))
            log.warning(f"Notion 429 — will retry after {retry_after}s")
            time.sleep(retry_after)
            raise requests.HTTPError("429 Rate Limited", response=resp)

        if resp.status_code >= 500:
            raise requests.HTTPError(f"Notion {resp.status_code}", response=resp)

        resp.raise_for_status()
        return resp.json() if resp.content else {}

    return redis_svc.notion_request(_do_request)


# ─────────────────────────────────────────────────────────────────────────────
# Database setup
# ─────────────────────────────────────────────────────────────────────────────

def _get_or_create_database() -> str:
    """
    Look for a database named 'DocForge Documents' inside the parent page.
    Creates it if it doesn't exist. Returns the database ID.
    """
    # Search for existing database
    res = _notion_request("post", f"{BASE_URL}/search", json={
            "query": "DocForge Documents",
            "filter": {"property": "object", "value": "database"}
        }
    )
    results = res.get("results", [])
    for r in results:
        if r.get("title", [{}])[0].get("plain_text") == "DocForge Documents":
            return r["id"]

    # Create database inside the parent page
    payload = {
        "parent": {"type": "page_id", "page_id": NOTION_PAGE_ID},
        "title": [{"type": "text", "text": {"content": "DocForge Documents"}}],
        "properties": {
            "Title":    {"title": {}},
            "Format": {
                "select": {
                    "options": [
                        {"name": "Word",  "color": "blue"},
                        {"name": "Excel", "color": "yellow"},
                    ]
                }
            },
            "Doc Type":   {"rich_text": {}},
            "Version":    {"number": {}},
            "Created At": {"date": {}},
        }
    }
    res = _notion_request("post", f"{BASE_URL}/databases", json=payload)
    return res["id"]


# ─────────────────────────────────────────────────────────────────────────────
# Block builders
# ─────────────────────────────────────────────────────────────────────────────

def _text(content: str, bold: bool = False, color: str = "default") -> dict:
    return {
        "type": "text",
        "text": {"content": str(content)[:2000]},
        "annotations": {"bold": bold, "color": color}
    }


def _heading2(text: str) -> dict:
    return {
        "object": "block",
        "type": "heading_2",
        "heading_2": {
            "rich_text": [_text(text, bold=True, color="yellow")],
            "color": "default"
        }
    }


def _heading3(text: str) -> dict:
    return {
        "object": "block",
        "type": "heading_3",
        "heading_3": {"rich_text": [_text(text, bold=True)]}
    }


def _paragraph(text: str) -> dict:
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {"rich_text": [_text(text)]}
    }


def _bullet(text: str) -> dict:
    return {
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {"rich_text": [_text(text)]}
    }


def _divider() -> dict:
    return {"object": "block", "type": "divider", "divider": {}}


def _callout(text: str, emoji: str = "📊") -> dict:
    return {
        "object": "block",
        "type": "callout",
        "callout": {
            "rich_text": [_text(text)],
            "icon": {"type": "emoji", "emoji": emoji},
            "color": "blue_background"
        }
    }


def _table_row(cells: list) -> dict:
    return {
        "type": "table_row",
        "table_row": {
            "cells": [[_text(str(c)[:2000])] for c in cells]
        }
    }


def _table(headers: list, rows: list) -> dict:
    """Build a Notion table block with headers + data rows."""
    all_rows = [_table_row(headers)] + [_table_row(r) for r in rows[:50]]
    return {
        "object": "block",
        "type": "table",
        "table": {
            "table_width": len(headers),
            "has_column_header": True,
            "has_row_header": False,
            "children": all_rows
        }
    }


# ─────────────────────────────────────────────────────────────────────────────
# Content → Notion blocks
# ─────────────────────────────────────────────────────────────────────────────

def _word_doc_to_blocks(sections: dict) -> list:
    """Convert Word document sections dict to Notion block list."""
    blocks = []
    for section_name, content in sections.items():
        blocks.append(_heading2(section_name.replace("_", " ").title()))

        if isinstance(content, str):
            for line in [l.strip() for l in content.split("\n") if l.strip()]:
                if line.startswith(("-", "*", "•", "▸")):
                    blocks.append(_bullet(line.lstrip("-*•▸ ")))
                else:
                    blocks.append(_paragraph(line))

        elif isinstance(content, list):
            for item in content:
                blocks.append(_bullet(str(item).strip().lstrip("-*•▸ ")))

        elif isinstance(content, dict):
            for k, v in content.items():
                blocks.append(_heading3(str(k).replace("_", " ").title()))
                blocks.append(_paragraph(str(v)))

        blocks.append(_divider())

    return blocks


def _excel_doc_to_blocks(excel_data: dict) -> list:
    """Convert Excel structured data to Notion blocks (tables per sheet)."""
    blocks = []
    sheets = excel_data.get("sheets", [])

    for sheet in sheets:
        sheet_name  = sheet.get("sheet_name", "Sheet")
        description = sheet.get("description", "")
        headers     = sheet.get("headers", [])
        rows        = sheet.get("rows", [])
        notes       = sheet.get("notes", "")

        blocks.append(_heading2(sheet_name))

        if description:
            blocks.append(_callout(description, "📋"))

        if headers and rows:
            # Pad rows to header width
            padded = [r + [""] * max(0, len(headers) - len(r)) for r in rows]
            blocks.append(_table(headers, padded))

        if notes:
            blocks.append(_callout(f"Notes: {notes}", "📝"))

        blocks.append(_divider())

    return blocks


# ─────────────────────────────────────────────────────────────────────────────
# Push document to Notion
# ─────────────────────────────────────────────────────────────────────────────

def push_to_notion(title: str, doc_format: str, content: dict,
                   db_id: int = None, version: int = 1) -> dict:
    """
    Create a new Notion page inside the DocForge Documents database.

    Returns:
      { "page_id": "...", "url": "https://notion.so/..." }
    """
    database_id = _get_or_create_database()

    # Build content blocks
    if doc_format == "excel":
        blocks = _excel_doc_to_blocks(content)
    else:
        blocks = _word_doc_to_blocks(content)

    # Notion API limits: 100 blocks per request
    # We create the page first then append blocks in batches
    from datetime import datetime, timezone, timedelta
    IST = timezone(timedelta(hours=5, minutes=30))
    now_ist = datetime.now(IST).isoformat()

    page_payload = {
        "parent": {"database_id": database_id},
        "icon":   {"type": "emoji", "emoji": "📊" if doc_format == "excel" else "📄"},
        "properties": {
            "Title":    {"title": [{"text": {"content": title}}]},
            "Format":   {"select": {"name": "Excel" if doc_format == "excel" else "Word"}},
            "Doc Type": {"rich_text": [{"text": {"content": title}}]},
            "Version":    {"number": version},
            "Created At": {"date": {"start": now_ist}},
        },
        # Add first batch of blocks (max 100)
        "children": blocks[:100]
    }

    page = _notion_request("post", f"{BASE_URL}/pages", json=page_payload)
    page_id = page["id"]

    # Append remaining blocks in batches of 100
    remaining = blocks[100:]
    for i in range(0, len(remaining), 100):
        batch = remaining[i:i+100]
        _notion_request("patch", f"{BASE_URL}/blocks/{page_id}/children", json={"children": batch})

    return {
        "page_id": page_id,
        "url":     page.get("url", f"https://notion.so/{page_id.replace('-', '')}")
    }


def update_notion_page(page_id: str, title: str, doc_format: str,
                       content: dict) -> dict:
    """
    Replace all content blocks in an existing Notion page.
    If the page no longer exists (404), creates a fresh page instead.
    """
    try:
        # Check page still exists before trying to update
        check = requests.get(
            f"{BASE_URL}/blocks/{page_id}/children",
            headers=NOTION_HEADERS,
        )
        if check.status_code == 404:
            # Page was deleted in Notion — create a fresh one
            return push_to_notion(title=title, doc_format=doc_format, content=content)

        existing = check.json().get("results", [])

        # Archive (delete) all existing blocks
        for block in existing:
            _notion_request("delete", f"{BASE_URL}/blocks/{block['id']}")

        # Build new blocks
        if doc_format == "excel":
            blocks = _excel_doc_to_blocks(content)
        else:
            blocks = _word_doc_to_blocks(content)

        # Append in batches
        for i in range(0, len(blocks), 100):
            batch = blocks[i:i+100]
            _notion_request("patch", f"{BASE_URL}/blocks/{page_id}/children", json={"children": batch})

        return {"page_id": page_id, "url": f"https://notion.so/{page_id.replace('-', '')}"}

    except Exception as e:
        # If anything goes wrong, attempt a fresh push
        if "404" in str(e):
            return push_to_notion(title=title, doc_format=doc_format, content=content)
        raise