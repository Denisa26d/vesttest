#!/usr/bin/env python3
"""
Polls RSS feeds for news in Timiș, Hunedoara, Arad and Caraș-Severin (plus
everything from a few national outlets), optionally filters by incident
keyword, and sends new items to Telegram. Meant to run every 10 minutes via
GitHub Actions. State — already-sent items (seen.json), bot settings, feed
health and recently sent stories (bot_state.json) — is kept by the workflow
on the repo's `state` branch between runs.
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
# An item can never be "eligible to resend" more than MAX_ITEM_AGE_HOURS
# after publish (is_fresh() rejects it regardless of seen state), so
# there's no benefit to keeping seen entries much longer than that. The
# +24h buffer just guards against feed date weirdness or a gap in cron
# runs, without letting the file grow unbounded like a flat 30-day window
# would.
SEEN_RETENTION_HOURS = config.MAX_ITEM_AGE_HOURS + 24
BOT_STATE_FILE = Path(__file__).parent / "bot_state.json"
REQUEST_TIMEOUT = 20
FETCH_RETRIES = 2
FETCH_RETRY_DELAY_SECONDS = 5
# Telegram allows ~1 message/second per chat (20/minute in groups). On a
# 429 it says how long to wait; we wait (capped) and retry.
TELEGRAM_SEND_INTERVAL_SECONDS = 1.0
TELEGRAM_RETRIES = 3
TELEGRAM_MAX_RETRY_WAIT_SECONDS = 60
REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.8",
    "Accept-Language": "ro-RO,ro;q=0.9,en;q=0.8",
}

# Groups that each have their own /all or /filtered mode: the four
# counties plus the "national" pseudo-county.
MODE_GROUPS = list(config.COUNTY_GROUPS) + [config.NATIONAL_GROUP]


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
AMBIGUOUS_PLACE_PATTERNS = {
    county: word_patterns(keywords) for county, keywords in config.AMBIGUOUS_PLACE_KEYWORDS.items()
}
EXCLUDE_PLACE_PATTERNS = word_patterns(config.EXCLUDE_PLACE_KEYWORDS)


def matched_counties(haystack, home_counties=()):
    """Counties whose places are named in the text. Ambiguous names (e.g.
    "brad") only count for a county when the outlet is local to it."""
    found = []
    for county, patterns in COUNTY_GROUP_PATTERNS.items():
        if any(p.search(haystack) for p in patterns):
            found.append(county)
        elif county in home_counties and any(
            p.search(haystack) for p in AMBIGUOUS_PLACE_PATTERNS.get(county, [])
        ):
            found.append(county)
    return found


def mentions_excluded_place(haystack):
    return any(p.search(haystack) for p in EXCLUDE_PLACE_PATTERNS)


def item_groups(haystack, source):
    """Which mode groups (counties, or "national") an item belongs to;
    empty means it's out of scope and shouldn't be sent."""
    home = source.get("counties", [])
    counties = matched_counties(haystack, home)
    if counties:
        return counties
    if home and config.LOCAL_OUTLET_ASSUMES_COUNTY:
        return list(home)
    if source.get("national"):
        return [config.NATIONAL_GROUP]
    return []


def content_matches_keywords(title, summary, categories=(), check_keyword=True, check_category=True,
                             check_places=True):
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
    if check_places and mentions_excluded_place(haystack):
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


# --- Cross-outlet de-duplication -------------------------------------------

# Common words (diacritics stripped, 4+ letters) that say nothing about
# which story a headline is about.
STORY_STOPWORDS = {
    "dupa", "care", "pentru", "este", "sunt", "fost", "fiind", "doua", "intr", "intre",
    "acest", "aceasta", "acesta", "aceste", "catre", "despre", "unde", "cand", "acum",
    "foarte", "mult", "multe", "multi", "inca", "toate", "toti", "peste", "langa", "dintre",
    "fara", "doar", "noua", "anul", "anului", "astazi", "ieri", "maine", "video", "foto",
    "update", "live", "breaking", "exclusiv", "oficial", "urma", "unei", "unui", "spre",
    "decat", "cele", "celor", "avut", "avea", "face", "facut", "vrea", "poate", "trebuie",
    "aici", "acolo", "cine", "ceea", "ceva", "nimic", "orice", "fiecare", "mare", "mari",
}


def story_tokens(title):
    """Significant words of a headline, cut to their first 5 letters so
    Romanian inflections match (masina/masini, accident/accidentul)."""
    words = re.findall(r"[a-z0-9]+", normalize(title))
    return sorted({w[:5] for w in words if len(w) >= 4 and w not in STORY_STOPWORDS})


def same_story(tokens_a, tokens_b):
    shared = len(set(tokens_a) & set(tokens_b))
    shorter = min(len(tokens_a), len(tokens_b)) or 1
    return shared >= config.DEDUP_MIN_SHARED_WORDS and shared / shorter >= config.DEDUP_MIN_OVERLAP


def find_story(stories, tokens, groups):
    """An earlier story with a near-identical headline about the same
    county (or both national) — so e.g. Timiș and Caraș-Severin power-cut
    notices with the same wording stay separate messages."""
    for story in stories:
        if set(story.get("groups", [])) & set(groups) and same_story(story["tokens"], tokens):
            return story
    return None


def prune_stories(stories):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=config.DEDUP_WINDOW_HOURS)
    return [s for s in stories if datetime.fromisoformat(s["sent_at"]) > cutoff]


# --- State -------------------------------------------------------------------

def load_seen():
    if not SEEN_FILE.exists():
        return {}
    try:
        return json.loads(SEEN_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_seen(seen):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=SEEN_RETENTION_HOURS)
    pruned = {
        k: v for k, v in seen.items()
        if datetime.fromisoformat(v) > cutoff
    }
    SEEN_FILE.write_text(json.dumps(pruned, indent=2, sort_keys=True), encoding="utf-8")


DEFAULT_MODE = "all" if config.SEND_ALL_ITEMS else "both"


def default_county_modes():
    return {group: DEFAULT_MODE for group in MODE_GROUPS}


def load_bot_state():
    state = {}
    if BOT_STATE_FILE.exists():
        try:
            state = json.loads(BOT_STATE_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            state = {}
    state.setdefault("county_modes", default_county_modes())
    for group in MODE_GROUPS:
        state["county_modes"].setdefault(group, DEFAULT_MODE)
    state.setdefault("update_offset", 0)
    state.setdefault("feed_health", {})
    state.setdefault("recent_stories", [])
    if "baselined_feeds" not in state:
        # First run with this version: feeds that already ran under the old
        # version have real seen entries, so they don't need a baseline.
        # National feeds switched to "send everything" and would otherwise
        # dump their last few hours into the chat.
        state["baselined_feeds"] = [f["name"] for f in config.all_feeds() if not f.get("national")]
    return state


def save_bot_state(state):
    BOT_STATE_FILE.write_text(json.dumps(state, indent=2, sort_keys=True, ensure_ascii=False),
                              encoding="utf-8")


def county_display(county):
    return config.COUNTY_DISPLAY_NAMES.get(county, county)


def mode_display(mode):
    if mode == "all":
        return "tot (nefiltrat)"
    return f"filtrat ({config.FILTER_TYPE_DISPLAY_NAMES.get(mode, mode)})"


def failing_feeds(state):
    return sorted(name for name, h in state["feed_health"].items()
                  if h.get("fails", 0) >= config.FEED_FAIL_ALERT_RUNS)


def format_status(state):
    lines = [
        f"• {county_display(group)}: {mode_display(state['county_modes'].get(group, DEFAULT_MODE))}"
        for group in MODE_GROUPS
    ]
    text = "📊 Mod curent per județ:\n" + "\n".join(lines)
    down = failing_feeds(state)
    if down:
        text += "\n\n⚠️ Surse care nu funcționează acum:\n" + "\n".join(f"• {n}" for n in down)
    else:
        text += "\n\n✅ Toate sursele funcționează."
    return text


HELP_TEXT = (
    "🤖 Comenzi disponibile:\n\n"
    "/all [județ] — trimite toate știrile pentru județul respectiv, fără filtrare\n"
    "/filtered [județ] [tip] — trimite doar incidentele (accidente, incendii, explozii, "
    "inundații, crimă, droguri, poliția de frontieră etc.) pentru județul respectiv\n"
    "/status — arată modul curent pentru fiecare județ și sursele căzute\n"
    "/help — acest mesaj\n\n"
    "Dacă nu specifici un județ, comanda se aplică la toate odată.\n\n"
    f"Județe: {', '.join(county_display(c) for c in MODE_GROUPS)}\n"
    "„Național” = știrile de la Antena3, Digi24, G4Media, HotNews, Adevărul care nu "
    "privesc unul din cele patru județe.\n"
    "Poți scrie și: timisoara, deva, resita, cs, hd, ar, nat (nu contează diacriticele).\n\n"
    "Tip de filtrare (opțional, după /filtered):\n"
    "cuvinte — doar articole care conțin un cuvânt cheie de incident (accident, "
    "incendiu, crimă etc.)\n"
    "categorie — doar articole pe care site-ul însuși le-a marcat cu categoria "
    "\"Eveniment\" (nu toate site-urile o folosesc)\n"
    "amandoua — oricare din cele două (implicit, dacă nu specifici tipul)\n\n"
    "Exemple:\n"
    "/all timis — Timiș primește tot\n"
    "/filtered national — de la presa națională vin doar incidentele\n"
    "/filtered hunedoara — Hunedoara primește incidente (cuvinte cheie sau categorie)\n"
    "/filtered arad cuvinte — Arad filtrat doar după cuvinte cheie\n"
    "/filtered caras-severin categorie — Caraș-Severin filtrat doar după categoria \"Eveniment\"\n\n"
    "Aceeași știre de la mai multe surse vine într-un singur mesaj; sursele în plus "
    "apar la final, la „🔁 Și la”.\n"
    "Apasă pe un hashtag (ex. #Timis) ca să vezi doar știrile acelui județ.\n\n"
    "Modificările se aplică începând cu următoarea rulare a botului "
    "(la câteva minute, nu instant)."
)


# --- Telegram ----------------------------------------------------------------

def telegram_call(token, method, data):
    """POST to the Telegram Bot API, waiting and retrying when rate limited
    (HTTP 429). Returns the API's "result" on success, None on failure."""
    url = f"https://api.telegram.org/bot{token}/{method}"
    for attempt in range(1, TELEGRAM_RETRIES + 1):
        try:
            resp = requests.post(url, data=data, timeout=REQUEST_TIMEOUT)
        except requests.RequestException as exc:
            print(f"[warn] telegram {method} failed: {exc}", file=sys.stderr)
            return None
        if resp.status_code == 429 and attempt < TELEGRAM_RETRIES:
            try:
                wait = resp.json().get("parameters", {}).get("retry_after", 5)
            except ValueError:
                wait = 5
            wait = min(wait, TELEGRAM_MAX_RETRY_WAIT_SECONDS)
            print(f"[warn] telegram rate limit on {method}, retrying in {wait}s", file=sys.stderr)
            time.sleep(wait + 0.5)
            continue
        if resp.status_code != 200:
            print(f"[warn] telegram {method} failed: {resp.status_code} {resp.text}", file=sys.stderr)
            return None
        return resp.json().get("result")
    return None


def send_telegram(token, chat_id, text, dry_run):
    """Returns the sent message's id (0 in dry-run), or None on failure."""
    if dry_run:
        print(f"[dry-run] would send:\n{text}\n")
        return 0
    result = telegram_call(token, "sendMessage", {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    })
    return result.get("message_id") if result else None


def edit_telegram(token, chat_id, message_id, text, dry_run):
    if dry_run:
        print(f"[dry-run] would edit message {message_id} to:\n{text}\n")
        return True
    result = telegram_call(token, "editMessageText", {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    })
    return result is not None


# Telegram commands you can send in the chat to switch modes without editing
# config.py: /all [county] sends everything for that county (or all of them
# if no county given), /filtered [county] applies keyword/category
# filtering, /status reports the current per-county mode and broken feeds.
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
        # "/status@MyBot" in group chats → "/status"
        command = parts[0].lower().split("@")[0] if parts else ""
        reply = None

        if command == "/all":
            arg = normalize(parts[1]) if len(parts) > 1 else ""
            if not arg:
                state["county_modes"] = {g: "all" for g in MODE_GROUPS}
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
                state["county_modes"] = {g: filter_type for g in MODE_GROUPS}
                reply = f"✅ Toate județele setate pe: {mode_display(filter_type)}."
        elif command == "/status":
            reply = format_status(state)
        elif command in ("/help", "/start"):
            reply = HELP_TEXT
        elif command.startswith("/"):
            reply = f"❓ Comandă necunoscută: '{command}'. Scrie /help pentru comenzile disponibile."

        if reply:
            send_telegram(token, chat_id, reply, dry_run=False)

    return state


# --- Feeds -------------------------------------------------------------------

def fetch_feed(source):
    """Returns (entries, None) on success, or (None, error message) if the
    fetch failed or the URL didn't return a feed at all (e.g. it redirects
    to the site's HTML homepage — which parses as zero entries and would
    otherwise look like a feed with nothing new)."""
    last_error = None
    for attempt in range(1, FETCH_RETRIES + 1):
        try:
            resp = requests.get(source["url"], headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
        except requests.RequestException as exc:
            last_error = str(exc)
            if attempt < FETCH_RETRIES:
                time.sleep(FETCH_RETRY_DELAY_SECONDS)
            continue
        parsed = feedparser.parse(resp.content)
        if parsed.version:
            return parsed.entries, None
        last_error = (f"nu e un feed RSS (răspuns {resp.headers.get('content-type', '?')} "
                      f"de la {resp.url})")
        break  # retrying won't turn a web page into a feed
    print(f"[warn] failed to fetch {source['name']}: {last_error}", file=sys.stderr)
    return None, last_error


def update_feed_health(state, source, error, token, chat_id, dry_run):
    """Count consecutive failed runs per feed; warn once in Telegram when a
    feed has been down for FEED_FAIL_ALERT_RUNS runs, and again when it
    comes back."""
    health = state["feed_health"]
    name = source["name"]
    if error is None:
        previous = health.pop(name, None)
        if previous and previous.get("alerted"):
            send_telegram(token, chat_id, f"✅ Sursa funcționează din nou: <b>{html.escape(name)}</b>",
                          dry_run)
        return
    entry = health.setdefault(name, {"fails": 0, "alerted": False})
    entry["fails"] += 1
    entry["last_error"] = error[:300]
    if entry["fails"] >= config.FEED_FAIL_ALERT_RUNS and not entry["alerted"]:
        text = (
            f"⚠️ Sursa nu funcționează de {entry['fails']} rulări la rând: <b>{html.escape(name)}</b>\n"
            f"{html.escape(source['url'])}\n"
            f"Eroare: {html.escape(entry['last_error'])}\n\n"
            "Primești alt mesaj când își revine. /status arată toate sursele căzute."
        )
        if send_telegram(token, chat_id, text, dry_run) is not None:
            entry["alerted"] = True


def format_message(source_name, title, link, send_all, groups):
    icon = "📰" if send_all else "🚨"
    tags = " ".join("#" + config.COUNTY_HASHTAGS.get(g, g) for g in groups)
    text = (
        f"{icon} <b>{html.escape(title)}</b>\n"
        f"📍 {html.escape(source_name)}\n"
        f"{html.escape(link)}"
    )
    if tags:
        text += f"\n{tags}"
    return text


def with_extra_sources(text, extras):
    if not extras:
        return text
    links = ", ".join(
        f'<a href="{html.escape(link, quote=True)}">{html.escape(name)}</a>' for name, link in extras
    )
    return f"{text}\n🔁 Și la: {links}"


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
    stories = prune_stories(bot_state["recent_stories"])
    feed_names = {f["name"] for f in config.all_feeds()}
    # Forget health/baseline entries for feeds removed from config.
    bot_state["feed_health"] = {n: h for n, h in bot_state["feed_health"].items() if n in feed_names}
    baselined = [n for n in bot_state["baselined_feeds"] if n in feed_names]

    new_count = merged_count = 0
    now_iso = datetime.now(timezone.utc).isoformat()

    for source in config.all_feeds():
        entries, error = fetch_feed(source)
        update_feed_health(bot_state, source, error, token, chat_id, args.dry_run)
        if entries is None:
            continue

        if source["name"] not in baselined:
            # New feed: mark what's already there as seen instead of dumping
            # the last MAX_ITEM_AGE_HOURS of it into the chat at once.
            for entry in entries:
                seen[item_id(entry)] = now_iso
            baselined.append(source["name"])
            print(f"Baselined new feed {source['name']} ({len(entries)} existing items skipped).")
            continue

        for entry in entries:
            uid = item_id(entry)
            if uid in seen:
                continue
            if not is_fresh(entry):
                continue
            title = entry.get("title", "").strip()
            summary = entry.get("summary", "")
            link = entry.get("link", "")

            groups = item_groups(normalize(f"{title} {summary}"), source)
            if not groups:
                continue
            modes = [county_modes.get(g, DEFAULT_MODE) for g in groups]
            # If the item touches multiple counties, the most permissive
            # setting among them wins: "all" bypasses filtering outright;
            # otherwise a signal counts if any matched county wants it.
            send_all = "all" in modes
            check_keyword = any(m in ("keyword", "both") for m in modes)
            check_category = any(m in ("category", "both") for m in modes)

            categories = [t.get("term", "") for t in entry.get("tags", [])]
            if not send_all and not content_matches_keywords(
                title, summary, categories, check_keyword=check_keyword, check_category=check_category,
                # Excluded places (Bucharest, Cluj…) exist to keep other
                # counties' incidents out of ours; for national news
                # they're exactly what's wanted.
                check_places=groups != [config.NATIONAL_GROUP],
            ):
                continue

            tokens = story_tokens(title)
            story = find_story(stories, tokens, groups)
            if story is not None:
                if source["name"] in story["sources"]:
                    # Same outlet posting the same story again (update,
                    # re-publish) — it's already in the chat.
                    seen[uid] = now_iso
                    continue
                extras = story["extras"] + [[source["name"], link]]
                if edit_telegram(token, chat_id, story["message_id"],
                                 with_extra_sources(story["text"], extras), args.dry_run):
                    story["extras"] = extras
                    story["sources"].append(source["name"])
                    seen[uid] = now_iso
                    merged_count += 1
                    continue
                # Edit failed (e.g. the original message was deleted) — send
                # it as a new message instead.

            text = format_message(source["name"], title, link, send_all, groups)
            message_id = send_telegram(token, chat_id, text, args.dry_run)
            if message_id is not None:
                seen[uid] = now_iso
                new_count += 1
                stories.append({
                    "tokens": tokens,
                    "groups": groups,
                    "title": title,
                    "text": text,
                    "message_id": message_id,
                    "sources": [source["name"]],
                    "extras": [],
                    "sent_at": now_iso,
                })
                if not args.dry_run:
                    time.sleep(TELEGRAM_SEND_INTERVAL_SECONDS)

    bot_state["recent_stories"] = stories
    bot_state["baselined_feeds"] = baselined
    save_seen(seen)
    save_bot_state(bot_state)
    print(f"Done. {new_count} new item(s) sent, {merged_count} merged into earlier messages.")


if __name__ == "__main__":
    main()
