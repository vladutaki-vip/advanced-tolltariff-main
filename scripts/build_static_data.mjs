/**
 * Build static data for Netlify from tolltariffen JSONs.
 * - HTC search index from customstariffstructure.json
 * - Best-origin duty per HTC from tollavgiftssats.json
 * - Split ratetradeagreements_index.json by chapter
 * Run from repo root: node scripts/build_static_data.mjs
 */
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, '..');
const DATA_RAW = path.join(REPO_ROOT, 'data', 'raw');
const DATA = path.join(REPO_ROOT, 'data');
const OUT = path.join(REPO_ROOT, 'frontend', 'data');

function ensureOutDir() {
  if (!fs.existsSync(OUT)) fs.mkdirSync(OUT, { recursive: true });
}

// ---------- HTC index (for search) ----------

function walkCommodities(nodes) {
  if (!Array.isArray(nodes)) nodes = nodes ? [nodes] : [];
  const out = [];
  for (const n of nodes) {
    if (!n || typeof n !== 'object') continue;
    if (n.type === 'commodity') {
      const code = String(n.id || n.hsNumber || '').trim();
      const name = String(n.item || '').trim();
      if (code) out.push({ code, name, description: '' });
    }
    for (const key of ['sections', 'chapters', 'divisions', 'headings', 'subchapters']) {
      if (!(key in n)) continue;
      const child = n[key];
      if (Array.isArray(child)) out.push(...walkCommodities(child));
      else if (child != null) out.push(...walkCommodities([child]));
    }
  }
  return out;
}

function buildHtcIndex() {
  const p = path.join(DATA_RAW, 'customstariffstructure.json');
  if (!fs.existsSync(p)) {
    console.log('Missing data/raw/customstariffstructure.json');
    return;
  }
  const data = JSON.parse(fs.readFileSync(p, 'utf8'));
  const commodities = walkCommodities(data.sections || []);
  const seen = new Set();
  const index = [];
  for (const { code, name } of commodities) {
    if (seen.has(code)) continue;
    seen.add(code);
    index.push({ code, name, description: '' });
  }
  ensureOutDir();
  fs.writeFileSync(path.join(OUT, 'htc_index.json'), JSON.stringify(index), 'utf8');
  console.log('Wrote htc_index.json with', index.length, 'HTCs.');
}

// ---------- Helpers for chapter-splitting ----------

function writeByChapter(obj, outSubdir) {
  const byChapter = {};
  for (const [code, value] of Object.entries(obj)) {
    if (!code || code.length < 2) continue;
    const ch = code.slice(0, 2);
    if (!byChapter[ch]) byChapter[ch] = {};
    byChapter[ch][code] = value;
  }
  const outDir = path.join(OUT, outSubdir);
  if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });
  for (const [ch, chunk] of Object.entries(byChapter).sort()) {
    fs.writeFileSync(path.join(outDir, ch + '.json'), JSON.stringify(chunk), 'utf8');
  }
  console.log('Wrote', outSubdir, 'with', Object.keys(byChapter).length, 'chapters.');
}

function splitByChapter(filePath, outSubdir) {
  if (!fs.existsSync(filePath)) {
    console.log('Missing', filePath);
    return;
  }
  const data = JSON.parse(fs.readFileSync(filePath, 'utf8'));
  const obj = typeof data === 'object' && data !== null && !Array.isArray(data) ? data : {};
  writeByChapter(obj, outSubdir);
}

// ---------- Best-origin duty from tollavgiftssats.json ----------

function parseDecimalComma(str) {
  if (str === null || str === undefined) return null;
  let s = String(str)
    .replace(/\u00a0/g, ' ')
    .replace(/\./g, '')
    .replace(',', '.')
    .trim();
  if (!s) return null;
  const v = Number(s);
  if (!isFinite(v)) return null;
  if (v >= 999999.99) return null;
  return v;
}

function buildBestOrigin() {
  const p = path.join(DATA_RAW, 'tollavgiftssats.json');
  if (!fs.existsSync(p)) {
    console.log('Missing data/raw/tollavgiftssats.json');
    return;
  }
  const data = JSON.parse(fs.readFileSync(p, 'utf8'));
  const varer = data.varer || [];
  const ordinaryGroups = new Set(['TAL', 'TALL', 'ALLE']);

  /** @type {Record<string, { ordinary: any, agreements: Record<string, any> }>} */
  const perCode = {};

  for (const v of varer) {
    const code = String(v.id || '').trim();
    if (!code) continue;
    const avtalesatser = Array.isArray(v.avtalesatser) ? v.avtalesatser : [];
    if (!avtalesatser.length) continue;

    if (!perCode[code]) perCode[code] = { ordinary: null, agreements: {} };
    const acc = perCode[code];

    for (const a of avtalesatser) {
      if (!a || typeof a !== 'object') continue;
      const lg = String(a.landgruppe || '').trim();
      if (!lg) continue;
      const isOrdinary = ordinaryGroups.has(lg);
      const satsList = Array.isArray(a.sats) ? a.sats : [];

      for (const s of satsList) {
        if (!s || typeof s !== 'object') continue;
        const val = parseDecimalComma(s.satsVerdi);
        if (val === null) continue;
        const unitCode = String(s.satsEnhet || '').trim();
        if (!unitCode) continue;

        let rateType;
        let unit = null;
        if (unitCode === 'P') {
          rateType = 'percent';
        } else if (unitCode === 'K') {
          rateType = 'per_kg';
          unit = 'kg';
        } else {
          rateType = 'per_item';
        }

        if (isOrdinary) {
          const cur = acc.ordinary;
          if (!cur || val < cur.value) {
            acc.ordinary = { value: val, rate_type: rateType, unit };
          }
        } else {
          const cur = acc.agreements[lg];
          if (!cur || val < cur.value) {
            acc.agreements[lg] = { value: val, rate_type: rateType, unit };
          }
        }
      }
    }
  }

  const bestOrigin = {};
  for (const [code, entry] of Object.entries(perCode)) {
    const agreementsArr = Object.entries(entry.agreements).map(([lg, info]) => ({
      code: lg,
      value: info.value,
      rate_type: info.rate_type,
      unit: info.unit || null,
    }));
    bestOrigin[code] = {
      ordinary: entry.ordinary
        ? {
            value: entry.ordinary.value,
            rate_type: entry.ordinary.rate_type,
            unit: entry.ordinary.unit || null,
          }
        : null,
      agreements: agreementsArr,
    };
  }

  writeByChapter(bestOrigin, 'best_origin');
}

// ---------- Utility: copy small JSONs ----------

function copyJson(name) {
  const src = path.join(DATA, name);
  if (!fs.existsSync(src)) {
    console.log('Missing', src);
    return;
  }
  ensureOutDir();
  fs.copyFileSync(src, path.join(OUT, name));
  console.log('Copied', name);
}

// ---------- Main ----------

function main() {
  ensureOutDir();
  buildHtcIndex();
  buildBestOrigin();
  splitByChapter(path.join(DATA, 'ratetradeagreements_index.json'), 'ratetradeagreements');
  copyJson('country_names.json');
  copyJson('landgroups_map.json');
  console.log('Static data build done.');
}

main();
