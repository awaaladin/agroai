# AgroAI Advisor backend

Central FastAPI backend for the AgroAI Advisor PWA (and a future Kotlin app). Versioned under `/v1`. Full contract: [../docs/api.md](../docs/api.md).

**Phase 2 status:** works end to end with mock providers (default) or the real Anthropic AI and Open-Meteo weather. Rate limits, spend cap, CORS and security headers (phase 3) are not built yet.

## Run locally (no Docker, no Redis)

```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env                                    # optional; defaults use mock AI and mock weather
uvicorn app.main:app --port 8001 --reload
```
Open http://localhost:8001/docs. Sessions and the weather cache live in a built-in in-memory store (`REDIS_URL=memory://`, the default), so they vanish when the server restarts. Run a single worker with it.

## Run with Docker + Redis (production-like)

```bash
cp .env.example .env        # set JWT_SECRET
docker compose up --build   # API on http://localhost:8000, with a real Redis (REDIS_URL is set by compose)
```

## Try it with curl

```bash
API=http://localhost:8001/v1

# 1. Health (public)
curl $API/health

# 2. Get an anonymous token for this device (generate the UUID once and reuse it)
DEVICE=$(python -c "import uuid; print(uuid.uuid4())")
TOKEN=$(curl -s -X POST $API/auth/anon -H 'Content-Type: application/json' \
  -d "{\"device_id\": \"$DEVICE\"}" | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# 3. Diagnose a photo (multipart). Any JPEG/PNG/WebP up to 5 MB, at least 200 px on the short side.
curl -s -X POST $API/diagnose -H "Authorization: Bearer $TOKEN" \
  -F image=@leaf.jpg -F crop=cassava -F language=pcm -F lat=5.05 -F lon=7.91 \
  -F "symptoms_text=leaves yellow and curling"
# -> note "session_id" in the answer
SESSION=<paste session_id>

# 4. Chat, continuing the diagnosis
curl -s -X POST $API/chat -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d "{\"session_id\": \"$SESSION\", \"message\": \"Can I spray today?\", \"language\": \"en\", \"lat\": 5.05, \"lon\": 7.91}"

# 5. Chat without a session (starts a new one)
curl -s -X POST $API/chat -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"message": "When should I plant maize?", "language": "pcm"}'

# 6. Weather advice
curl -s "$API/weather/advice?lat=5.05&lon=7.91&crop=maize" -H "Authorization: Bearer $TOKEN"

# 7. Share card for an extension officer (plain text, no image)
curl -s -X POST $API/share-card -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json'   -d "{\"session_id\": \"$SESSION\"}"

# 8. Delete the session now
curl -i -X DELETE $API/session/$SESSION -H "Authorization: Bearer $TOKEN"
```
In the mock, `crop=cassava|yam|maize|plantain|pepper` picks that crop's canned diagnosis; adding `symptoms_text="looks healthy"` returns the healthy plant. Send a very dark photo to see `image_quality.usable=false`.

## Real AI and real weather

Pick one AI provider in `.env`:

```bash
# Option A: Google Gemini. Has a FREE tier. Key: https://aistudio.google.com/apikey (Google account, no card)
VISION_PROVIDER=gemini
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-3.5-flash

# Option B: Anthropic Claude. Paid API credits (a Claude or Claude Code subscription does NOT include an API key;
# create one at https://console.anthropic.com and add prepaid credits)
VISION_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
VISION_MODEL=claude-sonnet-5-5

WEATHER_PROVIDER=open_meteo      # free, no key, cached 30 minutes per ~1 km cell
```
Both providers share the same prompts, safety checks and retry logic, so answers have the same shape and rules.
**Privacy note:** on Gemini's free tier Google may use submitted content (including crop photos) to improve its products. Fine for a demo; for real farmers use a paid tier or Anthropic.

Try photos (one AI call per photo per language):
```bash
python scripts/try_photos.py photos/cassava.jpg photos/yam.jpg photos/maize.jpg --both
```
How the AI is kept honest and safe: the system prompt (`app/ai/prompts.py`, versioned) carries the rules; structured outputs plus Pydantic enforce the JSON; `app/knowledge/safety.py` checks every answer against `safety.yaml` (banned pesticides, no doses, label and protective-gear wording) and regenerates once, otherwise returns a friendly 503; low confidence always escalates. `crops.yaml` and `safety.yaml` are starter lists: have an extension officer review them before real use.

## Configuration

See [.env.example](.env.example). Key variables: `JWT_SECRET` (required in production, 32+ chars), `REDIS_URL`, `VISION_PROVIDER` (`mock`, `gemini` or `anthropic`), `GEMINI_API_KEY`, `GEMINI_MODEL`, `ANTHROPIC_API_KEY`, `VISION_MODEL`, `WEATHER_PROVIDER` (`mock` or `open_meteo`), `ALLOWED_ORIGINS`, `DAILY_AI_CALL_LIMIT`, `MAX_IMAGE_BYTES`.

## Layout

```
app/api/v1/     routers (thin)         app/ai/        VisionProvider, Mock/Anthropic/Gemini providers
app/services/   diagnose, chat, sessions, image checks
app/weather/    WeatherProvider, mock, deterministic advice_rules.py
app/schemas/    Pydantic models        app/core/      config, JWT, logging
```
`app/main.py:create_app()` wires everything; tests pass fake Redis and mock providers into it.
