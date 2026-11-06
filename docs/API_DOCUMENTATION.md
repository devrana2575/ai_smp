# API Documentation

AI_SMP exposes two API surfaces:

1. the preserved legacy application API under `/api`; and
2. an additive research/model-lifecycle API under `/api/v2`.

Browser clients should call the Express gateway on port 5000. The FastAPI
service on port 8000 is internal and must not be exposed publicly.

## 1. Base URLs

| Service | Base URL | Audience |
|---------|----------|----------|
| Express gateway | `http://localhost:5000/api` | Browser and external clients |
| FastAPI AI service | `http://localhost:8000/api` | Internal only |
| FastAPI research v2 | `http://localhost:8000/api/v2` | Internal only; proxied by Express |

The frontend uses `VITE_API_BASE_URL` (default
`http://localhost:5000/api`) and appends `/v2/...` for research calls.

## 2. Authentication

Obtain a JWT through the legacy auth endpoints:

```http
POST /api/auth/register
Content-Type: application/json

{
  "name": "Researcher",
  "email": "researcher@example.com",
  "password": "a-long-password"
}
```

```http
POST /api/auth/login
Content-Type: application/json

{
  "email": "researcher@example.com",
  "password": "a-long-password"
}
```

Both return:

```json
{
  "id": "...",
  "name": "Researcher",
  "email": "researcher@example.com",
  "role": "user",
  "token": "<jwt>"
}
```

Send the token on every protected request:

```http
Authorization: Bearer <jwt>
```

The first registered user may be a normal user. Lifecycle and experiment
operations require `role = "admin"`; promote the account through your MongoDB
administration if necessary. Never put a JWT in a URL or commit it to source
control.

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

Legacy routes generally return:

```json
{ "detail": "Human-readable message" }
```

Research v2 routes return a structured envelope:

```json
{
  "error": {
    "code": "invalid_symbol",
    "message": "Invalid stock symbol",
    "details": {}
  }
}
```

`details` is present for AI-service errors and may contain field context. The
Express proxy translates AI-service `detail.error` payloads into this envelope.

Common codes:

| Code | Meaning |
|------|---------|
| `invalid_symbol` | Symbol failed validation |
| `invalid_request` | Invalid query/body or evaluation configuration |
| `invalid_job_id` | Job ID failed the allowed-character check |
| `rate_limited` | Rate limit exceeded |
| `walk_forward_report_not_found` | No stored report for the symbol |
| `return_report_not_found` | No stored return report for the symbol |
| `backtest_report_not_found` | No stored backtest report for the symbol |
| `job_not_found` | Unknown job ID |
| `no_active_model` | No active registered model for the symbol |
| `registry_unavailable` | No active model or registry cannot serve a prediction |
| `invalid_service_token` | Missing/incorrect internal service token (AI service direct call) |
| `service_auth_not_configured` | AI service has no service token configured and fails closed |
| `internal_error` | Unhandled server error; details are not exposed |
| `registry_error` | Invalid lifecycle operation |
| `no_prediction` | Active model produced no finite prediction |
| `ai_service_unavailable` | Express could not reach the AI service or it timed out |
| `ai_service_error` | Unstructured AI-service error |
| `report_read_failed` | Stored report could not be read/parsed |

HTTP status usage:

- `200` — success
- `201` — user registered
- `202` — background job accepted
- `400` — validation or experiment configuration error
- `401` — missing/invalid JWT
- `403` — authenticated but not admin
- `404` — report, job, or active model not found
- `409` — registry unavailable or no prediction
- `429` — rate limited
- `500` — internal/storage error
- `502` — AI service unavailable or timed out

## 4. Rate limits and timeouts

| Scope | Limit | Window | Response |
|-------|-------|--------|----------|
| Global Express `/api/` limiter | 600 production / 3,000 development requests (configurable) | 15 minutes | `{ "detail": "Too many requests..." }` |
| Research read limiter | 240 requests | 15 minutes | Structured `rate_limited` |
| Research expensive limiter | 8 requests | 15 minutes | Structured `rate_limited` |

The global limiter is applied before the research router, so the effective
budget is the tighter of the applicable limits. Tune the global limiter with
`API_RATE_LIMIT_WINDOW_MS` and `API_RATE_LIMIT_MAX`.

Express-to-AI-service HTTP calls use `AI_SERVICE_TIMEOUT_MS`
(default 180,000 ms). A timeout is translated to HTTP 502 with code
`ai_service_unavailable`. Background jobs are not cancelled by
`JOB_TIMEOUT_SECONDS` in the current implementation.

## 5. Legacy endpoints

All legacy endpoints are under `/api` and are mounted by Express. Unless noted,
they require `Authorization: Bearer <jwt>`.

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
| POST | `/predictions/train/:symbol` | Yes | Train all five legacy models; body `{"period": "1y"}` |
| POST | `/predictions/predict/:symbol` | Yes | Run legacy prediction and save it; body may select `algorithm` |
| GET | `/predictions/model-status/:symbol` | Yes | Saved model status |
| POST | `/predictions/evaluate/:symbol` | Yes | Evaluate saved models |
| GET | `/predictions/evaluation-summary` | Yes | Aggregate evaluation summary |
| GET | `/predictions/evaluation/:symbol` | Yes | Stored evaluation for a symbol |
| GET | `/predictions/stock-data/:symbol?period=1y` | Yes | Cleaned OHLCV rows |
| GET | `/predictions/stock-info/:symbol` | Yes | Company/quote metadata |
| GET | `/predictions/market-regime/:symbol` | Yes | Descriptive bull/bear/neutral regime indicator |
| GET | `/predictions/history?symbol=...` | Yes | Latest 50 saved predictions |
| GET | `/predictions/compare/:symbol` | Yes | Model comparison + data-point count |
| GET | `/predictions/dashboard` | Yes | Dashboard counts and latest predictions |

The legacy prediction path uses `saved_models/` and is unchanged by v2.
The market-regime response classifies the latest close against 50- and
200-session simple moving averages with 60-session momentum. It is a
descriptive label for historical prices, not a forecast or investment advice.

## 6. Research v2 endpoints

All v2 endpoints require a JWT. "Admin" means the JWT's user has
`role = "admin"`. "Expensive" means the research expensive limiter is applied.

### 6.1 Walk-forward evaluation

#### GET `/api/v2/evaluation/walk-forward/:symbol`

Returns the stored walk-forward JSON report. `404` if no report exists.

#### POST `/api/v2/evaluation/walk-forward/:symbol`

Auth: admin. Expensive. Returns `202` with a job:

```json
{
  "job": {
    "job_id": "642ef069-8c61-427b-b84f-b6d049b30999",
    "job_type": "walk_forward_evaluation",
    "status": "queued",
    "created_at": "2026-11-04T04:36:00+00:00",
    "started_at": null,
    "completed_at": null,
    "result": null,
    "error": null
  }
}
```

Body (all fields optional):

```json
{
  "period": "2y",
  "folds": 5,
  "holdout_fraction": 0.2,
  "min_train_samples": 60,
  "min_validation_samples": 10,
  "min_holdout_samples": 10,
  "initial_train_fraction": 0.5
}
```

Constraints: `folds` 1–20; `holdout_fraction` 0.05–0.5; sample minimums
20–5,000 / 5–1,000 / 5–1,000; `initial_train_fraction` 0.2–0.9.

### 6.2 Return-target experiment

#### GET `/api/v2/forecasting/return-experiment/:symbol`

Returns the stored return-forecasting report. `404` if missing.

#### POST `/api/v2/forecasting/return-experiment/:symbol`

Auth: admin. Expensive. Same body and constraints as walk-forward. Returns `202`
with a `return_forecasting_experiment` job.

### 6.3 Backtesting

#### GET `/api/v2/backtesting/:symbol`

Returns the stored backtest JSON report. `404` if missing.

#### POST `/api/v2/backtesting/:symbol`

Auth: admin. Expensive. Runs a fresh in-memory walk-forward evaluation
internally (without writing a walk-forward report), then the backtest, and
writes the backtest report. Returns `202` with a `backtest` job.

Body extends the evaluation fields:

```json
{
  "period": "2y",
  "folds": 5,
  "holdout_fraction": 0.2,
  "model": "linear_regression",
  "signal_source": "selected",
  "starting_capital": 100000,
  "transaction_cost_bps": 5,
  "slippage_bps": 5,
  "max_capital_allocation": 1.0,
  "buy_threshold": 0.005,
  "sell_threshold": -0.005,
  "run_sensitivity": true,
  "cost_scenarios_bps": [0, 5, 10, 25, 50],
  "slippage_scenarios_bps": [0, 5, 10, 25],
  "threshold_scenarios": [[0, 0], [0.005, -0.005], [0.01, -0.01], [0.02, -0.02]]
}
```

Constraints: `signal_source` is `selected` or `ensemble`; capital > 0 and
≤ 1e12; costs/slippage 0–5,000 bps; allocation (0, 1]; thresholds −1–1;
`buy_threshold` must be ≥ `sell_threshold` when both are supplied. At most 20
scenarios are allowed in each sensitivity list, and every threshold pair must
satisfy `sell <= buy`. If the sensitivity fields are omitted, the defaults
shown above are used.

The completed report contains `strategies`, `strategy_comparison`,
`sensitivity` (cost/slippage cross-product plus threshold scenarios),
`assumptions`, `reproducibility`, `data`, `warnings`, and `limitations`. All
scenario runs reuse the same chronological out-of-sample rows and next-open
execution assumption.

### 6.4 Reports and jobs

#### GET `/api/v2/reports`

Returns file listings for `walk_forward`, `return_forecasting`, `backtesting`,
and `jobs`:

```json
{
  "schema_version": "1.0",
  "categories": {
    "walk_forward": [
      {"name": "COALINDIA_NS_walk_forward.json", "size_bytes": 235393, "modified_at": 1762230975.5}
    ],
    "return_forecasting": [],
    "backtesting": [],
    "jobs": []
  }
}
```

`modified_at` is a filesystem timestamp.

#### GET `/api/v2/jobs?limit=50`

Returns `{ "jobs": [...] }`. `limit` is 1–200; default 50. Jobs are sorted newest
first.

#### GET `/api/v2/jobs/:job_id`

Returns one job record. `404` if unknown. Job statuses: `queued`, `running`,
`completed`, `failed`. On success, `result` contains the report object; on
failure, `error` contains `"ExceptionType: message"`.

### 6.5 Model registry

#### GET `/api/v2/models`

Returns a registry summary:

```json
{
  "schema_version": "1.0",
  "updated_at": "...",
  "symbols": [
    {
      "symbol": "TATASTEEL.NS",
      "active_version": "v0",
      "version_count": 1,
      "candidate_count": 0,
      "last_updated": "..."
    }
  ],
  "total_symbols": 1,
  "total_versions": 1
}
```

#### GET `/api/v2/models/:symbol`

Returns `{ "symbol", "registry", "versions" }` for the symbol. An unknown symbol
returns an empty registry state rather than a 404.

#### GET `/api/v2/models/:symbol/active`

Returns the active version entry. `404` with `no_active_model` if none.

#### POST `/api/v2/models/:symbol/train`

Auth: admin. Expensive. Body:

```json
{ "period": "1y", "notes": "Retrain after Q3" }
```

Returns `202` with a `candidate_training` job. The result is the candidate
version entry. The candidate is not active.

#### POST `/api/v2/models/:symbol/evidence/:version`

Auth: admin. Attaches documented walk-forward evaluation evidence to a
non-active candidate. Body:

```json
{ "report_id": "TATASTEEL_NS_walk_forward.json" }
```

`report_id` is optional; when omitted the service uses the symbol's standard
report file. The report must exist in the configured evaluation report
directory, have `status = "completed"`, match the candidate symbol and exact
feature schema, and contain selected-model development metrics plus a baseline
comparison. The service stores the report ID, SHA-256 hash, generation time,
dataset period/fingerprint, random seed, evaluation configuration, feature
schema, selected model, metrics, and baseline comparison in the registry
entry. Attaching new evidence invalidates any previous approval.

#### POST `/api/v2/models/:symbol/approve/:version`

Auth: admin. Body:

```json
{
  "approved": true,
  "evaluation_report_id": "TATASTEEL_NS_walk_forward.json"
}
```

Approval is evidence-based. The service attaches and validates the walk-forward
report before setting approval metadata; approval fails if no completed report
matches the candidate. The Express proxy supplies `approved_by` from the
authenticated user. Returns the version entry.

#### POST `/api/v2/models/:symbol/activate/:version`

Auth: admin. Body:

```json
{ "approved": true }
```

Validates that the version was explicitly approved with attached evidence,
then re-validates the artifact manifest (exact feature schema, target
formulation, model list, SVR scaler, plain `.pkl` names). Activation never
approves a candidate automatically. Returns the active version entry.

#### POST `/api/v2/models/:symbol/rollback`

Auth: admin. Body:

```json
{ "approved": true }
```

Reactivates the most recent previously active version that is not current.
`400` if no prior activation exists.

#### POST `/api/v2/models/:symbol/deactivate`

Auth: admin. Clears the active version. Returns:

```json
{
  "symbol": "TATASTEEL.NS",
  "previous_active_version": "v0",
  "active_version": null
}
```

### 6.6 Registered-model prediction

#### POST `/api/v2/forecasting/predict/:symbol`

Auth: any authenticated user. Expensive limiter. Body:

```json
{ "record": true }
```

`record` defaults to true. The Express proxy always sends `record: true` and
saves a sanitized legacy `Prediction` row after a successful prediction.

Illustrative response (values are placeholders, not market data):

```json
{
  "symbol": "TATASTEEL.NS",
  "model_id": "TATASTEEL.NS:v0",
  "model_version": "v0",
  "feature_timestamp": "2026-11-03",
  "current_price": 123.45,
  "predicted_price": 124.01,
  "predicted_return": 0.0045,
  "signal": "HOLD",
  "models": {
    "linear_regression": { "prediction": 124.1 },
    "decision_tree": { "prediction": 123.8 },
    "random_forest": { "prediction": 124.3 },
    "svr": { "prediction": 123.9 },
    "xgboost": { "prediction": 123.95 }
  },
  "ensemble_prediction": 124.01,
  "target_formulation": "absolute_price",
  "artifact_schema_version": 1,
  "prediction_id": "...",
  "savedPredictionId": "..."
}
```

Signal threshold: BUY if predicted return > +1%, SELL if < −1%, otherwise HOLD;
N/A if no finite ensemble. The legacy prediction path is not used.

### 6.7 Monitoring

#### GET `/api/v2/monitoring/:symbol`

Returns record counts, model-version counts, tracking metrics, latest prediction,
data freshness, warnings, and limitations. If no completed predictions exist,
`tracking_metrics.metrics` is `null` and a warning says not to report performance
until outcomes mature.

#### GET `/api/v2/monitoring/:symbol/drift`

Returns a PSI-based feature-drift report comparing the most recent
`DRIFT_RECENT_ROWS` (default 30) feature rows against the preceding
`DRIFT_REFERENCE_ROWS` (default 120). A feature is flagged when PSI is greater
than or equal to `DRIFT_PSI_THRESHOLD` (default 0.2). Missing/insufficient values
produce a warning, not a fabricated score.

#### GET `/api/v2/monitoring/:symbol/predictions?page=1&page_size=20`

Returns newest-first records:

```json
{
  "symbol": "TATASTEEL.NS",
  "page": 1,
  "page_size": 20,
  "total": 0,
  "total_pages": 0,
  "items": []
}
```

`page` ≥ 1; `page_size` 1–200.

#### POST `/api/v2/monitoring/:symbol/update-actuals`

Auth: admin. Expensive. Body:

```json
{ "period": "6mo" }
```

Matches pending records to the next session and attaches `actual_price`,
`actual_date`, error fields, `direction_correct`, and `status = "completed"`.
Returns:

```json
{
  "symbol": "TATASTEEL.NS",
  "updated": 3,
  "still_pending": 1,
  "total_records": 4
}
```

Direction is `null` when either the prediction or the actual movement is zero.

## 7. Job workflow

1. Submit an expensive POST. It returns `202` and a job ID.
2. Poll `GET /api/v2/jobs/{job_id}` at a reasonable interval (for example, every
   2–5 seconds).
3. On `completed`, read `result` or fetch the latest report endpoint.
4. On `failed`, inspect `error` and the AI-service logs; fix the input/data issue
   and resubmit.

Jobs are in-process and are not a durable distributed queue. A process restart
can lose queued/running work even though completed job state is persisted to
disk.

## 8. cURL examples

```bash
# Login
TOKEN=$(curl -s -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"..."}' | jq -r .token)

# Latest walk-forward report
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:5000/api/v2/evaluation/walk-forward/COALINDIA.NS

# Start a backtest (admin)
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"period":"2y","folds":5,"starting_capital":100000}' \
  http://localhost:5000/api/v2/backtesting/COALINDIA.NS

# Poll a job
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:5000/api/v2/jobs/<job-id>

# Monitoring summary
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:5000/api/v2/monitoring/COALINDIA.NS
```

## 9. Notes and limitations

- The FastAPI `/api/v2` routes have no end-user authentication. Use Express or a
  private network boundary.
- Stored reports are returned as-is; they include schema versions, warnings,
  limitations, and data fingerprints.
- Pagination is provided for monitoring predictions and job listings only.
  Report and registry responses are bounded by the number of symbols/versions.
- The API does not provide real-time streaming quotes, order placement, or
  brokerage integration.
- All forecasts and backtests are research outputs, not investment advice.
