# API Documentation

AI_SMP has one browser-facing API surface: the Express gateway under `/api`.
The FastAPI service exposes the same prediction and market-data operations under
its own `/api` prefix, but it is internal and must not be exposed publicly.

Browser clients should call the Express gateway on port 5000. Express forwards
requests to the FastAPI service on port 8000 with a separate service token.

## 1. Base URLs

| Service | Base URL | Audience |
|---------|----------|----------|
| Express gateway | `http://localhost:5000/api` | Browser and external clients |
| FastAPI AI service | `http://localhost:8000/api` | Internal only |

The frontend uses `VITE_API_BASE_URL` (default
`http://localhost:5000/api`).

## 2. Authentication

Obtain a JWT through the auth endpoints:

```http
POST /api/auth/register
Content-Type: application/json

{
  "name": "Analyst",
  "email": "analyst@example.com",
  "password": "a-long-password"
}
```

```http
POST /api/auth/login
Content-Type: application/json

{
  "email": "analyst@example.com",
  "password": "a-long-password"
}
```

Both return:

```json
{
  "id": "...",
  "name": "Analyst",
  "email": "analyst@example.com",
  "role": "user",
  "token": "<jwt>"
}
```

Send the token on every protected request:

```http
Authorization: Bearer <jwt>
```

Company create, update, and delete operations require `role = "admin"`. Never
put a JWT in a URL or commit it to source control.

### Service-to-service authentication

Browsers authenticate to Express with a JWT. Express authenticates to the
internal FastAPI service with a separate shared secret:

```http
X-Internal-Service-Token: <service token>
```

The AI service requires this header on every `/api/*` route except public
`/health`. If `SERVICE_AUTH_TOKEN` is not configured, protected routes fail
closed with HTTP 503. A missing or incorrect header returns HTTP 401 with
`invalid_service_token`. Browser clients must never call the AI service
directly and must never receive the service token.

## 3. Error format

Application routes return:

```json
{ "detail": "Human-readable message" }
```

AI-service errors may include a structured payload:

```json
{
  "detail": {
    "error": {
      "code": "invalid_service_token",
      "message": "Invalid internal service token"
    }
  }
}
```

HTTP status usage:

- `200` — success
- `201` — user or company created
- `400` — validation or prediction error
- `401` — missing/invalid JWT or service token
- `403` — authenticated but not admin
- `404` — company or saved data not found
- `429` — rate limited
- `500` — internal/storage error
- `502` — AI service unavailable or timed out
- `503` — AI service authentication is not configured

## 4. Rate limits and timeouts

| Scope | Limit | Window | Response |
|-------|-------|--------|----------|
| Global Express `/api/` limiter | 600 production / 3,000 development requests (configurable) | 15 minutes | `{ "detail": "Too many requests..." }` |

Tune the global limiter with `API_RATE_LIMIT_WINDOW_MS` and
`API_RATE_LIMIT_MAX`.

Express-to-AI-service HTTP calls use `AI_SERVICE_TIMEOUT_MS`
(default 180,000 ms). A timeout is translated to HTTP 502 with code
`ai_service_unavailable`.

## 5. Endpoints

All endpoints are under `/api` and are mounted by Express. Unless noted, they
require `Authorization: Bearer <jwt>`.

### 5.1 Auth

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/auth/register` | No | Create a user and return a JWT |
| POST | `/auth/login` | No | Authenticate and return a JWT |
| GET | `/auth/profile` | Yes | Current user profile |
| PUT | `/auth/profile` | Yes | Update `name` / `email` |
| PUT | `/auth/change-password` | Yes | Change password with `currentPassword` / `newPassword` |

### 5.2 Companies

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/companies` | Yes | List active companies |
| GET | `/companies/symbol/:symbol` | Yes | Company by ticker |
| GET | `/companies/:id` | Yes | Company by MongoDB ID |
| POST | `/companies` | Admin | Add a company |
| PUT | `/companies/:id` | Admin | Update a company |
| DELETE | `/companies/:id` | Admin | Delete a company |
| POST | `/companies/seed` | Yes | Seed the default company set |

### 5.3 Predictions and data

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/predictions/train/:symbol` | Yes | Train all five models; body `{"period": "1y"}` |
| POST | `/predictions/predict/:symbol` | Yes | Run a prediction and save it; body may select `algorithm` |
| GET | `/predictions/model-status/:symbol` | Yes | Saved model status |
| POST | `/predictions/evaluate/:symbol` | Yes | Evaluate saved models |
| GET | `/predictions/evaluation-summary` | Yes | Aggregate evaluation summary |
| GET | `/predictions/evaluation/:symbol` | Yes | Stored evaluation for a symbol |
| GET | `/predictions/stock-data/:symbol?period=1y` | Yes | Cleaned OHLCV rows |
| GET | `/predictions/stock-info/:symbol` | Yes | Company/quote metadata |
| GET | `/predictions/market-regime/:symbol` | Yes | Descriptive bull/bear/neutral regime indicator |
| GET | `/predictions/history?symbol=...` | Yes | Latest 50 saved predictions |
| GET | `/predictions/compare/:symbol` | Yes | Model comparison and data-point count |
| GET | `/predictions/dashboard` | Yes | Dashboard counts and latest predictions |

The prediction path uses `saved_models/` for production model artifacts. The
market-regime response classifies the latest close against 50- and 200-session
simple moving averages with 60-session momentum. It is a descriptive label for
historical prices, not a forecast or investment advice.

## 6. Notes and limitations

- The FastAPI routes have no end-user authentication. Use Express or a private
  network boundary.
- The API does not provide real-time streaming quotes, order placement, or
  brokerage integration.
- All forecasts are estimates, not investment advice or a guarantee of profit.
