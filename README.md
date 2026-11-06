# AI_SMP 2.0 — AI Stock Market Research & Prediction Platform

AI_SMP is a full-stack research platform for Indian Metal & Mining equities. It
keeps the original five-model price-prediction application and adds a
leakage-aware research stack: chronological walk-forward evaluation, return-target
experiments, simulated backtesting, a versioned model registry, prediction
monitoring, versioned APIs, and an analytics UI.

> **Important:** This is research and educational software, not investment
> advice. Historical simulations are not evidence of future profitability.
> Market data is fetched from Yahoo Finance through `yfinance`; results depend on
> the data available at run time and are labelled with their evaluation period.
> No live brokerage integration or real-money trading is implemented.

---

## What is in the 2.0 platform?

| Area | Capability |
|------|------------|
| Existing prediction app | JWT authentication, company management, five ML models, equal-weight ensemble, BUY/SELL/HOLD signals, dashboard and comparison views |
| Phase 2 evaluation | Chronological expanding-window walk-forward validation, locked final holdout, naive-persistence baseline, equal-weight ensemble comparison |
| Phase 2.1 return experiments | Absolute-price, simple-return, and log-return targets with price reconstruction, zero-return baseline, and normalized metrics |
| Phase 3 backtesting | Buy-and-hold, cash, persistence, model-directional, and threshold strategies with costs, slippage, position sizing, trade histories, equity curves, and risk metrics |
| Phase 4 model lifecycle | File-backed model registry, versioned candidate training, approval, activation, rollback, artifact validation, audit log, registered-model prediction |
| Monitoring | Prediction tracking, actual-outcome updates, completed-prediction metrics, data freshness, feature drift (PSI) |
| APIs | Existing Express API preserved; additive authenticated `/api/v2` research APIs with validation, pagination, rate limits, structured errors |
| Analytics UI | Walk-forward, return experiments, backtesting, registry, and monitoring pages under `/research` |
| Quality | 89 Python tests, 3 Node proxy tests, frontend build, ESLint, Ruff, dependency audits |

The legacy training and prediction paths are unchanged by the research features.
Research reports and registry artifacts are stored separately from
`saved_models/`; activating a registered model affects only the v2
registered-model prediction path.

---

## Tech stack

| Layer | Technology |
|-------|------------|
| Frontend | React 18, Vite 5, TailwindCSS 3, Recharts |
| Backend | Node.js 20.19+, Express 4, MongoDB, Mongoose, JWT, `express-rate-limit` |
| AI service | Python 3.9–3.12 (3.11 recommended), FastAPI, scikit-learn, XGBoost, pandas, NumPy, joblib |
| Data | Yahoo Finance via `yfinance` |
| Research storage | JSON/CSV reports, file-backed model registry, JSONL monitoring records |

Python 3.13+ is not supported by the pinned scientific packages.

---

## Repository layout

```text
ai_smp/
├── ai-service/                    # Python FastAPI: legacy ML + research services
│   ├── app/
│   │   ├── models/                # Five ML model wrappers
│   │   ├── routes/                # Legacy and additive /api/v2 routes
│   │   ├── schemas/               # Pydantic request/response models
│   │   └── services/              # Data, features, prediction, evaluation,
│   │                              # backtesting, registry, monitoring, jobs
│   ├── scripts/                   # CLI runners for research experiments
│   ├── tests/                     # Pytest suite
│   ├── evaluation_reports/        # Walk-forward reports and summary
│   ├── research_reports/          # Return experiments and job state
│   ├── backtesting_reports/       # Backtest reports, equity curves, trades
│   ├── model_registry/            # Registry metadata and research artifacts
│   ├── monitoring/                # JSONL prediction tracking
│   ├── saved_models/              # Legacy production model artifacts
│   ├── requirements.txt
│   └── requirements-dev.txt
├── backend/                       # Express gateway and JSON API
│   ├── src/controllers/           # Legacy and research controllers
│   ├── src/routes/                # /api and /api/v2 routes
│   ├── src/services/aiClient.js   # Timeout-aware AI-service client
│   └── tests/                     # Node test runner tests
├── frontend/                      # React + Vite UI
│   └── src/pages/                 # Existing pages + /research analytics pages
├── docs/                          # In-depth methodology and architecture docs
│   └── PROJECT_OVERVIEW.md        # Legacy project overview
└── README.md
```

The required methodology documents are in [`docs/`](docs/):

- [Architecture](docs/ARCHITECTURE.md)
- [ML methodology](docs/ML_METHODOLOGY.md)
- [Evaluation methodology](docs/EVALUATION_METHODOLOGY.md)
- [Backtesting methodology](docs/BACKTESTING_METHODOLOGY.md)
- [Model registry](docs/MODEL_REGISTRY.md)
- [API documentation](docs/API_DOCUMENTATION.md)
- [Contributing](docs/CONTRIBUTING.md)
- [Development setup](docs/DEVELOPMENT_SETUP.md)

---

## Quick start

### Prerequisites

- Python 3.9–3.12 (3.11 recommended)
- Node.js 20.19+ (or 22.13+/24+)
- MongoDB running on `localhost:27017`
- Network access to Yahoo Finance for live data fetches

### 1. AI service (port 8000)

```powershell
cd ai-service
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Put the generated value in `ai-service/.env` as `SERVICE_AUTH_TOKEN`, then run:

```powershell
python run.py
```

On macOS/Linux use `source venv/bin/activate`. If PowerShell blocks activation:
`Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`.

The API fails closed if the service token is missing. Interactive docs are
disabled unless `ENABLE_DOCS=true`; do not enable them publicly.

Optional development/test dependencies:

```powershell
pip install -r requirements-dev.txt
```

### 2. Backend (port 5000)

```powershell
cd backend
Copy-Item .env.example .env
npm install
npm run dev
```

Generate a strong JWT secret rather than using the placeholder:

```powershell
node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"
```

Set `AI_SERVICE_TOKEN` in `backend/.env` to the same value as the AI service's
`SERVICE_AUTH_TOKEN`. The backend forwards it to the internal service.

### 3. Frontend (port 5173)

```powershell
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>. If the backend is not on port 5000, copy
`frontend/.env.example` to `frontend/.env.local` and set `VITE_API_BASE_URL`
(including the `/api` suffix).

---

## Environment variables

### `ai-service/.env`

```dotenv
ENVIRONMENT=development
HOST=127.0.0.1
PORT=8000
DEBUG=false
ENABLE_DOCS=false
SERVICE_AUTH_TOKEN=<generated-service-token>
CORS_ORIGINS=http://localhost:5173,http://localhost:3000,http://localhost:8080
```

`SERVICE_AUTH_TOKEN` is required for API requests; the service fails closed if
it is absent. Production startup also rejects `DEBUG=true`, wildcard CORS,
malformed origins, and tokens shorter than 32 characters.

Research defaults can be overridden without changing the legacy training path:

```dotenv
EVALUATION_PERIOD=2y
EVALUATION_FOLDS=5
EVALUATION_HOLDOUT_FRACTION=0.2
EVALUATION_MIN_TRAIN_SAMPLES=60
EVALUATION_MIN_VALIDATION_SAMPLES=10
EVALUATION_MIN_HOLDOUT_SAMPLES=10
EVALUATION_INITIAL_TRAIN_FRACTION=0.5
EVALUATION_REPORT_DIR=...
RESEARCH_REPORT_DIR=...
RETURN_REPORT_DIR=...
BACKTEST_REPORT_DIR=...
MODEL_REGISTRY_DIR=...
MONITORING_DIR=...
JOB_STATE_DIR=...
JOB_MAX_WORKERS=2
JOB_TIMEOUT_SECONDS=1800
BACKTEST_STARTING_CAPITAL=100000
BACKTEST_TRANSACTION_COST_BPS=5
BACKTEST_SLIPPAGE_BPS=5
BACKTEST_MAX_CAPITAL_ALLOCATION=1.0
BACKTEST_BUY_THRESHOLD=0.005
BACKTEST_SELL_THRESHOLD=-0.005
RISK_FREE_RATE=0.0
TRADING_DAYS_PER_YEAR=252
DRIFT_PSI_THRESHOLD=0.2
DRIFT_REFERENCE_ROWS=120
DRIFT_RECENT_ROWS=30
```

`JOB_TIMEOUT_SECONDS` is reserved configuration; the in-process job runner does
not currently cancel running jobs at that limit. HTTP calls from Express to the
AI service are bounded by `AI_SERVICE_TIMEOUT_MS`.

### `backend/.env`

```dotenv
NODE_ENV=development
PORT=5000
MONGODB_URI=mongodb://localhost:27017/ai-smp
JWT_SECRET=replace-with-a-long-random-secret
JWT_EXPIRE=7d
AI_SERVICE_URL=http://localhost:8000
AI_SERVICE_TOKEN=<same value as SERVICE_AUTH_TOKEN>
AI_SERVICE_TIMEOUT_MS=180000
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
```

Backend startup validation rejects missing/placeholder/weak secrets, missing
MongoDB configuration, wildcard production CORS, malformed origins, and invalid
timeouts without printing secret values.

### `frontend/.env.local` (optional)

```dotenv
VITE_API_BASE_URL=http://localhost:5000/api
```

---

## Research workflow

### Walk-forward evaluation

```powershell
cd ai-service
.\venv\Scripts\python.exe -m scripts.run_walk_forward_evaluation COALINDIA.NS HINDALCO.NS HINDZINC.NS JINDALSTEL.NS JSWSTEEL.NS TATASTEEL.NS
```

Writes `evaluation_reports/{SYMBOL}_walk_forward.json` and
`evaluation_reports/walk_forward_summary.csv`. It never writes to
`saved_models/`.

### Return-target experiments

```powershell
.\venv\Scripts\python.exe -m scripts.run_return_forecasting COALINDIA.NS HINDALCO.NS HINDZINC.NS JINDALSTEL.NS JSWSTEEL.NS TATASTEEL.NS
```

Writes `research_reports/return_forecasting/` reports and a family-level summary.

### Backtests

```powershell
.\venv\Scripts\python.exe -m scripts.run_backtesting COALINDIA.NS HINDALCO.NS HINDZINC.NS JINDALSTEL.NS JSWSTEEL.NS TATASTEEL.NS
```

Writes JSON reports, equity-curve CSVs, trade CSVs, strategy-comparison CSVs, and
`backtesting_reports/backtest_summary.csv`. Reports include configurable
cost/slippage cross-product and threshold sensitivity scenarios, causal
signal/execution validation, assumptions, and reproducibility metadata.

A deterministic artificial dataset for offline tests lives at
`ai-service/tests/fixtures/synthetic_ohlcv.csv`. It is not market data; reports
derived from it must be labelled synthetic.

### Analytics UI

After signing in, open:

- `/research/walk-forward`
- `/research/return-forecasting`
- `/research/backtesting`
- `/research/registry`
- `/research/monitoring`

Experiment, training, activation, rollback, and actual-outcome update actions
require an admin token. Registered-model prediction requires authentication.
GET views require authentication.

### Register and activate a model

1. Run a completed walk-forward evaluation for the symbol.
2. Train a candidate: `POST /api/v2/models/{symbol}/train`
3. Attach the evaluation report:
   `POST /api/v2/models/{symbol}/evidence/{version}` with
   `{"report_id": "{SYMBOL}_walk_forward.json"}`.
4. Review metrics, baseline comparison, feature schema, seed, report hash, and
   `candidate_vs_active`.
5. Approve it: `POST /api/v2/models/{symbol}/approve/{version}` with
   `{"approved": true, "evaluation_report_id": "{SYMBOL}_walk_forward.json"}`.
6. Activate it: `POST /api/v2/models/{symbol}/activate/{version}` with
   `{"approved": true}`. Activation requires prior approval with evidence.
7. Predict with the active version: `POST /api/v2/forecasting/predict/{symbol}`
8. Roll back with `POST /api/v2/models/{symbol}/rollback`
   (`{"approved": true}` required)

Training never approves or activates a candidate. Approval never happens
automatically, and no research action writes to `saved_models/`.

All expensive operations run as background jobs; poll `GET /api/v2/jobs/{job_id}`.

---

## Actual experimental results

These are the results produced by the live reports in this working tree. They
are a historical simulation on six NSE symbols using a 2-year `yfinance`
history, five expanding walk-forward folds, and an 89-row locked final holdout
(COALINDIA, HINDALCO, HINDZINC, JSWSTEEL, TATASTEEL; JINDALSTEL has 89 holdout
rows and 354 development rows). They are not a profitability claim.

### Phase 2 — selected model versus baselines (holdout)

The development-selected model was `linear_regression` for all six symbols. The
naive-persistence baseline had lower RMSE than both the selected model and the
equal-weight ensemble for all six symbols.

| Symbol | Selected LR RMSE | Persistence RMSE | Ensemble RMSE | Selected direction accuracy | Ensemble direction accuracy |
|--------|------------------|------------------|---------------|-----------------------------|-----------------------------|
| COALINDIA.NS | 5.2904 | **5.1340** | 9.8415 | 47.13% | 48.28% |
| HINDALCO.NS | 16.0471 | **14.9091** | 19.2646 | 53.93% | 50.56% |
| HINDZINC.NS | 11.2199 | **11.0827** | 11.7107 | 50.56% | 53.93% |
| JINDALSTEL.NS | 17.9109 | **17.3097** | 19.3793 | 51.69% | 53.93% |
| JSWSTEEL.NS | 20.0331 | **19.9396** | 26.7991 | 52.81% | 51.69% |
| TATASTEEL.NS | 2.6784 | **2.5096** | 4.4366 | 43.82% | 41.57% |

The persistence baseline abstains from direction by construction, so its
directional accuracy is reported as `null` (not zero) with 0% signal coverage and
100% abstention.

### Phase 2.1 — target formulation

For every symbol and every family (absolute price, simple return, log return),
the best reconstructed-price model was the zero-return persistence baseline. The
best family by reconstructed-price RMSE and by return RMSE was
`absolute_price` for all six symbols. In other words, these experiments did not
show a return-target formulation beating the zero-return benchmark on this data.

### Phase 3 — simulated backtest (default costs)

Default settings: 100,000 starting capital, 5 bps transaction cost, 5 bps
slippage, long-only, one position at a time, forced final liquidation. Cash and
persistence return 0% by design.

| Symbol | Buy & hold | Model directional | Threshold | Highest simulated return |
|--------|------------|-------------------|-----------|--------------------------|
| COALINDIA.NS | **13.94%** | 3.95% | -2.21% | Buy & hold |
| HINDALCO.NS | **18.23%** | 0.67% | 9.43% | Buy & hold |
| HINDZINC.NS | **7.81%** | -31.97% | -20.89% | Buy & hold |
| JINDALSTEL.NS | 3.78% | -1.10% | **5.19%** | Threshold |
| JSWSTEEL.NS | 14.64% | 2.05% | **17.17%** | Threshold |
| TATASTEEL.NS | **5.19%** | -5.29% | -7.84% | Buy & hold |

The model-directional strategy lost money on HINDZINC, JINDALSTEL, and
TATASTEEL, and the threshold strategy lost money on COALINDIA, HINDZINC, and
TATASTEEL. Buy-and-hold was the highest-return strategy for four of six symbols.
These outcomes are sensitive to the single historical path and should not be
generalized.

---

## Testing and quality checks

From `ai-service/`:

```powershell
.\venv\Scripts\python.exe -m pytest -q
ruff check .
.\venv\Scripts\python.exe -m compileall -q app tests scripts
```

Current result in this audit: **104 Python tests passed**; Ruff 0.16.7 and
compileall pass. A small number of httpx/TestClient deprecation warnings remain.

From `backend/`:

```powershell
npm test
npm run lint
```

Current result in this audit: **7 Node tests passed**; ESLint passes.

From `frontend/`:

```powershell
npm run lint
npm run build
```

Run these after frontend changes; a chunk-size warning is expected for the
single-page bundle and is not a build failure.

CI is defined in `.github/workflows/ci.yml`. It runs the Python, backend, and
frontend checks above on pushes and pull requests. Do not mark a workflow
successful unless these commands actually pass.

Dependency checks: `npm ls --depth=0` succeeds in both Node packages. Python
runtime imports were verified with the pinned environment. A non-force
`npm audit fix` updated `axios`, Express, body-parser, and related transitive
packages. Final status:

- Backend production tree (`npm audit --omit=dev`): **0 vulnerabilities**.
  Full backend audit: 6 moderate advisories in dev tooling (`minimatch` via
  ESLint 10 and nodemon). npm's suggested fix is a breaking force change.
- Frontend production tree (`npm audit --omit=dev`): 2 moderate `react-router`
  advisories. The fix is `react-router-dom` 7.18.5, a major migration that was
  not performed.
- Full frontend audit: 9 advisories (8 moderate, 1 high), including Vite 5 /
  esbuild dev-server issues and `minimatch`. npm's only fix is a force upgrade
  to Vite 8 or a downgrade of ESLint.

Do not run `npm audit fix --force` without reviewing breaking changes and
re-running the full test/build suite.

---

## Security notes

- The FastAPI service is internal-only. Every `/api/*` route requires a shared
  `X-Internal-Service-Token`; only `/health` is public. If the token is not
  configured, protected routes fail closed with HTTP 503. Express forwards the
  token server-side from `AI_SERVICE_TOKEN`.
- Express remains the browser authentication/authorization boundary. All
  `/api/v2` routes require a JWT. Experiment, training, evidence attachment,
  approval, activation, rollback, deactivation, and actual-outcome update routes
  require the `admin` role; registered-model prediction requires authentication.
  Rate limits are applied at both the global Express level and the research
  router level.
- Production startup validation rejects debug mode, weak/missing secrets,
  wildcard CORS, malformed origins, and invalid timeouts without echoing secret
  values. `DEBUG` defaults to false; interactive FastAPI docs are opt-in.
- Symbols, job IDs, versions, artifact paths, pagination, numeric ranges, and
  request bodies are validated. Registry paths cannot live inside
  `saved_models/`; artifact names must be plain `.pkl` files; report IDs must
  resolve inside the report directory.
- Candidate approval requires a completed, schema-matched walk-forward report
  with metrics and a baseline comparison. Activation requires prior explicit
  approval and attached evidence; it never auto-approves. Evidence includes the
  report ID/hash, dataset period/fingerprint, seed, config, feature schema, and
  metrics.
- AI-service HTTP calls have a configurable timeout (`AI_SERVICE_TIMEOUT_MS`,
  default 180 seconds). Background jobs run in-process; do not expose the AI
  service publicly.
- Never commit `.env` files, JWTs, service tokens, model artifacts, or generated
  monitoring data. The repository's `.gitignore` covers environment files and
  common build output.
- Research output is stored separately from legacy production models. Only an
  explicit, audited activation changes the v2 registered-model path.

See [docs/SECURITY.md](docs/SECURITY.md) and
[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for details and residual risks.

---

## Limitations

- The models use a small set of technical indicators and a single historical
  path; they do not model fundamentals, news, regime changes, or market impact.
- Live `yfinance` results can change as new sessions arrive and as Yahoo revises
  history. The reports include a data fingerprint for reproducibility checks.
- Backtests are simplified: proportional costs and slippage, no taxes, borrow,
  liquidity constraints, corporate-action adjustments, or intraday fills.
- Feature drift is a warning signal, not proof of model degradation.
- MongoDB is required for the legacy authentication/company/prediction app; the
  research analytics endpoints themselves are file-backed in the AI service.
- No result in this repository should be presented as a guarantee of profit.

---

## License

MIT
