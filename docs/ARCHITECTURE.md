# Architecture

This document describes AI_SMP: a React frontend, an Express gateway, MongoDB
application storage, and an internal FastAPI service for market data and machine
learning.

## 1. System context

```text
┌────────────────────────────────────────────────────────────────────┐
│ Browser (React + Vite, port 5173)                                  │
│  - dashboard, companies, stock detail, prediction, comparison      │
│  - results, reports                                                │
└───────────────────────────────┬────────────────────────────────────┘
                                │ HTTP + JWT
                                ▼
┌────────────────────────────────────────────────────────────────────┐
│ Express gateway (port 5000)                                        │
│  - /api/auth, /api/companies, /api/predictions                     │
│  - JWT authentication, admin checks, rate limits, timeouts         │
│  - MongoDB persistence for users, companies, saved predictions     │
└───────────────────────────────┬────────────────────────────────────┘
                                │ HTTP (internal network)
                                ▼
┌────────────────────────────────────────────────────────────────────┐
│ FastAPI AI service (port 8000)                                     │
│  - data fetch and cleaning                                         │
│  - feature engineering                                             │
│  - model training, evaluation, and prediction                      │
│  - yfinance data source; saved_models/ artifacts                   │
└────────────────────────────────────────────────────────────────────┘
```

MongoDB stores application data and prediction history. The AI service stores
trained model artifacts in `ai-service/saved_models/`.

## 2. Components

### 2.1 Frontend

- React 18 with React Router and TailwindCSS.
- `src/context/AuthContext.jsx` stores the JWT and current user.
- `src/services/api.js` attaches the bearer token to requests.
- `src/pages/` contains the login/register flow, dashboard, company pages,
  stock detail, prediction, comparison, results, and reports.
- Protected routes require an authenticated user; admin-only company actions are
  enforced by the backend.

### 2.2 Express gateway

- `src/app.js` mounts the auth, company, and prediction routes.
- `src/routes/prediction.routes.js` requires JWT authentication for prediction
  and saved-data operations.
- `src/config/env.js` validates backend configuration before startup. It
  rejects missing or placeholder secrets, weak production secrets, missing
  MongoDB configuration, malformed CORS entries, wildcard CORS in production,
  and invalid timeouts without echoing secret values.
- `src/app.js` applies environment-driven CORS, request IDs, basic security
  headers, and a 1 MB JSON body limit. The error handler logs structured
  context and returns a generic message for 5xx responses.
- `src/services/aiClient.js` configures the AI-service base URL, a request
  timeout (default 180 seconds), and forwards the shared
  `X-Internal-Service-Token` header when `AI_SERVICE_TOKEN` is configured.
- The AI service requires the shared service token for every API route. The
  Express gateway is the only intended caller; browser traffic never reaches
  the AI service directly.

### 2.3 FastAPI AI service

`app/main.py` includes the prediction and stock-data routers. Every API router
is mounted with the `require_service_token` dependency from `app/security.py`;
only `/health` remains public. Interactive docs are disabled unless
`ENABLE_DOCS=true`.

Services:

- `data_service.py`: validates symbols and fetches/cleans OHLCV data.
- `feature_engineering.py`: builds 16 causal technical features and the
  training-only next-day target. `transform_features()` retains the latest
  trading day for inference.
- `prediction_service.py`: trains the five models, evaluates them, produces the
  equal-weight ensemble prediction, and calculates the descriptive market
  regime.
- `model_manager.py`: saves/loads `saved_models/` artifacts.
- `security.py`: service-to-service token dependency and fail-closed behavior.

## 3. Request flow

```text
Browser -> Express /api/predictions/* -> AI service /api/*
        -> X-Internal-Service-Token
        -> yfinance -> clean -> features -> saved models -> ensemble
        -> Express stores Prediction in MongoDB -> Browser
```

Training and prediction are synchronous from the browser's perspective. The
Express client timeout (`AI_SERVICE_TIMEOUT_MS`) bounds long-running requests.

The market-regime endpoint uses the same cleaned price data and classifies the
latest close against 50- and 200-session simple moving averages with
60-session momentum. It is descriptive, not a forecast.

## 4. Storage layout

| Path | Contents |
|------|----------|
| MongoDB | Users, companies, and saved prediction records |
| `ai-service/saved_models/{SYMBOL}/` | Five model `.pkl` files, SVR scaler, metrics, evaluation data |

## 5. Security boundaries

| Boundary | Control |
|----------|---------|
| Browser -> Express | JWT bearer token; protected frontend routes; CORS allowlist |
| Express -> AI service | Shared `X-Internal-Service-Token`; internal service URL; timeout |
| AI service direct access | All API routers require the service token; missing configuration fails closed with 503; `/health` only public |
| Company changes | Express JWT authentication plus `adminOnly` |
| Input validation | Symbol validation and bounded request bodies |
| Configuration | Production startup validation; no wildcard CORS; DEBUG false by default; docs opt-in |
| Secrets | `.env` files are gitignored; secrets are never returned in API errors |

The AI service has service-to-service authentication but no end-user
authentication of its own. Keep it on a private network or loopback interface
and do not expose port 8000 publicly. See [SECURITY.md](SECURITY.md) for the
threat model and operational guidance.

## 6. Failure modes and responses

- **Yahoo Finance unavailable or rate-limited:** the AI service raises a
  runtime error and Express returns a structured error to the browser.
- **Insufficient history:** training or prediction returns an error explaining
  that the symbol does not have enough rows.
- **Missing model artifacts:** prediction returns an error until the symbol is
  trained.
- **AI-service timeout:** Express returns a 502-style error after
  `AI_SERVICE_TIMEOUT_MS`.
- **MongoDB unavailable:** authentication, company management, and prediction
  history requests fail until the database is reachable.
