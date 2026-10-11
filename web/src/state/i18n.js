// i18n through plain JSON dictionaries (src/state/locales/*.json): every UI string and spoken phrase lives there,
// so another language is one new file plus an entry in LANGUAGES.
import en from './locales/en.json';
import pcm from './locales/pcm.json';
import { settings } from './store.js';

const DICTS = { en, pcm };
export const LANGUAGES = [
  { code: 'en', label: 'English', speak: 'English' },
  { code: 'pcm', label: 'Pidgin', speak: 'Pidgin' },
];

/** Look up a dotted key ("home.greeting.morning"), falling back to English, then to the key itself. */
export function t(key, vars = {}) {
  const lang = settings.get().language;
  const find = (d) => key.split('.').reduce((o, k) => (o && typeof o === 'object' ? o[k] : undefined), d);
  let s = find(DICTS[lang]) ?? find(DICTS.en) ?? key;
  if (typeof s !== 'string') return key;
  for (const [k, v] of Object.entries(vars)) s = s.replaceAll(`{${k}}`, v);
  return s;
}

/** Pick one of several variants (for rotating friendly messages), stable per index. */
export function tList(key) {
  const lang = settings.get().language;
  const find = (d) => key.split('.').reduce((o, k) => (o ? o[k] : undefined), d);
  const v = find(DICTS[lang]) ?? find(DICTS.en);
  return Array.isArray(v) ? v : [String(v ?? key)];
}

export const currentLanguage = () => settings.get().language;
