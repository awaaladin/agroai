// Bespoke crop illustrations (48x48, line and fill) so the crop picker works for people who read little.
const L = 'fill="rgb(var(--c-leaf))"';
const S = 'fill="rgb(var(--c-sun))"';
const C = 'fill="rgb(var(--c-clay))"';
const wrap = (b) => `<svg viewBox="0 0 48 48" width="1em" height="1em" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${b}</svg>`;

export const CROPS = ['cassava', 'yam', 'maize', 'plantain', 'cocoyam', 'pepper', 'other'];

export const cropIcon = {
  // palmate cassava leaf: five lobes from one point
  cassava: wrap(`<path d="M24 40 V 30" /><path d="M24 30 C 14 28 8 20 6 12 C 16 14 22 20 24 30 Z" ${L}/><path d="M24 30 C 34 28 40 20 42 12 C 32 14 26 20 24 30 Z" ${L}/><path d="M24 30 C 18 22 18 12 24 5 C 30 12 30 22 24 30 Z" ${L}/><path d="M24 30 C 14 32 8 30 4 26 C 10 22 18 24 24 30 Z" ${L}/><path d="M24 30 C 34 32 40 30 44 26 C 38 22 30 24 24 30 Z" ${L}/>`),
  // heart-shaped yam leaf on a vine
  yam: wrap(`<path d="M24 42 C 12 34 6 26 8 18 C 10 10 20 10 24 18 C 28 10 38 10 40 18 C 42 26 36 34 24 42 Z" ${L}/><path d="M24 42 V 18 M24 28 L 15 21 M24 28 L 33 21"/>`),
  // maize cob in husk
  maize: wrap(`<path d="M24 6 C 31 10 33 22 31 34 C 29 40 19 40 17 34 C 15 22 17 10 24 6 Z" ${S}/><path d="M20 14 H 28 M19 20 H 29 M19 26 H 29 M20 32 H 28 M24 8 V 38"/><path d="M17 36 C 8 34 6 24 8 16 C 14 22 17 28 18 36 Z" ${L}/><path d="M31 36 C 40 34 42 24 40 16 C 34 22 31 28 30 36 Z" ${L}/>`),
  // plantain: a bunch of fingers
  plantain: wrap(`<path d="M10 14 C 12 30 26 40 40 38 C 28 34 20 26 18 12 Z" ${S}/><path d="M16 10 C 18 26 30 34 42 32 C 32 28 26 22 24 8 Z" ${S}/><path d="M22 6 C 24 18 32 26 42 26 C 34 22 30 16 30 5 Z" ${S}/><path d="M18 6 C 18 3 26 3 26 6"/>`),
  // cocoyam: big heart leaf on a long stalk
  cocoyam: wrap(`<path d="M24 44 V 22"/><path d="M24 22 C 10 24 4 12 10 6 C 16 2 22 8 24 14 C 26 8 32 2 38 6 C 44 12 38 24 24 22 Z" ${L}/><path d="M24 22 L 24 12 M24 20 L 14 11 M24 20 L 34 11"/>`),
  // chilli pepper
  pepper: wrap(`<path d="M30 10 C 40 14 40 30 24 42 C 14 40 12 24 22 14 C 24 12 28 10 30 10 Z" ${C}/><path d="M30 10 C 31 6 35 5 38 6"/><path d="M26 10 C 26 6 22 4 20 4"/>`),
  other: wrap(`<path d="M8 36 C 8 20 18 8 40 8 C 40 28 30 38 12 38 Z" ${L}/><path d="M12 34 L 28 18"/><path d="M20 22 C 20 18 28 18 28 22 C 28 25 24 25 24 28"/><circle cx="24" cy="31" r="0.8" fill="currentColor"/>`),
};
