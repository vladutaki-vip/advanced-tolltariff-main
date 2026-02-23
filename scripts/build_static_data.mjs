/**
 * Build static data for Netlify: HTC index from tolltariffen JSONs, split large files by chapter.
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
  if (!fs.existsSync(OUT)) fs.mkdirSync(OUT, { recursive: true });
  fs.writeFileSync(path.join(OUT, 'htc_index.json'), JSON.stringify(index), 'utf8');
  console.log('Wrote htc_index.json with', index.length, 'HTCs.');
}

function splitByChapter(filePath, outSubdir) {
  if (!fs.existsSync(filePath)) {
    console.log('Missing', filePath);
    return;
  }
  const data = JSON.parse(fs.readFileSync(filePath, 'utf8'));
  const obj = typeof data === 'object' && data !== null && !Array.isArray(data) ? data : {};
  const byChapter = {};
  for (const [code, value] of Object.entries(obj)) {
    if (code.length >= 2) {
      const ch = code.slice(0, 2);
      if (!byChapter[ch]) byChapter[ch] = {};
      byChapter[ch][code] = value;
    }
  }
  const outDir = path.join(OUT, outSubdir);
  if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });
  for (const [ch, chunk] of Object.entries(byChapter).sort()) {
    fs.writeFileSync(path.join(outDir, ch + '.json'), JSON.stringify(chunk), 'utf8');
  }
  console.log('Wrote', outSubdir, 'with', Object.keys(byChapter).length, 'chapters.');
}

function copyJson(name) {
  const src = path.join(DATA, name);
  if (!fs.existsSync(src)) {
    console.log('Missing', src);
    return;
  }
  if (!fs.existsSync(OUT)) fs.mkdirSync(OUT, { recursive: true });
  fs.copyFileSync(src, path.join(OUT, name));
  console.log('Copied', name);
}

function main() {
  if (!fs.existsSync(OUT)) fs.mkdirSync(OUT, { recursive: true });
  buildHtcIndex();
  splitByChapter(path.join(DATA, 'best_zero_countries.json'), 'best_zero');
  splitByChapter(path.join(DATA, 'ratetradeagreements_index.json'), 'ratetradeagreements');
  copyJson('country_names.json');
  copyJson('landgroups_map.json');
  console.log('Static data build done.');
}

main();
