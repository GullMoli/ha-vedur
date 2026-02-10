"""Constants for the Veðurstofa Íslands integration."""
from __future__ import annotations

DOMAIN = "vedur"
CONF_STATION_ID = "station_id"
CONF_STATION_NAME = "station_name"
CONF_ALERT_LANGUAGE = "alert_language"

# API URLs
FORECAST_URL = (
    "https://xmlweather.vedur.is/"
    "?op_w=xml&type=forec&lang=en&view=xml&ids={station_id}"
)
OBSERVATION_URL = (
    "https://xmlweather.vedur.is/"
    "?op_w=xml&type=obs&lang=en&view=xml&ids={station_id}"
)
ALERTS_URL = "https://api.vedur.is/cap/v1/capbroker/active/feed/met"

ALERT_LANGUAGES = {
    "is": "Íslenska",
    "en": "English",
}

# Update interval (seconds)
UPDATE_INTERVAL = 600  # 10 minutes

# Popular stations — full list: https://www.vedur.is/vedur/stodvar/
POPULAR_STATIONS = {
    "1": "Reykjavík",
    "422": "Akureyri",
    "571": "Egilsstaðir",
    "6015": "Ísafjörður",
    "802": "Vestmannaeyjar",
    "1474": "Keflavíkurflugvöllur",
    "1350": "Selfoss",
    "4912": "Húsavík",
    "53": "Patreksfjörður",
    "6272": "Bolungarvík",
    "2642": "Blönduós",
    "2481": "Sauðárkrókur",
    "3471": "Siglufjörður",
    "3696": "Ólafsfjörður",
    "4172": "Grímsey",
    "5544": "Raufarhöfn",
    "5767": "Þórshöfn",
    "625": "Seyðisfjörður",
    "680": "Neskaupstaður",
    "705": "Eskifjörður",
    "798": "Höfn í Hornafirði",
    "920": "Kirkjubæjarklaustur",
    "990": "Vík í Mýrdal",
    "1099": "Hella",
    "1194": "Hvolsvöllur",
    "1597": "Þorlákshöfn",
    "1833": "Grindavík",
    "31572": "Bláfjöll",
    "1477": "Reykjanesbær",
    "1924": "Akranes",
    "2247": "Borgarnes",
    "2319": "Stykkishólmur",
}

# Wind direction mapping (Icelandic + English abbreviations → degrees)
WIND_DIRECTION_MAP = {
    # Icelandic
    "N": 0, "NNA": 22.5, "NA": 45, "ANA": 67.5,
    "A": 90, "ASA": 112.5, "SA": 135, "SSA": 157.5,
    "S": 180, "SSV": 202.5, "SV": 225, "VSV": 247.5,
    "V": 270, "VNV": 292.5, "NV": 315, "NNV": 337.5,
    # English
    "NNE": 22.5, "NE": 45, "ENE": 67.5, "E": 90,
    "ESE": 112.5, "SE": 135, "SSE": 157.5, "SSW": 202.5,
    "SW": 225, "WSW": 247.5, "W": 270, "WNW": 292.5, "NW": 315,
}

# Weather condition text → HA condition key
CONDITION_MAP = {
    "clear sky": "sunny",
    "partly cloudy": "partlycloudy",
    "cloudy": "cloudy",
    "overcast": "cloudy",
    "light rain": "rainy",
    "rain": "rainy",
    "rain showers": "rainy",
    "drizzle": "rainy",
    "light drizzle": "rainy",
    "snow": "snowy",
    "light snow": "snowy",
    "snow showers": "snowy",
    "sleet": "snowy-rainy",
    "light sleet": "snowy-rainy",
    "fog": "fog",
    "mist": "fog",
    "thunder": "lightning",
    "thunderstorm": "lightning-rainy",
}

# CAP severity → color mapping
SEVERITY_MAP = {
    "extreme": "red",
    "severe": "orange",
    "moderate": "yellow",
    "minor": "yellow",
    "unknown": "unknown",
}

SEVERITY_ORDER = {"red": 3, "orange": 2, "yellow": 1, "unknown": 0}


def highest_severity(alerts: list[dict]) -> str:
    """Return the highest severity color from a list of alerts."""
    best = "none"
    best_val = -1
    for alert in alerts:
        sev = alert.get("severity_color", "unknown")
        val = SEVERITY_ORDER.get(sev, 0)
        if val > best_val:
            best_val = val
            best = sev
    return best
