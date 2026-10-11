// Turn any failure into one friendly sentence in the farmer's language (spoken and written, with a retry).
import { t } from '../../state/i18n.js';
import { settings } from '../../state/store.js';

/** @param {unknown} e an ApiError or any thrown value */
export function friendlyError(e) {
  const pcm = settings.get().language === 'pcm';
  const kind = e?.kind;
  if (kind === 'rate') {
    const server = pcm ? e.detailPcm : e.detail;
    return server || t('errors.rate', { seconds: e.retryAfter || 30 });
  }
  // The backend's own sentences are friendly (English only); Pidgin readers get ours for transport problems.
  if (kind === 'client' || kind === 'server') {
    // Only show the backend's own friendly sentences; framework defaults like "Not Found" are not for farmers.
    const generic = !e.detail || /^(not found|method not allowed|internal server error|bad request|unprocessable)/i.test(e.detail);
    if (pcm || generic) return t('errors.server');
    return e.detail;
  }
  if (kind === 'offline') return t('errors.offline');
  if (kind === 'timeout') return t('errors.timeout');
  if (kind === 'session') return t('errors.session');
  return t('errors.network');
}

/** Small inline alert with a retry button. Returns the element; caller appends it. */
export function errorBox(message, onRetry) {
  const box = document.createElement('div');
  box.className = 'card flex flex-col gap-3 border-clay-ink';
  box.setAttribute('role', 'alert');
  box.innerHTML = `<p class="font-bold text-clay-ink"></p>`;
  box.querySelector('p').textContent = message;
  if (onRetry) {
    const b = document.createElement('button');
    b.type = 'button'; b.className = 'btn btn-primary self-start'; b.textContent = t('common.retry');
    b.addEventListener('click', onRetry);
    box.append(b);
  }
  return box;
}
