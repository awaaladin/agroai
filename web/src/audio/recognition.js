// Speech recognition, feature-detected. When it is missing (Firefox, some iOS) screens show a typing-first UI
// instead of an error; `recognitionSupported` is the single flag they read.
// The mic glow is driven from these events (start, result, end): no second mic stream is opened for a waveform.

const Ctor = typeof window !== 'undefined' ? (window.SpeechRecognition || window.webkitSpeechRecognition) : undefined;
export const recognitionSupported = !!Ctor;

const MAX_RESTARTS = 40; // browsers end a session after a few seconds of quiet; while held we simply start again

/**
 * Listen for as long as the farmer holds the button, and deliver the words only after they let go.
 * Browsers stop recognition on their own after a pause. That must never send the message: while the button is
 * held we restart quietly and keep the words said so far; `stop()` (button released) is the only thing that sends.
 * @param {{language:'en'|'pcm', onStart?:()=>void, onPartial?:(t:string)=>void, onFinal:(t:string)=>void,
 *   onEnd?:()=>void, onError?:(code:string)=>void}} h
 * @returns {{stop():void}}
 */
export function listen({ onStart, onPartial, onFinal, onEnd, onError }) {
  if (!Ctor) { onError?.('unsupported'); return { stop() {} }; }
  let finalText = '';
  let interim = '';
  let released = false; // the farmer let go
  let fatal = '';       // a real failure (mic blocked, no network): stop for good
  let finished = false;
  let started = false;
  let restarts = 0;
  let current = null;

  const spoken = () => (finalText + ' ' + interim).replace(/\s+/g, ' ').trim();

  function finish() {
    if (finished) return;
    finished = true;
    const text = spoken();
    if (text && !fatal) onFinal(text);
    onEnd?.();
  }

  function begin() {
    const r = new Ctor();
    current = r;
    r.lang = 'en-NG'; // Nigerian English recognises Pidgin best
    r.interimResults = true;
    r.continuous = true;
    r.maxAlternatives = 1;
    r.onstart = () => { if (!started) { started = true; onStart?.(); } };
    r.onresult = (e) => {
      interim = '';
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const txt = e.results[i][0].transcript;
        if (e.results[i].isFinal) finalText += (finalText ? ' ' : '') + txt.trim(); else interim += txt;
      }
      onPartial?.(spoken());
    };
    r.onerror = (e) => {
      const code = e.error || 'error';
      // Silence and our own stop() are normal; onend decides whether to carry on.
      if (code === 'no-speech' || code === 'aborted') return;
      fatal = code; // 'not-allowed', 'network', 'audio-capture'...
      onError?.(code);
    };
    r.onend = () => {
      if (!released && !fatal && restarts < MAX_RESTARTS) {
        restarts += 1;
        interim = ''; // a restarted session starts its own interim text
        try { begin(); return; } catch { /* fall through and finish */ }
      }
      finish();
    };
    try { r.start(); } catch { fatal = 'busy'; onError?.('busy'); finish(); }
  }

  begin();
  return {
    stop() {
      released = true;
      try { current?.stop(); } catch { finish(); }
      // Safety: if the browser never reports the end, do not hang the button.
      setTimeout(finish, 2500);
    },
  };
}
