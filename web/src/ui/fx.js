// Small shared effects. Everything here is optional polish: with reduced motion (OS or in-app switch) the final
// state is shown at once, and no information depends on any of it.
import { t } from '../state/i18n.js';

const reduced = () =>
  matchMedia('(prefers-reduced-motion: reduce)').matches || document.documentElement.dataset.motion === 'reduce';
const easeOut = (x) => 1 - (1 - x) ** 3;
// A small overshoot, like a seed pushing up through soil.
const easeSpring = (x) => 1 + 2.2 * (x - 1) ** 3 + 1.2 * (x - 1) ** 2;

/* ---- Sunrise gauge: "how sure I am" is the sun climbing an arc from the horizon ---------------------------- */
const ARC = { cx: 100, cy: 100, r: 80 };
const sunAt = (p) => {
  const a = Math.PI * (1 - p);
  return [ARC.cx + ARC.r * Math.cos(a), ARC.cy - ARC.r * Math.sin(a)];
};

export function gaugeSvg(label) {
  return `
  <svg class="gauge" viewBox="0 0 200 118" role="img" aria-label="${label}">
    <path class="g-track" pathLength="1" d="M20 100 A80 80 0 0 1 180 100"/>
    <path class="g-fill" pathLength="1" d="M20 100 A80 80 0 0 1 180 100"/>
    <path class="g-ground" d="M4 101 H 196"/>
    <g class="g-tick" aria-hidden="true"><path d="M100 14 V 22 M43 43 L 49 49 M157 43 L 151 49"/></g>
    <g class="g-sun" aria-hidden="true">
      <circle r="11"/>
      <path d="M0 -19 V -15 M0 15 V 19 M-19 0 H -15 M15 0 H 19 M-13 -13 L -10 -10 M13 -13 L 10 -10"/>
    </g>
  </svg>`;
}

/** Animate a gauge from the horizon to p (0 to 1). Returns the element's final value text target if given. */
export function runGauge(svg, p, { ms = 1500, delay = 350, onValue } = {}) {
  const fill = svg.querySelector('.g-fill');
  const sun = svg.querySelector('.g-sun');
  const set = (v) => {
    fill.style.strokeDasharray = '1';
    fill.style.strokeDashoffset = String(1 - v);
    const [x, y] = sunAt(v);
    sun.setAttribute('transform', `translate(${x.toFixed(2)} ${y.toFixed(2)})`);
    onValue?.(v);
  };
  if (reduced()) { set(p); return () => {}; }
  set(0);
  let raf; let start;
  const timer = setTimeout(() => {
    const step = (now) => {
      start ??= now;
      const k = Math.min(1, (now - start) / ms);
      set(Math.max(0, Math.min(1, p * easeSpring(k))));
      if (k < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
  }, delay);
  return () => { clearTimeout(timer); cancelAnimationFrame(raf); };
}

/* ---- Count-up numbers -------------------------------------------------------------------------------------- */
export function countUp(el, to, { ms = 1100, suffix = '' } = {}) {
  if (reduced()) { el.textContent = `${to}${suffix}`; return; }
  let start;
  const step = (now) => {
    start ??= now;
    const k = Math.min(1, (now - start) / ms);
    el.textContent = `${Math.round(to * easeOut(k))}${suffix}`;
    if (k < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

/* ---- Scroll reveal: .sr elements rise in once as they enter the screen; [data-count] numbers count up ------- */
export function watchScroll(root) {
  const items = root.querySelectorAll('.sr, [data-count]');
  if (!items.length) return () => {};
  if (reduced() || !('IntersectionObserver' in window)) {
    items.forEach((el) => {
      el.classList.add('in');
      if (el.dataset.count) el.textContent = `${el.dataset.count}${el.dataset.suffix || ''}`;
    });
    return () => {};
  }
  const io = new IntersectionObserver((entries) => {
    entries.forEach((e) => {
      if (!e.isIntersecting) return;
      io.unobserve(e.target);
      e.target.classList.add('in');
      if (e.target.dataset.count) countUp(e.target, Number(e.target.dataset.count), { suffix: e.target.dataset.suffix || '' });
    });
  }, { rootMargin: '0px 0px -8% 0px', threshold: 0.15 });
  items.forEach((el) => io.observe(el));
  return () => io.disconnect();
}

/* ---- Spotlight: a soft glow follows the pointer inside [data-spot] cards (mouse only) ---------------------- */
export function spotlight(root) {
  if (reduced() || !matchMedia('(hover: hover)').matches) return;
  root.querySelectorAll('[data-spot]').forEach((el) => {
    el.addEventListener('pointermove', (e) => {
      const r = el.getBoundingClientRect();
      el.style.setProperty('--sx', `${e.clientX - r.left}px`);
      el.style.setProperty('--sy', `${e.clientY - r.top}px`);
    });
  });
}

/* ---- "Working" pill: a seedling that sways, shown only if a save or similar takes longer than ~0.5 s -------- */
export function mountBusy() {
  let pending = 0;
  let timer = null;
  let pill = null;
  const show = () => {
    if (pill) return;
    pill = document.createElement('div');
    pill.className = 'busy-pill';
    pill.setAttribute('role', 'status');
    pill.innerHTML = `<svg viewBox="0 0 48 48" width="1.6em" height="1.6em" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" class="busy-seed">
        <path d="M24 42 V 22"/><path d="M24 28 C 14 28 10 20 10 14 C 18 14 24 20 24 28 Z" fill="rgb(var(--c-leaf))"/><path d="M24 22 C 32 22 38 16 38 8 C 30 8 24 14 24 22 Z" fill="rgb(var(--c-leaf))"/></svg>
      <span>${t('auth.working')}</span>`;
    document.body.appendChild(pill);
  };
  const hide = () => { clearTimeout(timer); timer = null; pill?.remove(); pill = null; };
  window.addEventListener('api:busy', (e) => {
    pending = Math.max(0, pending + e.detail);
    if (pending > 0 && !timer && !pill) timer = setTimeout(show, 550);
    if (pending === 0) hide();
  });
}
