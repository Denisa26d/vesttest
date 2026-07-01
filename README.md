# Western Romania incident monitor

Polls RSS feeds every 10 minutes for accident/fire/explosion/flood/landslide/
crime/infrastructure-failure news in Timiș, Hunedoara and Caraș-Severin, and
posts new matches to a Telegram chat. Runs on GitHub Actions' free tier.

## Sources

- Local news RSS (already configured, working): Tion.ro, Opinia Timișoarei,
  Ziua de Vest, Servus Press, Știrile CS, Express de Banat, Reper24.
- Google Alerts RSS — you add these yourself, see below.

**Not included:** ISU/IPJ social-media monitoring via Nitter/X. As of mid-2026
public Nitter mirrors are effectively dead (tested 6 instances against
@ISUTIMIS — all failed), and the ISU/IPJ county sites (isuhd.igsu.ro,
isucs.igsu.ro, tm.politiaromana.ro) are JavaScript apps with no RSS or public
API, so they can't be polled without a headless browser (which would burn
through Actions free minutes at a 10-minute cadence). In practice, local
news picks up ISU/IPJ statements within minutes of them being issued, so the
RSS + Google Alerts combination covers the same ground. If you later want to
add X monitoring, the cleanest free option is self-hosting RSS-Bridge (e.g.
on Render's free tier) and adding its feed URL to `config.py`.

## 1. Add your Telegram secrets to GitHub

1. Go to `https://github.com/Denisa26d/vesttest/settings/secrets/actions`
2. Click **New repository secret**, add:
   - Name: `TELEGRAM_BOT_TOKEN`, Value: your bot token from @BotFather
   - Name: `TELEGRAM_CHAT_ID`, Value: your chat ID
3. Save both. They're encrypted at rest and never shown in logs.

## 2. Set up Google Alerts RSS feeds

1. Go to https://www.google.com/alerts
2. Create one alert per county, e.g.:
   - `Timiș (accident OR incendiu OR explozie OR inundație OR "alunecare de teren")`
   - `Hunedoara (accident OR incendiu OR explozie OR inundație OR "alunecare de teren")`
   - `Reșița OR "Caraș-Severin" (accident OR incendiu OR explozie OR inundație OR "alunecare de teren")`
3. Click **Show options** and set: Sources = News, Language = Romanian,
   Region = Romania, How many = All results, Deliver to = **RSS feed**.
4. Click **Create Alert**.
5. On the "My Alerts" page, click the RSS icon next to each alert to get its
   feed URL.
6. Paste those URLs into `GOOGLE_ALERTS_FEEDS` in [config.py](config.py).

## 3. Test

Push these files to `main`, then in the GitHub UI go to **Actions →
Incident monitor → Run workflow** to trigger it manually (don't wait for the
schedule). Check the run logs and your Telegram chat.

To test locally without sending anything to Telegram:

```
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python monitor.py --dry-run
```

## Tuning

- Add/remove RSS sources in `RSS_FEEDS` in [config.py](config.py).
- Add/remove incident keywords in `INCLUDE_KEYWORDS` / `EXCLUDE_KEYWORDS`.
- `seen.json` tracks already-sent items (30-day retention) and is
  committed back to the repo automatically by the workflow.

## Known limitations

- An item counts as "in-county" if a county/city name appears anywhere in
  the title or summary — this occasionally matches people *from* the county
  who were involved in an incident elsewhere, not just incidents *in* the
  county.
- GitHub disables scheduled workflows after 60 days with zero repository
  activity. Since this repo only auto-commits when there's a new incident
  match, an unusually quiet 60-day stretch could pause the schedule — check
  the Actions tab occasionally, or just re-run the workflow manually to
  reset the clock.
