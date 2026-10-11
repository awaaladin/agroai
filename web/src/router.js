// Small hash router. Screens are lazy-loaded modules (own chunk each) exporting
//   render(host, ctx) -> optional cleanup function
// Page changes use the View Transitions API when present, otherwise a plain fade-slide (.page-enter).
const routes = new Map();
let guard = null;
let hostEl = null;
let cleanup = null;
let navToken = 0;

/** @param {string} path e.g. '/home' @param {() => Promise<{render:Function}>} loader */
export function route(path, loader) { routes.set(path, loader); }

export function currentPath() {
  const h = location.hash.replace(/^#/, '') || '/';
  return h.split('?')[0];
}
export function query() { return new URLSearchParams((location.hash.split('?')[1]) || ''); }

export function go(path, { replace = false } = {}) {
  if (replace) location.replace(`#${path}`); else location.hash = path;
}

/**
 * Navigate with a shared-element morph: the pressed element and the next screen's `.morph-target` share a
 * view-transition-name, so the card visually grows into the new page's heading.
 */
export function morph(el, path) {
  document.querySelectorAll('[style*="view-transition-name"]').forEach((n) => { n.style.viewTransitionName = ''; });
  el.style.viewTransitionName = 'morph';
  go(path);
}

/** @param {(path:string)=>string|null} fn return a path to redirect to, or null to allow */
export function setGuard(fn) { guard = fn; }
/** Re-render the current page (after a language change, for example). */
export function reload() { if (hostEl) show(hostEl); }

// Direction-aware motion: going back to the page you came from slides the other way, like a real app.
const visited = [];
function directionFor(path) {
  if (visited.length >= 2 && visited[visited.length - 2] === path) { visited.pop(); return 'back'; }
  if (visited[visited.length - 1] !== path) visited.push(path);
  if (visited.length > 30) visited.shift();
  return 'forward';
}

async function show(host) {
  const token = ++navToken;
  const path = currentPath();
  const redirect = guard?.(path);
  if (redirect && redirect !== path) { go(redirect, { replace: true }); return; }
  const loader = routes.get(path) || routes.get('*');
  if (!loader) return;
  const root = document.documentElement;
  root.dataset.nav = directionFor(path);
  root.dataset.loading = '1'; // a thin progress line appears only if the page takes a moment (see main.css)
  let mod;
  try { mod = await loader(); } catch { delete root.dataset.loading; host.textContent = 'Could not load this page. Please reload.'; return; }
  if (token !== navToken) return; // a newer navigation won
  delete root.dataset.loading;

  const swap = () => {
    cleanup?.();
    host.replaceChildren();
    host.classList.remove('page-enter');
    cleanup = mod.render(host, { path, query: query() }) || null;
    host.scrollTop = 0; window.scrollTo(0, 0);
    // Move focus to the page and tell screen readers where we are.
    host.focus({ preventScroll: true });
    const title = host.querySelector('h1')?.textContent;
    if (title) document.title = `${title}: AgroAI Advisor`;
    document.dispatchEvent(new Event('route:rendered')); // the boot screen leaves on the first one
  };

  if (document.startViewTransition) {
    document.startViewTransition(swap);
  } else {
    swap();
    void host.offsetWidth; // restart the CSS animation
    host.classList.add('page-enter');
  }
}

export function startRouter(host) {
  hostEl = host;
  window.addEventListener('hashchange', () => show(host));
  show(host);
}
