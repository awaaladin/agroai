# Privacy

- **Photos** are processed in memory only. They are never written to disk, stored in Redis, or logged. The share card contains no image.
- **Sessions** live in Redis with a 30-minute TTL (refreshed on use) and hold: language, crop, the diagnosis, the farmer's typed symptoms, recent chat turns and a location rounded to 2 decimals (about 1 km). `DELETE /v1/session/{id}` removes one immediately.
- **Identity** is an anonymous random device UUID chosen by the browser. No name, phone number or email is collected.
- **Logs** are structured JSON with a request ID, method, path, status and duration. No bodies, images, messages or coordinates.
- **Third parties**: the photo and the farmer's text go to the AI vendor (Anthropic or Google Gemini) to produce the answer, and the rounded location goes to Open-Meteo for weather. On Google's free Gemini tier, submitted content may be used to improve Google's products; use a paid tier or Anthropic where that is not acceptable. Redis persistence is off in the compose file.
