from __future__ import annotations
import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from ..models import HTC, Rate, RateType


def _parse_decimal_comma(s: str | None) -> Optional[Decimal]:
    if not s:
        return None
    s = s.strip().replace("\xa0", " ")
    # Norwegian decimal comma
    s = s.replace(".", "").replace(",", ".")
    try:
        return Decimal(s)
    except Exception:
        return None


essential_type = "MV"  # Merverdiavgift (VAT) as default percent rate


def import_default_rates_from_fees(db: Session, path: Path, source_url: str | None = None) -> int:
    """
    Import a default percent rate per HTC from innfoerselsavgift.json.
    Heuristic: use landgruppe == 'ALLE' and avgiftstype == 'MV' (VAT), enhet == 'P' (percent).

    Stores as Rate(country_iso='*', rate_type=percent).
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    varer = data.get("varer", [])
    total_varer = len(varer)
    progress_step = max(1, (total_varer // 20) if total_varer else 1)
    total_varer = len(varer)
    # Aim for ~20 progress updates across the dataset
    progress_step = max(1, total_varer // 20) or 1

    added = 0
    ordinary_groups = {"TAL", "TALL", "ALLE"}
    updated = 0

    # Index HTC by exact 8-digit code for quick lookup
    def get_htc(code: str) -> Optional[HTC]:
        return db.query(HTC).filter(HTC.code == code).first()

    ordinary_groups = {"TAL", "TALL", "ALLE"}

    for v in varer:
        code = str(v.get("id") or "").strip()
        if not code:
            continue
        # expect default group 'ALLE'
        for lg in v.get("avgiftsatser", []):
            if lg.get("landgruppe") != "ALLE":
                continue
            for t in lg.get("avgiftstyper", []):
                if t.get("avgiftstype") != essential_type:
                    continue
                # find percent entry
                for g in t.get("avgiftsgrupper", []):
                    if g.get("enhet") != "P":
                        continue
                    val = _parse_decimal_comma(g.get("sats"))
                    if val is None:
                        continue
                    vf = g.get("fomdato") or None
                    vt = g.get("tomdato") or None
                    # Map to/from date
                    def parse_d(d: str | None) -> Optional[date]:
                        if not d:
                            return None
                        try:
                            y, m, dd = d.split("-")
                        except ValueError:
                            return None
                        try:
                            return date(int(y), int(m), int(dd))
                        except Exception:
                            return None

                    htc = get_htc(code)
                    if not htc:
                        # Unknown code, skip
                        break
                    existing = (
                        db.query(Rate)
                        .filter(
                            Rate.htc_id == htc.id,
                            Rate.country_iso == "*",
                            Rate.rate_type == RateType.PERCENT,
                            Rate.is_exemption == False,
                        )
                        .first()
                    )
                    if existing:
                        # update if different
                        changed = False
                        if existing.value != val:
                            existing.value = val
                            changed = True
                        pf = parse_d(vf)
                        pt = parse_d(vt)
                        if existing.valid_from != pf:
                            existing.valid_from = pf
                            changed = True
                        if existing.valid_to != pt:
                            existing.valid_to = pt
                            changed = True
                        if source_url and existing.source_url != source_url:
                            existing.source_url = source_url
                            changed = True
                        if changed:
                            updated += 1
                    else:
                        db.add(
                            Rate(
                                htc_id=htc.id,
                                country_iso="*",
                                rate_type=RateType.PERCENT,
                                value=val,
                                currency=None,
                                unit=None,
                                is_exemption=False,
                                agreement=None,
                                conditions=None,
                                valid_from=parse_d(vf),
                                valid_to=parse_d(vt),
                                source_url=source_url,
                                priority=0,
                            )
                        )
                        added += 1
                    break  # only first percent group for MV
            # landgruppe loop
    if added or updated:
        db.commit()
    return added


def import_customs_duty_from_toll(db: Session, path: Path, source_url: str | None = None) -> int:
    """
    Import ordinary customs duty (MFN) and preferential agreement rates from tollavgiftssats.json.

    JSON structure (simplified):
      {
        "versjon": "...",
        "varer": [
          {
            "id": "25081000",
            "enhet": "Kg",
            "avtalesatser": [
              {"landgruppe": "TAL", "sats": [{"satsVerdi": "0,00", "satsEnhet": "K", "fomdato": "YYYY-MM-DD", "tomdato": ""}]},
              {"landgruppe": "EUE", "sats": [...]},
              ...
            ]
          }
        ]
      }

    Heuristics:
      - Ordinary duty: entries where landgruppe in ("TAL", "ALLE"). Stored with country_iso='*' and agreement=None.
      - Preferential rates: other landgruppe codes. Stored with country_iso='*' and agreement=<landgruppe>.
      - Units:
          satsEnhet == 'P' -> RateType.PERCENT
          satsEnhet == 'K' -> RateType.PER_KG (unit='kg')
          otherwise -> RateType.PER_ITEM
      - Skip sentinel/invalid values (>= 999999.99) and blank unit codes.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    varer = data.get("varer", [])

    def parse_d(d: str | None) -> Optional[date]:
        if not d:
            return None
        try:
            y, m, dd = d.split("-")
            return date(int(y), int(m), int(dd))
        except Exception:
            return None

    def get_htc(code: str) -> Optional[HTC]:
        return db.query(HTC).filter(HTC.code == code).first()

    added = 0
    ordinary_groups = {"TAL", "TALL", "ALLE"}

    for idx, v in enumerate(varer, 1):
        code = str(v.get("id") or "").strip()
        if not code:
            continue
        htc = get_htc(code)
        if not htc:
            # Unknown HTC; skip
            continue

        avtalesatser = v.get("avtalesatser", [])
        for a in avtalesatser:
            landgruppe = (a.get("landgruppe") or "").strip()
            is_ordinary = landgruppe in ordinary_groups
            sats_list = a.get("sats", [])
            for s in sats_list:
                val = _parse_decimal_comma(s.get("satsVerdi"))
                if val is None:
                    continue
                # skip sentinel/placeholder extremely large values
                try:
                    if val >= Decimal("999999.99"):
                        continue
                except Exception:
                    pass

                unit_code = (s.get("satsEnhet") or "").strip()
                if not unit_code:
                    # missing unit; skip
                    continue

                if unit_code == "P":
                    rate_type = RateType.PERCENT
                    unit = None
                    currency = None
                elif unit_code == "K":
                    rate_type = RateType.PER_KG
                    unit = "kg"
                    currency = "NOK"
                else:
                    rate_type = RateType.PER_ITEM
                    unit = None
                    currency = "NOK"

                pf = parse_d(s.get("fomdato") or None)
                pt = parse_d(s.get("tomdato") or None)

                # Prevent duplicates on re-import: match on key fields
                # Try to find existing ordinary entry (agreement=None)
                existing_ordinary = (
                    db.query(Rate)
                    .filter(
                        Rate.htc_id == htc.id,
                        Rate.country_iso == "*",
                        Rate.rate_type == rate_type,
                        Rate.value == val,
                        Rate.valid_from == pf,
                        Rate.valid_to == pt,
                        Rate.agreement == None,
                    )
                    .first()
                )
                if existing_ordinary:
                    continue

                # If this is ordinary but previously stored under landgruppe (e.g., 'TALL'), normalize to agreement=None
                if is_ordinary:
                    existing_grouped = (
                        db.query(Rate)
                        .filter(
                            Rate.htc_id == htc.id,
                            Rate.country_iso == "*",
                            Rate.rate_type == rate_type,
                            Rate.value == val,
                            Rate.valid_from == pf,
                            Rate.valid_to == pt,
                            Rate.agreement == landgruppe,
                        )
                        .first()
                    )
                    if existing_grouped:
                        existing_grouped.agreement = None
                        existing_grouped.priority = 0
                        continue

                # Otherwise add new entry (ordinary or preferential)
                db.add(
                    Rate(
                        htc_id=htc.id,
                        country_iso="*",
                        rate_type=rate_type,
                        value=val,
                        currency=currency,
                        unit=unit,
                        is_exemption=False,
                        agreement=None if is_ordinary else landgruppe,
                        conditions=None,
                        valid_from=pf,
                        valid_to=pt,
                        source_url=source_url,
                        priority=0 if is_ordinary else 10,
                    )
                )
                added += 1

        # Periodic progress logging (useful on hosted platforms like Render)
        try:
            if idx % progress_step == 0 or idx == total_varer:
                print(
                    f"[import-duty] {idx}/{total_varer} HTCs processed, added {added} rates so far.",
                    flush=True,
                )
        except Exception:
            pass

    if added:
        db.commit()
    return added
