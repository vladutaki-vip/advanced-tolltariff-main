from __future__ import annotations

from .countries import get_country_name
import json
from pathlib import Path

# Best-effort mapping of landgruppe codes to human-friendly names.
# This can be expanded/verified against Toll data catalogs.
LANDGROUPS: dict[str, str] = {
    # Ordinary baseline groups
    "TAL": "Ordinary tariff (baseline)",
    "TALL": "Ordinary tariff (baseline)",
    "ALLE": "All countries (baseline)",

    # Regional blocs / agreements
    "EUE": "European Union",
    "TOES": "EEA / EØS",
    "TEF": "EFTA",

    # Country-specific agreements
    "TIN": "India",
    "TMD": "Moldova",
    "TUK": "United Kingdom",

    # GSP groups (Generalized System of Preferences)
    "TGB": "GSP (standard)",
    "TGSP": "GSP (preferential)",
    "TGS1": "GSP (least developed)",
}

# Aliases from FTA landCodes to landgruppe codes used in Toll datasets
ALIASES: dict[str, str] = {
    "EU": "EUE",
    "EEA": "TOES",
    "EFTA": "TEF",
    "GB": "TUK",
    "IN": "TIN",
    "MD": "TMD",
    "GSP": "TGB",
    "GSP+": "TGSP",
    "GSP-LDC": "TGS1",
    "GCC": "TGCC",
    "SACU": "TSAC",
}
# Map landgruppe to ISO2 country codes
LANDGROUP_COUNTRIES: dict[str, list[str]] = {
    # EFTA
    "TEF": ["NO", "IS", "LI", "CH"],
    # EU27
    "EUE": [
        "AT","BE","BG","HR","CY","CZ","DE","DK","EE","ES","FI","FR","GR","HU","IE",
        "IT","LT","LU","LV","MT","NL","PL","PT","RO","SE","SI","SK"
    ],
    # EEA = EU + NO, IS, LI
    "TOES": [
        "AT","BE","BG","HR","CY","CZ","DE","DK","EE","ES","FI","FR","GR","HU","IE",
        "IT","LT","LU","LV","MT","NL","PL","PT","RO","SE","SI","SK",
        "NO","IS","LI"
    ],
    # Country-specific
    "TIN": ["IN"],
    "TMD": ["MD"],
    "TUK": ["GB"],
    # GSP categories include multiple countries; left empty for now or managed separately
    "TGB": [],
    "TGSP": [],
    "TGS1": [],
}

_MAP_JSON = Path("data/landgroups_map.json")
_DYNAMIC_GROUPS: dict[str, dict] = {}
if _MAP_JSON.exists():
    try:
        obj = json.loads(_MAP_JSON.read_text(encoding="utf-8"))
        _DYNAMIC_GROUPS = obj.get("groups") or {}
    except Exception:
        _DYNAMIC_GROUPS = {}

def get_landgroup_name(code: str | None) -> str | None:
    if not code:
        return None
    code = ALIASES.get(code, code)
    # Prefer dynamic mapping if available
    dyn = _DYNAMIC_GROUPS.get(code)
    if isinstance(dyn, dict) and dyn.get("name"):
        return dyn["name"]
    return LANDGROUPS.get(code)

def get_landgroup_countries(code: str | None) -> list[dict[str, str]]:
    if not code:
        return []
    code = ALIASES.get(code, code)
    iso_list = []
    dyn = _DYNAMIC_GROUPS.get(code)
    if isinstance(dyn, dict) and isinstance(dyn.get("countries"), list):
        iso_list = [str(x) for x in dyn["countries"]]
    else:
        iso_list = LANDGROUP_COUNTRIES.get(code, [])
    return [{"iso": iso, "name": get_country_name(iso) or iso} for iso in iso_list]
