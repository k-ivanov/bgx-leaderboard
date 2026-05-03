import { defineConfig } from 'astro/config';
import tailwind from '@astrojs/tailwind';
import vue from '@astrojs/vue';
// NOTE: @astrojs/sitemap disabled in Phase 2 — its build hook errors when
// rehydrating our large (~500+) set of prerendered routes. Phase 4 adds a
// custom sitemap generator as a post-build step. robots.txt already references
// /sitemap-index.xml so the hookup point is set.

// BGX Hard Enduro frontend — Astro SSG.
// Generates static HTML for every URL at build time. Zero JS shipped by default;
// interactive features opt into Vue islands via `client:*` directives.

export default defineConfig({
  // `site` is used by @astrojs/sitemap + <link rel="canonical"> tags. Override
  // via `SITE` env var in production (Railway) — defaults to localhost for dev.
  site: process.env.SITE || 'http://localhost:5001',
  output: 'static',
  trailingSlash: 'ignore',
  build: {
    format: 'directory',
    inlineStylesheets: 'auto',
  },
  integrations: [
    tailwind({ applyBaseStyles: false }),
    vue(),
  ],
  vite: {
    server: {
      proxy: {
        // Dev: the Astro dev server proxies /api/* to the FastAPI backend
        // so `fetch('/api/…')` works the same in dev and in production.
        // Use 127.0.0.1 (not `localhost`): Node ≥17 resolves `localhost`
        // to IPv6 ::1 first, but uvicorn binds IPv4 only by default, so
        // the proxy gets ECONNREFUSED and every /api/track call drops.
        '/api': {
          target: process.env.API_URL || 'http://127.0.0.1:5001',
          changeOrigin: true,
        },
      },
    },
  },
});
