#!/usr/bin/env python3
"""
Polls RSS feeds for emergency/incident news in Timiș, Hunedoara and
Caraș-Severin counties, filters by keyword, and sends new matches to
Telegram. Meant to run every 10 minutes via GitHub Actions; state
(which items were already sent) is kept in seen.json in the repo.
"""
import argparse
import hashlib
import html
import json
import os
import sys
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

import feedparser
import requests

import config

SEEN_FILE = Path(__file__).parent / "seen.json"
SEEN_RETENTION_DAYS = 30
REQUEST_TIMEOUT = 20
USER_AGENT = "Mozilla/5.0 (compatible; RomaniaIncidentMonitor/1.0)"


def strip_diacritics(text):
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(c for c in normalized if not unicodedata.combining(c))


def normalize(text):
    return strip_diacritics(text or "").lower()


def matches_filters(title, summary):
    haystack = normalize(f"{title} {summary}")
    if not any(kw in haystack for kw in config.COUNTY_KEYWORDS):
        return False
    if not any(kw in haystack for kw in config.INCLUDE_KEYWORDS):
        return False
    if any(kw in haystack for kw in config.EXCLUDE_KEYWORDS):
        return False
    return True


def item_id(entry):
    key = entry.get("id") or entry.get("link") or entry.get("title", "")
    return hashlib.sha1(key.encode("utf-8", "ignore")).hexdigest()


def load_seen():
    if not SEEN_FILE.exists():
        return {}
    try:
        return json.loads(SEEN_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_seen(seen):
    cutoff = datetime.now(timezone.utc) - timedelta(days=SEEN_RETENTION_DAYS)
    pruned = {
        k: v for k, v in seen.items()
        if datetime.fromisoformat(v) > cutoff
    }
    SEEN_FILE.write_text(json.dumps(pruned, indent=2, sort_keys=True), encoding="utf-8")


def fetch_feed(source):
    try:
        resp = requests.get(source["url"], headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as exc:
        print(f"[warn] failed to fetch {source['name']}: {exc}", file=sys.stderr)
        return []
    parsed = feedparser.parse(resp.content)
    return parsed.entries


def format_message(source_name, title, link):
    return (
        f"🚨 <b>{html.escape(title)}</b>\n"
        f"📍 {html.escape(source_name)}\n"
        f"{html.escape(link)}"
    )


def send_telegram(token, chat_id, text, dry_run):
    if dry_run:
        print(f"[dry-run] would send:\n{text}\n")
        return True
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        resp = requests.post(
            url,
            data={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": False,
            },
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code != 200:
            print(f"[warn] telegram send failed: {resp.status_code} {resp.text}", file=sys.stderr)
            return False
        return True
    except requests.RequestException as exc:
        print(f"[warn] telegram send failed: {exc}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Print matches instead of sending to Telegram")
    args = parser.parse_args()

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not args.dry_run and (not token or not chat_id):
        print("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set (or pass --dry-run)", file=sys.stderr)
        sys.exit(1)

    seen = load_seen()
    new_count = 0
    now_iso = datetime.now(timezone.utc).isoformat()

    for source in config.all_feeds():
        entries = fetch_feed(source)
        for entry in entries:
            uid = item_id(entry)
            if uid in seen:
                continue
            title = entry.get("title", "").strip()
            summary = entry.get("summary", "")
            link = entry.get("link", "")
            if not matches_filters(title, summary):
                continue

            text = format_message(source["name"], title, link)
            if send_telegram(token, chat_id, text, args.dry_run):
                seen[uid] = now_iso
                new_count += 1

    save_seen(seen)
    print(f"Done. {new_count} new item(s) sent.")


if __name__ == "__main__":
    main()
