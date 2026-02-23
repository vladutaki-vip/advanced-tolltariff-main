from decimal import Decimal
from datetime import date
import typer
from sqlalchemy.orm import Session

from .db import Base, engine, SessionLocal
from .models import HTC, Rate, RateType
from pathlib import Path
from .etl.opendata import fetch_structure_json, fetch_import_fees_json, RAW_DIR, fetch_landgroups_json, fetch_fta_json
from .etl.structure_import import import_structure_json
from .etl.rates_import import import_default_rates_from_fees, import_customs_duty_from_toll
from .models import Rate
from .data.landgroups import LANDGROUPS, get_landgroup_countries
from .etl.landgroups_import import import_landgroups_json
from .etl.fta_import import import_fta

app = typer.Typer(help="CLI pentru Advanced Tolltariff")

@app.command()
def ingest_sample():
    """Comandă stub pentru ingestie (demo)."""
    typer.echo("Ingestie demo – de implementat după confirmarea sursei.")


@app.command("seed-demo")
def seed_demo():
    """Populează DB cu un exemplu minim pentru testare API."""
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    try:
        code = "0101.21"
        htc = db.query(HTC).filter(HTC.code == code).first()
        if not htc:
            htc = HTC(code=code, name="Live horses", description="Pure-bred breeding animals")
            db.add(htc)
            db.flush()

        # MFN example: 10% ad valorem for all countries (not real data)
        existing = db.query(Rate).filter(Rate.htc_id == htc.id, Rate.country_iso == "*", Rate.rate_type == RateType.PERCENT).first()
        if not existing:
            db.add(
                Rate(
                    htc_id=htc.id,
                    country_iso="*",  # wildcard = all
                    rate_type=RateType.PERCENT,
                    value=Decimal("10.0"),
                    is_exemption=False,
                    source_url="demo",
                )
            )

        # Example exemption: EU (use NO pseudo-country groups later)
        existing2 = db.query(Rate).filter(Rate.htc_id == htc.id, Rate.country_iso == "EU", Rate.rate_type == RateType.PERCENT).first()
        if not existing2:
            db.add(
                Rate(
                    htc_id=htc.id,
                    country_iso="EU",
                    rate_type=RateType.PERCENT,
                    value=Decimal("0.0"),
                    is_exemption=True,
                    agreement="EEA/EU",
                    source_url="demo",
                )
            )

        db.commit()
        typer.echo("Seed demo complet. Cod: 0101.21 cu rate MFN si exceptie EU.")
    finally:
        db.close()


@app.command("fetch-opendata")
def fetch_opendata():
    """Descarcă resursele principale din portalul Open Data (structura tarifului)."""
    path = fetch_structure_json()
    typer.echo(f"Am descărcat structura: {path}")


@app.command("fetch-import-fees")
def fetch_import_fees():
    """Descarcă "innfoerselsavgift.json" (avgifter la import) pentru rate implicite."""
    path = fetch_import_fees_json()
    typer.echo(f"Am descărcat innfoerselsavgift: {path}")

@app.command("import-structure")
def import_structure(file: str | None = typer.Option(None, "--file", help="Calea către customstariffstructure.json")):
    """Importă structura tarifului (HTC) din JSON în baza de date."""
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    try:
        from pathlib import Path

        if file:
            path = Path(file)
        else:
            # Prefer local raw file if present to avoid network on hosted envs
            local = RAW_DIR / "customstariffstructure.json"
            path = local if local.exists() else fetch_structure_json()
        if not path.exists():
            raise typer.Exit(code=1)

        added = import_structure_json(db, path)
        typer.echo(f"Import structura finalizat. HTC noi adăugate: {added}.")
    finally:
        db.close()


@app.command("scan-agreements")
def scan_agreements(out: str = typer.Option("data/landgroups_catalog.json", help="Output JSON path")):
    """Scanează DB pentru toate codurile de landgruppe (agreements) prezente și produce un catalog JSON.

    Include frecvența pe HTCurile afectate și marchează dacă există mapping de nume.
    """
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    try:
        rows = db.query(Rate.agreement).filter(Rate.agreement != None).all()
        codes = {}
        for (code,) in rows:
            if not code:
                continue
            codes.setdefault(code, {"name": LANDGROUPS.get(code), "count": 0})
            codes[code]["count"] += 1
        import json
        from pathlib import Path
        Path(out).write_text(json.dumps({"agreements": codes}, ensure_ascii=False, indent=2), encoding="utf-8")
        typer.echo(f"Catalog salvat: {out} (agreements: {len(codes)})")
    finally:
        db.close()


@app.command("fetch-landgroups")
def fetch_landgroups():
    """Descarcă landgruppe.json (country groups)."""
    path = fetch_landgroups_json()
    typer.echo(f"Am descărcat landgrupper: {path}")

@app.command("fetch-fta")
def fetch_fta():
    """Descarcă ratetradeagreements.json (free trade agreements per HTC)."""
    path = fetch_fta_json()
    typer.echo(f"Am descărcat FTA: {path}")


@app.command("import-landgroups")
def import_landgroups(file: str | None = typer.Option(None, "--file", help="Calea către landgruppe.json")):
    """Importă landgruppe -> countries mapping și salvează în data/landgroups_map.json.

    API-ul va folosi acest fișier pentru a afișa nume și țări pentru fiecare agreement.
    """
    if file:
        path = Path(file)
    else:
        path = RAW_DIR / "landgruppe.json"
    if not path.exists():
        typer.echo(f"Fișierul nu există: {path}. Rulați întâi fetch-landgroups sau furnizați --file.")
        raise typer.Exit(code=1)
    out = import_landgroups_json(path)
    typer.echo(f"Import landgrupper finalizat: {out}")

@app.command("import-fta")
def import_fta_cmd(file: str | None = typer.Option(None, "--file", help="Calea către ratetradeagreements.json")):
    """Importă free trade agreements per HTC și scrie indexul în data/ratetradeagreements_index.json"""
    from pathlib import Path
    if file:
        path = Path(file)
    else:
        path = RAW_DIR / "ratetradeagreements.json"
    if not path.exists():
        typer.echo(f"Fișierul nu există: {path}. Rulați întâi fetch-fta sau furnizați --file.")
        raise typer.Exit(code=1)
    out = import_fta(path)
    typer.echo(f"Import FTA finalizat: {out}")


@app.command("export-best-zero")
def export_best_zero(out: str = typer.Option("data/best_zero_countries.json", help="Output JSON path for best zero-duty by HTC")):
    """Exportă, pentru fiecare HTC, lista de țări potențiale cu taxă vamală zero (excluzând TVA),
    derivată din landgruppe -> countries.

    Dacă un landgruppe nu are mapare de țări, nu va contribui la listă.
    """
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    try:
        import json
        from collections import defaultdict
        from pathlib import Path
        # Build per-HTC zero groups
        from .models import HTC, Rate, RateType
        result = {}
        htcs = db.query(HTC).order_by(HTC.code).all()
        for h in htcs:
            zero_groups = set()
            for r in h.rates:
                if r.rate_type == RateType.PERCENT:
                    continue
                # value is Decimal
                if float(r.value) == 0.0 and r.agreement:
                    zero_groups.add(r.agreement)
            countries = []
            for g in sorted(zero_groups):
                for c in get_landgroup_countries(g):
                    countries.append(c)
            if countries:
                result[h.code] = {"countries": countries}
        Path(out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        typer.echo(f"Best zero countries exportat: {out} (HTC-uri: {len(result)})")
    finally:
        db.close()

@app.command("import-default-rates")
def import_default_rates(file: str | None = typer.Option(None, "--file", help="Calea către innfoerselsavgift.json")):
    """Importă rata implicită (MV % din valoare) pentru fiecare cod din JSON.

    Heuristic: landgruppe=ALLE, avgiftstype=MV, enhet=P
    """
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    try:
        if file:
            path = Path(file)
        else:
            # Prefer local raw file if present
            local = RAW_DIR / "innfoerselsavgift.json"
            path = local if local.exists() else fetch_import_fees_json()
        if not path.exists():
            raise typer.Exit(code=1)
        added = import_default_rates_from_fees(db, path, source_url=str(path))
        typer.echo(f"Import rate implicite finalizat. Rate noi adăugate: {added}.")
    finally:
        db.close()


@app.command("import-duty-rates")
def import_duty_rates(file: str | None = typer.Option(None, "--file", help="Calea către tollavgiftssats.json")):
    """Importă taxele vamale (MFN) și ratele preferențiale din tollavgiftssats.json.

    Stochează taxa ordinară cu `country_iso='*'` și ratele preferențiale cu `agreement=<landgruppe>`.
    """
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    try:
        if file:
            path = Path(file)
        else:
            path = RAW_DIR / "tollavgiftssats.json"
        if not path.exists():
            typer.echo(f"Fișierul nu există: {path}. Furnizați calea cu --file.")
            raise typer.Exit(code=1)

        added = import_customs_duty_from_toll(db, path, source_url=str(path))
        typer.echo(f"Import taxe vamale finalizat. Rate noi adăugate: {added}.")
    finally:
        db.close()

    

if __name__ == "__main__":
    app()
