// Formatting helpers for the BGX UI. Locale-agnostic on purpose — all
// user-facing months/days come from the microcopy library or these functions.

/**
 * Format a millisecond duration as `H:MM:SS.CS` or `MM:SS.CS`.
 * Matches the existing FastHTML app's `fmt_ms` behavior.
 * Returns `—` (no-time token) when input is null/undefined.
 */
export function formatTime(ms: number | null | undefined): string {
  if (ms == null) return '—';
  // When ms is a string ("100.00") that slipped through somewhere, coerce safely.
  const msNum = typeof ms === 'number' ? ms : Number(ms);
  if (!Number.isFinite(msNum)) return '—';
  ms = msNum;
  const totalSeconds = Math.floor(ms / 1000);
  const cs = Math.floor((ms % 1000) / 10)
    .toString()
    .padStart(2, '0');
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  const s = seconds.toString().padStart(2, '0');
  const m = minutes.toString().padStart(2, '0');
  if (hours > 0) {
    return `${hours}:${m}:${s}.${cs}`;
  }
  return `${m}:${s}.${cs}`;
}

/**
 * Format an ISO date string to a short table cell (`Apr 18`).
 * Returns `—` for null. Uses English month names regardless of locale
 * (intentional — UI chrome is English per design-review §14).
 */
// Bulgarian month names. Short form uses the conventional 3-letter abbreviations
// with a trailing period where the full word is longer than the stem.
const SHORT_MONTHS = [
  'ян.', 'февр.', 'март', 'апр.', 'май', 'юни',
  'юли', 'авг.', 'септ.', 'окт.', 'ноем.', 'дек.',
];

const LONG_MONTHS = [
  'януари', 'февруари', 'март', 'април', 'май', 'юни',
  'юли', 'август', 'септември', 'октомври', 'ноември', 'декември',
];

export function formatDateShort(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return `${SHORT_MONTHS[d.getUTCMonth()]} ${d.getUTCDate().toString().padStart(2, '0')}`;
}

export function formatDateLong(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return `${LONG_MONTHS[d.getUTCMonth()]} ${d.getUTCDate()}, ${d.getUTCFullYear()}`;
}

/**
 * Did the given ISO date already happen, relative to "now"?
 * Dates without a time default to midnight UTC; if the date is today, it
 * counts as past (races usually finish before the calendar flips).
 */
export function isPast(iso: string | null | undefined, now: Date = new Date()): boolean {
  if (!iso) return false;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return false;
  // Compare calendar day in UTC
  const today = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()));
  const event = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()));
  return event.getTime() < today.getTime();
}

/**
 * Bulgarian-flavored ordinal for race placings ("Най-добро: 1-во").
 * Uses the neuter form (implicit "място"): 1-во, 2-ро, 3-то, 4-то, 5-о, ...
 * Keeps it simple — no full declension table, just the common abbreviated forms.
 */
export function ordinal(n: number): string {
  if (n === 1) return '1-во';
  if (n === 2) return '2-ро';
  if (n === 3) return '3-то';
  if (n === 4) return '4-то';
  if (n === 7) return '7-мо';
  if (n === 8) return '8-мо';
  return `${n}-о`;
}

/**
 * Fallback category display name lookup when only the code is available.
 * The backend returns the canonical `display_name` on CategoryRef — prefer that.
 *
 * Category names kept in English because they are the federation's official
 * class labels ("Expert", "Pro", "Junior" etc.) that match the results CSVs
 * and rider licences. Changing them to Bulgarian here would create a
 * mismatch with the printed materials.
 */
export function categoryDisplayName(code: string, fallback?: string): string {
  const TABLE: Record<string, string> = {
    profi: 'Pro',
    expert: 'Expert',
    standard: 'Standard',
    standard_junior: 'Standard Junior',
    junior: 'Junior',
    women: 'Women',
    seniors_40: 'Senior 40+',
    seniors_50: 'Senior 50+',
  };
  return TABLE[code] ?? fallback ?? code;
}
