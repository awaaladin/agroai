// Speech recognition, feature-detected. When it is missing (Firefox, some iOS) screens show a typing-first UI
// instead of an error; `recognitionSupported` is the single flag they read.
// The mic glow is driven from these events (start, result, end): no second mic stream is opened for a waveform.

const Ctor = typeof window !== 'undefined' ? (window.SpeechRecognition || window.webkitSpeechRecognition) : undefined;
export const recognitionSupported = !!Ctor;

/**
 * Start listening. Returns a handle with stop(); callbacks never throw into the caller.
 * @param {{language:'en'|'pcm', onStart?:()=>void, onPartial?:(t:string)=>void, onFinal:(t:string)=>void,
 *   onEnd?:()=>void, onError?:(code:string)=>void}} h
 */
export function listen({ language, onStart, onPartial, onFinal, onEnd, onError }) {
  if (!Ctor) { onError?.('unsupported'); return { stop() {} }; }
  const r = new Ctor();
  // Nigerian English recognises Pidgin best; fall back to the browser default if unsupported.
  r.lang = 'en-NG';
  r.interimResults = true;
  r.continuous = false;
  r.maxAlternatives = 1;
  let finalText = '';
  r.onstart = () => onStart?.();
  r.onresult = (e) => {
    let interim = '';
    for (let i = e.resultIndex; i < e.results.length; i++) {
      const t = e.results[i][0].transcript;
      if (e.results[i].isFinal) finalText += t; else interim += t;
    }
    if (interim) onPartial?.((finalText + interim).trim());
  };
  r.onerror = (e) => onError?.(e.error || 'error'); // 'not-allowed', 'no-speech', 'network', 'audio-capture'
  r.onend = () => { if (finalText.trim()) onFinal(finalText.trim()); onEnd?.(); };
  try { r.start(); } catch { onError?.('busy'); }
  return { stop() { try { r.stop(); } catch { /* already stopped */ } } };
}
