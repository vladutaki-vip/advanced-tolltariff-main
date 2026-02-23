"""
Build static data for Netlify: HTC search index from tolltariffen JSONs,
split large files by chapter for on-demand load. Run from repo root.
"""
from __future__ import annotations
import json
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = REPO_ROOT / "data" / "raw"
DATA = REPO_ROOT / "data"
OUT = REPO_ROOT / "frontend" / "data"


def walk_commodities(nodes) -> list[tuple[str, str]]:
    if not isinstance(nodes, list):
        nodes = [nodes] if nodes else []
    out = []
    for n in nodes:
        if not isinstance(n, dict):
            continue
        if n.get("type") == "commodity":
            code = str(n.get("id") or n.get("hsNumber") or "").strip()
            name = (n.get("item") or "").strip()
            if code:
                out.append((code, name))
        for key in ("sections", "chapters", "divisions", "headings", "subchapters"):
            if key not in n:
                continue
            child = n[key]
            if isinstance(child, list):
                out.extend(walk_commodities(child))
            elif child is not None:
                out.extend(walk_commodities([child]))
    return out


def build_htc_index():
    path = DATA_RAW / "customstariffstructure.json"
    if not path.exists():
        print("Missing data/raw/customstariffstructure.json")
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    commodities = walk_commodities(data.get("sections", []))
    seen = set()
    index = []
    for code, name in commodities:
        if code in seen:
            continue
        seen.add(code)
        index.append({"code": code, "name": name, "description": ""})
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "htc_index.json").write_text(json.dumps(index, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"Wrote htc_index.json with {len(index)} HTCs.")


def split_by_chapter(file_path: Path, out_subdir: str, key_in_file: str | None = None):
    """Read a JSON object keyed by HTC code; write one file per chapter (01..99)."""
    if not file_path.exists():
        print(f"Missing {file_path}")
        return
    data = json.loads(file_path.read_text(encoding="utf-8"))
    if key_in_file:
        data = data.get(key_in_file, data)
    if not isinstance(data, dict):
        return
    by_chapter: dict[str, dict] = {}
    for code, value in data.items():
        if len(code) >= 2:
            ch = code[:2]
            by_chapter.setdefault(ch, {})[code] = value
    out_dir = OUT / out_subdir
    out_dir.mkdir(parents=True, exist_ok=True)
    for ch, chunk in sorted(by_chapter.items()):
        (out_dir / f"{ch}.json").write_text(json.dumps(chunk, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {out_subdir}/ with {len(by_chapter)} chapters.")


def copy_json(name: str):
    src = DATA / name
    if not src.exists():
        print(f"Missing {src}")
        return
    OUT.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, OUT / name)
    print(f"Copied {name}")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    build_htc_index()
    split_by_chapter(DATA / "best_zero_countries.json", "best_zero")
    split_by_chapter(DATA / "ratetradeagreements_index.json", "ratetradeagreements")
    copy_json("country_names.json")
    copy_json("landgroups_map.json")
    print("Static data build done.")


if __name__ == "__main__":
    main()
