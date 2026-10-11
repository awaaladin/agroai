"""The signed-in farmer: profile, saved crop checks, and deleting their data. Guests get 401 here."""
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel

from app.api.deps import get_accounts
from app.core.rate_limit import limit
from app.core.security import current_user
from app.schemas.accounts import CheckSummary, Profile, ProfileUpdate
from app.schemas.diagnose import DiagnoseResponse
from app.services.accounts import AccountService

router = APIRouter(prefix="/me", tags=["me"], dependencies=[Depends(limit("general"))])


class SavedCheck(BaseModel):
    id: str
    created_at: datetime
    result: DiagnoseResponse


@router.get("", response_model=Profile)
async def me(user_id: Annotated[str, Depends(current_user)], accounts: Annotated[AccountService, Depends(get_accounts)]) -> Profile:
    return await accounts.profile(await accounts.get(user_id))


@router.patch("", response_model=Profile)
async def update_me(body: ProfileUpdate, user_id: Annotated[str, Depends(current_user)],
                    accounts: Annotated[AccountService, Depends(get_accounts)]) -> Profile:
    return await accounts.profile(await accounts.update(user_id, body))


@router.get("/checks", response_model=list[CheckSummary])
async def checks(user_id: Annotated[str, Depends(current_user)], accounts: Annotated[AccountService, Depends(get_accounts)],
                 limit_: Annotated[int, Query(alias="limit", ge=1, le=100)] = 20,
                 offset: Annotated[int, Query(ge=0)] = 0) -> list[CheckSummary]:
    return await accounts.list_checks(user_id, limit_, offset)


@router.get("/checks/{check_id}", response_model=SavedCheck)
async def check(check_id: str, user_id: Annotated[str, Depends(current_user)],
                accounts: Annotated[AccountService, Depends(get_accounts)]) -> SavedCheck:
    found = await accounts.get_check(user_id, check_id)
    if found is None:
        raise HTTPException(404, "I could not find that check.")
    result, created = found
    return SavedCheck(id=check_id, created_at=created, result=result)


@router.delete("/checks/{check_id}", status_code=204)
async def delete_check(check_id: str, user_id: Annotated[str, Depends(current_user)],
                       accounts: Annotated[AccountService, Depends(get_accounts)]) -> Response:
    await accounts.delete_check(user_id, check_id)
    return Response(status_code=204)


@router.delete("/history", status_code=204)
async def clear_history(user_id: Annotated[str, Depends(current_user)],
                        accounts: Annotated[AccountService, Depends(get_accounts)]) -> Response:
    """Delete every saved check and chat message, keeping the account."""
    await accounts.clear_history(user_id)
    return Response(status_code=204)


@router.delete("", status_code=204)
async def delete_account(user_id: Annotated[str, Depends(current_user)],
                         accounts: Annotated[AccountService, Depends(get_accounts)]) -> Response:
    """Delete the account and everything saved with it. Cannot be undone."""
    await accounts.delete_account(user_id)
    return Response(status_code=204)
