// Animated weather icons (CSS keyframes in animations.css): sun rays rotate slowly, rain drops fall, clouds drift.
// WMO weather codes -> one of eight kinds, each with a word in both languages (never colour or icon alone).

/** @param {number} code WMO weather code @returns {'clear'|'partly'|'cloudy'|'fog'|'drizzle'|'rain'|'showers'|'storm'} */
export function kindOf(code) {
  if (code === 0) return 'clear';
  if (code === 1 || code === 2) return 'partly';
  if (code === 3) return 'cloudy';
  if (code === 45 || code === 48) return 'fog';
  if (code >= 51 && code <= 57) return 'drizzle';
  if ((code >= 61 && code <= 67) || (code >= 71 && code <= 77)) return 'rain';
  if (code >= 80 && code <= 86) return 'showers';
  if (code >= 95) return 'storm';
  return 'cloudy';
}

const SUN = `<g class="wx-rays" stroke="rgb(var(--c-sun))" stroke-width="3" stroke-linecap="round"><path d="M24 3 V9 M24 39 V45 M3 24 H9 M39 24 H45 M9 9 L13 13 M35 35 L39 39 M9 39 L13 35 M35 13 L39 9"/></g><circle cx="24" cy="24" r="9" fill="rgb(var(--c-sun))" stroke="rgb(var(--c-ink))" stroke-width="2"/>`;
const CLOUD = (y = 0) => `<g class="wx-cloud"><path d="M14 ${34 + y} C 7 ${34 + y} 7 ${24 + y} 14 ${24 + y} C 15 ${15 + y} 28 ${14 + y} 30 ${22 + y} C 38 ${21 + y} 40 ${34 + y} 33 ${34 + y} Z" fill="rgb(var(--c-surface))" stroke="rgb(var(--c-ink))" stroke-width="2.2" stroke-linejoin="round"/></g>`;
const DROPS = (n = 3) => [0, 1, 2, 3].slice(0, n).map((i) => `<path class="wx-drop" style="--i:${i}" d="M${15 + i * 6} 38 l-1.6 4" stroke="rgb(var(--c-leaf))" stroke-width="3" stroke-linecap="round"/>`).join('');

const BODY = {
  clear: SUN,
  partly: `<g transform="translate(6 -4) scale(.8)">${SUN}</g>${CLOUD(2)}`,
  cloudy: `${CLOUD(-2)}<g transform="translate(6 6) scale(.9)" opacity=".7">${CLOUD(0)}</g>`,
  fog: `${CLOUD(-4)}<path d="M10 38 H 38 M14 43 H 34" stroke="rgb(var(--c-ink-soft))" stroke-width="2.6" stroke-linecap="round"/>`,
  drizzle: `${CLOUD(-4)}${DROPS(2)}`,
  rain: `${CLOUD(-4)}${DROPS(4)}`,
  showers: `<g transform="translate(8 -6) scale(.7)">${SUN}</g>${CLOUD(-2)}${DROPS(3)}`,
  storm: `${CLOUD(-4)}<path class="wx-bolt" d="M25 30 L 19 40 H 25 L 22 47 L 32 35 H 26 Z" fill="rgb(var(--c-sun))" stroke="rgb(var(--c-ink))" stroke-width="1.6" stroke-linejoin="round"/>`,
};

/** @param {number} code @param {string} [label] accessible name */
export function weatherIcon(code, label = '') {
  const k = kindOf(code);
  return `<svg class="wx wx-${k}" viewBox="0 0 48 48" width="1em" height="1em" fill="none" role="${label ? 'img' : 'presentation'}" ${label ? `aria-label="${label}"` : 'aria-hidden="true"'} focusable="false">${BODY[k]}</svg>`;
}
