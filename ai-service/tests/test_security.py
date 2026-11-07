from fastapi.testclient import TestClient

from app.config import Settings, settings
from app.main import app
from app.security import SERVICE_TOKEN_HEADER


SERVICE_TOKEN = "test-internal-service-token-0123456789"
AUTH_HEADERS = {SERVICE_TOKEN_HEADER: SERVICE_TOKEN}


def test_health_is_public_but_api_requires_service_token():
    public = TestClient(app)
    assert public.get("/health").status_code == 200

    missing = public.get("/api/evaluation-summary")
    assert missing.status_code == 401
    assert missing.json()["detail"]["error"]["code"] == "invalid_service_token"

    wrong = public.get(
        "/api/evaluation-summary", headers={SERVICE_TOKEN_HEADER: "wrong-token"}
    )
    assert wrong.status_code == 401


def test_authorized_service_call_succeeds():
    client = TestClient(app, headers=AUTH_HEADERS)
    response = client.get("/api/evaluation-summary")
    assert response.status_code == 200
    assert "evaluation_source" in response.json()


def test_api_fails_closed_when_token_is_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "SERVICE_AUTH_TOKEN", "")
    client = TestClient(app, headers=AUTH_HEADERS)
    response = client.get("/api/evaluation-summary")
    assert response.status_code == 503
    assert (
        response.json()["detail"]["error"]["code"]
        == "service_auth_not_configured"
    )


def test_legacy_api_routes_are_also_protected():
    client = TestClient(app)
    response = client.get("/api/model-status/TEST.NS")
    assert response.status_code == 401


def test_production_configuration_rejects_unsafe_values():
    unsafe = Settings()
    unsafe.ENVIRONMENT = "production"
    unsafe.DEBUG = True
    unsafe.SERVICE_AUTH_TOKEN = "short"
    unsafe.CORS_ORIGINS = ["*"]
    try:
        unsafe.validate()
    except ValueError as exc:
        message = str(exc)
        assert "DEBUG must be false" in message
        assert "at least 32 characters" in message
        assert "wildcard CORS" in message
    else:
        raise AssertionError("unsafe production configuration was accepted")


def test_production_configuration_accepts_explicit_safe_values():
    safe = Settings()
    safe.ENVIRONMENT = "production"
    safe.DEBUG = False
    safe.SERVICE_AUTH_TOKEN = "a" * 48
    safe.CORS_ORIGINS = ["https://app.example.test"]
    safe.validate()
