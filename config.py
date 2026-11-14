"""
Feed sources and keyword filters for the incident monitor.
Edit this file to add/remove sources or tune what counts as a match —
monitor.py itself should not need to change.
"""

# Default mode for a county with no explicit override yet (see COUNTY_GROUPS
# below). If True, every fresh/unseen item for that county is sent to
# Telegram with keyword/category filtering skipped entirely. Overridden
# per-county at runtime via the /all and /filtered Telegram bot commands
# (state persisted in bot_state.json) — editing this only changes the
# starting default, not an override already in place.
SEND_ALL_ITEMS = True

# Pseudo-county for national-outlet articles that name none of our places.
# Has its own /all or /filtered mode like a county.
NATIONAL_GROUP = "national"

# Plain local-news RSS feeds. Add more by finding "<site>/feed" or "<site>/feed/"
# on any WordPress-based outlet (most Romanian local news sites are WordPress).
RSS_FEEDS = [
    # "counties" marks an outlet as local to those counties: its articles
    # count for that county even when the headline doesn't name a town (see
    # LOCAL_OUTLET_ASSUMES_COUNTY below). National outlets have no
    # "counties" key, so their articles must name one of our places.
    # Timiș / Timișoara (primary focus)
    {"name": "Tion.ro (Timiș)", "url": "https://www.tion.ro/feed/", "counties": ["timis"]},
    {"name": "Opinia Timișoarei (Timiș)", "url": "https://www.opiniatimisoarei.ro/feed/", "counties": ["timis"]},
    {"name": "Ziua de Vest (Timiș)", "url": "https://www.ziuadevest.ro/feed/", "counties": ["timis"]},
    {"name": "Express de Banat (Timiș/Caraș-Severin)", "url": "https://expressdebanat.ro/feed/",
     "counties": ["timis", "caras-severin"]},
    {"name": "Renașterea Bănățeană (Timiș)", "url": "https://renasterea.ro/feed", "counties": ["timis"]},
    {"name": "Banat24 (Timiș/Banat)", "url": "https://banat24.ro/feed", "counties": ["timis"]},
    {"name": "PressAlert (Timiș)", "url": "https://www.pressalert.ro/feed", "counties": ["timis"]},
    {"name": "Timișoara Știri (Timiș)", "url": "https://www.timisoarastiri.ro/feed", "counties": ["timis"]},
    {"name": "Sursa de Vest (Timiș)", "url": "https://www.sursadevest.ro/feed", "counties": ["timis"]},
    {"name": "Tribuna TM (Timiș)", "url": "https://tribunasnm.ro/feed", "counties": ["timis"]},
    # NOTE: Vest24 and Știri pe Surse both block GitHub Actions' shared-runner
    # IPs (Cloudflare bot protection) with a 403, even though they work fine
    # from other IPs. Removed rather than fought — 12 other sources remain.
    # Hunedoara
    {"name": "Servus Press (Hunedoara)", "url": "https://servuspress.ro/feed/", "counties": ["hunedoara"]},
    {"name": "Stiri din Hunedoara (Hunedoara)", "url": "https://stiridinhunedoara.ro/feed", "counties": ["hunedoara"]},
    {"name": "Mesagerul Hunedorean (Hunedoara)", "url": "https://www.mesagerulhunedorean.ro/feed",
     "counties": ["hunedoara"]},
    # Arad
    {"name": "Aradon (Arad)", "url": "https://www.aradon.ro/feed", "counties": ["arad"]},
    {"name": "Arad24 (Arad)", "url": "https://arad24.net/feed", "counties": ["arad"]},
    {"name": "Glasul Aradului (Arad)", "url": "https://www.glsa.ro/feed", "counties": ["arad"]},
    # Caraș-Severin / Reșița
    {"name": "Știrile CS (Caraș-Severin)", "url": "https://stirilecs.ro/feed/", "counties": ["caras-severin"]},
    {"name": "Reper24 (Caraș-Severin)", "url": "https://reper24.ro/feed/", "counties": ["caras-severin"]},
    # National — "national": True means every article is sent, not only
    # ones naming our places (together ~600-700 items/day). Articles that
    # do name one of our counties are tagged and moded as that county;
    # the rest fall under the "national" group, which /all national and
    # /filtered national control like a county.
    {"name": "Antena3 (National)", "url": "https://www.antena3.ro/rss", "national": True},
    {"name": "Digi24 (National)", "url": "https://www.digi24.ro/rss", "national": True},
    {"name": "G4Media (National)", "url": "https://www.g4media.ro/feed", "national": True},
    {"name": "HotNews (National)", "url": "https://hotnews.ro/feed", "national": True},
    {"name": "Adevarul (National)", "url": "https://adevarul.ro/rss/index", "national": True},
]

# Google Alerts RSS feeds. Create one alert per county + incident-keyword query
# at https://www.google.com/alerts with delivery set to "RSS feed", then paste
# the feed URL here (see README for the exact walkthrough). Leave this list
# empty and the script just skips it — nothing breaks.
GOOGLE_ALERTS_FEEDS = [
    # {"name": "Google Alert - Timiș incidente", "url": "https://www.google.com/alerts/feeds/XXXXXXXX/YYYYYYYY"},
    # {"name": "Google Alert - Hunedoara incidente", "url": "https://www.google.com/alerts/feeds/XXXXXXXX/ZZZZZZZZ"},
    # {"name": "Google Alert - Caraș-Severin incidente", "url": "https://www.google.com/alerts/feeds/XXXXXXXX/WWWWWWWW"},
]

def all_feeds():
    return RSS_FEEDS + GOOGLE_ALERTS_FEEDS

# Items older than this are ignored, even if never seen before. Keeps a
# stale/backfilled feed entry (or a first-ever run against a feed with old
# posts) from dumping months-old "news" into the chat.
MAX_ITEM_AGE_HOURS = 5

# Substrings (diacritics-stripped, lowercase) that mark an item as a relevant
# incident. Stems are used on purpose so conjugations/plurals match too
# (e.g. "incendi" catches incendiu, incendii, incendiat).
INCLUDE_KEYWORDS = [
    # accidents
    "accident", "ciocnire", "tamponare", "coliziune", "rasturnat",
    # fires
    "incendi", "ars din temelii", "cuprins de flacari",
    # explosions
    "explozi", "explod",
    # landslides
    "alunecare de teren", "alunecari de teren",
    # floods
    "inundat", "viitura", "cod rosu de inundatii", "cod portocaliu de inundatii",
    # building collapses
    "prabus", "surpare", "surpat",
    # gas leaks
    "scurgere de gaz", "scurgeri de gaz", "explozie de gaz", "emanatii de gaz", "miros de gaz",
    # power outages
    "pana de curent", "pene de curent", "avarie electrica", "intrerupere de curent",
    # crime
    "crima", "omor", "ucis", "injunghia", "impuscat", "talharie", "jaf", "jefuit",
    "spargere", "rapire", "agresat",
    # deaths/casualties from an incident, phrased without "accident" itself
    # (e.g. a body being found). Deliberately not adding bare "a murit" /
    # "deces" — those alone also match ordinary obituaries (a retired
    # official dying of old age, a celebrity, etc.), which is exactly the
    # kind of noise we're filtering out.
    "gasit mort", "gasita moarta", "victima mortala", "si-a pierdut viata",
    "a decedat in urma", "a murit in urma",
    # drugs
    "drog", "narcotic", "substante interzise", "substante psihoactive",
    "laborator clandestin",
    # border police (relevant here: Timiș/Arad/Caraș-Severin all border
    # Serbia or Hungary, so smuggling/migrant-trafficking busts are common)
    "politia de frontiera", "politisti de frontiera", "frontiera",
    "contrabanda", "trafic de migranti", "migranti", "perchezitii", "scandal", "bataie",
]

# If any of these appear, the item is dropped even if it matched an include
# keyword above (keeps political/cultural/admin coverage out).
EXCLUDE_KEYWORDS = [
    "consiliul local", "sedinta de consiliu", "hotarare de consiliu",
    "primaria", "primarul", "primar general",
    "buget local", "alegeri", "candidat", "campanie electorala",
    "cultura", "festival", "teatru", "muzeu", "expozitie", "targ de",
    "politica", "guvern", "ministru", "parlament", "senat", "coalitie",
    # figurative uses of fire/crime words in sports & entertainment headlines
    "incendiar", "spargere de tipare", "meci de foc",
    # "bataie de joc" is a common idiom for "being mishandled/mocked"
    # (e.g. a project being badly managed), not an actual physical fight
    "bataie de joc",
]

# Same idea as EXCLUDE_KEYWORDS, but matched as whole words (see
# COUNTY_GROUPS below for why) since these are short place names prone to
# colliding with unrelated words (e.g. "arad" inside "parada"/parade).
#
# News often mentions a Timiș/Hunedoara/CS person ("a woman from Hunedoara")
# in an incident that actually happened elsewhere. If one of these other
# counties/cities is also named, treat the incident as happening there
# instead of in our target counties.
EXCLUDE_PLACE_KEYWORDS = [
    "sibiu", "bihor", "oradea", "alba iulia", "targu jiu", "gorj",
    "mehedinti", "drobeta-turnu severin", "valcea", "ramnicu valcea",
    "cluj-napoca", "arges", "bucuresti",
]

# Most (not all) of the outlets in RSS_FEEDS tag incident-type articles
# with an "Eveniment" WordPress category — a stronger signal than keyword
# guessing since it's the outlet's own editorial classification. Used as an
# extra OR condition alongside INCLUDE_KEYWORDS, not a replacement: several
# outlets never use this category at all, so relying on it alone would
# silently drop those sources.
CATEGORY_HINTS = ["eveniment"]

# Only alert on items whose title/summary mentions one of these places
# (keeps unrelated national/international stories out of the county feeds).
# Timiș is the primary focus; Hunedoara, Arad and Caraș-Severin are also
# in scope. Grouped per county (not a flat list) so /all and /filtered bot
# commands can target one county at a time — see COUNTY_ALIASES below for
# the names accepted in those commands.
COUNTY_GROUPS = {
    "timis": ["timis", "timisoara", "lugoj", "sannicolau mare", "jimbolia", "buzias", "deta",
              "gataia", "recas", "ciacova", "dumbravita", "giroc", "ghiroda", "mosnita",
              "sacalaz", "sanandrei",
              # inhabitants ("timișenii", "timișorenii" …)
              "timisean", "timiseana", "timiseni", "timisenii", "timisene",
              "timisorean", "timisoreana", "timisoreni", "timisorenii"],
    "hunedoara": ["hunedoara", "deva", "petrosani", "orastie", "hateg", "lupeni", "simeria",
                  "calan", "geoagiu", "uricani", "petrila", "aninoasa",
                  # see AMBIGUOUS_PLACE_KEYWORDS for bare "brad"/"vulcan"
                  "orasul brad", "municipiul brad", "orasul vulcan", "municipiul vulcan",
                  "hunedorean", "hunedoreana", "hunedoreni", "hunedorenii"],
    "arad": ["arad", "ineu", "lipova", "curtici", "pecica", "nadlac", "chisineu-cris",
             "chisineu cris", "sebis", "pancota", "orasul santana",
             "aradean", "aradeana", "aradeni", "aradenii"],
    "caras-severin": ["caras-severin", "caras severin", "resita", "caransebes", "oravita",
                      "baile herculane", "otelu rosu", "moldova noua", "bocsa", "anina",
                      "resitean", "resiteana", "resiteni", "resitenii"],
}

# Town names that are also everyday words or famous names: "brad" (fir
# tree, Brad Pitt), "vulcan" (volcano), "santana" (Carlos Santana),
# "faget" (beech forest). These only count when the article comes from an
# outlet local to that county — a national outlet's Christmas-tree story
# shouldn't land in Hunedoara. Qualified forms like "orasul Brad" are in
# COUNTY_GROUPS above and count from any outlet.
AMBIGUOUS_PLACE_KEYWORDS = {
    "timis": ["faget"],
    "hunedoara": ["brad", "vulcan"],
    "arad": ["santana"],
}

# If True, every article from an outlet with a "counties" entry in
# RSS_FEEDS is in scope: one naming one of our towns is tagged with that
# county, any other (no town named, or another county's) is tagged with
# the outlet's own county. Together with national outlets' "national"
# flag, this means /all sends everything every outlet publishes, while
# /filtered still drops other counties' incidents (EXCLUDE_PLACE_KEYWORDS).
# Set to False to only send local-outlet articles that name one of our
# places.
LOCAL_OUTLET_ASSUMES_COUNTY = True

# Hashtag added to each Telegram message, so tapping it in the chat shows
# only that county's news. Telegram hashtags can't contain "-".
COUNTY_HASHTAGS = {
    "timis": "Timis",
    "hunedoara": "Hunedoara",
    "arad": "Arad",
    "caras-severin": "CarasSeverin",
    NATIONAL_GROUP: "National",
}

# The same incident is usually reported by several outlets. Within this
# many hours, an item whose headline is close enough to one already sent
# is added as an extra link to the original Telegram message instead of
# being sent again. "Close enough" = at least DEDUP_MIN_SHARED_WORDS
# significant words in common, and those make up at least
# DEDUP_MIN_OVERLAP of the shorter headline's words.
DEDUP_WINDOW_HOURS = 3
DEDUP_MIN_SHARED_WORDS = 3
DEDUP_MIN_OVERLAP = 0.6

# After this many runs in a row where a feed fails (error, or it returns a
# web page instead of RSS), send one Telegram warning; another message
# follows when it recovers. At one run per 10 minutes, 6 = about an hour.
FEED_FAIL_ALERT_RUNS = 6

# Names accepted after /all or /filtered in a Telegram command, mapped to
# the COUNTY_GROUPS key they set. Diacritics/case don't matter (normalized
# before lookup).
COUNTY_ALIASES = {
    "timis": "timis", "timisoara": "timis",
    "hunedoara": "hunedoara", "hd": "hunedoara", "deva": "hunedoara",
    "arad": "arad", "ar": "arad",
    "caras-severin": "caras-severin", "caras severin": "caras-severin",
    "cs": "caras-severin", "resita": "caras-severin",
    "national": NATIONAL_GROUP, "nationale": NATIONAL_GROUP, "nat": NATIONAL_GROUP,
}

# Proper display names (with diacritics) for bot replies.
COUNTY_DISPLAY_NAMES = {
    "timis": "Timiș",
    "hunedoara": "Hunedoara",
    "arad": "Arad",
    "caras-severin": "Caraș-Severin",
    NATIONAL_GROUP: "Național",
}

# When a county is in filtered mode, this controls which signal(s) count as
# a match: "keyword" = INCLUDE_KEYWORDS only, "category" = CATEGORY_HINTS
# only, "both" (default) = either one. Set per-county via the /filtered bot
# command, e.g. "/filtered hunedoara categorie".
FILTER_TYPE_ALIASES = {
    "keyword": "keyword", "keywords": "keyword", "cuvinte": "keyword", "cuvant": "keyword",
    "category": "category", "categorie": "category", "categorii": "category",
    "both": "both", "amandoua": "both", "ambele": "both",
}
FILTER_TYPE_DISPLAY_NAMES = {
    "keyword": "cuvinte cheie",
    "category": "categorie",
    "both": "cuvinte cheie + categorie",
}
