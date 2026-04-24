/** @type {import('tailwindcss').Config} */
// BGX tokens — extracted from design-review.md §3.1–§3.6.
// Any change here is a design-system change and must update design-review.md.

export default {
  content: ['./src/**/*.{astro,html,vue,ts,tsx,md,mdx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Surfaces — stacked for depth without shadows (flat-dark aesthetic)
        bg: {
          base: '#0b0d10',       // page background
          elevated: '#14171c',   // cards, nav, containers
          muted: '#1a1f26',      // table headers, chips, year-switcher track
        },
        border: {
          DEFAULT: '#242932',    // card borders, dividers
          muted: '#1d2128',      // table row dividers
        },
        // Foreground palette
        fg: {
          DEFAULT: '#e7ebef',    // body text, rider names
          muted: '#8891a0',      // secondary text, meta
          faint: '#5a6472',      // labels, footer (never primary body text — contrast 3.2:1)
        },
        // Primary accent — gold/amber (one accent, no secondary colors)
        accent: {
          DEFAULT: '#f59e0b',
          strong: '#fbbf24',
          soft: 'rgba(245, 158, 11, 0.12)',
        },
        // Podium metallics — ONLY for 1st/2nd/3rd indicators, never decorative
        podium: {
          gold: '#fbbf24',
          silver: '#cbd5e1',
          bronze: '#f97316',
        },
        danger: '#ef4444',
      },
      fontFamily: {
        sans: ["'Inter Variable'", '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
        mono: ["'JetBrains Mono Variable'", 'ui-monospace', 'monospace'],
      },
      maxWidth: {
        container: '1200px',
      },
      borderRadius: {
        pill: '9999px',
      },
      fontSize: {
        // Small table header / stat label sizes from the current CSS
        'xs-wide': ['11px', { letterSpacing: '0.06em' }],
      },
      boxShadow: {
        // Deliberately minimal — flat-dark look uses borders, not shadows
        none: 'none',
      },
      transitionDuration: {
        DEFAULT: '150ms',
      },
    },
  },
  plugins: [],
};
