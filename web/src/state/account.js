// Account actions shared by screens: sign in/up, sign out, and keeping local settings in step with the profile.
import { settings } from './store.js';
import { setUser, clearUser, updateProfile } from '../api/auth.js';
import { login, register, me, updateMe } from '../api/endpoints.js';
import { setSessionId } from './session.js';
import { clearWork } from './session.js';
import { go } from '../router.js';

/** Copy the profile's town, location and language into local settings so every screen uses them. */
export function applyProfile(p) {
  settings.set({
    language: p.language || settings.get().language,
    town: p.town || '',
    lat: p.lat ?? null,
    lon: p.lon ?? null,
    locationSource: p.lat != null ? (p.town ? 'town' : 'gps') : '',
    guest: false,
    onboarded: true,
  });
}

function signedIn(res) {
  setSessionId('');  // conversations started as a guest do not belong to the account
  clearWork();
  setUser(res);
  applyProfile(res.user);
  return res.user;
}

export async function signIn(phone, pin) { return signedIn(await login(phone, pin)); }
export async function signUp(body) { return signedIn(await register(body)); }

export function logout() {
  clearUser();
  setSessionId('');
  clearWork();
  settings.set({ guest: false, town: '', lat: null, lon: null, locationSource: '' });
  go('/');
}

/** Refresh the profile from the server (after a check is saved, after edits). */
export async function refreshProfile() {
  const p = await me();
  updateProfile(p);
  return p;
}

export async function saveProfile(patch) {
  const p = await updateMe(patch);
  updateProfile(p);
  applyProfile(p);
  return p;
}

export function continueAsGuest() {
  settings.set({ guest: true, onboarded: true });
  go('/dashboard');
}
