# Advanced Tolltariff (Norvegia)

Caută coduri HTC (HS) și vezi **țările cu cele mai mici tarife vamale** (inclusiv 0%) și acordurile preferențiale. Datele sunt încărcate din fișierele JSON (tolltariffen și cele din `data/`).

## Funcționalități

- **Căutare HTC** – după cod sau denumire (din `data/raw/customstariffstructure.json`)
- **Țări cu cele mai mici tarife** – afișare țări cu tarif 0% pentru un cod (din `data/best_zero_countries.json`)
- **Acorduri preferențiale** – acorduri și țări per cod (din `data/ratetradeagreements_index.json` + `landgroups_map.json`)

## Deploy gratuit pe Netlify

Proiectul este doar **frontend static** + **date JSON**. Fără backend, fără Docker. Netlify rulează un build care generează `frontend/data/` din sursele din `data/`.

### Pași

1. Conectează repo-ul la Netlify (Import from Git).
2. Netlify folosește `netlify.toml`:
   - **Build command:** `npm run build` (rulează `node scripts/build_static_data.mjs` și generează `frontend/data/`)
   - **Publish directory:** `frontend`
3. Deploy. Site-ul va servi `index.html`, `app.js`, `style.css` și tot ce e în `frontend/data/` (inclusiv `/data/htc_index.json`, `/data/best_zero/XX.json`, etc.).

### Build local (opțional)

Pentru a genera fișierele din `frontend/data/` înainte de push:

```bash
npm run build
```

Necesită Node.js. Scriptul citește din `data/raw/customstariffstructure.json` și din `data/*.json`, scrie în `frontend/data/` (index HTC, fișiere pe capitole pentru best_zero și ratetradeagreements, plus copii pentru `country_names.json` și `landgroups_map.json`).

## Structura datelor

- **data/raw/** – surse tolltariffen (customstariffstructure, tollavgiftssats, etc.)
- **data/** – JSON-uri procesate: best_zero_countries.json, ratetradeagreements_index.json, country_names.json, landgroups_map.json
- **frontend/data/** – generat la build: htc_index.json, best_zero/01.json…, ratetradeagreements/01.json…, plus copii ale country_names și landgroups_map

## Rulare locală (fără backend)

Poți servi doar frontend-ul static:

```bash
cd frontend
npx serve .
```

Deschizi `http://localhost:3000`. Asigură-te că ai rulat `npm run build` din rădăcina proiectului ca să existe `frontend/data/`.

## Backend Python (opțional, doar local)

Dacă vrei API-ul FastAPI și baza SQLite doar pe mașina ta:

```bash
pip install -r requirements.txt
python -m uvicorn tolltariff.api.main:app --reload --port 8001
```

UI-ul vechi este la http://localhost:8001/ui/ (același frontend poate fi servit de Netlify fără backend).
