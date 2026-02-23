/**
 * Static frontend: all data from /data/*.json (tolltariffen + processed). No backend API.
 */
const DATA = '/data';

let htcIndex = null;
let countryNames = null;
let landgroupsMap = null;
const bestOriginCache = {};
const agreementsCache = {};

async function fetchJson(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(url + ' ' + r.status);
  return r.json();
}

async function getHtcIndex() {
  if (htcIndex) return htcIndex;
  htcIndex = await fetchJson(`${DATA}/htc_index.json`);
  return htcIndex;
}

async function getCountryNames() {
  if (countryNames) return countryNames;
  countryNames = await fetchJson(`${DATA}/country_names.json`);
  return countryNames;
}

async function getLandgroupsMap() {
  if (landgroupsMap) return landgroupsMap;
  landgroupsMap = await fetchJson(`${DATA}/landgroups_map.json`);
  return landgroupsMap;
}

function getCountryName(iso) {
  return (countryNames && countryNames[iso]) || iso;
}

function getLandgroupName(code) {
  if (!code) return null;
  const groups = landgroupsMap && landgroupsMap.groups;
  if (groups && groups[code]) return groups[code].name || code;
  const aliases = { EU: 'EUE', EEA: 'TOES', EFTA: 'TEF', GB: 'TUK', IN: 'TIN', MD: 'TMD', GSP: 'TGB', 'GSP+': 'TGSP', 'GSP-LDC': 'TGS1', GCC: 'TGCC', SACU: 'TSAC' };
  const c = aliases[code] || code;
  if (groups && groups[c]) return groups[c].name || c;
  return code;
}

function getLandgroupCountries(code) {
  if (!code) return [];
  const groups = landgroupsMap && landgroupsMap.groups;
  const aliases = { EU: 'EUE', EEA: 'TOES', EFTA: 'TEF', GB: 'TUK', IN: 'TIN', MD: 'TMD', GSP: 'TGB', 'GSP+': 'TGSP', 'GSP-LDC': 'TGS1', GCC: 'TGCC', SACU: 'TSAC' };
  const c = aliases[code] || code;
  const g = groups && groups[c];
  const isoList = (g && g.countries) ? g.countries : [];
  return isoList.map(iso => ({ iso, name: getCountryName(iso) }));
}

// Search HTC by code or name (client-side from htc_index.json)
async function searchHtc(q, limit = 50) {
  const index = await getHtcIndex();
  const lower = (q || '').toLowerCase().trim();
  if (!lower) return index.slice(0, limit);
  const filtered = index.filter(
    h => h.code.includes(lower) || (h.name && h.name.toLowerCase().includes(lower))
  );
  return filtered.slice(0, Math.min(limit, 200));
}

// Best origin: calculează grupurile de țări cu cel mai mic tarif din best_origin/XX.json
async function getBestOrigin(code) {
  if (!code || code.length < 2) return null;
  const ch = code.slice(0, 2);
  if (!bestOriginCache[ch]) {
    try {
      bestOriginCache[ch] = await fetchJson(`${DATA}/best_origin/${ch}.json`);
    } catch {
      return null;
    }
  }
  const entry = bestOriginCache[ch][code];
  if (!entry) return null;

  await getCountryNames();
  await getLandgroupsMap();

  const agreements = Array.isArray(entry.agreements) ? entry.agreements : [];
  if (!agreements.length) {
    return {
      code,
      countries: [],
      info: { message: 'Nu există acorduri preferențiale cu tarif mai mic decât cel de bază.' },
    };
  }

  // Găsim valoarea minimă dintre acorduri (ignorăm cele fără value).
  const numeric = agreements.filter(a => typeof a.value === 'number');
  if (!numeric.length) {
    return { code, countries: [], info: { message: 'Nu există tarife numerice pentru acest cod.' } };
  }
  let minVal = Infinity;
  numeric.forEach(a => {
    if (a.value < minVal) minVal = a.value;
  });
  const bestGroups = numeric.filter(a => a.value === minVal);

  // Extindem grupurile în liste de țări și deduplicăm ISO.
  const allCountries = [];
  bestGroups.forEach(g => {
    const countries = getLandgroupCountries(g.code);
    countries.forEach(c => allCountries.push(c));
  });
  const byIso = new Map();
  allCountries.forEach(c => {
    if (!c || !c.iso) return;
    if (!byIso.has(c.iso)) byIso.set(c.iso, c);
  });

  return {
    code,
    countries: Array.from(byIso.values()),
    info: {
      min_value: minVal,
      unit: bestGroups[0]?.unit || null,
      rate_type: bestGroups[0]?.rate_type || null,
    },
  };
}

// Agreements for HTC from ratetradeagreements/XX.json + landgroups
async function getAgreements(code) {
  if (!code || code.length < 2) return { code, agreements: [] };
  const ch = code.slice(0, 2);
  if (!agreementsCache[ch]) {
    try {
      agreementsCache[ch] = await fetchJson(`${DATA}/ratetradeagreements/${ch}.json`);
    } catch (e) {
      return { code, agreements: [] };
    }
  }
  const entry = agreementsCache[ch][code];
  if (!entry) return { code, agreements: [] };
  await getCountryNames();
  await getLandgroupsMap();
  const agreements = [];
  for (const [classifier, landCodes] of Object.entries(entry)) {
    const groups = (landCodes || []).map(lc => ({
      code: lc,
      name: getLandgroupName(lc),
      countries: getLandgroupCountries(lc),
    }));
    const allCountries = groups.flatMap(g => g.countries);
    const byIso = new Map();
    allCountries.forEach(c => byIso.set(c.iso, c));
    agreements.push({ agreement: classifier, agreement_name: getLandgroupName(classifier) || classifier, countries: Array.from(byIso.values()) });
  }
  return { code, agreements };
}

function renderCountries(container, countries) {
  const list = document.createElement('div');
  list.className = 'country-list';
  (countries || []).forEach(c => {
    const el = document.createElement('span');
    el.className = 'country';
    el.textContent = typeof c === 'object' ? `${c.name || c.iso} (${c.iso})` : c;
    list.appendChild(el);
  });
  container.appendChild(list);
}

function renderBestOrigin(output, data) {
  output.innerHTML = '';
  if (!data) {
    const item = document.createElement('div');
    item.className = 'item';
    item.textContent = 'Nu există date pentru acest cod sau tarif aplicabil.';
    output.appendChild(item);
    return;
  }
  if (!data.countries || !data.countries.length) {
    const item = document.createElement('div');
    item.className = 'item';
    item.textContent = data.info && data.info.message
      ? data.info.message
      : 'Nu există acorduri mai avantajoase decât tariful de bază.';
    output.appendChild(item);
    return;
  }
  const item = document.createElement('div');
  item.className = 'item';
  const h3 = document.createElement('h3');
  h3.textContent = `Țări cu cele mai mici tarife pentru ${data.code}`;
  item.appendChild(h3);
  renderCountries(item, data.countries);
  const meta = document.createElement('div');
  meta.className = 'meta';
  const unitText = data.info && data.info.unit ? ` / ${data.info.unit}` : '';
  meta.textContent = data.info && typeof data.info.min_value === 'number'
    ? `Tarif minim pe grupurile afișate: ${data.info.min_value}${unitText} (${data.info.rate_type || ''}).`
    : 'Acorduri cu cele mai mici tarife vamale disponibile.';
  item.appendChild(meta);
  output.appendChild(item);
}

function renderAgreements(output, data) {
  output.innerHTML = '';
  const items = data.agreements || [];
  if (!items.length) {
    const item = document.createElement('div');
    item.className = 'item';
    item.textContent = data.code ? 'Nu există acorduri preferențiale pentru acest cod.' : 'Introdu un cod HTC.';
    output.appendChild(item);
    return;
  }
  items.forEach(a => {
    const item = document.createElement('div');
    item.className = 'item';
    const h3 = document.createElement('h3');
    h3.textContent = a.agreement_name || a.agreement || 'Acord';
    item.appendChild(h3);
    renderCountries(item, a.countries || []);
    output.appendChild(item);
  });
}

function renderSearch(output, items) {
  output.innerHTML = '';
  items.forEach(htc => {
    const item = document.createElement('div');
    item.className = 'item';
    const h3 = document.createElement('h3');
    h3.textContent = `${htc.code} — ${htc.name || ''}`;
    item.appendChild(h3);
    const meta = document.createElement('div');
    meta.className = 'meta';
    meta.textContent = htc.description || '';
    item.appendChild(meta);
    output.appendChild(item);
  });
}

window.addEventListener('DOMContentLoaded', () => {
  // Preload names for display
  getCountryNames().catch(() => {});
  getLandgroupsMap().catch(() => {});

  const bestForm = document.getElementById('bestForm');
  const bestOutput = document.getElementById('bestOutput');
  bestForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const code = document.getElementById('htcCode').value.trim();
    bestOutput.innerHTML = '<div class="item">Se încarcă…</div>';
    try {
      const data = await getBestOrigin(code);
      renderBestOrigin(bestOutput, data);
    } catch (err) {
      bestOutput.innerHTML = `<div class="item">Eroare: ${err.message}</div>`;
    }
  });

  const agreementsBtn = document.getElementById('agreementsBtn');
  const zeroBtn = document.getElementById('zeroBtn');
  const agreementsOutput = document.getElementById('agreementsOutput');
  const agreementsCode = document.getElementById('agreementsCode');

  agreementsBtn.addEventListener('click', async () => {
    const code = agreementsCode.value.trim();
    agreementsOutput.innerHTML = '<div class="item">Se încarcă…</div>';
    try {
      const data = await getAgreements(code);
      renderAgreements(agreementsOutput, data);
    } catch (err) {
      agreementsOutput.innerHTML = `<div class="item">Eroare: ${err.message}</div>`;
    }
  });

  zeroBtn.addEventListener('click', async () => {
    const code = agreementsCode.value.trim();
    agreementsOutput.innerHTML = '<div class="item">Se încarcă…</div>';
    try {
      const data = await getBestOrigin(code);
      renderAgreements(
        agreementsOutput,
        data && data.countries
          ? { code, agreements: [{ agreement_name: 'Cele mai mici tarife', countries: data.countries }] }
          : { code, agreements: [] }
      );
    } catch (err) {
      agreementsOutput.innerHTML = `<div class="item">Eroare: ${err.message}</div>`;
    }
  });

  const searchBtn = document.getElementById('searchBtn');
  const searchOutput = document.getElementById('searchOutput');
  searchBtn.addEventListener('click', async () => {
    const q = document.getElementById('searchQuery').value.trim();
    searchOutput.innerHTML = '<div class="item">Se încarcă…</div>';
    try {
      const items = await searchHtc(q, 50);
      if (items.length === 0) {
        searchOutput.innerHTML = '<div class="item">Niciun rezultat. Încearcă alt cod sau denumire.</div>';
        return;
      }
      renderSearch(searchOutput, items);
    } catch (err) {
      searchOutput.innerHTML = `<div class="item">Eroare: ${err.message}. Asigură-te că ai rulat build-ul (npm run build) și că fișierele sunt în /data/.</div>`;
    }
  });
});
