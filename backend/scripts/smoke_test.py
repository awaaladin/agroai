"""Smoke test for a running API (local or deployed). Uses only the standard library.

    python scripts/smoke_test.py http://localhost:8001
    python scripts/smoke_test.py https://agroai-api.onrender.com --photo leaf.jpg
    python scripts/smoke_test.py https://agroai-api.onrender.com --origin https://agroai.vercel.app

Without --photo it checks health, auth, weather, chat and security headers (no photo cost). With --photo it also runs a
diagnosis, share card and delete. A real AI call is made for chat and diagnose, so each run costs a little quota.
Exit code 0 = everything passed.
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.request
import uuid

FAILED = []


def call(method, url, headers=None, body=None, raw=None):
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    h = dict(headers or {})
    if body is not None:
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def check(name, ok, detail=""):
    print(("  ok    " if ok else "  FAIL  ") + name + (f"  ({detail})" if detail and not ok else ""))
    if not ok:
        FAILED.append(name)


def multipart(fields, file_field, filename, content, ctype):
    boundary = uuid.uuid4().hex
    parts = []
    for k, v in fields.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\n'
                 f"Content-Type: {ctype}\r\n\r\n".encode() + content + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("base", help="API base URL, e.g. http://localhost:8001")
    ap.add_argument("--photo", help="a JPEG/PNG/WebP crop photo to run through /diagnose")
    ap.add_argument("--origin", help="a browser origin to test CORS with (must be in ALLOWED_ORIGINS)")
    a = ap.parse_args()
    base = a.base.rstrip("/") + "/v1"
    t0 = time.time()

    print("Health")
    s, h, b = call("GET", f"{base}/health")
    info = json.loads(b) if s == 200 else {}
    check("GET /health is 200", s == 200, s)
    check("status ok (database and store reachable)", info.get("status") == "ok", info)
    print(f"        database={info.get('database')} ai={info.get('vision_provider')} weather={info.get('weather_provider')}")

    print("Security headers")
    check("nosniff", h.get("X-Content-Type-Options") == "nosniff")
    check("no-store", "no-store" in h.get("Cache-Control", ""))
    check("CSP present", "Content-Security-Policy" in h)
    if a.base.startswith("https://"):
        check("HSTS (https)", "Strict-Transport-Security" in h)

    if a.origin:
        print("CORS")
        s, h, _ = call("OPTIONS", f"{base}/chat", headers={"Origin": a.origin, "Access-Control-Request-Method": "POST",
                                                           "Access-Control-Request-Headers": "authorization,content-type"})
        check("allowed origin is accepted", h.get("Access-Control-Allow-Origin") == a.origin, h.get("Access-Control-Allow-Origin"))
        s, h, _ = call("OPTIONS", f"{base}/chat", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"})
        check("other origins are refused", h.get("Access-Control-Allow-Origin") is None)

    print("Auth")
    s, _, _ = call("POST", f"{base}/chat", body={"message": "hi"})
    check("no token -> 401", s == 401, s)
    s, _, b = call("POST", f"{base}/auth/anon", body={"device_id": str(uuid.uuid4())})
    token = json.loads(b).get("access_token") if s == 200 else None
    check("POST /auth/anon issues a token", bool(token), s)
    if not token:
        return finish(t0)
    auth = {"Authorization": f"Bearer {token}"}

    print("Weather (real forecast)")
    s, _, b = call("GET", f"{base}/weather/advice?lat=5.04&lon=7.93&crop=cassava", headers=auth)
    w = json.loads(b) if s == 200 else {}
    check("GET /weather/advice is 200", s == 200, s)
    check("5-day forecast", len(w.get("days", [])) == 5)
    check("advice has English and Pidgin", all(i.get("message") and i.get("message_pcm") for i in w.get("advice", [])))

    print("Chat (real AI)")
    s, _, b = call("POST", f"{base}/chat", headers=auth, body={"message": "My cassava leaves are yellow. What should I check?", "language": "en"})
    c = json.loads(b) if s == 200 else {}
    check("POST /chat is 200", s == 200, f"{s} {b[:120]!r}")
    check("answer and spoken text", bool(c.get("answer_text")) and bool(c.get("spoken_text")))
    sid = c.get("session_id")

    if a.photo:
        print("Diagnose (real AI)")
        content = open(a.photo, "rb").read()
        ctype = "image/png" if a.photo.lower().endswith("png") else "image/webp" if a.photo.lower().endswith("webp") else "image/jpeg"
        body, content_type = multipart({"language": "en", "lat": "5.04", "lon": "7.93"}, "image", "leaf", content, ctype)
        s, _, b = call("POST", f"{base}/diagnose", headers={**auth, "Content-Type": content_type}, raw=body)
        d = json.loads(b) if s == 200 else {}
        check("POST /diagnose is 200", s == 200, f"{s} {b[:120]!r}")
        usable = d.get("image_quality", {}).get("usable")
        check("photo judged (usable or a clear retake message)", usable is True or bool(d.get("spoken_text")))
        if usable:
            a_ = d["assessment"]
            check("assessment has reasoning", all(a_.get(k) for k in ("likely_problem", "what_i_see", "why_i_think_so", "what_could_change_my_mind")))
            check("low confidence escalates", a_["confidence"] >= 0.6 or d["escalate"]["recommended"])
            sid = d["session_id"]
            s, _, b = call("POST", f"{base}/share-card", headers=auth, body={"session_id": sid})
            check("POST /share-card has text", s == 200 and "Likely problem" in json.loads(b).get("text", ""), s)

    if sid:
        print("Session")
        s, _, _ = call("DELETE", f"{base}/session/{sid}", headers=auth)
        check("DELETE /session is 204", s == 204, s)
        s, _, _ = call("POST", f"{base}/chat", headers=auth, body={"session_id": sid, "message": "hi"})
        check("deleted session is gone (404)", s == 404, s)

    return finish(t0)


def finish(t0) -> int:
    print(f"\n{'ALL PASSED' if not FAILED else 'FAILED: ' + ', '.join(FAILED)}  ({time.time() - t0:.0f}s)")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
