# AgroAI Advisor: web app (PWA)

Vite + Tailwind CSS + Alpine.js (installed, used from phase 2) + vanilla ES modules. No React.
Talks to the FastAPI backend in `../backend` and is built to `../docs/api.md`.

**Status: Phase 1 (foundation).** Done: tokens and themes, router, i18n (`en`, `pcm`), API client with the
anonymous-token flow, shared speech queue, speech recognition detection, earcons, haptics, the Sprout (all states)
and the `/kitchen-sink` developer page. Onboarding, crop check, chat, weather, settings and PWA install come in
phases 2 to 5. There is no demo mode: every answer comes from the real backend.

## Run

```bash
cp .env.example .env.local      # VITE_API_BASE=http://localhost:8001
npm install
npm run dev                     # http://localhost:5173  (dev page: http://localhost:5173/#/kitchen-sink)
```
Start the backend first (`../backend`, `uvicorn app.main:app --port 8001`). The backend only answers browsers whose
origin is in its `ALLOWED_ORIGINS` (localhost:5173 and 127.0.0.1:5173 are in the local `.env`).

## Checks

| Command | What it does |
|---|---|
| `npm run build` | production build (currently about 12 KB gzipped JS, budget 150 KB) |
| `npm run contrast` | WCAG contrast of every colour pair the UI uses |
| `npm run audit` | opens each route in a real browser at 320, 375, 414 and 768 px in all three themes; fails on horizontal scroll or script errors; reports touch targets under 56 px; saves screenshots to `audit/` |
| `node scripts/live-check.mjs` | clicks the kitchen-sink API buttons against the running backend |

## Design

Read `../docs/design-and-motion-guide.md` first. Short version: colours only through the tokens in
`src/styles/main.css`; motion only with the spring curves and durations in `src/styles/animations.css`; transform and
opacity only; everything must survive `prefers-reduced-motion` and the in-app switch.

Colour rules from the contrast check (`npm run contrast`): body text and buttons are forest on cream (10.8:1).
Leaf green, sun gold and terracotta are fills and icons; coloured text uses the darker `leaf-ink` and `clay-ink`
tokens. Text sizes are fluid and multiply by the user's text-size setting.

## Speech notes

- No browser ships a Pidgin voice. Pidgin text is spoken with the best English (Nigeria, then UK) voice. Pick another
  in Settings (phase 5). Say this in the pitch.
- Voice input (`SpeechRecognition`) works on Chrome for Android; Firefox and some iOS versions lack it, so screens
  show a typing-first layout. `POST /v1/transcribe` exists on the backend for a recorder-based fallback.
- Screen readers: the setting "I use a screen reader" turns off all automatic speech so the app never talks over it.
  Tapping Listen still speaks.

## Layout

```
src/main.js  router.js
api/      client.js (fetch, timeouts, retry, typed errors), auth.js (token flow), endpoints.js
state/    store.js (settings, persisted), i18n.js, locales/{en,pcm}.json
audio/    speech.js (queue), recognition.js, earcons.js
device/   haptics.js   (camera, location, share arrive in phase 3)
ui/       sprout.js, halo.js, components/ripple.js
screens/  home.js (placeholder), kitchen-sink.js
styles/   main.css (tokens, components), animations.css (motion language)
```
