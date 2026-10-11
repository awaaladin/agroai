// A small set of soft marimba-like earcons made with the Web Audio API (no audio files to download).
// Muted by Settings. Short, quiet, never more than a few notes.
import { settings } from '../state/store.js';

let ctx;
function audio() {
  if (!ctx) {
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return null;
    ctx = new AC();
  }
  if (ctx.state === 'suspended') ctx.resume();
  return ctx;
}

// A marimba-ish note: a sine with a quick attack and a woody exponential decay, plus a soft 4x overtone.
function note(c, freq, start, dur = 0.35, gain = 0.16) {
  const t = c.currentTime + start;
  [[1, gain], [4, gain * 0.25]].forEach(([mult, g]) => {
    const o = c.createOscillator(); const v = c.createGain();
    o.type = 'sine'; o.frequency.value = freq * mult;
    v.gain.setValueAtTime(0.0001, t);
    v.gain.exponentialRampToValueAtTime(g, t + 0.01);
    v.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    o.connect(v).connect(c.destination);
    o.start(t); o.stop(t + dur + 0.05);
  });
}

const SOUNDS = {
  listenOn: [[523.25, 0], [659.25, 0.1]],           // rising: I am listening
  listenOff: [[659.25, 0], [523.25, 0.1]],          // falling: done
  captured: [[392, 0], [587.33, 0.08]],             // photo taken
  ready: [[523.25, 0], [659.25, 0.12], [783.99, 0.24]], // answer ready
  error: [[329.63, 0], [261.63, 0.14]],             // gentle, not alarming
};

/** @param {'listenOn'|'listenOff'|'captured'|'ready'|'error'} name */
export function earcon(name) {
  if (!settings.get().sound) return;
  const c = audio();
  if (!c || !SOUNDS[name]) return;
  SOUNDS[name].forEach(([f, at]) => note(c, f, at));
}
