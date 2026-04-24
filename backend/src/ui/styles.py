"""Shared CSS for the redesigned dashboard."""

from fasthtml.common import Style


def base_styles():
    return Style(
        """
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

        :root {
            --bg: #0b0d10;
            --bg-elevated: #14171c;
            --bg-muted: #1a1f26;
            --border: #242932;
            --border-muted: #1d2128;
            --text: #e7ebef;
            --text-muted: #8891a0;
            --text-faint: #5a6472;
            --accent: #f59e0b;
            --accent-soft: rgba(245, 158, 11, 0.12);
            --accent-strong: #fbbf24;
            --gold: #fbbf24;
            --silver: #cbd5e1;
            --bronze: #f97316;
            --danger: #ef4444;
        }

        * { box-sizing: border-box; }
        html, body { margin: 0; padding: 0; }

        body {
            background: var(--bg);
            color: var(--text);
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            font-feature-settings: 'cv11', 'ss01';
            -webkit-font-smoothing: antialiased;
        }

        .mono { font-family: 'JetBrains Mono', ui-monospace, monospace; font-variant-numeric: tabular-nums; }
        .num { font-variant-numeric: tabular-nums; }

        a { color: var(--text); text-decoration: none; }
        a:hover { color: var(--accent); }

        .nav {
            border-bottom: 1px solid var(--border);
            background: rgba(11, 13, 16, 0.92);
            backdrop-filter: saturate(160%) blur(12px);
            position: sticky; top: 0; z-index: 20;
        }
        .nav-inner {
            max-width: 1200px; margin: 0 auto; padding: 14px 24px;
            display: flex; align-items: center; justify-content: space-between; gap: 24px;
        }
        .brand { font-weight: 800; letter-spacing: -0.01em; font-size: 15px; }
        .brand .dot { color: var(--accent); }

        .year-switcher { display: flex; gap: 4px; background: var(--bg-muted); padding: 4px; border-radius: 999px; border: 1px solid var(--border); }
        .year-switcher a {
            padding: 6px 14px; border-radius: 999px; font-size: 13px; font-weight: 600;
            color: var(--text-muted); transition: all 0.15s ease;
        }
        .year-switcher a.active { background: var(--accent); color: #0b0d10; }
        .year-switcher a:hover:not(.active) { color: var(--text); }

        .nav-links { display: flex; gap: 16px; font-size: 13px; color: var(--text-muted); }
        .nav-links a.active { color: var(--text); }

        .container { max-width: 1200px; margin: 0 auto; padding: 32px 24px; }

        .page-header { margin-bottom: 32px; }
        .page-header h1 { margin: 0 0 8px 0; font-size: 32px; font-weight: 800; letter-spacing: -0.02em; }
        .page-header p { margin: 0; color: var(--text-muted); font-size: 15px; }

        .event-buttons { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
        .event-btn {
            display: inline-flex; align-items: center; gap: 8px;
            padding: 8px 14px; border-radius: 8px; font-size: 13px; font-weight: 600;
            background: var(--bg-elevated); border: 1px solid var(--border); color: var(--text-muted);
            transition: all 0.15s ease;
        }
        .event-btn:hover { border-color: var(--accent); color: var(--text); }
        .event-btn.active { background: var(--accent-soft); border-color: var(--accent); color: var(--accent-strong); }
        .event-btn-num {
            font-family: 'JetBrains Mono', ui-monospace, monospace;
            font-size: 11px; color: var(--text-faint); letter-spacing: 0.04em;
        }
        .event-btn.active .event-btn-num { color: var(--accent); }
        .event-btn-name { letter-spacing: -0.005em; }

        .category-tabs { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 24px; }
        .category-tab {
            padding: 8px 16px; border-radius: 8px; font-size: 13px; font-weight: 600;
            background: var(--bg-elevated); border: 1px solid var(--border); color: var(--text-muted);
            transition: all 0.15s ease;
        }
        .category-tab:hover { border-color: var(--accent); color: var(--text); }
        .category-tab.active { background: var(--accent); border-color: var(--accent); color: #0b0d10; }

        .card {
            background: var(--bg-elevated); border: 1px solid var(--border); border-radius: 12px;
            overflow: hidden;
        }
        .card-header {
            padding: 18px 20px; border-bottom: 1px solid var(--border);
            display: flex; align-items: baseline; justify-content: space-between; gap: 16px;
        }
        .card-header h2 { margin: 0; font-size: 18px; font-weight: 700; letter-spacing: -0.01em; }
        .card-header .sub { color: var(--text-muted); font-size: 13px; }

        .stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-bottom: 24px; }
        .stat {
            background: var(--bg-elevated); border: 1px solid var(--border); border-radius: 10px;
            padding: 16px 18px;
        }
        .stat .label { font-size: 11px; text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-faint); margin-bottom: 6px; }
        .stat .value { font-size: 24px; font-weight: 700; letter-spacing: -0.01em; }

        table { width: 100%; border-collapse: collapse; font-size: 14px; }
        th {
            text-align: left; font-weight: 600; font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase;
            color: var(--text-faint); padding: 12px 14px; border-bottom: 1px solid var(--border);
            background: var(--bg-muted); position: sticky; top: 0;
        }
        td { padding: 14px; border-bottom: 1px solid var(--border-muted); }
        tr:hover td { background: rgba(245, 158, 11, 0.03); }
        td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
        td.center, th.center { text-align: center; }

        .pos {
            display: inline-flex; align-items: center; justify-content: center;
            width: 30px; height: 30px; border-radius: 8px; font-weight: 700; font-size: 13px;
            background: var(--bg-muted); color: var(--text-muted);
        }
        .pos-1 { background: rgba(251, 191, 36, 0.14); color: var(--gold); }
        .pos-2 { background: rgba(203, 213, 225, 0.12); color: var(--silver); }
        .pos-3 { background: rgba(249, 115, 22, 0.14); color: var(--bronze); }
        .pos-dnf { color: var(--text-faint); font-size: 11px; width: auto; padding: 0 10px; }

        .points {
            display: inline-block; padding: 3px 10px; border-radius: 999px; font-weight: 600; font-size: 12px;
            background: var(--accent-soft); color: var(--accent-strong);
        }
        .points-25 { background: rgba(251, 191, 36, 0.16); color: var(--gold); }
        .points-0 { background: transparent; color: var(--text-faint); }
        .score { color: var(--text); }
        .score-dim { color: var(--text-faint); }

        .rider-name { font-weight: 500; }
        .rider-meta { font-size: 12px; color: var(--text-muted); }

        .badge {
            display: inline-block; padding: 3px 8px; border-radius: 6px; font-size: 11px;
            font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em;
            background: var(--bg-muted); color: var(--text-muted); border: 1px solid var(--border);
        }
        .badge-accent { background: var(--accent-soft); color: var(--accent-strong); border-color: transparent; }

        .empty { padding: 48px 24px; text-align: center; color: var(--text-muted); font-size: 14px; }

        .footer { border-top: 1px solid var(--border); padding: 24px; text-align: center; color: var(--text-faint); font-size: 12px; }

        .scrollx { overflow-x: auto; }

        .event-link { color: var(--text-muted); text-decoration: none; display: inline-block; }
        .event-link:hover { color: var(--accent); }

        .kv { display: grid; grid-template-columns: auto 1fr; gap: 4px 16px; font-size: 13px; }
        .kv dt { color: var(--text-faint); text-transform: uppercase; letter-spacing: 0.06em; font-size: 11px; padding-top: 2px; }
        .kv dd { margin: 0; font-variant-numeric: tabular-nums; }

        @media (max-width: 720px) {
            .container { padding: 20px 16px; }
            .page-header h1 { font-size: 24px; }
            .nav-inner { padding: 12px 16px; flex-wrap: wrap; gap: 12px; }
            .stat .value { font-size: 20px; }
        }
        """
    )
