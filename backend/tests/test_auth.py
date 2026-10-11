import time
import uuid

import jwt
import pytest

from app.core.config import Settings
from app.core.security import ALGORITHM, create_token, decode_token
from tests.conftest import auth_headers


def test_token_roundtrip_is_bound_to_device(settings):
    device = uuid.uuid4()
    token, ttl = create_token(device, settings)
    assert ttl == 24 * 3600
    assert decode_token(token, settings) == str(device)


def test_expired_token_rejected(settings):
    token, _ = create_token(uuid.uuid4(), settings, now=time.time() - 2 * settings.jwt_ttl_seconds)
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_token(token, settings)


def test_token_signed_with_other_secret_rejected(settings):
    other = Settings(jwt_secret="a-completely-different-secret-value-123456", _env_file=None)
    token, _ = create_token(uuid.uuid4(), other)
    with pytest.raises(jwt.InvalidSignatureError):
        decode_token(token, settings)


def test_none_algorithm_rejected(settings):
    forged = jwt.encode({"sub": "x", "exp": time.time() + 60, "typ": "anon"}, key="", algorithm="none")
    with pytest.raises(jwt.PyJWTError):
        decode_token(forged, settings)


def test_wrong_token_type_rejected(settings):
    token = jwt.encode({"sub": "x", "exp": time.time() + 60, "typ": "admin"}, settings.jwt_secret, algorithm=ALGORITHM)
    with pytest.raises(jwt.InvalidTokenError):
        decode_token(token, settings)


def test_production_refuses_weak_secret():
    with pytest.raises(ValueError):
        Settings(env="production", _env_file=None)


def test_anon_endpoint_issues_token(client):
    r = client.post("/v1/auth/anon", json={"device_id": str(uuid.uuid4())})
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer" and body["expires_in"] == 86400 and body["access_token"]


def test_anon_rejects_non_uuid(client):
    assert client.post("/v1/auth/anon", json={"device_id": "not-a-uuid"}).status_code == 422


@pytest.mark.parametrize("method,path", [
    ("get", "/v1/weather/advice?lat=5&lon=7.9"),
    ("post", "/v1/chat"),
    ("post", "/v1/diagnose"),
    ("delete", f"/v1/session/{uuid.uuid4()}"),
])
def test_protected_endpoints_need_token(client, method, path):
    r = getattr(client, method)(path)
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"


def test_garbage_token_is_401(client):
    r = client.get("/v1/weather/advice?lat=5&lon=7.9", headers={"Authorization": "Bearer nonsense"})
    assert r.status_code == 401


def test_health_is_public(client):
    r = client.get("/v1/health")
    assert r.status_code == 200 and r.json()["status"] == "ok" and r.json()["redis"] is True
    assert "x-request-id" in r.headers


def test_each_device_gets_its_own_token(client):
    a, b = auth_headers(client), auth_headers(client)
    assert a != b
