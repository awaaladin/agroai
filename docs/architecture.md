# Architecture

```
Browser PWA / future Kotlin app
        |  HTTPS, Bearer token (anonymous, 24 h)
        v
FastAPI  /v1/*  ──► routers (validate input, auth)
                      │
                      ├─► DiagnoseService ──► image quality gate (no AI call if unusable)
                      │                  ├─► WeatherProvider ──► advice_rules (deterministic)
                      │                  └─► VisionProvider  (Mock now; Anthropic in phase 2)
                      ├─► ChatService   ──► same providers, weather only for time-sensitive questions
                      └─► SessionStore  ──► Redis (30 min TTL, bound to device)
```

Design decisions

- **Providers behind interfaces.** `VisionProvider` and `WeatherProvider` are the only seams to outside services, so tests and demos run offline and the AI vendor can change.
- **Rules decide, AI explains.** Spraying, planting, heat, drought and drying advice come from `weather/advice_rules.py` (pure functions, unit-tested). The AI only receives the results to put into words.
- **Honesty is enforced in code, not just in the prompt.** `apply_guardrails` sets `escalate.recommended` whenever confidence is below 0.6, whatever the provider returned.
- **No guessing on bad photos.** A cheap in-memory check (size, brightness) rejects unusable images before any paid AI call.
- **Anonymous auth.** A browser cannot keep a secret, so `/auth/anon` swaps a random device UUID for a short-lived signed JWT. Sessions are bound to that device; other devices get 404.
- **Stateless API, state in Redis.** Sessions only. Images are never stored.
