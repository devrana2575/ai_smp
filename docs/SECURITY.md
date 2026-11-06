# Security

This document describes the security posture of AI_SMP after the production
readiness hardening. It is an engineering baseline, not a certification.

## 1. Trust boundaries

```text
Browser
  |  JWT (end-user authentication)
  v
Express backend  --- shared service token --->  FastAPI AI service
  |                                              |
  | MongoDB                                      | local report/registry files
```

- The browser authenticates to Express with a JWT and never receives the
  internal service token.
- Express is the public API boundary. It enforces JWT authentication, admin-only
  lifecycle operations, rate limits, symbol validation, and CORS.
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

The legacy prediction controller and all v2 research proxies use the shared
`backend/src/services/aiClient.js`, which forwards the token server-side.

## 3. End-user authorization

Express keeps the existing JWT behavior. `auth` rejects missing/invalid tokens;
`adminOnly` protects candidate training, evidence attachment, approval,
activation, rollback, deactivation, evaluation runs, return experiments,
backtests, and actual-outcome updates. Registered-model prediction requires a
JWT but is not admin-only.

Frontend authentication and navigation are unchanged. Browser requests continue
to go to Express, never to FastAPI.

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
- Report-read failures do not return filesystem paths or parser details.
- Express logs structured error context with a request ID. Production 5xx
  responses return `Internal server error`; stack traces are development-only.
- Request IDs are accepted from `X-Request-Id` or generated with `crypto`.
- Do not include request bodies or credentials in production error logs.

## 8. Model registry safety

- Registry paths are checked with `realpath`; the registry cannot equal or live
  inside `saved_models/`.
- Artifact manifests must contain exactly the five model artifacts and the SVR
  scaler.
- Artifact names must be plain `.pkl` filenames and must resolve inside the
  version directory.
- Feature schema, target formulation, model list, and SVR-scaler presence are
  validated before prediction or activation.
- Approval requires a completed walk-forward report. The service validates the
  report status, symbol, feature schema, selected model, development metrics,
  baseline comparison, dataset fingerprint, seed, and generation time.
- The registry stores the report ID, SHA-256 hash, metrics, baseline comparison,
  feature schema, dataset period, seed, and evaluation configuration.
- Activation requires prior explicit approval with attached evidence. It never
  auto-approves.
- Rollback requires the previous version to have been approved and to still
  validate.
- No research action writes to `saved_models/`.

## 9. Backtesting integrity

- Only chronological out-of-sample walk-forward rows are traded.
- Every execution date must be strictly after its signal date.
- Signals use the feature-day close; execution uses the next session open.
- Costs and slippage are charged on both entry and exit.
- Cost/slippage/threshold sensitivity scenarios reuse the same rows and
  execution assumptions.
- Reports record source report ID/hash, dataset period, config, feature schema,
  model version, seed, generation time, and synthetic-data status.
- Backtest results are historical simulations. They are never presented as
  guaranteed future profitability.

## 10. Tests

Security and behavioral tests include:

- `ai-service/tests/test_security.py`: public health, unauthorized/authorized
  service calls, fail-closed token configuration, legacy route protection,
  production config rejection/acceptance.
- `ai-service/tests/test_model_registry_service.py`: evidence-backed approval,
  missing evidence rejection, schema mismatch rejection, explicit activation,
  artifact manifest validation, registry path guard.
- `ai-service/tests/test_backtesting_service.py`: causal date rejection,
  sensitivity structure, cost impact, threshold validation.
- `ai-service/tests/test_synthetic_fixture.py`: offline synthetic dataset.
- `backend/tests/config.test.js`: service-token forwarding, production config
  validation, CORS parsing.
- `backend/tests/research.controller.test.js`: symbol validation and structured
  error translation.

## 11. Residual risks and limitations

- Service-token authentication protects against unauthenticated direct access,
  but any process with the token can call the AI service. Protect the secret and
  the network path.
- The service token is static. Rotation requires coordinated restarts unless a
  secret manager or token exchange is added.
- File-backed registry and report directories rely on host-level access control.
  A filesystem writer can tamper with files; hashes detect some changes but are
  not a tamper-proof ledger.
- In-process locks are not safe for multiple AI-service writers across hosts.
  Run one research writer or add a shared lock/store.
- Rate limiting is in-memory per Express instance. A multi-instance deployment
  needs a shared rate-limit store. The global `/api/` budget defaults to 600
  requests per 15 minutes in production and 3,000 in development; tune it with
  `API_RATE_LIMIT_MAX` and `API_RATE_LIMIT_WINDOW_MS`.
- Job failures may expose an exception type/message to authenticated users; do
  not place secrets in exception messages.
- No independent penetration test, dependency-vulnerability audit, or formal
  threat model has been performed.
