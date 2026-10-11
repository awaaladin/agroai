// Chat: press-and-hold the mic to speak, or type. The transcript is shown, answers are spoken and shown, follow-up
// suggestions are tappable chips, and the conversation continues from the crop check when there is one.
import { t, tList } from '../state/i18n.js';
import { settings } from '../state/store.js';
import { speak, stop } from '../audio/speech.js';
import { listen, recognitionSupported } from '../audio/recognition.js';
import { earcon } from '../audio/earcons.js';
import { haptic } from '../device/haptics.js';
import { chat, transcribe } from '../api/endpoints.js';
import { halo } from '../ui/halo.js';
import { icons } from '../ui/icons/index.js';
import { friendlyError } from '../ui/components/friendly.js';
import { work, getSessionId, setSessionId } from '../state/session.js';
import { getLocation } from '../device/location.js';

const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const canRecord = typeof MediaRecorder !== 'undefined' && !!navigator.mediaDevices?.getUserMedia;

export function render(host) {
  const voiceOk = recognitionSupported || canRecord;
  host.innerHTML = `
    <div class="mx-auto flex min-h-[60dvh] max-w-xl flex-col gap-4 px-5 py-6">
      <a class="btn btn-ghost -ml-3 self-start" href="#/dashboard">${icons.back()} ${t('common.back')}</a>
      <h1 class="morph-target">${t('chat.title')}</h1>
      <ol id="log" class="flex flex-1 flex-col gap-4" aria-live="polite" aria-label="${t('chat.title')}"></ol>
      <div id="chips" class="flex flex-wrap gap-2"></div>
      <p id="voice-note" class="text-small text-ink-soft" ${voiceOk ? 'hidden' : ''}>${t('chat.typeInstead')}</p>
      <form id="form" class="sticky bottom-0 flex flex-col gap-3 bg-bg py-3">
        <div class="flex items-center gap-3">
          <input id="text" class="input min-w-0 flex-1" autocomplete="off" maxlength="1000" placeholder="${t('chat.placeholder')}" aria-label="${t('chat.placeholder')}">
          <button class="btn btn-leaf" type="submit" id="send">${t('chat.send')}</button>
        </div>
        ${voiceOk ? `<span class="inline-flex self-center" id="mic-wrap"><button type="button" class="btn btn-sun" id="mic">${icons.mic()} ${t('chat.hold')}</button></span>` : ''}
        <p id="mic-status" class="min-h-[1.5em] text-center text-small font-bold" role="status" aria-live="polite"></p>
      </form>
    </div>`;

  const $ = (s) => host.querySelector(s);
  const log = $('#log');
  let busy = false;
  let listening = false;

  function bubble(who, text) {
    const li = document.createElement('li');
    const mine = who === 'you';
    li.className = `reveal max-w-[90%] rounded-seed px-5 py-3 ${mine ? 'self-end bg-ink text-bg' : 'self-start bg-surface border-2 border-line'}`;
    li.innerHTML = `<span class="sr-only">${mine ? t('chat.you') : t('chat.advisor')}: </span>`;
    li.append(document.createTextNode(text));
    log.append(li);
    li.scrollIntoView({ block: 'end', behavior: 'smooth' });
    return li;
  }

  function showChips(items) {
    $('#chips').replaceChildren(...(items || []).slice(0, 3).map((s) => {
      const b = document.createElement('button');
      b.type = 'button'; b.className = 'chip'; b.textContent = s;
      b.addEventListener('click', () => ask(s));
      return b;
    }));
  }

  async function ask(message) {
    message = message.trim();
    if (!message || busy) return;
    busy = true; stop();
    bubble('you', message);
    $('#text').value = '';
    showChips([]);
    const wait = bubble('advisor', t('chat.thinking') + '...');
    const loc = getLocation();
    try {
      const r = await chat({
        message, language: settings.get().language, session_id: getSessionId() || undefined,
        lat: loc?.lat, lon: loc?.lon, crop: work.result?.crop?.name || work.crop || undefined,
      });
      setSessionId(r.session_id);
      wait.lastChild.textContent = r.answer_text;
      showChips(r.follow_up_suggestions);
      earcon('ready'); 
      speak(r.spoken_text, { auto: true });
    } catch (e) {
      if (e?.kind === 'client' && e.status === 404) setSessionId(''); // the conversation expired: next one starts fresh
      const msg = friendlyError(e);
      wait.lastChild.textContent = msg;
      earcon('error'); 
      speak(msg, { auto: true });
    } finally {
      busy = false;
    }
  }

  // --- starting point: what we know, or three example questions ---
  if (work.result?.assessment) {
    bubble('advisor', `${work.result.assessment.likely_problem}. ${t('chat.empty')}`);
  } else {
    bubble('advisor', t('chat.empty'));
  }
  showChips(work.result?.farmer_questions?.length ? work.result.farmer_questions : tList('chat.starters'));

  $('#form').addEventListener('submit', (e) => { e.preventDefault(); ask($('#text').value); });

  // --- press and hold to speak ---
  if (voiceOk) {
    const micHalo = halo($('#mic-wrap'));
    const mic = $('#mic');
    let rec = null;      // SpeechRecognition handle
    let recorder = null; // MediaRecorder fallback
    const setListening = (on) => {
      listening = on; micHalo.set(on);
      $('#mic-status').textContent = on ? t('chat.listening') : '';
      mic.setAttribute('aria-pressed', String(on));
    };

    async function startRecorder() {
      let stream;
      try { stream = await navigator.mediaDevices.getUserMedia({ audio: true }); }
      catch { $('#mic-status').textContent = t('errors.mic'); earcon('error'); return; }
      const chunks = [];
      recorder = new MediaRecorder(stream);
      recorder.ondataavailable = (e) => e.data.size && chunks.push(e.data);
      recorder.onstop = async () => {
        stream.getTracks().forEach((tr) => tr.stop());
        setListening(false); earcon('listenOff');
        const blob = new Blob(chunks, { type: recorder.mimeType || 'audio/webm' });
        if (blob.size < 800) return; // nothing was said
        $('#mic-status').textContent = t('chat.thinking');
        try { const { text } = await transcribe(blob, settings.get().language); $('#mic-status').textContent = ''; ask(text); }
        catch (e) { $('#mic-status').textContent = friendlyError(e); }
      };
      setListening(true); earcon('listenOn');
      recorder.start();
    }

    const start = (e) => {
      e.preventDefault();
      if (busy || listening) return;
      stop(); haptic('tap');
      if (recognitionSupported) {
        rec = listen({
          language: settings.get().language,
          onStart: () => { setListening(true); earcon('listenOn'); },
          onPartial: (txt) => { $('#text').value = txt; },
          onFinal: (txt) => { $('#text').value = ''; ask(txt); },
          onEnd: () => { setListening(false); earcon('listenOff'); },
          onError: (c) => { setListening(false); $('#mic-status').textContent = c === 'not-allowed' ? t('errors.mic') : c === 'no-speech' ? '' : t('errors.mic'); },
        });
      } else {
        startRecorder();
      }
    };
    const end = () => { rec?.stop(); if (recorder && recorder.state === 'recording') recorder.stop(); };
    mic.addEventListener('pointerdown', start);
    ['pointerup', 'pointerleave', 'pointercancel'].forEach((ev) => mic.addEventListener(ev, end));
    // Keyboard: hold Space or Enter.
    mic.addEventListener('keydown', (e) => { if ((e.key === ' ' || e.key === 'Enter') && !e.repeat) start(e); });
    mic.addEventListener('keyup', (e) => { if (e.key === ' ' || e.key === 'Enter') end(); });
  }

  return () => { stop(); };
}
