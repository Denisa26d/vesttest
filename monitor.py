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
BOT_STATE_FILE = Path(__file__).parent / "bot_state.json"
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
# with the same letters (e.g. "devastator"). Kept per-county (not one flat
# list) so /all and /filtered bot commands can target a single county.
COUNTY_GROUP_PATTERNS = {
    county: word_patterns(keywords) for county, keywords in config.COUNTY_GROUPS.items()
}
EXCLUDE_PLACE_PATTERNS = word_patterns(config.EXCLUDE_PLACE_KEYWORDS)


def matched_counties(haystack):
    return [county for county, patterns in COUNTY_GROUP_PATTERNS.items()
            if any(p.search(haystack) for p in patterns)]


def content_matches_keywords(title, summary, categories=(), check_keyword=True, check_category=True):
    """Incident keyword/category matching only — no county check (that's
    handled separately in main() so per-county mode can apply). Which
    signal(s) count is controlled by check_keyword/check_category, set from
    the county's filter type ("keyword", "category", or "both")."""
    haystack = normalize(f"{title} {summary}")
    category_hit = check_category and any(
        hint in normalize(cat) for cat in categories for hint in config.CATEGORY_HINTS
    )
    keyword_hit = check_keyword and any(kw in haystack for kw in config.INCLUDE_KEYWORDS)
    if not category_hit and not keyword_hit:
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


DEFAULT_MODE = "all" if config.SEND_ALL_ITEMS else "both"


def default_county_modes():
    return {county: DEFAULT_MODE for county in config.COUNTY_GROUPS}


def load_bot_state():
    if not BOT_STATE_FILE.exists():
        return {"county_modes": default_county_modes(), "update_offset": 0}
    try:
        state = json.loads(BOT_STATE_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"county_modes": default_county_modes(), "update_offset": 0}
    state.setdefault("county_modes", default_county_modes())
    for county in config.COUNTY_GROUPS:
        state["county_modes"].setdefault(county, DEFAULT_MODE)
    state.setdefault("update_offset", 0)
    return state


def save_bot_state(state):
    BOT_STATE_FILE.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def county_display(county):
    return config.COUNTY_DISPLAY_NAMES.get(county, county)


def mode_display(mode):
    if mode == "all":
        return "tot (nefiltrat)"
    return f"filtrat ({config.FILTER_TYPE_DISPLAY_NAMES.get(mode, mode)})"


def format_status(county_modes):
    lines = [
        f"• {county_display(county)}: {mode_display(mode)}"
        for county, mode in sorted(county_modes.items())
    ]
    return "📊 Mod curent per județ:\n" + "\n".join(lines)


HELP_TEXT = (
    "🤖 Comenzi disponibile:\n\n"
    "/all [județ] — trimite toate știrile pentru județul respectiv, fără filtrare\n"
    "/filtered [județ] [tip] — trimite doar incidentele (accidente, incendii, explozii, "
    "inundații, crimă, droguri, poliția de frontieră etc.) pentru județul respectiv\n"
    "/status — arată modul curent pentru fiecare județ\n"
    "/help — acest mesaj\n\n"
    "Dacă nu specifici un județ, comanda se aplică la toate patru odată.\n\n"
    f"Județe: {', '.join(county_display(c) for c in sorted(config.COUNTY_GROUPS))}\n"
    "Poți scrie și: timisoara, deva, resita, cs, hd, ar (nu contează diacriticele).\n\n"
    "Tip de filtrare (opțional, după /filtered):\n"
    "cuvinte — doar articole care conțin un cuvânt cheie de incident (accident, "
    "incendiu, crimă etc.)\n"
    "categorie — doar articole pe care site-ul însuși le-a marcat cu categoria "
    "\"Eveniment\" (nu toate site-urile o folosesc)\n"
    "amandoua — oricare din cele două (implicit, dacă nu specifici tipul)\n\n"
    "Exemple:\n"
    "/all timis — Timiș primește tot\n"
    "/filtered hunedoara — Hunedoara primește incidente (cuvinte cheie sau categorie)\n"
    "/filtered arad cuvinte — Arad filtrat doar după cuvinte cheie\n"
    "/filtered caras-severin categorie — Caraș-Severin filtrat doar după categoria \"Eveniment\"\n\n"
    "Modificările se aplică începând cu următoarea rulare a botului "
    "(la câteva minute, nu instant)."
)


# Telegram commands you can send in the chat to switch modes without editing
# config.py: /all [county] sends everything for that county (or all four if
# no county given), /filtered [county] applies keyword/category filtering,
# /status reports the current per-county mode.
def poll_commands(token, chat_id, state):
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    try:
        resp = requests.get(
            url,
            params={"offset": state["update_offset"], "timeout": 0},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        updates = resp.json().get("result", [])
    except requests.RequestException as exc:
        print(f"[warn] failed to poll telegram commands: {exc}", file=sys.stderr)
        return state

    for update in updates:
        state["update_offset"] = update["update_id"] + 1
        message = update.get("message", {})
        if str(message.get("chat", {}).get("id")) != str(chat_id):
            continue  # ignore commands from anyone but the configured chat
        text = message.get("text", "").strip()
        parts = text.split()
        command = parts[0].lower() if parts else ""
        reply = None

        if command == "/all":
            arg = normalize(parts[1]) if len(parts) > 1 else ""
            if not arg:
                state["county_modes"] = {c: "all" for c in config.COUNTY_GROUPS}
                reply = "✅ Toate județele setate pe: tot (nefiltrat)."
            else:
                county = config.COUNTY_ALIASES.get(arg)
                if county:
                    state["county_modes"][county] = "all"
                    reply = f"✅ {county_display(county)}: setat pe tot (nefiltrat)."
                else:
                    reply = f"⚠️ Județ necunoscut: '{parts[1]}'.\n\n" + HELP_TEXT
        elif command == "/filtered":
            county = None
            filter_type = "both"
            unrecognized = []
            for tok in parts[1:]:
                norm_tok = normalize(tok)
                if norm_tok in config.FILTER_TYPE_ALIASES:
                    filter_type = config.FILTER_TYPE_ALIASES[norm_tok]
                elif norm_tok in config.COUNTY_ALIASES:
                    county = config.COUNTY_ALIASES[norm_tok]
                else:
                    unrecognized.append(tok)
            if unrecognized:
                reply = f"⚠️ Nu am recunoscut: '{' '.join(unrecognized)}'.\n\n" + HELP_TEXT
            elif county:
                state["county_modes"][county] = filter_type
                reply = f"✅ {county_display(county)}: setat pe {mode_display(filter_type)}."
            else:
                state["county_modes"] = {c: filter_type for c in config.COUNTY_GROUPS}
                reply = f"✅ Toate județele setate pe: {mode_display(filter_type)}."
        elif command == "/status":
            reply = format_status(state["county_modes"])
        elif command in ("/help", "/start"):
            reply = HELP_TEXT
        elif command.startswith("/"):
            reply = f"❓ Comandă necunoscută: '{command}'. Scrie /help pentru comenzile disponibile."

        if reply:
            send_telegram(token, chat_id, reply, dry_run=False)

    return state


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


def format_message(source_name, title, link, send_all):
    icon = "📰" if send_all else "🚨"
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
    bot_state = load_bot_state()
    if not args.dry_run:
        bot_state = poll_commands(token, chat_id, bot_state)
    county_modes = bot_state["county_modes"]

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

            counties = matched_counties(normalize(f"{title} {summary}"))
            if not counties:
                continue
            modes = [county_modes.get(c, DEFAULT_MODE) for c in counties]
            # If the item touches multiple counties, the most permissive
            # setting among them wins: "all" bypasses filtering outright;
            # otherwise a signal counts if any matched county wants it.
            send_all = "all" in modes
            check_keyword = any(m in ("keyword", "both") for m in modes)
            check_category = any(m in ("category", "both") for m in modes)

            categories = [t.get("term", "") for t in entry.get("tags", [])]
            if not send_all and not content_matches_keywords(
                title, summary, categories, check_keyword=check_keyword, check_category=check_category
            ):
                continue

            text = format_message(source["name"], title, link, send_all)
            if send_telegram(token, chat_id, text, args.dry_run):
                seen[uid] = now_iso
                new_count += 1
                if not args.dry_run:
                    time.sleep(0.4)  # stay under Telegram's per-chat rate limit

    save_seen(seen)
    save_bot_state(bot_state)
    print(f"Done. {new_count} new item(s) sent.")


if __name__ == "__main__":
    main()
