from __future__ import annotations
import json
from pathlib import Path
from typing import Iterable, Tuple, Dict, Any

from sqlalchemy.orm import Session

from ..models import HTC


def _walk_nodes(nodes: Iterable[Dict[str, Any]]):
    for n in nodes:
        yield n
        for child_list_name in ("sections", "chapters", "divisions", "headings", "subchapters"):
            if isinstance(n, dict) and child_list_name in n and isinstance(n[child_list_name], list):
                for c in _walk_nodes(n[child_list_name]):
                    yield c


def _iter_commodities(doc: Dict[str, Any]) -> Iterable[Tuple[str, str]]:
    for n in _walk_nodes(doc.get("sections", [])):
        if not isinstance(n, dict):
            continue
        if n.get("type") == "commodity":
            code = str(n.get("id") or n.get("hsNumber") or "").strip()
            item = (n.get("item") or "").strip()
            if code:
                yield code, item


def import_structure_json(db: Session, path: Path) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    count = 0
    seen = set()
    for code, item in _iter_commodities(data):
        # Deduplicate within this run
        if code in seen:
            continue
        seen.add(code)

        h = db.query(HTC).filter(HTC.code == code).first()
        if h:
            # Update name if missing/different
            if item and (not h.name or h.name != item):
                h.name = item
        else:
            h = HTC(code=code, name=item)
            db.add(h)
            count += 1

        if count and count % 500 == 0:
            db.flush()

    db.commit()
    return count
