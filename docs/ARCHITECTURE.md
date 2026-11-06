# Architecture

This document describes the AI_SMP 2.0 system: the preserved legacy prediction
application and the additive research, backtesting, registry, monitoring, and
analytics layers.

## 1. System context

```text
┌────────────────────────────────────────────────────────────────────┐
│ Browser (React + Vite, port 5173)                                  │
│  - legacy pages: dashboard, companies, prediction, comparison      │
│  - research pages: walk-forward, return experiments, backtesting,  │
│    registry, monitoring                                            │
└───────────────────────────────┬────────────────────────────────────┘
                                │ HTTP + JWT
                                ▼
┌────────────────────────────────────────────────────────────────────┐
│ Express gateway (port 5000)                                        │
│  - /api/auth, /api/companies, /api/predictions (legacy)            │
│  - /api/v2/* research proxy (auth, admin, rate limits, timeouts)   │
│  - MongoDB persistence for users, companies, legacy predictions    │
└───────────────────────────────┬────────────────────────────────────┘
                                │ HTTP (internal network)
                                ▼
┌────────────────────────────────────────────────────────────────────┐
│ FastAPI AI service (port 8000)                                     │
│  - legacy: data fetch, feature engineering, train, predict, eval   │
│  - research: walk-forward, return experiments, backtesting,        │
│    model registry, monitoring, background jobs                     │
│  - yfinance data source; file-backed reports and artifacts         │
└────────────────────────────────────────────────────────────────────┘
```

MongoDB stores application data. The research features are intentionally
file-backed so an experiment or candidate model cannot overwrite the active
production model or the legacy prediction history.

## 2. Components

### 2.1 Frontend

- React 18 with React Router and TailwindCSS.
- `src/context/AuthContext.jsx` stores the JWT and current user.
- `src/services/api.js` attaches the bearer token to requests.
- `src/services/researchService.js` wraps the v2 endpoints and polls
  background jobs.
- `src/components/research/ResearchUi.jsx` provides shared metrics, tables,
  status badges, empty states, and warnings.
- Research routes:
  - `/research/walk-forward`
  - `/research/return-forecasting`
  - `/research/backtesting`
  - `/research/registry`
  - `/research/monitoring`
- The existing pages and API calls are preserved. Cross-links from the dashboard
  and stock detail page provide discoverability.

### 2.2 Express gateway

- `src/app.js` mounts `/api/v2` alongside the existing `/api` routes.
- `src/routes/research.routes.js`:
  - requires JWT authentication for every v2 request;
  - applies a read rate limiter (240 requests / 15 minutes);
  - applies an expensive-operation limiter (8 requests / 15 minutes) to
    training, experiments, backtests, registered prediction, and actual-outcome
    updates;
  - applies `adminOnly` to experiment, training, approval, activation, rollback,
    deactivation, and actual-outcome operations; registered-model prediction
    requires authentication but is not admin-only.
- `src/services/aiClient.js` configures the AI-service base URL, a request
  timeout (default 180 seconds), forwards the shared
  `X-Internal-Service-Token` header when `AI_SERVICE_TOKEN` is configured, and
  translates AI-service error payloads into the
  `{ "error": { "code", "message", "details" } }` envelope.
- `src/config/env.js` validates backend configuration before startup. It
  rejects missing or placeholder secrets, weak production secrets, missing
  MongoDB configuration, malformed CORS entries, wildcard CORS in production,
  and invalid timeouts without echoing secret values.
- `src/app.js` applies environment-driven CORS, request IDs, basic security
  headers, and a 1 MB JSON body limit. The error handler logs structured
  context and returns a generic message for 5xx responses.
- `src/controllers/research.controller.js` validates symbols and pagination,
  proxies v2 calls, and, for registered-model predictions, persists a sanitized
  legacy `Prediction` document after a successful prediction.
- The AI service requires the shared service token for every API route. The
  Express gateway is the only intended caller; browser traffic never reaches
  the AI service directly.

### 2.3 FastAPI AI service

`app/main.py` includes the legacy routers and the additive
`research_routes.router` under `/api/v2`. Every API router is mounted with the
`require_service_token` dependency from `app/security.py`; only `/health`
remains public. Interactive docs are disabled unless `ENABLE_DOCS=true`.

Legacy services:

- `data_service.py`: validates symbols and fetches/cleans OHLCV data.
- `feature_engineering.py`: builds 16 causal technical features and the
  training-only next-day target. `transform_features()` retains the latest
  trading day for inference.
- `prediction_service.py`: trains the five models, evaluates them, and produces
  the legacy ensemble prediction.
- `model_manager.py`: saves/loads legacy `saved_models/` artifacts.

Research services:

- `walk_forward_evaluation.py`: chronological expanding-window evaluation,
  final holdout isolation, baseline and ensemble comparison, JSON reports.
- `evaluation_metrics.py`: pure metric functions with abstention-aware
  direction, coverage, normalized errors, and baseline comparisons.
- `return_forecasting_service.py`: absolute/simple/log target families with
  price reconstruction and zero-return baseline.
- `risk_metrics_service.py`: equity, drawdown, trade, monthly-return, and
  strategy-comparison metrics.
- `backtesting_service.py`: next-open execution simulation, five strategies,
  costs/slippage, configurable cost/slippage/threshold sensitivity, causal date
  validation, reproducibility metadata.
- `model_registry_service.py`: versioned candidates, evidence-backed approval,
  explicit activation, rollback, artifact validation, audit log,
  active-model prediction.
- `model_monitoring_service.py`: JSONL prediction tracking, actuals, metrics,
  pagination, freshness, PSI drift.
- `job_service.py`: in-process thread pool with JSON job-state files.
- `security.py`: service-to-service token dependency and fail-closed behavior.

## 3. Request flows

### 3.1 Legacy prediction flow

```text
Browser -> Express /api/predictions/* -> AI service /api/*
        -> X-Internal-Service-Token
        -> yfinance -> clean -> features -> saved models -> ensemble
        -> Express stores Prediction in MongoDB -> Browser
```

Legacy behavior is unchanged by the v2 research layer. The legacy prediction
controller uses the shared `aiClient`, so it forwards the internal token too.

### 3.2 Research experiment flow

```text
Browser -> Express /api/v2/... (JWT + admin + rate limit)
        -> AI service /api/v2/... (X-Internal-Service-Token)
        -> job_service.submit(...) -> HTTP 202 { job }
        -> AI service runs evaluation/backtest in a worker thread
        -> report JSON/CSV on disk
Browser polls /api/v2/jobs/{id} until completed/failed
        -> fetches latest report by symbol
```

The expensive request returns immediately; the worker result is stored in the
job record and the report is written to the configured report directory. This
avoids holding a browser HTTP connection open for a multi-minute experiment.

### 3.3 Registered-model prediction flow

```text
Browser -> Express /api/v2/forecasting/predict/{symbol}
        -> AI service loads the active version's artifacts from model_registry/
        -> validates feature schema and artifact paths
        -> predicts with the version's five models + equal-weight ensemble
        -> optionally records the prediction in monitoring/
        -> Express sanitizes model outputs and stores a legacy Prediction row
```

No active registered model means the v2 prediction returns a conflict; the
legacy production path is not consulted or changed.

### 3.4 Monitoring flow

```text
Prediction -> monitoring/predictions/{SYMBOL}.jsonl (status=pending)
            -> update-actuals maps the feature date to the next session
            -> status=completed, actual_price, error, direction_correct
            -> monitoring summary recomputes metrics from completed records
```

Feature drift compares the most recent 30 feature rows with the preceding 120
rows using PSI over reference quantile bins. It is warning-only.

## 4. Storage layout

| Path | Contents | Overwritten by research? |
|------|----------|--------------------------|
| `ai-service/saved_models/` | Legacy model `.pkl` files and metrics | No |
| `ai-service/evaluation_reports/` | Walk-forward JSON per symbol, summary CSV | Yes, same symbol |
| `ai-service/research_reports/return_forecasting/` | Return experiment JSON and summary CSV | Yes, same symbol |
| `ai-service/research_reports/jobs/` | Background job state JSON | Per job ID |
| `ai-service/backtesting_reports/` | Backtest JSON, equity CSV, trades CSV, comparison CSV, summary CSV | Yes, same symbol |
| `ai-service/model_registry/registry.json` | Version metadata, active version, audit-relevant state | Atomic replace |
| `ai-service/model_registry/audit.jsonl` | Append-only lifecycle audit records | Append-only |
| `ai-service/model_registry/artifacts/{SYMBOL}/{version}/` | Candidate model artifacts | Never overwritten |
| `ai-service/monitoring/predictions/{SYMBOL}.jsonl` | Prediction tracking records | Rewritten atomically on updates |

Report writes use UTF-8 JSON with non-finite values converted to `null`.
Registry and monitoring writes use temporary files plus `os.replace` for atomic
replacement. The registry refuses to reuse an existing artifact directory.

## 5. Evaluation design boundaries

The research layer enforces these boundaries:

- Evaluation uses a separate `EvaluationConfig` and a longer default history
  (`2y`) than legacy training (`1y`).
- Folds are chronological and expanding; no shuffling.
- A validation row's target date must be after the last training target date.
- The final holdout is created before model selection and is not used for
  selection, tuning, or ensemble weights.
- SVR scalers are fitted per fold on training rows only.
- Return predictions are reconstructed into prices before price metrics.
- Zero predicted movement is abstention, not a wrong direction.
- Backtest signals use the feature-day close and execute at the next session's
  open.

See [EVALUATION_METHODOLOGY.md](EVALUATION_METHODOLOGY.md) and
[BACKTESTING_METHODOLOGY.md](BACKTESTING_METHODOLOGY.md) for details.

## 6. Security boundaries

| Boundary | Control |
|----------|---------|
| Browser -> Express | JWT bearer token; protected frontend routes; CORS allowlist |
| Express -> AI service | Shared `X-Internal-Service-Token`; internal service URL; timeout; structured error translation |
| AI service direct access | All API routers require the service token; missing configuration fails closed with 503; `/health` only public |
| Lifecycle/experiment state changes | Express `adminOnly` plus FastAPI service-token dependency |
| Candidate approval | Completed walk-forward report attached, hashed, schema-matched; no automatic approval |
| Candidate activation/rollback | Requires prior explicit approval and attached evidence; validates artifact manifest |
| Registered-model prediction | JWT authentication; expensive rate limiter; service token |
| Expensive v2 routes | Dedicated rate limiter (8 / 15 min) plus global limiter |
| Input validation | Symbol regex, job ID regex, Pydantic ranges, page/page_size checks |
| File paths | Registry and monitoring roots checked with `realpath`; artifact names restricted to plain file names; report IDs restricted to the report directory; registry cannot live inside `saved_models` |
| Artifacts | Exact feature schema, target formulation, model list, SVR scaler, plain `.pkl` names, full manifest |
| Configuration | Production startup validation; no wildcard CORS; DEBUG false by default; docs opt-in |
| Secrets | `.env` files are gitignored; secrets are never returned in API errors; JWT/service tokens generated locally |

The AI service has service-to-service authentication but no end-user
authentication of its own. Keep it on a private network or loopback interface
and do not expose port 8000 publicly. See [SECURITY.md](SECURITY.md) for the
threat model and operational guidance.

## 7. Concurrency and operational behavior

- `job_service` uses a bounded thread pool (`JOB_MAX_WORKERS`, default 2).
- Job state is persisted to `research_reports/jobs/{job_id}.json`.
- Running jobs are not cancelled by `JOB_TIMEOUT_SECONDS` in the current
  implementation; the setting is reserved for a future supervisor.
- Registry and monitoring services use process-local `RLock` objects. They are
  safe for the single-process research deployment shown here, not for multiple
  writers across processes.
- Registry writes use an atomic temporary-file replace; monitoring rewrites its
  per-symbol JSONL atomically.
- Report generation is not transactional across files. A failed job may leave a
  partial report; rerun the experiment to replace it.

## 8. Design decisions and trade-offs

| Decision | Reason | Trade-off |
|----------|--------|-----------|
| Keep research separate from legacy training | Avoid changing existing inference and saved models | Some logic (feature preparation) is shared, but report and registry schemas are additional surface area |
| File-backed reports/registry | Simple, inspectable, no database migration | Not horizontally scalable; single-process locks |
| Background jobs in-process | Avoid adding a broker for a research app | Jobs are lost on process restart if a worker is running; no distributed queue |
| Next-open execution | Avoid same-bar look-ahead in backtests | Does not model intraday fills or market impact |
| Abstention semantics | Zero movement is not a directional call | Directional accuracy has fewer samples and can be `null` |
| Locked holdout | Honest out-of-sample estimate | One holdout path; no repeated holdout tuning |
| Admin-only lifecycle actions | Prevent accidental activation | Requires an admin account and operational discipline |

## 9. Failure modes and responses

- **Yahoo Finance unavailable or rate-limited:** the AI service raises a
  validation/runtime error; the job fails with a structured error and the
  previous report remains in place.
- **Insufficient history:** evaluation raises `InsufficientEvaluationData`;
  registry training rejects candidates below the row threshold.
- **Incompatible artifacts:** activation refuses if the feature schema or
  required files no longer match. This prevents silently loading an old model
  against new features.
- **No active registry model:** v2 registered prediction returns 409; legacy
  prediction is unaffected.
- **Corrupt monitoring JSONL:** the monitoring service reports a read error
  rather than silently dropping records.
- **Corrupt registry JSON:** the service raises a registry schema error; it does
  not attempt to guess or repair metadata.
- **AI-service timeout:** Express returns a 502-style structured error after
  `AI_SERVICE_TIMEOUT_MS`.
