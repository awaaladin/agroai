"""Run real crop photos through the real AI and real weather, and print what a farmer would get.

    cd backend
    export GEMINI_API_KEY=...                  # free key: https://aistudio.google.com/apikey
    export ANTHROPIC_API_KEY=sk-ant-...        # paid alternative (PowerShell: $env:GEMINI_API_KEY="...")
    python scripts/try_photos.py photos/cassava.jpg photos/yam.jpg photos/maize.jpg
    python scripts/try_photos.py photos/cassava.jpg --lang pcm --crop cassava --symptoms "leaves yellow and curling"
    python scripts/try_photos.py photos/*.jpg --both        # English and Pidgin for each photo

Needs `pip install -r requirements-dev.txt`. Uses an in-memory Redis, so nothing persists. Each photo is one AI call
per language (free on Gemini's free tier, paid on Anthropic). Photos are read from disk here only because you pass them in; the API itself never writes images.
"""
import argparse
import asyncio
import mimetypes
import os
import sys
from pathlib import Path

import fakeredis

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import Settings  # noqa: E402
from app.main import build_vision, build_weather  # noqa: E402
from app.knowledge.safety import audit_diagnosis  # noqa: E402
from app.schemas.common import Language  # noqa: E402
from app.services.crop_names import normalize_crop  # noqa: E402
from app.services.diagnose_service import DiagnoseService  # noqa: E402
from app.services.image_utils import sniff_mime  # noqa: E402
from app.services.session_store import SessionStore  # noqa: E402

UYO = (5.04, 7.93)


async def run(args) -> None:
    settings = Settings(vision_provider=args.provider, weather_provider="open_meteo")
    redis = fakeredis.FakeAsyncRedis(decode_responses=True)
    service = DiagnoseService(build_vision(settings), build_weather(settings, redis), SessionStore(redis, 1800))
    langs = [Language.en, Language.pcm] if args.both else [Language(args.lang)]

    for path in args.photos:
        data = Path(path).read_bytes()
        mime = sniff_mime(data) or mimetypes.guess_type(path)[0]
        for lang in langs:
            print("=" * 78)
            print(f"{path}  [{lang.value}]  provider={settings.vision_provider} "
                  f"model={settings.gemini_model if settings.vision_provider == 'gemini' else settings.vision_model}")
            res = await service.run(
                device_id="try-photos", image=data, mime=mime, language=lang, crop=normalize_crop(args.crop),
                symptoms_text=args.symptoms, lat=UYO[0], lon=UYO[1],
            )
            if not res.image_quality.usable:
                print(f"PHOTO NOT USABLE ({res.image_quality.issue}): {res.spoken_text}")
                continue
            a = res.assessment
            print(f"crop: {res.crop.name} ({res.crop.confidence:.2f})")
            print(f"problem: {a.likely_problem}  confidence {a.confidence:.2f}  alternatives: "
                  + ", ".join(f"{x.name} {x.confidence:.2f}" for x in a.alternatives))
            print(f"what I see: {a.what_i_see}\nwhy: {a.why_i_think_so}\nwould change my mind: {a.what_could_change_my_mind}")
            for x in res.actions:
                print(f"  {x.step}. [{x.when}] {x.what}  (why: {x.why})")
            print("prevention:", *res.prevention, sep="\n  - ")
            print("questions:", *res.farmer_questions, sep="\n  - ")
            print(f"weather note: {res.weather_note}")
            print(f"escalate: {res.escalate.recommended} {res.escalate.reason or ''}")
            print(f"SPOKEN: {res.spoken_text}")
            print(f"safety audit: {audit_diagnosis(res) or 'clean'}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("photos", nargs="+")
    ap.add_argument("--provider", choices=["gemini", "anthropic"], default=None,
                    help="default: gemini if GEMINI_API_KEY is set, else anthropic")
    ap.add_argument("--lang", choices=["en", "pcm"], default="en")
    ap.add_argument("--both", action="store_true", help="run each photo in English and Pidgin")
    ap.add_argument("--crop")
    ap.add_argument("--symptoms")
    parsed = ap.parse_args()
    parsed.provider = parsed.provider or ("gemini" if os.environ.get("GEMINI_API_KEY") else "anthropic")
    asyncio.run(run(parsed))
