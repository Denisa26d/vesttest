# Western Romania incident monitor

Polls RSS feeds every 10 minutes and posts new articles to a Telegram chat:
everything published by local outlets in Timiș (primary focus), Hunedoara,
Arad and Caraș-Severin, plus everything from five national outlets.

## How it decides what to send

Every article is put in a group, and each group has its own mode, which you
switch from the Telegram chat (`/all`, `/filtered`, `/status`, `/help`):

| Article | Group |
|---|---|
| Names a town in one of the four counties (any outlet) | that county |
| From a local outlet, names no town of ours | the outlet's county |
| From a national outlet, names no town of ours | `national` |

- `/all <group>` (the default): send every article in that group.
- `/filtered <group>`: only incidents (accidents, fires, crime, drugs,
  border police… see `INCLUDE_KEYWORDS` / `EXCLUDE_KEYWORDS` in
  [config.py](config.py)). E.g. `/filtered national` keeps the national
  outlets (~600-700 articles/day) down to incidents only.

Other behaviour:

- **Duplicates merge.** When several outlets report the same story (near-
  identical headline, same county, within 3 hours), you get one message;
  later outlets are added to it as `🔁 Și la:` links (an edit, so no extra
  notification).
- **County hashtags** (`#Timis`, `#Arad`, `#National` …) on every message;
  tap one to see only that group.
- **Dead feed warning.** If a feed fails 6 runs in a row (~1 hour) — error,
  or it returns a web page instead of RSS — you get one warning, and another
  message when it recovers. `/status` lists feeds that are down.
- **New feeds start quiet.** The first time a feed is seen, its current
  articles are marked as already sent; only articles published after that
  are sent, so adding a feed doesn't flood the chat.
- Ambiguous town names (`brad`, `vulcan`, `santana`, `faget`) only count
  from that county's own outlets, so "Brad Pitt" isn't Hunedoara news.

## Sources

Local: Tion.ro, Opinia Timișoarei, Ziua de Vest, Express de Banat,
Renașterea Bănățeană, Banat24, PressAlert, Timișoara Știri, Sursa de Vest,
Tribuna TM (Timiș); Servus Press, Știri din Hunedoara, Mesagerul Hunedorean
(Hunedoara); Aradon, Arad24, Glasul Aradului (Arad); Știrile CS, Reper24
(Caraș-Severin). National: Antena3, Digi24, G4Media, HotNews, Adevărul.
Plus Google Alerts RSS, which you set up yourself (see below).

To add a source, add it to `RSS_FEEDS` in [config.py](config.py) — with
`"counties": [...]` for a local outlet or `"national": True` for a national
one. Check the URL really returns RSS (open it in a browser: you should see
XML, not the website); e.g. Digi24's `/feed/` silently redirects to the
homepage, the real feed is `/rss`.

**Not included:** ISU/IPJ social-media monitoring via Nitter/X (public
Nitter mirrors are effectively dead as of mid-2026) and the ISU/IPJ county
sites directly (they're JavaScript apps with no RSS/API). Local news picks
up ISU/IPJ statements within minutes of release in practice, so this isn't
a real coverage gap.

## Where it runs

GitHub Actions' `schedule` trigger is documented as best-effort and
skips/delays runs under load — too unreliable for a 10-minute cadence. But
`workflow_dispatch` runs (manual or API-triggered) don't have that
deprioritization. So instead of `schedule:`, an external free scheduler
([cron-job.org](https://cron-job.org), no card required) calls the
GitHub API to trigger `workflow_dispatch` every 10 minutes. Execution still
happens on GitHub Actions (free, no card) — only the "wake up on schedule"
part moved elsewhere.

The bot's state — `seen.json` (already-sent articles) and `bot_state.json`
(modes, feed health, recent stories for merging) — is saved after each run
to the `state` branch, which always holds a single commit (force-pushed).
GitHub Actions runners are ephemeral, so this is how it survives between
runs, without adding a commit to `main` every 10 minutes. The copies of
those files on `main` are only the starting point used if the `state`
branch is ever missing.

## 1. Create a GitHub token for the trigger

1. Go to https://github.com/settings/tokens?type=beta → **Generate new
   token** (fine-grained).
2. Set **Repository access** → Only select repositories → `vesttest`.
3. Under **Permissions** → **Repository permissions** → set **Actions** to
   **Read and write**.
4. Generate it and copy the token (`github_pat_...`) somewhere safe — you
   won't see it again. This token only has access to this one repo's
   Actions, nothing else on your account.

## 2. Set up cron-job.org to trigger it every 10 minutes

1. Sign up free at https://cron-job.org (email only, no card).
2. **Create cronjob**:
   - **Title**: `vesttest incident monitor`
   - **URL**: `https://api.github.com/repos/Denisa26d/vesttest/actions/workflows/monitor.yml/dispatches`
   - **Request method**: `POST`
   - **Schedule**: every 10 minutes
   - Under **Advanced** → **Headers**, add:
     - `Authorization: Bearer <your github_pat_... token>`
     - `Accept: application/vnd.github+json`
     - `Content-Type: application/json`
   - Under **Advanced** → **Request body**: `{"ref":"main"}`
3. Save and enable it.

Once both are set up, check the **Actions** tab on GitHub after ~10-15
minutes — you should see `Incident monitor` runs appearing on schedule.

## 3. Set up Google Alerts RSS feeds (optional)

1. Go to https://www.google.com/alerts
2. Create one alert per county, e.g.:
   - `Timiș (accident OR incendiu OR explozie OR inundație OR "alunecare de teren")`
   - `Hunedoara (accident OR incendiu OR explozie OR inundație OR "alunecare de teren")`
   - `Arad (accident OR incendiu OR explozie OR inundație OR "alunecare de teren")`
   - `Reșița OR "Caraș-Severin" (accident OR incendiu OR explozie OR inundație OR "alunecare de teren")`
3. Click **Show options** and set: Sources = News, Language = Romanian,
   Region = Romania, How many = All results, Deliver to = **RSS feed**.
4. Click **Create Alert**.
5. On the "My Alerts" page, click the RSS icon next to each alert to get its
   feed URL.
6. Paste those URLs into `GOOGLE_ALERTS_FEEDS` in [config.py](config.py).

## Testing locally

```
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python monitor.py --dry-run
```

Real sends need `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` as env vars —
never hardcode them in a file that gets committed.

## Tuning

- Add/remove RSS sources in `RSS_FEEDS` in [config.py](config.py).
- Add towns to `COUNTY_GROUPS`; ambiguous ones to `AMBIGUOUS_PLACE_KEYWORDS`.
- `SEND_ALL_ITEMS` is only the starting mode for a group with no `/all` or
  `/filtered` set yet; use the Telegram commands to change modes.
- Add/remove incident keywords in `INCLUDE_KEYWORDS` / `EXCLUDE_KEYWORDS`
  (only used for groups in `/filtered` mode).
- `LOCAL_OUTLET_ASSUMES_COUNTY = False` to only send local-outlet articles
  that name one of our towns.
- `DEDUP_*` settings tune duplicate merging, `FEED_FAIL_ALERT_RUNS` the
  dead-feed warning.
- `MAX_ITEM_AGE_HOURS` controls the freshness window (currently 5).

## Alternative: running on your own always-on machine

If you'd rather not depend on GitHub Actions + cron-job.org at all (e.g.
you have a Raspberry Pi or a Mac that's always on), `deploy/setup_vm.sh`
and `deploy/run_monitor.sh` set up the same script under a local cron job
instead — see the comments in those files. This also works on a cloud VM
if you're fine with a provider that requires card verification (Oracle
Cloud's Always Free tier is the standard free-forever option for that).
In that setup `seen.json` would stay local to that machine instead of
round-tripping through git — let me know if you want to switch to it and
I'll adjust the `.gitignore`/workflow accordingly.

## Known limitations

- An item counts as "in-county" if a county/city name appears anywhere in
  the title or summary — this occasionally matches people *from* the
  county who were involved in an incident elsewhere. `EXCLUDE_PLACE_KEYWORDS`
  in [config.py](config.py) covers the most common neighboring counties
  (Sibiu, Bihor, etc.) for this.
- A single feed occasionally fails for one run (site-side rate limiting,
  transient timeout) — this is logged as `[warn]` and skipped. If the same
  feed keeps failing for ~an hour, the bot tells you in Telegram.
- Duplicate merging compares headlines only. Outlets that rewrite a story
  with completely different wording still arrive as separate messages.
