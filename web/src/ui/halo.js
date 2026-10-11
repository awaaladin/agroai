// Mic halo: a glow ring that pulses while listening. The pulse is driven by recognition events (start/end),
// not by a second microphone stream. Wrap any button: halo(buttonEl).set(true/false).
export function halo(el) {
  el.classList.add('halo');
  return { set(active) { el.dataset.active = active ? 'true' : 'false'; } };
}
