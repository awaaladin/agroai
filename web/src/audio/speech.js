// Shared speech queue: everything the app says goes through here, so audio never overlaps.
// - Pidgin is spoken with the best available English (Nigeria, then UK) voice: no browser ships a Pidgin voice.
// - It must not fight a screen reader: when the user says they use one (Settings), nothing is spoken automatically;
//   only an explicit tap on Listen/Repeat speaks.
import { settings } from '../state/store.js';

const synth = typeof window !== 'undefined' ? window.speechSynthesis : undefined;
export const speechSupported = !!synth;

const queue = [];
let current = null;
const stateListeners = new Set();
let voicesReady = null;

function emit(state) { stateListeners.forEach((fn) => fn(state)); }

/** Browsers load voices asynchronously (Chrome fires voiceschanged). Resolve once they exist, or after 1.5 s. */
function loadVoices() {
  if (!synth) return Promise.resolve([]);
  if (voicesReady) return voicesReady;
  voicesReady = new Promise((resolve) => {
    const have = synth.getVoices();
    if (have.length) return resolve(have);
    const done = () => resolve(synth.getVoices());
    synth.addEventListener('voiceschanged', done, { once: true });
    setTimeout(done, 1500);
  });
  return voicesReady;
}

// Browsers do not say whether a voice is female or male, so we recognise the well-known names.
const FEMALE = /\b(female|woman|zira|hazel|susan|aria|jenny|libby|sonia|ezinne|natasha|samantha|karen|moira|tessa|fiona|victoria|serena|catherine|heera|emily|olivia|amy|emma|salli|joanna|kendra|kimberly|ivy|zoe|mia|google uk english female)\b/i;
const MALE = /\b(male|man|david|mark|george|guy|ryan|abeo|thomas|alex|daniel|oliver|arthur|fred|james|richard|william|brian|matthew|joey|justin|kevin|google uk english male)\b/i;

/** @returns {'female'|'male'|'unknown'} */
export function voiceGender(v) {
  if (/\bfemale\b/i.test(v.name)) return 'female';
  if (/\bmale\b/i.test(v.name)) return 'male';
  if (FEMALE.test(v.name)) return 'female';
  if (MALE.test(v.name)) return 'male';
  return 'unknown';
}

const localeRank = (v) => (/en[-_]NG/i.test(v.lang) ? 0 : /en[-_]GB/i.test(v.lang) ? 1 : /en[-_](ZA|KE|GH)/i.test(v.lang) ? 2 : /^en/i.test(v.lang) ? 3 : 9);

/**
 * English voices, best first for this farmer: the gender they asked for, then Nigerian, British, other English.
 * @param {'female'|'male'|'any'} [prefer]
 */
export async function listVoices(prefer = settings.get().voiceGender) {
  const voices = (await loadVoices()).filter((v) => /^en/i.test(v.lang));
  const genderRank = (v) => (prefer === 'any' || voiceGender(v) === prefer ? 0 : voiceGender(v) === 'unknown' ? 1 : 2);
  return voices.sort((a, b) => genderRank(a) - genderRank(b) || localeRank(a) - localeRank(b) || a.name.localeCompare(b.name));
}

async function pickVoice() {
  const { voiceURI } = settings.get();
  const voices = await listVoices();
  return (voiceURI && voices.find((v) => v.voiceURI === voiceURI)) || voices[0] || null;
}

function next() {
  if (current || !queue.length || !synth) { if (!current && !queue.length) emit('idle'); return; }
  const job = queue.shift();
  pickVoice().then((voice) => {
    const u = new SpeechSynthesisUtterance(job.text);
    if (voice) { u.voice = voice; u.lang = voice.lang; } else u.lang = 'en-NG';
    u.rate = settings.get().speechRate;
    u.onstart = () => emit('speaking');
    const finish = () => { current = null; job.resolve(); next(); };
    u.onend = finish;
    u.onerror = finish; // 'canceled' on stop() and real errors both just move on
    current = { u, job };
    synth.speak(u);
  });
}

/**
 * Speak text. By default it queues behind what is already being said.
 * @param {string} text
 * @param {{interrupt?:boolean, auto?:boolean}} [o] auto: this is automatic speech (obeys auto-read and screen-reader mode)
 * @returns {Promise<void>} resolves when finished (or immediately when speech is unavailable or muted)
 */
export function speak(text, { interrupt = false, auto = false } = {}) {
  const s = settings.get();
  if (!synth || !text || (auto && (!s.autoRead || s.screenReader))) return Promise.resolve();
  if (interrupt) stop();
  return new Promise((resolve) => { queue.push({ text, resolve }); next(); });
}

export function stop() {
  queue.splice(0).forEach((j) => j.resolve());
  if (synth) synth.cancel();
  current = null;
  emit('idle');
}

export function pause() { synth?.pause(); emit('paused'); }
export function resume() { synth?.resume(); emit('speaking'); }
export const isSpeaking = () => !!current || !!synth?.speaking;

/** Subscribe to 'speaking' | 'paused' | 'idle' (the Sprout and the Listen buttons follow this). */
export function onSpeechState(fn) { stateListeners.add(fn); return () => stateListeners.delete(fn); }

// Stop talking when the page is hidden or closed.
if (typeof document !== 'undefined') {
  document.addEventListener('visibilitychange', () => { if (document.hidden) stop(); });
  window.addEventListener('pagehide', stop);
}
