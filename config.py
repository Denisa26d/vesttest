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

# Plain local-news RSS feeds. Add more by finding "<site>/feed" or "<site>/feed/"
# on any WordPress-based outlet (most Romanian local news sites are WordPress).
RSS_FEEDS = [
    # Timiș / Timișoara (primary focus)
    {"name": "Tion.ro (Timiș)", "url": "https://www.tion.ro/feed/"},
    {"name": "Opinia Timișoarei (Timiș)", "url": "https://www.opiniatimisoarei.ro/feed/"},
    {"name": "Ziua de Vest (Timiș)", "url": "https://www.ziuadevest.ro/feed/"},
    {"name": "Express de Banat (Timiș/Caraș-Severin)", "url": "https://expressdebanat.ro/feed/"},
    {"name": "Renașterea Bănățeană (Timiș)", "url": "https://renasterea.ro/feed"},
    {"name": "Banat24 (Timiș/Banat)", "url": "https://banat24.ro/feed"},
    {"name": "PressAlert (Timiș)", "url": "https://www.pressalert.ro/feed"},
    {"name": "Timișoara Știri (Timiș)", "url": "https://www.timisoarastiri.ro/feed"},
    {"name": "Sursa de Vest (Timiș)", "url": "https://www.sursadevest.ro/feed"},
    {"name": "Tribuna TM (Timiș)", "url": "https://tribunasnm.ro/feed"},
    # NOTE: Vest24 and Știri pe Surse both block GitHub Actions' shared-runner
    # IPs (Cloudflare bot protection) with a 403, even though they work fine
    # from other IPs. Removed rather than fought — 12 other sources remain.
    # Hunedoara
    {"name": "Servus Press (Hunedoara)", "url": "https://servuspress.ro/feed/"},
    {"name": "Stiri din Hunedoara (Hunedoara)", "url": "https://stiridinhunedoara.ro/feed"},
    {"name": "Mesagerul Hunedorean (Hunedoara)", "url": "https://www.mesagerulhunedorean.ro/feed"},
    #Arad
    {"name": "Aradon (Arad)", "url": "https://www.aradon.ro/feed"},
    {"name": "Arad24 (Arad)", "url": "https://arad24.net/feed"},
    {"name": "Glasul Aradului (Arad)", "url": "https://www.glsa.ro/feed"},
    # Caraș-Severin / Reșița
    {"name": "Știrile CS (Caraș-Severin)", "url": "https://stirilecs.ro/feed/"},
    {"name": "Reper24 (Caraș-Severin)", "url": "https://reper24.ro/feed/"},
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
    "timis": ["timis", "timisoara"],
    "hunedoara": ["hunedoara", "deva", "petrosani", "orastie", "hateg", "brad", "vulcan", "lupeni"],
    "arad": ["arad", "ineu", "lipova", "santana", "curtici", "pecica", "nadlac", "chisineu-cris"],
    "caras-severin": ["caras-severin", "caras severin", "resita", "oravita", "baile herculane",
                       "otelu rosu", "moldova noua"],
}

# Names accepted after /all or /filtered in a Telegram command, mapped to
# the COUNTY_GROUPS key they set. Diacritics/case don't matter (normalized
# before lookup).
COUNTY_ALIASES = {
    "timis": "timis", "timisoara": "timis",
    "hunedoara": "hunedoara", "hd": "hunedoara", "deva": "hunedoara",
    "arad": "arad", "ar": "arad",
    "caras-severin": "caras-severin", "caras severin": "caras-severin",
    "cs": "caras-severin", "resita": "caras-severin",
}

# Proper display names (with diacritics) for bot replies.
COUNTY_DISPLAY_NAMES = {
    "timis": "Timiș",
    "hunedoara": "Hunedoara",
    "arad": "Arad",
    "caras-severin": "Caraș-Severin",
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
