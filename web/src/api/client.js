// Tiny API client: fetch with timeouts, careful retries, the anonymous-token flow and friendly typed errors.
// Contract: docs/api.md. Base URL from VITE_API_BASE (never hard-coded).
import { getToken, handleUnauthorized } from './auth.js';

export const API_BASE = (import.meta.env.VITE_API_BASE || '').replace(/\/$/, '');

/**
 * @typedef {'offline'|'network'|'timeout'|'rate'|'session'|'client'|'server'} ErrorKind
 * Every failure becomes one ApiError so screens can show a friendly spoken and written message with a retry.
 */
export class ApiError extends Error {
  /** @param {ErrorKind} kind @param {object} [extra] */
  constructor(kind, extra = {}) {
    super(extra.detail || kind);
    this.kind = kind;
    this.status = extra.status ?? 0;
    this.detail = extra.detail ?? '';        // server's friendly sentence (English)
    this.detailPcm = extra.detailPcm ?? '';  // server's Pidgin version when it sends one (429)
    this.retryAfter = extra.retryAfter ?? 0; // seconds, for 'rate'
  }
}

const TIMEOUTS = { default: 20_000, diagnose: 60_000, chat: 45_000 };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function timedFetch(url, init, timeoutMs, external) {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(new DOMException('timeout', 'TimeoutError')), timeoutMs);
  const onAbort = () => ctl.abort(external.reason);
  external?.addEventListener('abort', onAbort, { once: true });
  try {
    return await fetch(url, { ...init, signal: ctl.signal });
  } finally {
    clearTimeout(timer);
    external?.removeEventListener('abort', onAbort);
  }
}

function classify(err) {
  if (err instanceof ApiError) return err;
  if (err?.name === 'TimeoutError' || err?.name === 'AbortError') return new ApiError('timeout');
  if (typeof navigator !== 'undefined' && navigator.onLine === false) return new ApiError('offline');
  return new ApiError('network');
}

async function toApiError(res) {
  let body = {};
  try { body = await res.json(); } catch { /* not JSON */ }
  const detail = typeof body.detail === 'string' ? body.detail
    : Array.isArray(body.detail) ? 'Please check what you sent and try again.' : '';
  if (res.status === 401) return new ApiError('session', { status: 401, detail });
  if (res.status === 429) {
    const retryAfter = Number(res.headers.get('Retry-After')) || body.retry_after || 30;
    return new ApiError('rate', { status: 429, detail, detailPcm: body.detail_pcm || '', retryAfter });
  }
  return new ApiError(res.status >= 500 ? 'server' : 'client', { status: res.status, detail });
}

/**
 * @param {string} path e.g. '/v1/chat'
 * @param {{method?:string, json?:object, form?:FormData, timeout?:number, signal?:AbortSignal, auth?:boolean}} [opt]
 */
export async function request(path, opt = {}) {
  const { method = 'GET', json, form, signal, auth = true } = opt;
  const timeout = opt.timeout ?? TIMEOUTS.default;
  // Only GETs are retried automatically: a retried POST could repeat a paid AI call.
  const attempts = method === 'GET' ? 3 : 1;
  const plain = (url, init) => timedFetch(url, init, TIMEOUTS.default, signal);

  let lastErr;
  for (let i = 0; i < attempts; i++) {
    try {
      const headers = {};
      if (json !== undefined) headers['Content-Type'] = 'application/json';
      if (auth) headers.Authorization = `Bearer ${await getToken(API_BASE, plain)}`;
      const init = { method, headers, body: json !== undefined ? JSON.stringify(json) : form };
      let res = await timedFetch(`${API_BASE}${path}`, init, timeout, signal);

      if (res.status === 401 && auth) {
        // A guest token just expired: renew it and retry once. An account token means the farmer must log in again.
        if (handleUnauthorized() === 'logged-out') throw new ApiError('session', { status: 401, detail: 'Please log in again.' });
        headers.Authorization = `Bearer ${await getToken(API_BASE, plain, { force: true })}`;
        res = await timedFetch(`${API_BASE}${path}`, { ...init, headers }, timeout, signal);
      }
      if (res.ok) return res.status === 204 ? null : await res.json();
      const err = await toApiError(res);
      if (err.kind === 'server' && i < attempts - 1) { await sleep(400 * 2 ** i); lastErr = err; continue; }
      throw err;
    } catch (e) {
      lastErr = classify(e);
      if (lastErr.kind === 'rate' || lastErr.kind === 'client' || lastErr.kind === 'session') throw lastErr;
      if (signal?.aborted) throw lastErr;
      if (i < attempts - 1) await sleep(400 * 2 ** i); else throw lastErr;
    }
  }
  throw lastErr;
}

export { TIMEOUTS };
