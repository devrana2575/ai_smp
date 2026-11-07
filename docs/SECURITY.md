# Security

This document describes the security posture of AI_SMP. It is an engineering
baseline, not a certification.

## 1. Trust boundaries

```text
Browser
  |  JWT (end-user authentication)
  v
Express backend  --- shared service token --->  FastAPI AI service
  |                                              |
  | MongoDB                                      | saved_models/ files
```

- The browser authenticates to Express with a JWT and never receives the
  internal service token.
- Express is the public API boundary. It enforces JWT authentication, admin-only
  company operations, rate limits, symbol validation, and CORS.
- FastAPI is an internal service. Every API router requires the shared service
  token; only `/health` is public.
- The AI service has no end-user accounts. Do not expose its port publicly.

## 2. Service-to-service authentication

- Header: `X-Internal-Service-Token`
- AI-service setting: `SERVICE_AUTH_TOKEN`
- Backend setting: `AI_SERVICE_TOKEN` (must be identical)
- Implementation: `ai-service/app/security.py`, mounted on every API router in
  `ai-service/app/main.py`
- Comparison: `secrets.compare_digest`
- Missing header or mismatch: HTTP 401 `invalid_service_token`
- Missing server-side configuration: HTTP 503
  `service_auth_not_configured` (fail closed)
- Public route: `GET /health` only
- Interactive docs and OpenAPI: disabled unless `ENABLE_DOCS=true`

The prediction controller uses `backend/src/services/aiClient.js`, which
forwards the token server-side.

## 3. End-user authorization

Express keeps the existing JWT behavior. `auth` rejects missing/invalid tokens;
`adminOnly` protects company create, update, and delete operations. Prediction,
market-data, and saved-report reads require a JWT but are not admin-only.

Frontend authentication and navigation remain protected. Browser requests
continue to go to Express, never directly to FastAPI.

## 4. Configuration safety

AI service:

- `DEBUG` defaults to `false`.
- `HOST` defaults to `127.0.0.1`.
- `ENABLE_DOCS` defaults to `false`.
- Startup validation rejects invalid environments/ports, empty CORS lists,
  production `DEBUG=true`, missing/short production service tokens, wildcard
  CORS, and non-absolute CORS origins.
- `CORS_ORIGINS` is an explicit comma-separated allowlist.

Backend:

- `src/config/env.js` validates `JWT_SECRET`, `MONGODB_URI`, `AI_SERVICE_TOKEN`,
  `CORS_ORIGINS`, and `AI_SERVICE_TIMEOUT_MS`.
- Placeholder/weak secrets are rejected. Production requires at least 32
  characters for JWT and service secrets.
- Wildcard and malformed CORS origins are rejected.
- Validation error messages name the setting, never the secret value.

## 5. Secrets

- Keep `.env` files out of source control; both `.env.example` files contain
  placeholders only.
- Generate secrets with a CSPRNG, for example:
  `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
- Use different values for `JWT_SECRET`, `SERVICE_AUTH_TOKEN`, and any database
  credentials. Rotate the service token by updating both services together.
- Do not log request headers, environment dumps, `.env` contents, JWTs, or the
  service token. Startup validation prints setting names only.
- Production deployments should inject secrets from a secret manager or
  protected environment rather than a checked-in file.

## 6. CORS and headers

- Express CORS uses `CORS_ORIGINS`. Production must list exact origins.
- FastAPI CORS uses the same explicit allowlist setting.
- Express sets `X-Request-Id`, `X-Content-Type-Options: nosniff`,
  `X-Frame-Options: DENY`, and `Referrer-Policy: no-referrer`.
- JSON bodies are limited to 1 MB.

## 7. Error handling, logging, and request IDs

- FastAPI has a global exception handler that logs the exception server-side and
  returns a generic `internal_error` payload.
- Express logs structured error context with a request ID. Production 5xx
  responses return `Internal server error`; stack traces are development-only.
- Request IDs are accepted from `X-Request-Id` or generated with `crypto`.
- Do not include request bodies or credentials in production error logs.

## 8. Tests

Security and behavioral tests include:

- `ai-service/tests/test_security.py`: public health, unauthorized/authorized
  service calls, fail-closed token configuration, legacy route protection,
  production config rejection/acceptance.
- `ai-service/tests/test_data_service.py`: symbol validation and data cleaning.
- `ai-service/tests/test_market_regime.py`: market-regime classification.
- `backend/tests/config.test.js`: service-token forwarding, production config
  validation, CORS parsing.

## 9. Residual risks and limitations

- Service-token authentication protects against unauthenticated direct access,
  but any process with the token can call the AI service. Protect the secret and
  the network path.
- The service token is static. Rotation requires coordinated restarts unless a
  secret manager or token exchange is added.
- `saved_models/` relies on host-level access control. A filesystem writer can
  tamper with model artifacts.
- Rate limiting is in-memory per Express instance. A multi-instance deployment
  needs a shared rate-limit store. The global `/api/` budget defaults to 600
  requests per 15 minutes in production and 3,000 in development; tune it with
  `API_RATE_LIMIT_MAX` and `API_RATE_LIMIT_WINDOW_MS`.
- No independent penetration test or formal threat model has been performed.
