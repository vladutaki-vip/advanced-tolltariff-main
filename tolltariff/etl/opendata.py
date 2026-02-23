from __future__ import annotations
import json
from pathlib import Path
from typing import Optional

import httpx
from ..config import settings

DATA_DIR = settings.data_dir
RAW_DIR = DATA_DIR / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

# Open data resource URLs
CUSTOMS_TARIFF_STRUCTURE_JSON = "https://data.toll.no/dataset/4e6ec703-ca3c-4aad-b7f2-d9e45da21e0a/resource/b8595e94-71d8-41fc-9c83-9ce5980685ad/download/customstariffstructure.json"
# Fees for imports (innfoerselsavgift) JSON resource
# Dataset id used in download path: df428f2b-53e9-4ef4-9774-dd38cf388e9e
# Resource id: 0ca5ccca-1a2e-4db0-ae5b-2f94ad7b0f0d
IMPORT_FEES_JSON = (
    "https://data.toll.no/dataset/df428f2b-53e9-4ef4-9774-dd38cf388e9e/resource/0ca5ccca-1a2e-4db0-ae5b-2f94ad7b0f0d/download/innfoerselsavgift.json"
)

# Landgrupper (country groups) JSON resource
# Dataset id: 39c34027-4359-4617-9cab-c1732694236b
# Resource id: 5382af82-0fbd-4ddf-ac06-37d98c393a31
LANDGROUPS_JSON = (
    "https://data.toll.no/dataset/39c34027-4359-4617-9cab-c1732694236b/resource/5382af82-0fbd-4ddf-ac06-37d98c393a31/download/landgruppe.json"
)

# Medlemsland (country membership in groups) JSON resource
# Dataset id: 08fea877-30ee-4efd-b4df-3d404b3dfda0
# Resource id: 8e09e0f0-3728-40ce-bd3f-b87c3ca694cd
MEMBERS_JSON = (
    "https://data.toll.no/dataset/08fea877-30ee-4efd-b4df-3d404b3dfda0/resource/8e09e0f0-3728-40ce-bd3f-b87c3ca694cd/download/medlemsland.json"
)

# Free trade agreements JSON resource (agreements and participating countries)
# Dataset id: 35879701-da1e-40ed-90a1-30ef2f0c395c
# Resource id: fb5fed00-30b4-47c6-b8eb-46ebbb283541
FTA_JSON = (
    "https://data.toll.no/dataset/35879701-da1e-40ed-90a1-30ef2f0c395c/resource/fb5fed00-30b4-47c6-b8eb-46ebbb283541/download/ratetradeagreements.json"
)


def download(url: str, dest: Path) -> Path:
    with httpx.Client(timeout=60) as client:
        r = client.get(url)
        r.raise_for_status()
        dest.write_bytes(r.content)
    return dest


def fetch_structure_json(out_path: Optional[Path] = None) -> Path:
    path = out_path or RAW_DIR / "customstariffstructure.json"
    return download(CUSTOMS_TARIFF_STRUCTURE_JSON, path)


def fetch_import_fees_json(out_path: Optional[Path] = None) -> Path:
    path = out_path or RAW_DIR / "innfoerselsavgift.json"
    return download(IMPORT_FEES_JSON, path)


def fetch_landgroups_json(out_path: Optional[Path] = None) -> Path:
    path = out_path or RAW_DIR / "landgruppe.json"
    return download(LANDGROUPS_JSON, path)


def fetch_members_json(out_path: Optional[Path] = None) -> Path:
    path = out_path or RAW_DIR / "medlemsland.json"
    return download(MEMBERS_JSON, path)


def fetch_fta_json(out_path: Optional[Path] = None) -> Path:
    path = out_path or RAW_DIR / "ratetradeagreements.json"
    return download(FTA_JSON, path)


if __name__ == "__main__":
    p = fetch_structure_json()
    print(f"Downloaded: {p}")
