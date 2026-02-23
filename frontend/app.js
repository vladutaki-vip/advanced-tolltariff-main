/**
 * Static frontend: all data from /data/*.json (tolltariffen + processed). No backend API.
 */
const DATA = '/data';

let htcIndex = null;
let countryNames = null;
let landgroupsMap = null;
const bestZeroCache = {};
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

// Best origin: țări cu cele mai mici tarife (zero duty) from best_zero/XX.json
async function getBestZeroCountries(code) {
  if (!code || code.length < 2) return null;
  const ch = code.slice(0, 2);
  if (!bestZeroCache[ch]) {
    try {
      bestZeroCache[ch] = await fetchJson(`${DATA}/best_zero/${ch}.json`);
    } catch (e) {
      return null;
    }
  }
  const entry = bestZeroCache[ch][code];
  return entry ? { code, countries: entry.countries || [] } : null;
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

function fmtCurrency(n) {
  if (n === null || n === undefined) return '-';
  return new Intl.NumberFormat('en-NO', { style: 'currency', currency: 'NOK', maximumFractionDigits: 2 }).format(n);
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
  if (!data || !data.countries) {
    const item = document.createElement('div');
    item.className = 'item';
    item.textContent = data && data.code ? 'Nu există date pentru acest cod sau tarif 0% nu e disponibil.' : 'Introdu un cod HTC și apasă Compute.';
    output.appendChild(item);
    return;
  }
  const item = document.createElement('div');
  item.className = 'item';
  const h3 = document.createElement('h3');
  h3.textContent = `Țări cu cele mai mici tarife (0% vamă) pentru ${data.code}`;
  item.appendChild(h3);
  renderCountries(item, data.countries);
  const meta = document.createElement('div');
  meta.className = 'meta';
  meta.textContent = 'Aceste țări beneficiază de tarif vamal 0% (acorduri preferențiale).';
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
      const data = await getBestZeroCountries(code);
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
      const data = await getBestZeroCountries(code);
      renderAgreements(agreementsOutput, data && data.countries ? { code, agreements: [{ agreement_name: 'Tarif 0%', countries: data.countries }] } : { code, agreements: [] });
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
