"""Vercel entry point: the same FastAPI app, served from the same origin as the web app.

vercel.json rewrites /v1/* here, so the browser calls the API with relative URLs (no CORS, no separate host).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.main import app  # noqa: E402,F401  (Vercel looks for a module-level ASGI `app`)
