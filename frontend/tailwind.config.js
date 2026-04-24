/** @type {import('tailwindcss').Config} */
// BGX tokens — extracted from design-review.md §3.1–§3.6.
// As of the light-theme toggle, colors are CSS variables (set in global.css)
// so the same utility classes (bg-bg-base, text-fg, border-border, …) work in
// both themes. The variables swap based on `<html class="dark">`.

export default {
  content: ['./src/**/*.{astro,html,vue,ts,tsx,md,mdx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        bg: {
          base: 'var(--color-bg-base)',
          elevated: 'var(--color-bg-elevated)',
          muted: 'var(--color-bg-muted)',
        },
        border: {
          DEFAULT: 'var(--color-border)',
          muted: 'var(--color-border-muted)',
        },
        fg: {
          DEFAULT: 'var(--color-fg)',
          muted: 'var(--color-fg-muted)',
          faint: 'var(--color-fg-faint)',
        },
        accent: {
          DEFAULT: 'var(--color-accent)',
          strong: 'var(--color-accent-strong)',
          soft: 'var(--color-accent-soft)',
        },
        podium: {
          gold: 'var(--color-podium-gold)',
          silver: 'var(--color-podium-silver)',
          bronze: 'var(--color-podium-bronze)',
        },
        danger: 'var(--color-danger)',
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
