// Tokens. Two kinds, both short-lived signed tokens from the backend:
//  - guest: POST /v1/auth/anon with a random device ID kept in localStorage (no account, nothing personal).
//  - account: POST /v1/auth/login or /register with phone and PIN; the token and the profile are kept here.
// getToken() prefers a valid account token and falls back to a guest token. A 401 on an account token logs out.

const DEVICE_KEY = 'agroai.device';
const GUEST_KEY = 'agroai.token';
const USER_KEY = 'agroai.user';
const REFRESH_MARGIN_MS = 60_000;

let guest = null;   // {token, expiresAt}
let user = null;    // {token, expiresAt, profile}
let inflight = null;
const listeners = new Set();

const safeGet = (k) => { try { return localStorage.getItem(k); } catch { return null; } };
const safeSet = (k, v) => { try { localStorage.setItem(k, v); } catch { /* storage blocked: stay in memory */ } };
const safeDel = (k) => { try { localStorage.removeItem(k); } catch { /* ignore */ } };

export function deviceId() {
  let id = safeGet(DEVICE_KEY);
  if (!id) {
    id = crypto.randomUUID ? crypto.randomUUID() : fallbackUuid();
    safeSet(DEVICE_KEY, id);
  }
  return id;
}

function fallbackUuid() { // very old browsers without crypto.randomUUID
  const b = crypto.getRandomValues(new Uint8Array(16));
  b[6] = (b[6] & 0x0f) | 0x40; b[8] = (b[8] & 0x3f) | 0x80;
  const h = [...b].map((x) => x.toString(16).padStart(2, '0')).join('');
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}

function loadUser() {
  if (user) return user;
  try { user = JSON.parse(safeGet(USER_KEY) || 'null'); } catch { user = null; }
  if (user && user.expiresAt <= Date.now()) { user = null; safeDel(USER_KEY); }
  return user;
}

/** The signed-in farmer's profile, or null (guest or signed out). */
export const currentUser = () => loadUser()?.profile ?? null;
export const isLoggedIn = () => !!loadUser();

export function onAuthChange(fn) { listeners.add(fn); return () => listeners.delete(fn); }
const emit = () => listeners.forEach((fn) => fn(currentUser()));

/** Store the response of /v1/auth/login or /v1/auth/register. */
export function setUser({ access_token, expires_in, user: profile }) {
  user = { token: access_token, expiresAt: Date.now() + expires_in * 1000, profile };
  safeSet(USER_KEY, JSON.stringify(user));
  emit();
}

export function updateProfile(profile) {
  if (!loadUser()) return;
  user.profile = profile;
  safeSet(USER_KEY, JSON.stringify(user));
  emit();
}

export function clearUser() {
  user = null;
  safeDel(USER_KEY);
  emit();
}

function loadGuest() {
  if (guest) return guest;
  try { guest = JSON.parse(safeGet(GUEST_KEY) || 'null'); } catch { guest = null; }
  return guest;
}

/** @param {string} base @param {(url:string, init:RequestInit)=>Promise<Response>} doFetch */
export async function getToken(base, doFetch, { force = false } = {}) {
  const u = loadUser();
  if (u && !force) return u.token;
  const g = loadGuest();
  if (!force && g && g.expiresAt - Date.now() > REFRESH_MARGIN_MS) return g.token;
  if (inflight) return inflight;
  inflight = (async () => {
    const res = await doFetch(`${base}/v1/auth/anon`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ device_id: deviceId() }),
    });
    if (!res.ok) throw Object.assign(new Error('auth failed'), { status: res.status });
    const body = await res.json();
    guest = { token: body.access_token, expiresAt: Date.now() + body.expires_in * 1000 };
    safeSet(GUEST_KEY, JSON.stringify(guest));
    return guest.token;
  })().finally(() => { inflight = null; });
  return inflight;
}

/** Called by the client on a 401. Account tokens log the farmer out; guest tokens are simply renewed. */
export function handleUnauthorized() {
  if (loadUser()) { clearUser(); return 'logged-out'; }
  guest = null; safeDel(GUEST_KEY);
  return 'renew';
}

// Back-compat name used by the client.
export const clearToken = handleUnauthorized;
