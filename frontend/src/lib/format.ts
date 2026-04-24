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
const SHORT_MONTHS = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
];

const LONG_MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
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
 * Convert an integer position (1st, 2nd, 3rd, …) to its ordinal string.
 * Used on rider page header ("Best: 1st").
 */
export function ordinal(n: number): string {
  if (n >= 11 && n <= 13) return `${n}th`;
  const last = n % 10;
  if (last === 1) return `${n}st`;
  if (last === 2) return `${n}nd`;
  if (last === 3) return `${n}rd`;
  return `${n}th`;
}

/**
 * Canonical per-category display name lookup. The backend already returns
 * `display_name` on CategoryRef, so this is used only as a fallback when
 * a caller has just the code.
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
