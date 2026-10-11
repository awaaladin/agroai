from fastapi import APIRouter, Depends, Request

from app.api.deps import get_accounts
from app.core.rate_limit import limit_ip_only
from app.core.security import create_token, create_user_token
from app.schemas.accounts import AuthResponse, LoginRequest, RegisterRequest
from app.schemas.auth import AnonRequest, TokenResponse
from app.services.accounts import AccountService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/anon", response_model=TokenResponse, dependencies=[Depends(limit_ip_only("anon"))])
async def anonymous_token(body: AnonRequest, request: Request) -> TokenResponse:
    """Exchange a browser-generated device ID for a short-lived signed token (a guest session).

    Call it again when the token is about to expire (expires_in seconds).
    """
    token, ttl = create_token(body.device_id, request.app.state.settings)
    return TokenResponse(access_token=token, expires_in=ttl)


@router.post("/register", response_model=AuthResponse, status_code=201, dependencies=[Depends(limit_ip_only("anon"))])
async def register(body: RegisterRequest, request: Request, accounts: AccountService = Depends(get_accounts)) -> AuthResponse:
    """Create an account with a Nigerian mobile number and a 4 to 6 digit PIN, and sign in."""
    user = await accounts.register(phone=body.phone, pin=body.pin, name=body.name, language=body.language.value,
                                   town=body.town, lat=body.lat, lon=body.lon)
    token, ttl = create_user_token(user.id, request.app.state.settings)
    return AuthResponse(access_token=token, expires_in=ttl, user=await accounts.profile(user))


@router.post("/login", response_model=AuthResponse, dependencies=[Depends(limit_ip_only("anon"))])
async def login(body: LoginRequest, request: Request, accounts: AccountService = Depends(get_accounts)) -> AuthResponse:
    """Sign in with phone number and PIN. After 5 wrong tries the number is locked for 15 minutes."""
    user = await accounts.login(phone=body.phone, pin=body.pin)
    token, ttl = create_user_token(user.id, request.app.state.settings)
    return AuthResponse(access_token=token, expires_in=ttl, user=await accounts.profile(user))
