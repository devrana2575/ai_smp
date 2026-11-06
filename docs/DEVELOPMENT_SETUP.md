# Development Setup

This guide sets up the full AI_SMP 2.0 stack locally: FastAPI AI service,
Express gateway, MongoDB, and the React frontend. It also covers the research
CLI, tests, linting, and common Windows issues.

## 1. Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Python | 3.9–3.12 (3.11 recommended) | 3.13+ is not supported by the pinned scientific stack |
| Node.js | 20.19+, 22.13+, or 24+ | Required by ESLint 10 in the dev toolchain; the app also runs on modern LTS releases |
| npm | 10+ | Ships with modern Node |
| MongoDB | 6+ | Local service on `27017` by default |
| Git | Current | Needed for branch/worktree workflow |
| OS | Windows, macOS, or Linux | Commands below show PowerShell and POSIX variants where useful |

Optional: `curl` and `jq` for API testing.

## 2. Clone and branch

```powershell
git clone <repository-url> ai_smp
cd ai_smp
git switch -c feature/your-change
```

Do not commit `.env` files, tokens, `node_modules/`, `venv/`, `dist/`, or local
model/report artifacts.

## 3. AI service

```powershell
cd ai-service
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

POSIX:

```bash
cd ai-service
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt -r requirements-dev.txt
```

Create `ai-service/.env` from `.env.example` and generate a service token:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

```dotenv
ENVIRONMENT=development
HOST=127.0.0.1
PORT=8000
DEBUG=false
ENABLE_DOCS=false
SERVICE_AUTH_TOKEN=<generated-service-token>
CORS_ORIGINS=http://localhost:5173,http://localhost:3000,http://localhost:8080
```

The API fails closed if `SERVICE_AUTH_TOKEN` is missing. Use the same value as
`AI_SERVICE_TOKEN` in `backend/.env`.

Run:

```powershell
python run.py
```

Verify:

```powershell
Invoke-RestMethod http://localhost:8000/health
```

Expected:

```json
{"status":"healthy","app":"AI Stock Prediction Service","version":"1.0.0"}
```

Interactive docs are disabled by default. Set `ENABLE_DOCS=true` for local
development only; production deployments should leave it false. Direct API
calls then require the service-token header, which browsers must never receive.

### If PowerShell blocks activation

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1
```

Alternatively call the interpreter directly without activation:

```powershell
.\venv\Scripts\python.exe -m pytest -q
```

### If the virtual environment has no pip

Recreate it rather than mixing system packages:

```powershell
Remove-Item -Recurse -Force venv
python -m venv venv
.\venv\Scripts\python.exe -m ensurepip --upgrade
.\venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt
```

## 4. MongoDB

Start MongoDB locally (service, Docker, or a managed instance) and confirm it is
reachable:

```powershell
mongosh "mongodb://127.0.0.1:27017/ai-smp" --eval "db.runCommand({ ping: 1 })"
```

The default URI is `mongodb://localhost:27017/ai-smp`. If you use a different
port or host, update `backend/.env`.

## 5. Backend

```powershell
cd backend
Copy-Item .env.example .env
npm install
```

Generate a strong JWT secret and put it in `backend/.env`:

```powershell
node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"
```

Example `backend/.env`:

```dotenv
PORT=5000
MONGODB_URI=mongodb://localhost:27017/ai-smp
JWT_SECRET=<generated-secret>
JWT_EXPIRE=7d
AI_SERVICE_URL=http://localhost:8000
AI_SERVICE_TOKEN=<same value as ai-service SERVICE_AUTH_TOKEN>
AI_SERVICE_TIMEOUT_MS=180000
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
NODE_ENV=development
```

Run:

```powershell
npm run dev
```

Verify:

```powershell
Invoke-RestMethod http://localhost:5000/health
```

Expected:

```json
{"status":"healthy","service":"AI-SMP Backend"}
```

If port 5000 is occupied, set a different `PORT` and update the frontend API
base URL (and the Vite proxy target if you rely on `/api` proxying).

## 6. Frontend

```powershell
cd frontend
Copy-Item .env.example .env.local
npm install
npm run dev
```

Default `.env.local`:

```dotenv
VITE_API_BASE_URL=http://localhost:5000/api
```

If the backend uses `5050`, change it to
`VITE_API_BASE_URL=http://localhost:5050/api`. Restart Vite after changing env
values.

Open <http://localhost:5173>, register/sign in, and seed companies through the UI
or:

```powershell
$token = (Invoke-RestMethod -Method Post http://localhost:5000/api/auth/login `
  -ContentType "application/json" `
  -Body '{"email":"you@example.com","password":"..."}').token

Invoke-RestMethod -Method Post http://localhost:5000/api/companies/seed `
  -Headers @{ Authorization = "Bearer $token" }
```

The seed endpoint requires authentication but not admin. Creating/updating/
deleting companies and all model-lifecycle actions require an admin user.
Promote an account in MongoDB if needed:

```javascript
db.users.updateOne({ email: "you@example.com" }, { $set: { role: "admin" } })
```

## 7. Research CLI

Run from `ai-service/` after activating the venv:

```powershell
# Walk-forward evaluation
.\venv\Scripts\python.exe -m scripts.run_walk_forward_evaluation `
  COALINDIA.NS HINDALCO.NS HINDZINC.NS JINDALSTEL.NS JSWSTEEL.NS TATASTEEL.NS

# Return-target experiments
.\venv\Scripts\python.exe -m scripts.run_return_forecasting `
  COALINDIA.NS HINDALCO.NS HINDZINC.NS JINDALSTEL.NS JSWSTEEL.NS TATASTEEL.NS

# Backtests
.\venv\Scripts\python.exe -m scripts.run_backtesting `
  COALINDIA.NS HINDALCO.NS HINDZINC.NS JINDALSTEL.NS JSWSTEEL.NS TATASTEEL.NS
```

Outputs:

| Command | Output |
|---------|--------|
| Walk-forward | `evaluation_reports/{SYMBOL}_walk_forward.json`, `walk_forward_summary.csv` |
| Return experiments | `research_reports/return_forecasting/{SYMBOL}_return_forecasting.json`, summary CSV |
| Backtests | `backtesting_reports/{SYMBOL}_backtest.json`, equity/trades/comparison CSVs, summary CSV |
| Background jobs | `research_reports/jobs/{job_id}.json` |
| Registry | `model_registry/registry.json`, `audit.jsonl`, `artifacts/...` |
| Monitoring | `monitoring/predictions/{SYMBOL}.jsonl` |

These are research artifacts. They are separate from the legacy
`saved_models/` directory.

## 8. Tests, lint, and build

### AI service

```powershell
cd ai-service
.\venv\Scripts\python.exe -m pytest -q
ruff check .
.\venv\Scripts\python.exe -m compileall -q app tests scripts
```

Current baseline in this audit: `109 passed`; Ruff `0.16.7` and compileall pass.
The tests set a test-only service token in `tests/conftest.py`. If your
environment has no `ruff`, use the pinned `ruff` from `requirements-dev.txt` or
a globally installed matching version.

### Backend

```powershell
cd backend
npm test
npm run lint
node --check src/app.js
node --check src/config/env.js
node --check src/routes/research.routes.js
node --check src/controllers/research.controller.js
```

Current baseline in this audit: `8 passed`; ESLint passes.

### Frontend

```powershell
cd frontend
npm run lint
npm run build
```

Current baseline: ESLint passes; Vite build succeeds. A chunk-size warning is
expected for the single-page bundle and is not a build failure.

### Continuous integration

`.github/workflows/ci.yml` runs three independent jobs on push and pull requests:

- **AI service:** Python 3.11, `pip install -r requirements-dev.txt`,
  `ruff check .`, `pytest -q`.
- **Backend:** Node 20, `npm ci`, `npm run lint`, `npm test`.
- **Frontend:** Node 20, `npm ci`, `npm run lint`, `npm run build`.

Do not mark the workflow successful unless these commands actually pass. Run
the same commands locally before pushing.

## 9. Environment variables

### AI service

`SERVICE_AUTH_TOKEN` is required for the API to serve requests. Generate a
development value and use the same value as `AI_SERVICE_TOKEN` in the backend:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

```dotenv
ENVIRONMENT=development
HOST=127.0.0.1
PORT=8000
DEBUG=false
ENABLE_DOCS=false
SERVICE_AUTH_TOKEN=<generated-service-token>
CORS_ORIGINS=http://localhost:5173,http://localhost:3000,http://localhost:8080
```

Production validation additionally requires `DEBUG=false`, no wildcard CORS
origins, absolute http(s) origins, and a service token of at least 32 characters.

Research defaults are optional and can be set in `ai-service/.env`:

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

`JOB_TIMEOUT_SECONDS` is reserved; the in-process job runner does not currently
cancel a running job at that limit. The Express AI-client timeout
(`AI_SERVICE_TIMEOUT_MS`) does bound HTTP requests.

### Backend

```dotenv
PORT=5000
MONGODB_URI=mongodb://localhost:27017/ai-smp
JWT_SECRET=<generated-secret>
JWT_EXPIRE=7d
AI_SERVICE_URL=http://localhost:8000
AI_SERVICE_TOKEN=<same value as SERVICE_AUTH_TOKEN>
AI_SERVICE_TIMEOUT_MS=180000
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
NODE_ENV=development
```

Production startup validates `JWT_SECRET`, `MONGODB_URI`, `AI_SERVICE_TOKEN`,
`CORS_ORIGINS`, and `AI_SERVICE_TIMEOUT_MS`. Placeholder or weak production
secrets, wildcard origins, and malformed origins are rejected without echoing
the secret values.

### Frontend

```dotenv
VITE_API_BASE_URL=http://localhost:5000/api
```

## 10. Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `Activate.ps1 cannot be loaded` | PowerShell execution policy | Run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` |
| `No module named pip` in venv | Venv created without pip | Recreate venv and run `python -m ensurepip --upgrade` |
| `yfinance` returns empty data | Network/VPN, invalid symbol, or unavailable period | Check connectivity and symbol; do not fabricate rows |
| `MongoDB Error` on backend start | MongoDB not running or wrong URI | Start MongoDB and verify `MONGODB_URI` |
| Frontend gets 401 | Missing/expired token | Sign in again; clear `localStorage` if stale |
| Frontend gets 403 on train/activate | Account is not admin | Promote the user in MongoDB |
| Frontend requests fail after port change | `VITE_API_BASE_URL` stale | Update `frontend/.env.local` and restart Vite |
| CORS error | Origin not allowlisted | Use `localhost:5173`/`3000` or update backend CORS |
| `rate_limited` | Too many research requests | Wait for the 15-minute window; see [API_DOCUMENTATION.md](API_DOCUMENTATION.md) |
| `ai_service_unavailable` | AI service down or timed out | Check port 8000, logs, and `AI_SERVICE_TIMEOUT_MS` |
| `No active registered model` | No candidate activated | Train, approve, and activate a version |
| `ModelRegistryError: feature schema incompatible` | Feature set changed after training | Retrain a new candidate; do not edit old artifacts |
| Python 3.13 install fails for scientific packages | Unsupported interpreter | Use Python 3.11/3.12 |
| ESLint requires a newer Node | Node < 20.19 | Upgrade Node to 20.19+, 22.13+, or 24+ |
| `npm audit` reports advisories | Existing dependency tree | Review and upgrade deliberately; do not run `audit fix --force` blindly |

## 11. Adding a feature or model safely

1. Add the model wrapper under `app/models/` and register its factory in the
   research services and registry.
2. Keep the feature column order stable. If it changes, bump the artifact schema
   version and retrain candidates.
3. Add the model to `MODEL_NAMES` and to the equal-weight ensemble only if that
   is an intentional production/research decision; document the change.
4. Add unit tests for fit/predict behavior and artifact loading.
5. Run walk-forward and return experiments with identical folds/holdout.
6. Update [ML_METHODOLOGY.md](ML_METHODOLOGY.md) and
   [EVALUATION_METHODOLOGY.md](EVALUATION_METHODOLOGY.md).
7. Never overwrite an active registry version. Create a new version and use the
   approval/activation workflow.

## 12. Related documents

- [README.md](../README.md)
- [ARCHITECTURE.md](ARCHITECTURE.md)
- [ML_METHODOLOGY.md](ML_METHODOLOGY.md)
- [EVALUATION_METHODOLOGY.md](EVALUATION_METHODOLOGY.md)
- [BACKTESTING_METHODOLOGY.md](BACKTESTING_METHODOLOGY.md)
- [MODEL_REGISTRY.md](MODEL_REGISTRY.md)
- [API_DOCUMENTATION.md](API_DOCUMENTATION.md)
- [CONTRIBUTING.md](CONTRIBUTING.md)
