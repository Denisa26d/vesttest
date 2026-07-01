"""
Feed sources and keyword filters for the incident monitor.
Edit this file to add/remove sources or tune what counts as a match —
monitor.py itself should not need to change.
"""

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
    {"name": "Vest24 (Timiș)", "url": "https://vest24.ro/feed"},
    {"name": "Timișoara Știri (Timiș)", "url": "https://www.timisoarastiri.ro/feed"},
    # National aggregator, relies on COUNTY_KEYWORDS filtering below to stay relevant
    {"name": "Știri pe Surse (national, filtered)", "url": "https://www.stiripesurse.ro/feed"},
    # Hunedoara
    {"name": "Servus Press (Hunedoara)", "url": "https://servuspress.ro/feed/"},
    # Arad
    {"name": "Aradon (Arad)", "url": "https://www.aradon.ro/feed"},
    {"name": "Arad24 (Arad)", "url": "https://arad24.net/feed"},
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
MAX_ITEM_AGE_HOURS = 24

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
    "contrabanda", "trafic de migranti", "migranti",
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
]

# Same idea as EXCLUDE_KEYWORDS, but matched as whole words (see
# COUNTY_KEYWORDS above for why) since these are short place names prone to
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

# Only alert on items whose title/summary mentions one of these places
# (keeps unrelated national/international stories out of the county feeds).
# Timiș is the primary focus; Hunedoara, Arad and Caraș-Severin are also
# in scope.
COUNTY_KEYWORDS = [
    "timis", "timisoara",
    "hunedoara", "deva", "petrosani", "orastie", "hateg", "brad", "vulcan", "lupeni",
    "arad", "ineu", "lipova", "santana", "curtici", "pecica", "nadlac", "chisineu-cris",
    "caras-severin", "caras severin", "resita", "oravita", "baile herculane", "otelu rosu", "moldova noua",
]
