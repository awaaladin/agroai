from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile

from app.api.deps import get_diagnose_service
from app.core.rate_limit import limit
from app.core.security import Principal, current_device, current_principal
from app.schemas.common import Language
from app.schemas.diagnose import DiagnoseResponse
from app.services.crop_names import normalize_crop
from app.services.diagnose_service import DiagnoseService
from app.services.image_utils import ALLOWED_MIME, sniff_mime

router = APIRouter(tags=["diagnose"])


@router.post("/diagnose", response_model=DiagnoseResponse,
             dependencies=[Depends(limit("general")), Depends(limit("diagnose"))])
async def diagnose(
    request: Request,
    image: Annotated[UploadFile, File(description="JPEG, PNG or WebP, up to 5 MB")],
    principal: Annotated[Principal, Depends(current_principal)],
    service: Annotated[DiagnoseService, Depends(get_diagnose_service)],
    crop: Annotated[str | None, Form(max_length=40)] = None,
    symptoms_text: Annotated[str | None, Form(max_length=500)] = None,
    lat: Annotated[float | None, Form(ge=-90, le=90)] = None,
    lon: Annotated[float | None, Form(ge=-180, le=180)] = None,
    language: Annotated[Language, Form()] = Language.en,
) -> DiagnoseResponse:
    max_bytes = request.app.state.settings.max_image_bytes
    if (image.content_type or "").lower() not in ALLOWED_MIME:
        raise HTTPException(415, "Please send a JPEG, PNG or WebP photo.")
    data = await image.read(max_bytes + 1)  # read one byte past the limit to detect oversize without buffering more
    if len(data) > max_bytes:
        raise HTTPException(413, "That photo is too big. Please send one under 5 MB.")
    mime = sniff_mime(data)
    if mime is None:
        raise HTTPException(415, "That file is not a photo I can read. Please send a JPEG, PNG or WebP photo.")
    if (lat is None) != (lon is None):
        raise HTTPException(422, "Send both lat and lon, or neither.")
    try:
        return await service.run(
            device_id=principal.owner, user_id=principal.user_id, image=data, mime=mime, language=language, crop=normalize_crop(crop),
            symptoms_text=symptoms_text, lat=lat, lon=lon,
        )
    except ValueError:
        raise HTTPException(422, "I could not open that photo. Please try another one.")
