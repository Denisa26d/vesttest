#!/usr/bin/env python3
"""
Polls RSS feeds for emergency/incident news in Timiș, Hunedoara and
Caraș-Severin counties, filters by keyword, and sends new matches to
Telegram. Meant to run every 10 minutes via GitHub Actions; state
(which items were already sent) is kept in seen.json in the repo.
"""
import argparse
import calendar
import hashlib
import html
import json
import os
import re
import sys
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

import feedparser
import requests

import config

SEEN_FILE = Path(__file__).parent / "seen.json"
SEEN_RETENTION_DAYS = 30
REQUEST_TIMEOUT = 20
FETCH_RETRIES = 2
FETCH_RETRY_DELAY_SECONDS = 5
REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.8",
    "Accept-Language": "ro-RO,ro;q=0.9,en;q=0.8",
}


def strip_diacritics(text):
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(c for c in normalized if not unicodedata.combining(c))


def normalize(text):
    return strip_diacritics(text or "").lower()


def word_patterns(keywords):
    return [re.compile(r"\b" + re.escape(strip_diacritics(kw).lower()) + r"\b") for kw in keywords]


# County/city names are matched as whole words (not substrings) so short
# names like "Deva" don't collide with unrelated words that merely start
# with the same letters (e.g. "devastator").
COUNTY_PATTERNS = word_patterns(config.COUNTY_KEYWORDS)
EXCLUDE_PLACE_PATTERNS = word_patterns(config.EXCLUDE_PLACE_KEYWORDS)


def matches_filters(title, summary):
    haystack = normalize(f"{title} {summary}")
    if not any(p.search(haystack) for p in COUNTY_PATTERNS):
        return False
    if not any(kw in haystack for kw in config.INCLUDE_KEYWORDS):
        return False
    if any(kw in haystack for kw in config.EXCLUDE_KEYWORDS):
        return False
    if any(p.search(haystack) for p in EXCLUDE_PLACE_PATTERNS):
        return False
    return True


def is_fresh(entry):
    struct = entry.get("published_parsed") or entry.get("updated_parsed")
    if not struct:
        return True  # no date available, don't drop it on that basis
    published = datetime.fromtimestamp(calendar.timegm(struct), tz=timezone.utc)
    age = datetime.now(timezone.utc) - published
    return age <= timedelta(hours=config.MAX_ITEM_AGE_HOURS)


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
    last_exc = None
    for attempt in range(1, FETCH_RETRIES + 1):
        try:
            resp = requests.get(source["url"], headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            return feedparser.parse(resp.content).entries
        except requests.RequestException as exc:
            last_exc = exc
            if attempt < FETCH_RETRIES:
                time.sleep(FETCH_RETRY_DELAY_SECONDS)
    print(f"[warn] failed to fetch {source['name']}: {last_exc}", file=sys.stderr)
    return []


def format_message(source_name, title, link):
    icon = "📰" if config.SEND_ALL_ITEMS else "🚨"
    return (
        f"{icon} <b>{html.escape(title)}</b>\n"
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
            if not is_fresh(entry):
                continue
            title = entry.get("title", "").strip()
            summary = entry.get("summary", "")
            link = entry.get("link", "")
            if not config.SEND_ALL_ITEMS and not matches_filters(title, summary):
                continue

            text = format_message(source["name"], title, link)
            if send_telegram(token, chat_id, text, args.dry_run):
                seen[uid] = now_iso
                new_count += 1
                if not args.dry_run:
                    time.sleep(0.4)  # stay under Telegram's per-chat rate limit

    save_seen(seen)
    print(f"Done. {new_count} new item(s) sent.")


if __name__ == "__main__":
    main()
