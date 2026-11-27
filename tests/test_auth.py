from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core import security
from app.core.config import get_settings
from tests.conftest import ADMIN, CLINICIAN, login

PROTECTED = [
    ("GET", "/patients"),
    ("GET", "/patients/count"),
    ("GET", "/models/diabetes"),
    ("GET", "/predictions/summary"),
    ("GET", "/reports/count"),
    ("GET", "/assistant/status"),
    ("GET", "/monitoring/alerts"),
    ("GET", "/auth/me"),
]


@pytest.mark.parametrize(("method", "path"), PROTECTED)
def test_routes_require_a_token(anon_client, method, path):
    response = anon_client.request(method, path)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_health_is_public(anon_client):
    assert anon_client.get("/health").status_code == 200


def test_login_and_me(anon_client):
    headers = login(anon_client, **CLINICIAN)
    me = anon_client.get("/auth/me", headers=headers).json()
    assert me["email"] == CLINICIAN["email"] and me["role"] == "clinician"
    assert me["last_login_at"] is not None
    assert "password_hash" not in me


def test_login_is_case_insensitive_on_email(anon_client):
    login(anon_client, CLINICIAN["email"].upper(), CLINICIAN["password"])


@pytest.mark.parametrize(
    ("email", "password"),
    [(CLINICIAN["email"], "wrong-password-1"), ("nobody@example.com", "whatever-123")],
)
def test_bad_credentials_get_the_same_error(anon_client, email, password):
    response = anon_client.post("/auth/token", data={"username": email, "password": password})
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password."


def test_expired_and_tampered_tokens_rejected(anon_client):
    secret = get_settings().jwt_secret
    expired = jwt.encode(
        {"sub": "1", "exp": datetime.now(UTC) - timedelta(minutes=1)}, secret, "HS256"
    )
    forged = jwt.encode({"sub": "1", "exp": datetime.now(UTC) + timedelta(hours=1)}, "x" * 32)
    for token in (expired, forged, "not-a-jwt"):
        response = anon_client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401


def test_user_management_is_admin_only(anon_client):
    clinician = login(anon_client, **CLINICIAN)
    admin = login(anon_client, **ADMIN)
    new_user = {
        "email": "nurse@example.com",
        "full_name": "Nurse Joy",
        "password": "Nurse-pass-123",
    }
    assert anon_client.post("/auth/users", json=new_user, headers=clinician).status_code == 403
    assert anon_client.get("/auth/users", headers=clinician).status_code == 403

    created = anon_client.post("/auth/users", json=new_user, headers=admin)
    assert created.status_code == 201 and created.json()["role"] == "clinician"
    assert anon_client.post("/auth/users", json=new_user, headers=admin).status_code == 409
    assert len(anon_client.get("/auth/users", headers=admin).json()) == 3

    nurse = login(anon_client, "nurse@example.com", "Nurse-pass-123")
    user_id = created.json()["id"]
    anon_client.patch(f"/auth/users/{user_id}", json={"is_active": False}, headers=admin)
    assert anon_client.get("/auth/me", headers=nurse).status_code == 401  # token now useless
    response = anon_client.post(
        "/auth/token", data={"username": "nurse@example.com", "password": "Nurse-pass-123"}
    )
    assert response.status_code == 401


def test_admin_cannot_deactivate_self_and_weak_passwords_rejected(anon_client):
    admin = login(anon_client, **ADMIN)
    me = anon_client.get("/auth/me", headers=admin).json()
    response = anon_client.patch(
        f"/auth/users/{me['id']}", json={"is_active": False}, headers=admin
    )
    assert response.status_code == 400
    weak = {"email": "x@example.com", "full_name": "X Y", "password": "1234567890"}
    assert anon_client.post("/auth/users", json=weak, headers=admin).status_code == 422


def test_production_refuses_default_secret(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "environment", "production")
    with pytest.raises(RuntimeError, match="CURANEX_JWT_SECRET"):
        security.check_secret_is_safe()
    monkeypatch.setattr(settings, "jwt_secret", "s" * 48)
    security.check_secret_is_safe()


def test_passwords_are_hashed_not_stored():
    hashed = security.hash_password("Some-pass-123")
    assert hashed.startswith("$argon2")
    assert security.verify_password("Some-pass-123", hashed)
    assert not security.verify_password("other", hashed)
    assert not security.verify_password("anything", None)
