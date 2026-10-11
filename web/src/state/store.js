// Small reactive settings store. Persists to localStorage (wrapped: storage can be blocked) and applies the
// visual settings (theme, text size, motion) to <html> immediately. Everything else reads from here.

const KEY = 'agroai.settings';

/** @typedef {{language:'en'|'pcm', theme:'light'|'dark'|'contrast', textScale:number, reduceMotion:boolean,
 *   autoRead:boolean, speechRate:number, voiceURI:string, voiceGender:'female'|'male'|'any', sound:boolean, haptics:boolean, town:string,
 *   onboarded:boolean, screenReader:boolean, perms:Record<string,string>, lat:number|null, lon:number|null,
 *   locationSource:''|'gps'|'town', guest:boolean}} Settings */

/** @type {Settings} */
const DEFAULTS = {
  language: 'en', theme: 'light', textScale: 1, reduceMotion: false, autoRead: true, speechRate: 0.95,
  voiceURI: '', voiceGender: 'female', sound: true, haptics: true, town: '', onboarded: false, guest: false,
  // Permission outcomes ('granted' | 'denied' | 'skipped') and the coarse farm location (rounded to 2 decimals).
  perms: {}, lat: null, lon: null, locationSource: '',
  // "I use a screen reader": never auto-speak, so the app does not talk over it.
  screenReader: false,
};

const listeners = new Set();
let state = { ...DEFAULTS };

function load() {
  try {
    const saved = JSON.parse(localStorage.getItem(KEY) || '{}');
    state = { ...DEFAULTS, ...saved };
  } catch { /* private mode or blocked storage: run on defaults for this visit */ }
  // First visit: follow the system dark setting unless the user chose a theme.
  if (!localStorage.getItem?.(KEY) && window.matchMedia?.('(prefers-color-scheme: dark)').matches) state.theme = 'dark';
  apply();
}

function apply() {
  const root = document.documentElement;
  root.dataset.theme = state.theme;
  root.style.setProperty('--text-scale', String(state.textScale));
  if (state.reduceMotion) root.dataset.motion = 'reduce'; else delete root.dataset.motion;
  root.lang = state.language === 'pcm' ? 'en-NG' : 'en';
}

export const settings = {
  get: () => state,
  /** @param {Partial<Settings>} patch */
  set(patch) {
    state = { ...state, ...patch };
    try { localStorage.setItem(KEY, JSON.stringify(state)); } catch { /* ignore */ }
    apply();
    listeners.forEach((fn) => fn(state));
  },
  subscribe(fn) { listeners.add(fn); return () => listeners.delete(fn); },
};

load();
