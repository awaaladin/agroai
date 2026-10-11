# Deploying the backend

The API is one container (or one `uvicorn` process). Browsers need HTTPS for camera and microphone, so deploy somewhere that gives you HTTPS automatically. All three options below do.

## What you need first

| Thing | Where from |
|---|---|
| Postgres database URL | Neon, Supabase, or the host's own Postgres. Looks like `postgresql://user:pass@host:5432/db?sslmode=require`. Tables are created and filled with starter crop and safety data automatically on first start. |
| `GEMINI_API_KEY` | https://aistudio.google.com/apikey (free tier; content may be used by Google) or `ANTHROPIC_API_KEY` (paid) |
| `JWT_SECRET` | `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| The web app's origin | e.g. `https://agroai.vercel.app`, for `ALLOWED_ORIGINS` |

## Environment variables

| Variable | Required | Notes |
|---|---|---|
| `ENV` | yes | `production` (turns on HSTS and refuses weak secrets or `*` origins) |
| `JWT_SECRET` | yes | 32+ random characters |
| `DATABASE_URL` | yes | Your Postgres URL. `postgres://` and `postgresql://` both work; `sslmode=require` is handled |
| `VISION_PROVIDER` | yes | `gemini` or `anthropic` |
| `GEMINI_API_KEY` / `ANTHROPIC_API_KEY` | yes (one) | Keep secret. Gemini also powers `/v1/transcribe` |
| `GEMINI_MODEL`, `GEMINI_FALLBACK_MODELS` | no | default `gemini-3.5-flash` with automatic fallbacks |
| `VISION_MODEL` | no | Anthropic model, default `claude-sonnet-5-5` |
| `ALLOWED_ORIGINS` | yes | Exact browser origins, comma separated. Never `*` |
| `DAILY_AI_CALL_LIMIT` | recommended | Global cap on paid AI calls per UTC day (default 200) |
| `TRUSTED_PROXY_HOPS` | yes | `1` on Render, Railway and Fly so per-IP limits see the real client |
| `REDIS_URL` | no | Default `memory://` is fine for one instance. Use a real Redis only if you run several instances (rate limits and the weather cache are shared through it) |
| `RATE_*`, `SESSION_TTL_SECONDS`, `MAX_IMAGE_BYTES`, `KNOWLEDGE_REFRESH_SECONDS` | no | See `.env.example` |

Run **one instance** unless you set `REDIS_URL` to a real Redis: the built-in store keeps rate-limit counters and the weather cache in the process.

## Option A: Render (simplest)

1. Push the repo to GitHub (the `agroai/backend` folder is the service root).
2. Render dashboard > New > **Web Service** > pick the repo. Root directory `agroai/backend`. Runtime **Docker** (it uses the `Dockerfile`).
3. Add the environment variables above. Health check path: `/v1/health`.
4. Deploy. Your URL is `https://<name>.onrender.com`. The free plan sleeps after 15 minutes idle, so the first request is slow: open it a few minutes before a demo.

## Option B: Railway

1. New project > Deploy from GitHub repo > set the root to `agroai/backend` (Dockerfile is detected).
2. Variables tab: add the variables above. Settings > Networking > Generate domain.
3. Healthcheck path `/v1/health`.

## Option C: Fly.io

```bash
cd agroai/backend
fly launch --no-deploy            # accept the Dockerfile, pick a region (e.g. Johannesburg or Paris, closest to Nigeria)
fly secrets set JWT_SECRET=... DATABASE_URL=... GEMINI_API_KEY=... ALLOWED_ORIGINS=https://your-web-app
fly secrets set ENV=production VISION_PROVIDER=gemini TRUSTED_PROXY_HOPS=1
fly deploy
```
In `fly.toml` set `internal_port = 8000` and an HTTP check on `/v1/health`.

## Smoke test

After every deploy:

```bash
python scripts/smoke_test.py https://YOUR-API-URL --origin https://YOUR-WEB-APP --photo some-leaf.jpg
```
It checks health (database reachable), security headers, CORS (allowed origin accepted, others refused), the token flow, real weather, a real chat, and with `--photo` a diagnosis, share card and session delete. It exits 0 only if everything passed. Leave out `--photo` to save AI quota.

## Operating notes

- **Editing crop and safety knowledge:** change rows in the `crops`, `crop_problems`, `crop_aliases` and `safety_terms` tables. The running app picks edits up within `KNOWLEDGE_REFRESH_SECONDS` (default 5 minutes). Starter rows are only inserted into empty tables, so your edits are never overwritten. Have an extension officer review the starter lists before real use.
- **Sessions** are rows in `sessions` and are deleted when they expire (30 minutes) or when the farmer deletes them.
- **Spend:** `DAILY_AI_CALL_LIMIT` is global. When it is reached the AI endpoints answer `429` until midnight UTC.
- **Logs** contain request ids, paths, status codes and timings only: no photos, messages or coordinates.
- **Rotate keys** if they were ever pasted into a chat or committed. Never commit `.env`.
