from __future__ import annotations
import json
from pathlib import Path
from typing import Any

from .opendata import fetch_fta_json

INDEX_PATH = Path("data/ratetradeagreements_index.json")


def import_fta(path: Path | None = None) -> Path:
    """Import ratetradeagreements.json and write an index per HTC:
    {
      "<htc>": {
        "FREE": ["EU", "IN", ...],
        "NA": [...]
      }
    }
    """
    if path is None:
        path = fetch_fta_json()
    data = json.loads(path.read_text(encoding="utf-8"))
    commodities = data.get("commodities", [])
    out: dict[str, dict[str, list[str]]] = {}
    for row in commodities:
        code = str(row.get("id") or "").strip()
        if not code:
            continue
        acc: dict[str, list[str]] = out.setdefault(code, {})
        for r in row.get("rateTradeAgreements", []):
            classifier = (r.get("customDuty", {}) or {}).get("classifier") or ""
            landCodes = r.get("landCodes") or []
            if not classifier or not isinstance(landCodes, list):
                continue
            acc.setdefault(classifier, [])
            for lc in landCodes:
                if lc and lc not in acc[classifier]:
                    acc[classifier].append(lc)
    INDEX_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return INDEX_PATH
