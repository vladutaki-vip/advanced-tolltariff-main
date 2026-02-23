from __future__ import annotations

import json
from pathlib import Path

# Minimal ISO alpha-2 -> country name mapping for common groups.
_BUILTIN: dict[str, str] = {
    # EFTA
    "NO": "Norway",
    "IS": "Iceland",
    "LI": "Liechtenstein",
    "CH": "Switzerland",

    # EU27
    "AT": "Austria",
    "BE": "Belgium",
    "BG": "Bulgaria",
    "HR": "Croatia",
    "CY": "Cyprus",
    "CZ": "Czechia",
    "DE": "Germany",
    "DK": "Denmark",
    "EE": "Estonia",
    "ES": "Spain",
    "FI": "Finland",
    "FR": "France",
    "GR": "Greece",
    "HU": "Hungary",
    "IE": "Ireland",
    "IT": "Italy",
    "LT": "Lithuania",
    "LU": "Luxembourg",
    "LV": "Latvia",
    "MT": "Malta",
    "NL": "Netherlands",
    "PL": "Poland",
    "PT": "Portugal",
    "RO": "Romania",
    "SE": "Sweden",
    "SI": "Slovenia",
    "SK": "Slovakia",

    # UK, India, Moldova
    "GB": "United Kingdom",
    "IN": "India",
    "MD": "Moldova",

    # Common partners and blocs
    "US": "United States",
    "CA": "Canada",
    "MX": "Mexico",
    "BR": "Brazil",
    "AR": "Argentina",
    "CL": "Chile",
    "CO": "Colombia",
    "PE": "Peru",
    "UY": "Uruguay",
    "PY": "Paraguay",
    "EC": "Ecuador",
    "BO": "Bolivia",
    "VE": "Venezuela",

    "CN": "China",
    "JP": "Japan",
    "KR": "South Korea",
    "TW": "Taiwan",
    "HK": "Hong Kong",
    "SG": "Singapore",
    "MY": "Malaysia",
    "TH": "Thailand",
    "VN": "Vietnam",
    "PH": "Philippines",
    "ID": "Indonesia",
    "BD": "Bangladesh",
    "LK": "Sri Lanka",
    "PK": "Pakistan",
    "KH": "Cambodia",
    "LA": "Laos",
    "MM": "Myanmar",
    "NP": "Nepal",
    "MN": "Mongolia",

    "AE": "United Arab Emirates",
    "SA": "Saudi Arabia",
    "QA": "Qatar",
    "KW": "Kuwait",
    "BH": "Bahrain",
    "OM": "Oman",

    "ZA": "South Africa",
    "NA": "Namibia",
    "BW": "Botswana",
    "LS": "Lesotho",
    "SZ": "Eswatini",
    "ZM": "Zambia",
    "ZW": "Zimbabwe",
    "MZ": "Mozambique",
    "AO": "Angola",
    "NG": "Nigeria",
    "GH": "Ghana",
    "KE": "Kenya",
    "TZ": "Tanzania",
    "UG": "Uganda",
    "RW": "Rwanda",
    "BI": "Burundi",
    "ET": "Ethiopia",

    "AU": "Australia",
    "NZ": "New Zealand",
}

_JSON_PATH = Path("data/country_names.json")
_EXTRA: dict[str, str] = {}
if _JSON_PATH.exists():
    try:
        _EXTRA = json.loads(_JSON_PATH.read_text(encoding="utf-8")) or {}
    except Exception:
        _EXTRA = {}

def get_country_name(iso2: str) -> str | None:
    iso2 = (iso2 or "").upper()
    return _EXTRA.get(iso2) or _BUILTIN.get(iso2)
