from fastapi import FastAPI, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..db import Base, engine, get_db
from .. import models, schemas
from ..data.landgroups import get_landgroup_name, get_landgroup_countries, LANDGROUPS
import json
from pathlib import Path
from ..config import settings

app = FastAPI(title="Advanced Tolltariff API")

# Create tables on startup (dev only). In production, use migrations.
Base.metadata.create_all(bind=engine)

# Serve a simple UI (prefer per-user data dir, fallback to bundled frontend)
frontend_candidates = [settings.data_dir / "frontend", Path("frontend")]  # second for dev
for fe in frontend_candidates:
    try:
        if fe.exists():
            app.mount("/ui", StaticFiles(directory=str(fe), html=True), name="ui")
            break
    except Exception:
        continue

@app.get("/")
def root():
    return RedirectResponse(url="/ui")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/debug/info")
def debug_info(db: Session = Depends(get_db)):
    try:
        htc_count = db.query(models.HTC).count()
        rate_count = db.query(models.Rate).count()
    except Exception:
        htc_count = None
        rate_count = None
    return {
        "database_url": settings.database_url,
        "htc_count": htc_count,
        "rate_count": rate_count,
        "data_dir": str(settings.data_dir),
        "data_dir_exists": settings.data_dir.exists(),
        "frontend_dir_exists": (settings.data_dir / "frontend").exists() or Path("frontend").exists(),
    }

@app.get("/htc", response_model=list[schemas.HTCSummary])
def list_htc(q: str | None = None, limit: int = 20, db: Session = Depends(get_db)):
    query = db.query(models.HTC)
    if q:
        like = f"%{q}%"
        query = query.filter((models.HTC.code.like(like)) | (models.HTC.name.ilike(like)))
    rows = query.order_by(models.HTC.code).limit(max(1, min(limit, 200))).all()
    return [schemas.HTCSummary(code=r.code, name=r.name, description=r.description) for r in rows]

@app.get("/htc/{code}", response_model=schemas.HTC)
def get_htc(code: str, origin_group: str | None = None, db: Session = Depends(get_db)):
    htc = db.query(models.HTC).filter(models.HTC.code == code).first()
    if not htc:
        raise HTTPException(status_code=404, detail="HTC not found")

    # Optionally filter/prioritize by origin_group (landgruppe code). Prefer agreement==origin_group, else ordinary.
    rates_sa = list(htc.rates)
    if origin_group:
        ordinary_groups = {"TAL", "TALL", "ALLE"}
        # Preferential: matching agreement and excluding VAT
        preferred = [
            r for r in rates_sa
            if (r.agreement or "") == origin_group and r.rate_type != models.RateType.PERCENT
        ]
        # Fallback to ordinary duty (exclude VAT), accounting for ordinary groups
        ordinary = [
            r for r in rates_sa
            if (r.agreement is None or r.agreement in ordinary_groups) and r.rate_type != models.RateType.PERCENT
        ]
        rates_sa = preferred or ordinary or rates_sa

    # Map SQLAlchemy -> Pydantic
    return schemas.HTC(
        code=htc.code,
        name=htc.name,
        description=htc.description,
        rates=[
            schemas.Rate(
                country_iso=r.country_iso,
                rate_type=schemas.RateType(r.rate_type.value),
                value=r.value,
                currency=r.currency,
                unit=r.unit,
                is_exemption=r.is_exemption,
                agreement=r.agreement,
                agreement_name=get_landgroup_name(r.agreement),
                conditions=r.conditions,
                valid_from=r.valid_from,
                valid_to=r.valid_to,
            )
            for r in rates_sa
        ],
    )

@app.get("/htc/{code}/zero-duty")
def get_zero_duty_agreements(code: str, db: Session = Depends(get_db)):
    """List agreements that provide zero customs duty for the given HTC (excludes VAT)."""
    htc = db.query(models.HTC).filter(models.HTC.code == code).first()
    if not htc:
        raise HTTPException(status_code=404, detail="HTC not found")
    out = []
    for r in htc.rates:
        if r.rate_type == models.RateType.PERCENT:
            continue
        try:
            if r.value == 0:
                out.append({
                    "agreement": r.agreement,
                    "agreement_name": get_landgroup_name(r.agreement),
                    "countries": get_landgroup_countries(r.agreement),
                    "type": r.rate_type.value,
                    "unit": r.unit,
                    "currency": r.currency,
                })
        except Exception:
            # value is Decimal; fallback conversion
            if float(r.value) == 0.0:
                out.append({
                    "agreement": r.agreement,
                    "agreement_name": get_landgroup_name(r.agreement),
                    "countries": get_landgroup_countries(r.agreement),
                    "type": r.rate_type.value,
                    "unit": r.unit,
                    "currency": r.currency,
                })
    return {"code": htc.code, "zero_duty": out}

@app.get("/htc/{code}/agreements")
def get_agreements(code: str, db: Session = Depends(get_db)):
    """List all agreements (preferential groups) present for the HTC, with country lists.

    Excludes VAT percent rates and ordinary baseline (agreement null / TAL/TALL/ALLE).
    """
    htc = db.query(models.HTC).filter(models.HTC.code == code).first()
    if not htc:
        raise HTTPException(status_code=404, detail="HTC not found")
    seen: dict[str, dict] = {}
    ordinary_groups = {"TAL", "TALL", "ALLE"}
    for r in htc.rates:
        if r.rate_type == models.RateType.PERCENT:
            continue
        if r.agreement is None or r.agreement in ordinary_groups:
            continue
        if r.agreement not in seen:
            seen[r.agreement] = {
                "agreement": r.agreement,
                "agreement_name": get_landgroup_name(r.agreement),
                "countries": get_landgroup_countries(r.agreement),
                "rates": [],
            }
        seen[r.agreement]["rates"].append({
            "type": r.rate_type.value,
            "value": str(r.value),
            "unit": r.unit,
            "currency": r.currency,
        })
    return {"code": htc.code, "agreements": list(seen.values())}

@app.get("/htc/{code}/fta")
def get_fta(code: str):
    """List free trade agreements for the HTC using the ratetradeagreements index, with country lists.
    Shows classifier groups (e.g., FREE) and participating landCodes.
    """
    idx_path = Path("data/ratetradeagreements_index.json")
    if not idx_path.exists():
        raise HTTPException(status_code=404, detail="FTA index not imported")
    idx = json.loads(idx_path.read_text(encoding="utf-8"))
    entry = idx.get(code)
    if not entry:
        return {"code": code, "agreements": []}
    items = []
    for classifier, landCodes in entry.items():
        # landCodes may include named groups (EU, EEA, EFTA, GB, IN, GSP+, GSP-LDC, GCC, SACU, etc.)
        # For known groups, enrich with countries via landgroups; otherwise include landCode as-is.
        groups = []
        for lc in landCodes:
            groups.append({
                "code": lc,
                "name": get_landgroup_name(lc),
                "countries": get_landgroup_countries(lc),
            })
        items.append({"classifier": classifier, "groups": groups})
    return {"code": code, "agreements": items}


@app.get("/htc/{code}/best-origin")
def best_origin(
    code: str,
    weight_kg: float | None = None,
    quantity: int | None = None,
    customs_value_nok: float | None = None,
    flatten: bool = False,
    top_n: int | None = None,
    db: Session = Depends(get_db),
):
    """Compute best origin groups (and countries) for minimal customs duty for an HTC.

    - Excludes VAT; considers customs duty rates only.
    - Computes NOK cost for available rate types when required inputs are present.
      - per_kg requires `weight_kg`
      - per_item requires `quantity`
      - percent requires `customs_value_nok`
    - Zero rates are treated as zero regardless of missing inputs.
    Returns top recommendations sorted by ascending cost.
    """
    htc = db.query(models.HTC).filter(models.HTC.code == code).first()
    if not htc:
        raise HTTPException(status_code=404, detail="HTC not found")

    def compute_cost(r: models.Rate) -> tuple[float | None, str | None]:
        # returns (cost_nok or None, basis)
        if r.rate_type == models.RateType.PERCENT:
            if float(r.value) == 0.0:
                return 0.0, "percent"
            if customs_value_nok is None:
                return None, None
            return float(r.value) / 100.0 * float(customs_value_nok), "percent"
        elif r.rate_type == models.RateType.PER_KG:
            if float(r.value) == 0.0:
                return 0.0, "per_kg"
            if weight_kg is None:
                return None, None
            return float(r.value) * float(weight_kg), "per_kg"
        else:  # PER_ITEM
            if float(r.value) == 0.0:
                return 0.0, "per_item"
            if quantity is None:
                return None, None
            return float(r.value) * float(quantity), "per_item"

    # Aggregate best per agreement (including ordinary baseline as None)
    best_per_group: dict[str | None, dict] = {}
    ordinary_groups = {"TAL", "TALL", "ALLE"}

    for r in htc.rates:
        if r.rate_type == models.RateType.PERCENT:
            # skip VAT percent stored separately (country_iso='*' and no agreement name for VAT)
            # We still include customs duty percent if present; we have no way to distinguish VAT vs duty here except currency/unit.
            # Heuristic: VAT in this system has country_iso='*' and agreement is None; but duty percent can also be None.
            # We'll include PERCENT but caller must provide customs_value_nok.
            pass
        # Determine group code; normalize ordinary
        grp = r.agreement
        if grp in ordinary_groups:
            grp = None

        cost, basis = compute_cost(r)
        # Consider only customs (non-VAT) rates: exclude entries with currency/unit both None and rate_type percent when agreement is None and country '*'
        # This heuristic will still allow percent duty when available.
        if cost is None:
            continue
        cur = best_per_group.get(grp)
        if not cur or cost < cur["cost_nok"]:
            best_per_group[grp] = {
                "agreement": r.agreement,
                "agreement_name": (get_landgroup_name(r.agreement) if r.agreement else "Ordinary (no agreement)"),
                "countries": get_landgroup_countries(r.agreement) if r.agreement else [],
                "rate_type": r.rate_type.value,
                "rate_value": float(r.value),
                "unit": r.unit,
                "currency": r.currency,
                "cost_nok": cost,
                "basis": basis,
            }

    # Sort by ascending cost
    ranked = sorted(best_per_group.values(), key=lambda x: x["cost_nok"])

    # If nothing is computable, provide a helpful hint
    if not ranked:
        return {
            "code": code,
            "recommendations": [],
            "hint": "No computable customs duty. Provide weight_kg, quantity, or customs_value_nok, or import duty rates (tollavgiftssats)."
        }

    # Optionally cut to top N
    if top_n is not None and top_n > 0:
        ranked = ranked[:top_n]

    if flatten:
        # Produce a flattened unique list of countries from selected groups
        seen_iso: set[str] = set()
        flat: list[dict[str, str]] = []
        for rec in ranked:
            for c in rec.get("countries", []) or []:
                iso = c.get("iso")
                if not iso or iso in seen_iso:
                    continue
                seen_iso.add(iso)
                flat.append({"iso": iso, "name": c.get("name") or iso})
        return {"code": code, "countries": flat, "from_groups": [
            {"agreement": r.get("agreement"), "agreement_name": r.get("agreement_name")} for r in ranked
        ]}

    return {"code": code, "recommendations": ranked}

@app.get("/agreements/catalog")
def agreements_catalog(db: Session = Depends(get_db)):
    """List all agreement codes present across the database with occurrence counts and known names."""
    rows = db.query(models.Rate.agreement).filter(models.Rate.agreement != None).all()
    counts: dict[str, int] = {}
    for (code,) in rows:
        if not code:
            continue
        counts[code] = counts.get(code, 0) + 1
    return {
        "agreements": [
            {"code": code, "name": get_landgroup_name(code), "count": count}
            for code, count in sorted(counts.items(), key=lambda kv: kv[0])
        ]
    }
