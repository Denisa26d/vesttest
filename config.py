"""
Feed sources and keyword filters for the incident monitor.
Edit this file to add/remove sources or tune what counts as a match —
monitor.py itself should not need to change.
"""

# Plain local-news RSS feeds. Add more by finding "<site>/feed" or "<site>/feed/"
# on any WordPress-based outlet (most Romanian local news sites are WordPress).
RSS_FEEDS = [
    # Timiș (primary focus)
    {"name": "Tion.ro (Timiș)", "url": "https://www.tion.ro/feed/"},
    {"name": "Opinia Timișoarei (Timiș)", "url": "https://www.opiniatimisoarei.ro/feed/"},
    {"name": "Ziua de Vest (Timiș)", "url": "https://www.ziuadevest.ro/feed/"},
    {"name": "Express de Banat (Timiș/Caraș-Severin)", "url": "https://expressdebanat.ro/feed/"},
    # National aggregator, relies on COUNTY_KEYWORDS filtering below to stay relevant
    {"name": "Știri pe Surse (national, filtered)", "url": "https://www.stiripesurse.ro/feed"},
    # Hunedoara
    {"name": "Servus Press (Hunedoara)", "url": "https://servuspress.ro/feed/"},
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

# Only alert on items whose title/summary mentions one of these places
# (keeps unrelated national/international stories out of the county feeds).
COUNTY_KEYWORDS = [
    "timis", "timisoara",
    "hunedoara", "deva", "petrosani", "orastie", "hateg", "brad", "vulcan", "lupeni",
    "caras-severin", "caras severin", "resita", "oravita", "baile herculane", "otelu rosu", "moldova noua",
]
