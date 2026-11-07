# AI_SMP — AI Stock Market Prediction Platform

AI_SMP is a full-stack application for Indian Metal & Mining equities. It
combines JWT authentication, a company database, five machine-learning
price-prediction models, an equal-weight ensemble, and a descriptive market
regime indicator.

> **Important:** This is educational software, not investment advice. Model
> outputs are estimates, not guaranteed future prices. Market data is fetched
> from Yahoo Finance through `yfinance`; results depend on the data available at
> run time. No live brokerage integration or real-money trading is implemented.

---

## What is in the platform?

| Area | Capability |
|------|------------|
| Prediction app | JWT authentication, company management, five ML models, equal-weight ensemble, BUY/SELL/HOLD signals, dashboard and comparison views |
| Market regime | Descriptive Bullish/Bearish/Neutral badge from the 50/200-session trend and 60-session momentum |
| Reports | Saved prediction history and legacy model-evaluation summaries |
| Quality | 48 Python tests, 5 Node tests, frontend build, ESLint, Ruff, dependency checks |

---

## Tech stack

| Layer | Technology |
|-------|------------|
| Frontend | React 18, Vite 5, TailwindCSS 3, Recharts |
| Backend | Node.js 20.19+, Express 4, MongoDB, Mongoose, JWT, `express-rate-limit` |
| AI service | Python 3.9–3.12 (3.11 recommended), FastAPI, scikit-learn, XGBoost, pandas, NumPy, joblib |
| Data | Yahoo Finance via `yfinance` |

Python 3.13+ is not supported by the pinned scientific packages.

---

## Repository layout

```text
ai_smp/
├── ai-service/                    # Python FastAPI: ML training and prediction
│   ├── app/
│   │   ├── models/                # Five ML model wrappers
│   │   ├── routes/                # Prediction and market-data routes
│   │   ├── schemas/               # Pydantic request/response models
│   │   └── services/              # Data, features, prediction, market regime
│   ├── saved_models/              # Production model artifacts
│   ├── tests/                     # Pytest suite
│   ├── requirements.txt
│   └── requirements-dev.txt
├── backend/                       # Express gateway and JSON API
│   ├── src/controllers/           # Auth, company, prediction controllers
│   ├── src/routes/                # /api routes
│   ├── src/services/aiClient.js   # Timeout-aware AI-service client
│   └── tests/                     # Node test runner tests
├── frontend/                      # React + Vite UI
│   └── src/pages/                 # Dashboard, companies, predictions, reports
├── docs/                          # Architecture and methodology docs
└── README.md
```

See [`docs/`](docs/) for architecture, API, security, deployment, development,
and ML methodology details.

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

## Testing and quality checks

From `ai-service/`:

```powershell
.\venv\Scripts\python.exe -m pytest -q
ruff check .
.\venv\Scripts\python.exe -m compileall -q app tests
```

Current result: **48 Python tests passed**; Ruff and compileall pass. A small
number of httpx/TestClient deprecation warnings remain.

From `backend/`:

```powershell
npm test
npm run lint
```

Current result: **5 Node tests passed**; ESLint passes.

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

Do not run `npm audit fix --force` without reviewing breaking changes and
re-running the full test/build suite.

---

## Security notes

- The FastAPI service is internal-only. Every `/api/*` route requires a shared
  `X-Internal-Service-Token`; only `/health` is public. If the token is not
  configured, protected routes fail closed with HTTP 503. Express forwards the
  token server-side from `AI_SERVICE_TOKEN`.
- Express remains the browser authentication/authorization boundary. Company
  management requires an authenticated admin user, while prediction and report
  views require authentication. Rate limits are configurable through the API
  rate-limit environment variables.
- Production startup validation rejects debug mode, weak/missing secrets,
  wildcard CORS, malformed origins, and invalid timeouts without echoing secret
  values. `DEBUG` defaults to false; interactive FastAPI docs are opt-in.
- Symbols, pagination, numeric ranges, and request bodies are validated before
  they reach the AI service.
- AI-service HTTP calls have a configurable timeout (`AI_SERVICE_TIMEOUT_MS`,
  default 180 seconds). Do not expose the AI service publicly.
- Never commit `.env` files, JWTs, service tokens, or model artifacts. The
  repository's `.gitignore` covers environment files and common build output.

See [docs/SECURITY.md](docs/SECURITY.md) and
[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for details and residual risks.

---

## Limitations

- The models use a small set of technical indicators and a single historical
  path; they do not model fundamentals, news, regime changes, or market impact.
- Live `yfinance` results can change as new sessions arrive and as Yahoo revises
  history.
- MongoDB is required for authentication, company management, and prediction
  history.
- No result in this repository should be presented as a guarantee of profit.

---

## License

MIT
