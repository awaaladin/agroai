"""Image checks. Everything happens in memory; nothing is written to disk or logged."""
import io

from PIL import Image, ImageChops, ImageFilter, ImageStat, UnidentifiedImageError

from app.schemas.common import Language
from app.schemas.diagnose import ImageQuality

ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}
MAX_PIXELS = 40_000_000  # refuse decompression bombs
MIN_SIDE_PX = 200
DARK_MEAN = 35  # mean luminance 0..255 below which the photo is too dark
# Two blur tests on a 512 px greyscale copy, calibrated on real crop photos (Wikimedia Commons, 1280 px) plus simulated blur:
# 1. mean absolute pixel gradient: real sharp photos scored 4 to 14; flat or extremely blurred images fall below 1.5.
# 2. detail kept after blurring the image once more (gradient ratio): real sharp photos 0.29 to 0.60, moderate-to-heavy
#    blur 0.59 to 0.98. A photo that is already blurry loses little, so a high ratio means "already blurry".
# Both are deliberately lenient: a false rejection annoys a farmer, and the AI also judges blur itself.
BLUR_MIN_GRADIENT = 1.5
BLUR_MAX_DETAIL_RATIO = 0.80

_ADVICE = {
    "too_dark": {
        Language.en: "The photo is too dark. Move into the light and try again.",
        Language.pcm: "The photo dark too much. Go where light dey and try again.",
    },
    "blurry": {
        Language.en: "The photo is blurry. Hold your phone still, let it focus on the leaf, and try again.",
        Language.pcm: "The photo no clear. Hold your phone steady make e focus for the leaf, then try again.",
    },
    "too_small": {
        Language.en: "Come closer to the leaf and hold your phone still.",
        Language.pcm: "Come near the leaf well well and hold your phone steady.",
    },
}


def sniff_mime(data: bytes) -> str | None:
    """Detect the real type from magic bytes (the client-sent content type is not trusted)."""
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def _mean_gradient(gray: Image.Image) -> float:
    w, h = gray.size
    dx = ImageChops.difference(gray.crop((0, 0, w - 1, h - 1)), gray.crop((1, 0, w, h - 1)))
    dy = ImageChops.difference(gray.crop((0, 0, w - 1, h - 1)), gray.crop((0, 1, w - 1, h)))
    return (ImageStat.Stat(dx).mean[0] + ImageStat.Stat(dy).mean[0]) / 2


def assess_quality(data: bytes, language: Language) -> ImageQuality:
    """Cheap pre-check so we never spend an AI call on a photo nobody can read.

    Raises ValueError if the bytes are not a decodable image.
    """
    try:
        img = Image.open(io.BytesIO(data))
        width, height = img.size
        if width * height > MAX_PIXELS:
            raise ValueError("image too large")
        if min(width, height) < MIN_SIDE_PX:
            return ImageQuality(usable=False, issue="too_small", advice=_ADVICE["too_small"][language])
        if img.format == "JPEG":
            img.draft("L", (256, 256))  # fast, low-res decode
        gray = img.convert("L")
        gray.thumbnail((512, 512))
        mean = ImageStat.Stat(gray).mean[0]
        sharpness = _mean_gradient(gray)
        detail_kept = _mean_gradient(gray.filter(ImageFilter.GaussianBlur(1.2))) / sharpness if sharpness > 0 else 1.0
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("not a readable image") from exc
    if mean < DARK_MEAN:
        return ImageQuality(usable=False, issue="too_dark", advice=_ADVICE["too_dark"][language])
    if sharpness < BLUR_MIN_GRADIENT or detail_kept > BLUR_MAX_DETAIL_RATIO:
        return ImageQuality(usable=False, issue="blurry", advice=_ADVICE["blurry"][language])
    return ImageQuality(usable=True)
