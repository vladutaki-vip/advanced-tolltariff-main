from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List

from sqlalchemy.orm import Session

from ..models import HTC


def iter_commodities(node: Any) -> Iterable[Dict[str, Any]]:
    if isinstance(node, dict):
        if node.get("type") == "commodity":
            yield node
        # Recurse into common container keys
        for key in ("chapters", "headings", "divisions", "subchapters", "subsubheadings", "sections"):
            child = node.get(key)
            if child is not None:
                yield from iter_commodities(child)
    elif isinstance(node, list):
        for item in node:
            yield from iter_commodities(item)


def parse_structure_json(path: Path) -> List[Dict[str, str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    commodities: List[Dict[str, str]] = []
    for c in iter_commodities(data):
        code = str(c.get("id") or c.get("hsNumber") or "").strip()
        item = (c.get("item") or c.get("description") or "").strip()
        if not code:
            continue
        commodities.append({"code": code, "name": item})
    return commodities


def load_commodities(db: Session, items: List[Dict[str, str]]) -> int:
    # Fetch existing codes to avoid duplicates
    existing = {r[0] for r in db.query(HTC.code).all()}
    to_add = []
    for it in items:
        code = it["code"]
        if code in existing:
            continue
        to_add.append(HTC(code=code, name=it.get("name")))
    if to_add:
        db.add_all(to_add)
    return len(to_add)
