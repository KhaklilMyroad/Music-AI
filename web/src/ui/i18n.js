// Localisation with RTL support. Mixed-direction text (a Hebrew sentence with a
// Latin place name or a Latin number) is handled by isolating the embedded run
// rather than reordering it by hand.

import { locales } from '../data.generated.js';

const RLM = '‏', LRM = '‎', FSI = '⁨', PDI = '⁩';

export class I18n {
  constructor(locale = 'en') { this.set(locale); }

  get available() { return Object.keys(locales).map((k) => ({ code: k, name: locales[k]._meta.name, dir: locales[k]._meta.direction })); }

  set(locale) {
    this.locale = locales[locale] ? locale : 'en';
    this.table = locales[this.locale];
    this.dir = this.table._meta.direction;
    document.documentElement.setAttribute('lang', this.locale);
    document.documentElement.setAttribute('dir', this.dir);
    return this.locale;
  }

  /** t('map.cost') -> localised string. A missing key returns the key itself,
   *  visibly, so a gap is caught in review instead of shipping as blank. */
  t(key, vars) {
    let s = this.table[key];
    if (s == null) { console.warn('[i18n] missing key', key, this.locale); return key; }
    if (vars) for (const [k, v] of Object.entries(vars)) s = s.replaceAll(`{${k}}`, this.isolate(v));
    return s;
  }

  has(key) { return this.table[key] != null; }

  /** Wrap an interpolated value so its own direction cannot flip the sentence. */
  isolate(v) { return this.dir === 'rtl' ? `${FSI}${v}${PDI}` : String(v); }

  /** Numbers stay in Latin digits per the locale meta, but get direction marks in RTL. */
  num(n, digits = 0) {
    const s = Number(n).toFixed(digits);
    return this.dir === 'rtl' ? `${LRM}${s}` : s;
  }

  date(iso) {
    const [y, m, d] = iso.split('-').map(Number);
    const months = this.locale === 'he'
      ? ['ינואר', 'פברואר', 'מרץ', 'אפריל', 'מאי', 'יוני', 'יולי', 'אוגוסט', 'ספטמבר', 'אוקטובר', 'נובמבר', 'דצמבר']
      : ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
    return this.locale === 'he' ? `${LRM}${d} ב${months[m - 1]} ${y}` : `${d} ${months[m - 1]} ${y}`;
  }

  /** Signed delta for a report line: direction-safe and sign-explicit. */
  delta(n) { const s = n > 0 ? `+${n}` : `${n}`; return this.dir === 'rtl' ? `${LRM}${s}` : s; }
}

export const i18n = new I18n(
  (typeof localStorage !== 'undefined' && localStorage.getItem('wbtm.locale'))
  || (typeof navigator !== 'undefined' && /^he/.test(navigator.language || '') ? 'he' : 'en')
);
