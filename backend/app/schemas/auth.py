from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AnonRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_id: UUID


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
