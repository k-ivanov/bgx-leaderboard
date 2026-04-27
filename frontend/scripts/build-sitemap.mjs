// Post-build sitemap generator.
//
// Walks the dist/ tree, finds every index.html, emits dist/sitemap.xml and
// dist/sitemap-index.xml so robots.txt's Sitemap directive resolves.
//
// We do NOT use @astrojs/sitemap because its build hook errors when
// rehydrating our ~1600-route prerendered set (eng-review note in
// astro.config.mjs). This is a tiny standalone pass that runs after
// `astro build`.

import { readdir, stat, writeFile } from 'node:fs/promises';
import { join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = fileURLToPath(new URL('.', import.meta.url));
const DIST = join(__dirname, '..', 'dist');
const SITE = process.env.SITE?.replace(/\/+$/, '') || 'http://localhost:5001';

// Routes we never want indexed (mirrors robots.txt Disallow).
const EXCLUDED = new Set(['/stats']);

async function walk(dir) {
  const out = [];
  const entries = await readdir(dir, { withFileTypes: true });
  for (const e of entries) {
    const p = join(dir, e.name);
    if (e.isDirectory()) {
      out.push(...(await walk(p)));
    } else if (e.isFile() && e.name === 'index.html') {
      out.push(p);
    }
  }
  return out;
}

function pathToUrl(filePath) {
  // dist/2025/expert/index.html → /2025/expert
  // dist/index.html              → /
  const rel = '/' + relative(DIST, filePath).replace(/\\/g, '/');
  const url = rel.replace(/\/index\.html$/, '');
  return url === '' ? '/' : url;
}

function escapeXml(s) {
  return s.replace(/[<>&'"]/g, (c) => ({
    '<': '&lt;',
    '>': '&gt;',
    '&': '&amp;',
    "'": '&apos;',
    '"': '&quot;',
  })[c]);
}

async function main() {
  let htmlFiles;
  try {
    htmlFiles = await walk(DIST);
  } catch (err) {
    console.error(`[sitemap] dist/ not found at ${DIST}; skipping. (Did you run 'astro build' first?)`);
    process.exit(0);
  }

  const urls = [];
  for (const f of htmlFiles) {
    const url = pathToUrl(f);
    if (EXCLUDED.has(url)) continue;
    const st = await stat(f);
    urls.push({
      loc: SITE + url,
      lastmod: st.mtime.toISOString().slice(0, 10),
    });
  }

  // sitemap.xml — flat list, sufficient under 50k URLs.
  const body = urls
    .map((u) => `  <url>\n    <loc>${escapeXml(u.loc)}</loc>\n    <lastmod>${u.lastmod}</lastmod>\n  </url>`)
    .join('\n');
  const sitemap = `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${body}\n</urlset>\n`;

  const indexBody = `  <sitemap>\n    <loc>${SITE}/sitemap.xml</loc>\n    <lastmod>${new Date().toISOString().slice(0, 10)}</lastmod>\n  </sitemap>`;
  const sitemapIndex = `<?xml version="1.0" encoding="UTF-8"?>\n<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${indexBody}\n</sitemapindex>\n`;

  await writeFile(join(DIST, 'sitemap.xml'), sitemap, 'utf-8');
  await writeFile(join(DIST, 'sitemap-index.xml'), sitemapIndex, 'utf-8');

  // Tally by URL prefix so a regression (e.g. accidentally re-introducing
  // legacy /{year}/{cat}/... pages) shows up in the build log.
  const tally = new Map();
  for (const u of urls) {
    const p = new URL(u.loc).pathname;
    const key = p === '/' ? '/'
      : p.startsWith('/rider/') ? '/rider/*'
      : p.startsWith('/results') ? '/results'
      : p.startsWith('/stats') ? '/stats'
      : p.split('/')[1] ? `/${p.split('/')[1]}/*` : 'other';
    tally.set(key, (tally.get(key) ?? 0) + 1);
  }
  const breakdown = [...tally.entries()]
    .sort((a, b) => b[1] - a[1])
    .map(([k, v]) => `${k}=${v}`)
    .join(', ');
  console.log(`[sitemap] wrote ${urls.length} URLs to dist/sitemap.xml + dist/sitemap-index.xml`);
  console.log(`[sitemap] breakdown: ${breakdown}`);

  // Sanity check: legacy /{year}/{cat}/... URLs were removed in the
  // frontend restructure (see .plans/frontend-restructure.md §T8). If they
  // reappear it means /[year]/... pages were re-added to src/pages/.
  const legacyKeys = [...tally.keys()].filter(k => /^\/\d{4}\/\*$/.test(k));
  if (legacyKeys.length > 0) {
    console.warn(`[sitemap] WARNING: legacy per-year URLs detected: ${legacyKeys.join(', ')}`);
  }
}

main().catch((err) => {
  console.error('[sitemap] failed:', err);
  process.exit(1);
});
