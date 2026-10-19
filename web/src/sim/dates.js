// Campaign dates are plain ISO strings in the save contract so that a save file
// stays readable and diffable. All arithmetic goes through here.

const MS_DAY = 86400000;

export function parseDate(iso) {
  const [y, m, d] = iso.split('-').map(Number);
  return Date.UTC(y, m - 1, d);
}
export function formatDate(ms) {
  const d = new Date(ms);
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, '0')}-${String(d.getUTCDate()).padStart(2, '0')}`;
}
export function addDays(iso, days) { return formatDate(parseDate(iso) + days * MS_DAY); }
export function daysBetween(a, b) { return Math.round((parseDate(b) - parseDate(a)) / MS_DAY); }
export function isOnOrAfter(a, b) { return parseDate(a) >= parseDate(b); }
export function isBefore(a, b) { return parseDate(a) < parseDate(b); }
/** inclusive window test; a null bound is open-ended */
export function inWindow(iso, from, to) {
  if (from && isBefore(iso, from)) return false;
  if (to && isBefore(to, iso)) return false;
  return true;
}
