# AgroAI Advisor API, v1

Base URL: `http://localhost:8000` (dev). All paths below are under `/v1`. Interactive docs: `/docs`; machine-readable: `/openapi.json`.

**Status (Phase 2):** health, auth, diagnose, chat, weather advice, share card and session delete are built. The AI is the real Anthropic provider when `VISION_PROVIDER=anthropic`, otherwise canned mock answers (same response shapes). Weather is Open-Meteo when `WEATHER_PROVIDER=open_meteo`, otherwise a mock. Rate limits, the daily AI cap, CORS and security headers (phase 3) are built. `POST /v1/transcribe` (stretch) is **not built yet**.

## Conventions

- JSON in and out, except `/diagnose` (multipart).
- `language` is `"en"` or `"pcm"` (Nigerian Pidgin). Default `en`.
- `confidence` values are floats from 0 to 1. Below `0.6` the API always sets `escalate.recommended = true`.
- Crop names: send what the farmer uses. `akpu`→cassava, `ubi`/`isu`→yam, `ede`→cocoyam, `oka`→maize, `ata`→pepper are normalised. Unknown crops pass through as lower-case text (answers will be more general).
- Every response carries `X-Request-ID`.
- Errors are `{"detail": "<friendly message>"}` with these codes. Validation errors (422 from schema checks) use FastAPI's list form: `{"detail": [{"loc": [...], "msg": "...", "type": "..."}]}`.

| Code | Meaning |
|---|---|
| 401 | Missing, invalid or expired token. Call `/auth/anon` again and retry once. Header `WWW-Authenticate: Bearer`. |
| 404 | Session not found, expired, or belongs to another device (indistinguishable on purpose). |
| 413 | Image over 5 MB. |
| 415 | Not a JPEG/PNG/WebP image (checked by content type **and** file bytes). |
| 422 | Invalid fields, undecodable image. |
| 409 | `/share-card` for a session that has no photo check yet. |
| 422 | (also) the AI refused the request. `detail` is a friendly sentence telling the farmer to ask an extension officer. |
| 429 | Rate limit or daily AI cap. Always carries a `Retry-After` header (seconds) and JSON `{"detail": "...", "detail_pcm": "...", "retry_after": 30}`: show or speak the message in the farmer's language, wait, then retry. Also returned (without `detail_pcm`) when the AI vendor is rate limiting. Limits per device and per IP: 60 requests/min overall, 20 `/diagnose` per hour, 60 `/chat` per hour (all configurable). |
| 503 | Weather service unavailable (`/weather/advice` only; diagnose and chat carry on without weather), **or** the AI could not give a valid, safe answer after one retry (`detail` is friendly and safe to speak). Offer a retry. |

## Auth flow

1. The browser generates a random UUID once and keeps it in `localStorage` as the device ID.
2. `POST /v1/auth/anon` with that ID returns a token valid for `expires_in` seconds (24 h).
3. Send `Authorization: Bearer <access_token>` on every other call.
4. On a 401, or shortly before `expires_in`, call `/auth/anon` again.

### POST /v1/auth/anon  (public)

Request
```json
{"device_id": "0b3f6a53-6c2f-4d8f-9c7e-1f6f4d9a2b11"}
```
Response 200
```json
{"access_token": "eyJ...", "token_type": "bearer", "expires_in": 86400}
```
`device_id` must be a UUID, otherwise 422.

## GET /v1/health  (public)

```json
{"status": "ok", "version": "0.1.0", "redis": true, "vision_provider": "mock", "weather_provider": "mock"}
```
`status` is `"degraded"` if Redis is unreachable.

## POST /v1/diagnose

`multipart/form-data`

| Field | Type | Notes |
|---|---|---|
| `image` | file, required | JPEG, PNG or WebP, max 5 MB. Processed in memory only. Compress on-device (about 1280 px long side). |
| `crop` | string, optional | max 40 chars |
| `symptoms_text` | string, optional | max 500 chars, what the farmer says they observe |
| `lat`, `lon` | float, optional | send both or neither. Used for weather; stored rounded to 2 decimals inside the session only. |
| `language` | `en` \| `pcm` | default `en` |

Response 200 (usable photo)
```json
{
  "session_id": "6f1d1c0e-...-uuid",
  "image_quality": {"usable": true, "issue": null, "advice": null},
  "crop": {"name": "cassava", "confidence": 0.95},
  "assessment": {
    "likely_problem": "Cassava mosaic disease",
    "confidence": 0.82,
    "alternatives": [{"name": "Cassava bacterial blight", "confidence": 0.1}],
    "what_i_see": "...", "why_i_think_so": "...", "what_could_change_my_mind": "..."
  },
  "actions": [{"step": 1, "what": "...", "when": "today", "why": "..."}],
  "prevention": ["..."],
  "farmer_questions": ["..."],
  "weather_note": "Rain is likely in the next few hours. Do not spray ...",
  "escalate": {"recommended": true, "reason": "..."},
  "spoken_text": "Full answer for reading aloud."
}
```
- `actions[].when` is `today`, `this_week` or `next_season`.
- `weather_note` is `null` when no location was sent or weather was unavailable. It comes from the deterministic rules, not the AI.
- `spoken_text` has no symbols or lists and is written in the requested language, ready for speech synthesis.

Response 200 (photo not usable). The AI is **not** called and nothing is guessed.
```json
{
  "session_id": null,
  "image_quality": {"usable": false, "issue": "too_dark", "advice": "The photo is too dark. Move into the light and try again."},
  "crop": null, "assessment": null, "actions": [], "prevention": [], "farmer_questions": [],
  "weather_note": null, "escalate": {"recommended": false, "reason": null},
  "spoken_text": "The photo is too dark. Move into the light and try again."
}
```
`issue` values: `too_dark`, `too_small` (too far away), `blurry` (all checked on the server before any AI call), and `not_a_plant`, `blurry`, `too_far`, `too_dark` (judged by the AI). Clients should treat any `issue` as "offer a one-tap retake" and speak `spoken_text`.

**Honesty guarantees the client can rely on** (enforced in code, not only in the prompt):
- `assessment.confidence` below 0.6 always comes with `escalate.recommended = true` and a `reason`.
- Crops outside the six knowledge-base crops (cassava, yam, maize, plantain, cocoyam, pepper) never get a confidence above 0.55, so they escalate.
- Answers never contain doses or banned pesticides; any chemical mention comes with "follow the label" and protective-gear advice. An answer that breaks these rules is regenerated once, then replaced by a 503.

## POST /v1/chat

Request
```json
{"session_id": "uuid (optional)", "message": "Can I spray today?", "language": "pcm", "lat": 5.05, "lon": 7.91, "crop": "cassava"}
```
`message` 1 to 1000 chars. Omit `session_id` to start a new conversation; pass the `session_id` from `/diagnose` to continue its context. Weather is fetched only for time-sensitive questions (spraying, planting, harvesting, drying, rain, fertilizer) and only if a location is known (sent now, or remembered in the session).

Response 200
```json
{
  "session_id": "uuid",
  "answer_text": "...",
  "spoken_text": "...",
  "follow_up_suggestions": ["What should I do first?"],
  "escalate": {"recommended": false, "reason": null},
  "confidence": 0.7
}
```

Unknown, expired or foreign `session_id` gives 404. Start a new conversation without `session_id`.

## GET /v1/weather/advice?lat=&lon=&crop=

`lat` -90..90 and `lon` -180..180 required; `crop` optional (changes heat and drought thresholds).

Response 200
```json
{
  "lat": 5.05, "lon": 7.91,
  "current": {"temp_c": 29.0, "condition_code": 2, "wind_kph": 11.0},
  "days": [
    {"date": "2026-10-01", "condition_code": 2, "high_c": 31.0, "low_c": 24.0, "rain_chance_pct": 20, "rain_mm": 0.5, "wind_kph": 11.0}
  ],
  "advice": [
    {"code": "no_spray_rain_likely", "severity": "warning", "message": "...", "message_pcm": "...", "dates": []}
  ]
}
```
- `days` has 5 entries, today first. `condition_code` is a WMO weather code (0 clear, 1-3 cloudy, 45/48 fog, 51-67 drizzle/rain, 80-82 showers, 95-99 thunderstorm). Map codes to icons and words on the client.
- `advice` is sorted warnings first, then info, then good. Both languages are always present: show `message` or `message_pcm` by the farmer's language and read it aloud.
- Rule codes: `no_spray_rain_likely`, `windy_no_spray`, `spray_ok`, `planting_window`, `heat_warning`, `dry_spell`, `drying_days`. `dates` lists ISO dates for `heat_warning` and `drying_days`.

## DELETE /v1/session/{session_id}

Deletes the session now. Returns `204` with no body, whether or not it existed (and does nothing for another device's session).

## POST /v1/share-card

Request
```json
{"session_id": "uuid from /diagnose"}
```
Response 200
```json
{
  "session_id": "uuid",
  "text": "AgroAI Advisor: crop check
Crop: cassava
Location (about 1 km): 5.05, 7.91
Likely problem: Cassava mosaic disease (sure, 82%)
Other possibilities: Cassava bacterial blight, Nutrient shortage
Farmer observed: yellow curling leaves
What the app saw: ...
Why I am sending this: ...
Questions for the officer / to check on the farm:
1. ...
This is an AI suggestion, not a final diagnosis. Please confirm."
}
```
- Plain text, always English (for the officer), built without AI. No image is included or stored. Location is the session's already-rounded position and the line is omitted if no location was given. "Farmer observed" appears only if `symptoms_text` was sent.
- Pass `text` to the Web Share API, or build a link: `https://wa.me/?text=` + `encodeURIComponent(text)`.
- 404 if the session is unknown, expired or another device's; 409 if the session has no diagnosis (only chat).

## Not built yet

- `POST /v1/transcribe` (stretch). Audio blob plus language; returns `{"text": "..."}`.

## Browser access and limits (phase 3)

- **CORS:** only origins listed in `ALLOWED_ORIGINS` may call the API from a browser. `Retry-After` and `X-Request-ID` are readable by the page.
- **Body size:** `/diagnose` accepts at most 5 MB of image (plus form fields); every other endpoint accepts 64 KB of JSON. Larger bodies get `413`.
- **Strict JSON:** unknown fields in request bodies are rejected with `422`.
- **Headers:** responses carry `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, a CSP and `Cache-Control: no-store`.
- **Daily AI cap:** `DAILY_AI_CALL_LIMIT` paid model calls per UTC day across all users; after that, AI endpoints return `429` until midnight UTC. Weather, share-card and session endpoints keep working.
