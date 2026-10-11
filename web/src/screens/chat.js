// Chat: press-and-hold the mic to speak, or type. The transcript is shown, answers are spoken and shown, follow-up
// suggestions are tappable chips, and the conversation continues from the crop check when there is one.
// The thread survives a language switch or reload (sessionStorage); accounts can reopen past conversations.
import { t, tList } from '../state/i18n.js';
import { qs } from '../ui/safe-dom.js';
import { settings } from '../state/store.js';
import { speak, stop } from '../audio/speech.js';
import { listen, recognitionSupported } from '../audio/recognition.js';
import { earcon } from '../audio/earcons.js';
import { haptic } from '../device/haptics.js';
import { chat, transcribe, myChats, myChat } from '../api/endpoints.js';
import { isLoggedIn } from '../api/auth.js';
import { halo } from '../ui/halo.js';
import { icons } from '../ui/icons/index.js';
import { friendlyError } from '../ui/components/friendly.js';
import { work, getSessionId, setSessionId, getChatLog, setChatLog, pushChat, clearChat } from '../state/session.js';
import { getLocation } from '../device/location.js';
import { query } from '../router.js';

const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const canRecord = typeof MediaRecorder !== 'undefined' && !!navigator.mediaDevices?.getUserMedia;
const fmt = (iso) => new Intl.DateTimeFormat(settings.get().language === 'pcm' ? 'en-NG' : 'en',
  { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }).format(new Date(iso));

export function render(host) {
  const voiceOk = recognitionSupported || canRecord;
  const signedIn = isLoggedIn();
  host.innerHTML = `
    <div class="mx-auto flex min-h-[60dvh] max-w-xl flex-col gap-4 px-5 py-6">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <a class="btn btn-ghost btn-sm -ml-1" href="#/dashboard">${icons.back()} ${t('common.back')}</a>
        <div class="flex gap-2">
          ${signedIn ? `<button type="button" class="btn btn-ghost btn-sm" id="past-btn" aria-expanded="false" aria-controls="past">${t('chat.past')}</button>` : ''}
          <button type="button" class="btn btn-ghost btn-sm" id="new-chat">${t('chat.newChat')}</button>
        </div>
      </div>
      <h1 class="morph-target">${t('chat.title')}</h1>
      <section id="past" class="card flex flex-col gap-3" hidden aria-label="${t('chat.past')}"></section>
      <ol id="log" class="flex flex-1 flex-col gap-4" aria-live="polite" aria-label="${t('chat.title')}"></ol>
      <div id="chips" class="flex flex-wrap gap-2"></div>
      <p id="voice-note" class="text-small text-ink-soft" ${voiceOk ? 'hidden' : ''}>${t('chat.typeInstead')}</p>
      <form id="form" class="sticky bottom-0 flex flex-col gap-3 bg-bg py-3">
        <div class="flex items-center gap-3">
          <input id="text" class="input min-w-0 flex-1" autocomplete="off" maxlength="1000" placeholder="${t('chat.placeholder')}" aria-label="${t('chat.placeholder')}">
          <button class="btn btn-leaf" type="submit" id="send">${t('chat.send')}</button>
        </div>
        ${voiceOk ? `<span class="inline-flex self-center" id="mic-wrap"><button type="button" class="btn btn-sun" id="mic" style="touch-action:none;user-select:none;-webkit-user-select:none">${icons.mic()} ${t('chat.hold')}</button></span>` : ''}
        <p id="mic-status" class="min-h-[1.5em] text-center text-small font-bold" role="status" aria-live="polite"></p>
      </form>
    </div>`;

  const $ = qs(host);
  const log = $('#log');
  let busy = false;
  let listening = false;

  function bubble(who, text, { remember = false, scroll = true } = {}) {
    const li = document.createElement('li');
    const mine = who === 'you';
    li.className = `reveal max-w-[90%] rounded-seed px-5 py-3 ${mine ? 'self-end bg-ink text-bg' : 'self-start bg-surface border-2 border-line'}`;
    li.innerHTML = `<span class="sr-only">${mine ? t('chat.you') : t('chat.advisor')}: </span>`;
    li.append(document.createTextNode(text));
    log.append(li);
    if (scroll) li.scrollIntoView({ block: 'end', behavior: 'smooth' });
    if (remember) pushChat(who, text);
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

  /** Draw the saved thread (after a language switch or reload) or the opening message and starter questions. */
  function drawThread() {
    log.replaceChildren();
    const saved = getChatLog();
    if (saved.length) {
      saved.forEach((m) => bubble(m.who, m.text, { scroll: false }));
      showChips([]);
      return;
    }
    const opener = work.result?.assessment ? `${work.result.assessment.likely_problem}. ${t('chat.empty')}` : t('chat.empty');
    bubble('advisor', opener, { scroll: false });
    showChips(work.result?.farmer_questions?.length ? work.result.farmer_questions : tList('chat.starters'));
  }

  async function ask(message) {
    message = message.trim();
    if (!message || busy) return;
    busy = true; stop();
    bubble('you', message, { remember: true });
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
      pushChat('advisor', r.answer_text);
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

  drawThread();
  $('#form').addEventListener('submit', (e) => { e.preventDefault(); ask($('#text').value); });

  // --- new chat, and past conversations for accounts ---
  $('#new-chat').addEventListener('click', () => {
    stop(); clearChat(); setSessionId('');
    $('#past').hidden = true;
    drawThread();
    $('#text').focus();
  });

  const pastBtn = $('#past-btn');
  const pastBox = $('#past');
  async function openPast() {
    pastBox.hidden = false;
    pastBtn.setAttribute('aria-expanded', 'true');
    pastBox.innerHTML = `<h2>${t('chat.past')}</h2><div class="skeleton h-16"></div>`;
    try {
      const rows = await myChats(20);
      if (!rows.length) { pastBox.innerHTML = `<h2>${t('chat.past')}</h2><p>${t('chat.pastNone')}</p>`; return; }
      pastBox.innerHTML = `<h2>${t('chat.past')}</h2>
        <ul class="flex flex-col gap-2">${rows.map((c) => `
          <li><button type="button" class="action-card flex flex-col gap-1 !p-3" data-conv="${c.id}">
            <span class="font-bold">${esc(c.title)}</span>
            <span class="text-small text-ink-soft">${fmt(c.last_at)} · ${t('chat.messages', { count: c.messages })}</span>
          </button></li>`).join('')}</ul>`;
      pastBox.querySelectorAll('[data-conv]').forEach((b) => b.addEventListener('click', async () => {
        b.disabled = true;
        try {
          const turns = await myChat(b.dataset.conv);
          setChatLog(turns.map((m) => ({ who: m.role === 'farmer' ? 'you' : 'advisor', text: m.text })));
          setSessionId(''); // the advisor still remembers your recent chat through your account
          pastBox.hidden = true; pastBtn.setAttribute('aria-expanded', 'false');
          drawThread();
          bubble('advisor', t('chat.resumed'));
        } catch (e) { b.disabled = false; pastBox.append(Object.assign(document.createElement('p'), { textContent: friendlyError(e) })); }
      }));
    } catch (e) {
      pastBox.innerHTML = `<h2>${t('chat.past')}</h2><p>${esc(friendlyError(e))}</p>`;
    }
  }
  pastBtn?.addEventListener('click', () => { if (pastBox.hidden) openPast(); else { pastBox.hidden = true; pastBtn.setAttribute('aria-expanded', 'false'); } });
  if (signedIn && query().get('history')) openPast();

  // --- press and hold to speak: nothing is sent until the button is released ---
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
      try { if (e.pointerId !== undefined) mic.setPointerCapture(e.pointerId); } catch { /* not supported */ }
      stop(); haptic('tap');
      $('#text').value = '';
      if (recognitionSupported) {
        rec = listen({
          language: settings.get().language,
          onStart: () => { setListening(true); earcon('listenOn'); },
          onPartial: (txt) => { $('#text').value = txt; }, // shown as you speak, never sent while held
          onFinal: (txt) => { $('#text').value = ''; ask(txt); }, // only after the button is released
          onEnd: () => { setListening(false); earcon('listenOff'); },
          onError: (c) => { setListening(false); $('#mic-status').textContent = c === 'not-allowed' ? t('errors.mic') : c === 'no-speech' ? '' : t('errors.mic'); },
        });
      } else {
        startRecorder();
      }
    };
    const end = () => { rec?.stop(); if (recorder && recorder.state === 'recording') recorder.stop(); };
    mic.addEventListener('pointerdown', start);
    // Pointer capture keeps the press with the button even if the finger drifts, so only a real release ends it.
    ['pointerup', 'pointercancel'].forEach((ev) => mic.addEventListener(ev, end));
    mic.addEventListener('contextmenu', (e) => e.preventDefault()); // long-press must not open a menu
    // Keyboard: hold Space or Enter.
    mic.addEventListener('keydown', (e) => { if ((e.key === ' ' || e.key === 'Enter') && !e.repeat) start(e); });
    mic.addEventListener('keyup', (e) => { if (e.key === ' ' || e.key === 'Enter') end(); });
  }

  return () => { stop(); };
}
