from __future__ import annotations
import json
from pathlib import Path
from typing import Any

from .opendata import RAW_DIR, fetch_landgroups_json, fetch_members_json, fetch_fta_json

MAP_PATH = Path("data/landgroups_map.json")


def _normalize_group_name(name: str | None) -> str | None:
    if not name:
        return None
    return name.strip()


def import_landgroups_json(path: Path | None = None) -> Path:
    """Import landgruppe -> countries mapping from official JSON and write a local map file.

    Output schema:
      {
        "groups": {
          "<code>": {
            "name": "<human name>",
            "countries": ["ISO2", ...]
          },
          ...
        }
      }
    """
    if path is None:
        path = fetch_landgroups_json()
    data = json.loads(path.read_text(encoding="utf-8"))
    # Expected structure: object with key 'landgrupper' or similar
    groups: dict[str, dict[str, Any]] = {}
    # Probe possible keys
    candidates = ["landgrupper", "groups", "data"]
    seq: list[Any] = []
    for k in candidates:
        v = data.get(k)
        if isinstance(v, list):
            seq = v
            break
    if not seq and isinstance(data, dict):
        # Some datasets may have flat dict with 'grupper'
        for k, v in data.items():
            if isinstance(v, list):
                seq = v
                break
    # Parse entries
    for row in seq:
        code = (row.get("landgruppekode") or row.get("kode") or row.get("landgruppe") or row.get("id") or "").strip()
        if not code:
            continue
        name = _normalize_group_name(row.get("landgruppenavn") or row.get("navn") or row.get("beskrivelse") or row.get("name"))
        # Countries may be under 'land', 'landkoder', 'countries'
        iso_list = []
        if isinstance(row.get("land"), list):
            iso_list = [str(x).strip() for x in row["land"] if x]
        elif isinstance(row.get("landkoder"), list):
            iso_list = [str(x).strip() for x in row["landkoder"] if x]
        elif isinstance(row.get("countries"), list):
            iso_list = [str(x).strip() for x in row["countries"] if x]
        groups[code] = {"name": name, "countries": iso_list}

    # Merge in membership: country -> groups
    members_path = fetch_members_json()
    members = json.loads(members_path.read_text(encoding="utf-8"))
    # Expect key 'medlemsland' list with 'landkode' and 'landgrupper'
    mseq = []
    for k in ("medlemsland", "countries"):
        v = members.get(k)
        if isinstance(v, list):
            mseq = v
            break
    # Build reverse mapping: group -> set of ISO2 codes
    rev: dict[str, set[str]] = {}
    for row in mseq:
        iso = (row.get("landkode") or row.get("iso") or "").strip()
        if not iso:
            continue
        lg = row.get("landgrupper") or row.get("groups") or []
        # landgrupper may be list of codes or list of objects with 'landgruppekode'
        codes: list[str] = []
        if isinstance(lg, list):
            for item in lg:
                if isinstance(item, str):
                    codes.append(item.strip())
                elif isinstance(item, dict):
                    code = (item.get("landgruppekode") or item.get("kode") or "").strip()
                    if code:
                        codes.append(code)
        for code in codes:
            rev.setdefault(code, set()).add(iso)

    # Merge rev into groups
    for code, info in groups.items():
        iso_list = sorted(rev.get(code, set()))
        info["countries"] = iso_list

    # Also integrate FTA dataset to cover bilateral and GSP categories
    try:
        fta_path = fetch_fta_json()
        fta = json.loads(fta_path.read_text(encoding="utf-8"))
        # Expect keys: 'agreements' or similar; entries with 'agreementcode', 'countries'
        fseq = []
        for k in ("agreements", "freeTradeAgreements", "data"):
            v = fta.get(k)
            if isinstance(v, list):
                fseq = v
                break
        for row in fseq:
            code = (row.get("agreementcode") or row.get("kode") or row.get("id") or "").strip()
            if not code:
                continue
            name = _normalize_group_name(row.get("agreementname") or row.get("name") or row.get("navn"))
            iso_list = []
            # Countries may be nested under 'countries' list of ISO codes or objects
            if isinstance(row.get("countries"), list):
                for c in row["countries"]:
                    if isinstance(c, str):
                        iso_list.append(c.strip())
                    elif isinstance(c, dict):
                        iso = (c.get("iso") or c.get("countrycode") or c.get("landkode") or "").strip()
                        if iso:
                            iso_list.append(iso)
            # Merge/overwrite existing
            entry = groups.setdefault(code, {"name": None, "countries": []})
            if name:
                entry["name"] = name
            if iso_list:
                # union
                existing = set(entry.get("countries") or [])
                entry["countries"] = sorted(existing.union(iso_list))
    except Exception:
        # FTA integration is best-effort
        pass

    out = {"groups": groups}
    MAP_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return MAP_PATH
