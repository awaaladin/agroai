"""Tokens and PIN hashing.

Two kinds of signed token (JWT, HS256):
- anonymous: bound to a browser-generated device ID (a guest).
- user: bound to an account id, issued by login or register.
Both resolve to an "owner key" used to scope sessions: the device UUID for guests, "user:<id>" for accounts.
"""
import hashlib
import hmac
import os
import re
import time
from dataclasses import dataclass
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings

ALGORITHM = "HS256"
_bearer = HTTPBearer(auto_error=False)
USER_PREFIX = "user:"


def create_token(device_id: UUID, settings: Settings, now: float | None = None) -> tuple[str, int]:
    iat = int(now if now is not None else time.time())
    exp = iat + settings.jwt_ttl_seconds
    token = jwt.encode(
        {"sub": str(device_id), "iat": iat, "exp": exp, "typ": "anon"}, settings.jwt_secret, algorithm=ALGORITHM
    )
    return token, settings.jwt_ttl_seconds


def create_user_token(user_id: str, settings: Settings, now: float | None = None) -> tuple[str, int]:
    iat = int(now if now is not None else time.time())
    ttl = settings.user_token_ttl_seconds
    token = jwt.encode(
        {"sub": user_id, "iat": iat, "exp": iat + ttl, "typ": "user"}, settings.jwt_secret, algorithm=ALGORITHM
    )
    return token, ttl


def decode_token(token: str, settings: Settings) -> str:
    """Return the owner key (device id, or 'user:<id>'), or raise jwt.PyJWTError."""
    claims = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM], options={"require": ["sub", "exp"]})
    typ = claims.get("typ")
    if typ == "anon":
        return claims["sub"]
    if typ == "user":
        return USER_PREFIX + claims["sub"]
    raise jwt.InvalidTokenError("wrong token type")


async def current_device(
    request: Request, creds: HTTPAuthorizationCredentials | None = Depends(_bearer)
) -> str:
    """FastAPI dependency: the owner key of the caller (guest device or account) or 401."""
    unauthorized = HTTPException(
        status_code=401,
        detail="Please sign in again.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if creds is None:
        raise unauthorized
    try:
        return decode_token(creds.credentials, request.app.state.settings)
    except jwt.PyJWTError:
        raise unauthorized


@dataclass
class Principal:
    owner: str
    user_id: str | None


async def current_principal(owner: str = Depends(current_device)) -> Principal:
    return Principal(owner=owner, user_id=owner[len(USER_PREFIX):] if owner.startswith(USER_PREFIX) else None)


async def current_user(principal: Principal = Depends(current_principal)) -> str:
    """The account id, or 401 for guests (used by /me endpoints)."""
    if principal.user_id is None:
        raise HTTPException(401, "Please log in to see your farm.", headers={"WWW-Authenticate": "Bearer"})
    return principal.user_id


# ---- phone numbers and PINs -------------------------------------------------------------------------------------

_NG_MOBILE = re.compile(r"^\+234[789][01]\d{8}$")


def normalize_phone(raw: str) -> str | None:
    """'0803 123 4567', '+234 803 123 4567', '2348031234567' -> '+2348031234567'; None if not a Nigerian mobile."""
    digits = re.sub(r"[\s\-().]", "", raw or "")
    if digits.startswith("+"):
        digits = digits[1:]
    if not digits.isdigit():
        return None
    if digits.startswith("0") and len(digits) == 11:
        digits = "234" + digits[1:]
    candidate = "+" + digits
    return candidate if _NG_MOBILE.match(candidate) else None


def mask_phone(phone: str) -> str:
    return phone[:-4].replace(phone[4:-4], "*" * len(phone[4:-4])) + phone[-4:] if len(phone) > 8 else "****"


def valid_pin(pin: str) -> bool:
    return bool(re.fullmatch(r"\d{4,6}", pin or ""))


def _material(pin: str, phone: str, secret: str) -> bytes:
    # Peppered with the server secret and bound to the phone, so a stolen database alone cannot be brute-forced
    # offline and identical PINs hash differently.
    return hmac.new(secret.encode(), f"{phone}:{pin}".encode(), hashlib.sha256).digest()


def hash_pin(pin: str, phone: str, secret: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(_material(pin, phone, secret), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_pin(pin: str, phone: str, secret: str, stored: str) -> bool:
    try:
        _, salt_hex, digest_hex = stored.split("$")
        digest = hashlib.scrypt(_material(pin, phone, secret), salt=bytes.fromhex(salt_hex), n=2**14, r=8, p=1, dklen=32)
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False
