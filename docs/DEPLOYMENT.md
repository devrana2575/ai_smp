# Deployment

This guide describes a conservative single-host deployment for AI_SMP. Adjust
process supervision, secret storage, and storage durability to your
environment.

## 1. Topology

```text
Internet / internal users
        |
        v
TLS reverse proxy
        |
        v
Express backend (public API, port 5000)
   |            |
   |            +--> MongoDB
   |
   +--- shared service token ---> FastAPI AI service (internal, port 8000)
                                      |
                                      +--> yfinance network access
                                      +--> saved_models/ artifacts
```

Run the AI service on loopback or a private network. Only the reverse proxy
should be reachable by users. The AI service is not a public authentication
boundary.

## 2. Required configuration

### AI service (`ai-service/.env`)

```dotenv
ENVIRONMENT=production
HOST=127.0.0.1
PORT=8000
DEBUG=false
ENABLE_DOCS=false
SERVICE_AUTH_TOKEN=<at least 32 random characters>
CORS_ORIGINS=https://app.example.com
```

Production startup rejects missing or short service tokens, debug mode,
wildcard CORS, malformed origins, and invalid ports/environments.

### Backend (`backend/.env`)

```dotenv
NODE_ENV=production
PORT=5000
MONGODB_URI=mongodb://<host>:27017/ai-smp
JWT_SECRET=<at least 32 random characters>
JWT_EXPIRE=7d
AI_SERVICE_URL=http://127.0.0.1:8000
AI_SERVICE_TOKEN=<same value as SERVICE_AUTH_TOKEN>
AI_SERVICE_TIMEOUT_MS=180000
CORS_ORIGINS=https://app.example.com
```

Backend startup rejects missing/placeholder/weak secrets, missing MongoDB
configuration, malformed origins, wildcard production origins, and invalid
timeouts.

### Frontend

Build-time environment:

```dotenv
VITE_API_BASE_URL=https://app.example.com/api
```

Run `npm run build` and serve `frontend/dist/` from the reverse proxy or a static
host. Do not ship an internal service token to the frontend.

## 3. Generate secrets

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"
```

Use independent values for the JWT secret and service token. Store them in a
secret manager or protected environment, not in Git. Rotate by updating both
services and restarting them together.

## 4. Install and start

AI service:

```powershell
cd ai-service
python -m venv venv
.\venv\Scripts\python.exe -m pip install --upgrade pip
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe run.py
```

Backend:

```powershell
cd backend
npm ci --omit=dev
npm start
```

Frontend:

```powershell
cd frontend
npm ci
npm run build
```

Use a process supervisor or service manager so both processes restart after a
crash. Send logs to a durable, access-controlled destination.

## 5. Reverse proxy and TLS

- Terminate TLS at the proxy.
- Expose only the backend port to users.
- Keep the AI service on loopback or a private interface/firewall.
- Do not proxy `/docs`, `/redoc`, or `/openapi.json` publicly; docs are disabled
  by default.
- Preserve `Authorization` and `X-Request-Id`; do not forward the internal
  service token from clients.
- Set reasonable request/read timeouts that account for training and prediction
  requests.

## 6. CORS

Set `CORS_ORIGINS` on both backend and AI service to the exact production
frontend origin(s), comma-separated. Never use `*` in production. If the
frontend domain changes, update both services and restart them.

## 7. Storage and backups

Persistent paths:

| Path | Contents |
|------|----------|
| MongoDB | Users, companies, prediction history |
| `ai-service/saved_models/` | Trained model artifacts and metrics |

Back up MongoDB and `saved_models/` together. Restore tests should verify that
the saved artifacts match the running feature-engineering schema before serving
predictions.

## 8. Startup and health checks

- AI service: `GET /health` remains public and returns status/app/version.
- Backend: `GET /health` returns service status.
- Do not use protected endpoints for liveness checks unless the probe also
  supplies the service token.
- A 503 `service_auth_not_configured` from the AI service means the service token
  is absent; fix configuration instead of bypassing the check.
- A 401 `invalid_service_token` means the backend and AI service tokens differ.

## 9. Deployment order

1. Back up persistent data.
2. Deploy the AI service with the new `SERVICE_AUTH_TOKEN`; verify `/health`.
3. Deploy the backend with the matching `AI_SERVICE_TOKEN`; verify `/health` and
   one authenticated read request.
4. Deploy the frontend build.
5. Run one authenticated prediction through Express in a non-production
   environment.
6. Confirm no request from the public network reaches the AI service directly.

Rolling the service token requires either a coordinated restart or a temporary
rotation mechanism; the current implementation supports one active token.

## 10. Model training and replacement

1. Confirm the symbol has enough clean history.
2. Train through `POST /api/predictions/train/:symbol`.
3. Review the returned metrics and model status.
4. Run a prediction and confirm the response.
5. Keep a backup of the previous `saved_models/{SYMBOL}/` directory so a model
   update can be rolled back.
6. Never present model estimates as guaranteed future performance.

## 11. CI and release checks

`.github/workflows/ci.yml` runs:

- AI service: Python 3.11, dependency install, `ruff check .`, `pytest -q`.
- Backend: Node 20, `npm ci`, `npm run lint`, `npm test`.
- Frontend: Node 20, `npm ci`, `npm run lint`, `npm run build`.

Run the same commands locally before release. Do not treat a workflow as passed
unless the commands actually succeeded. A chunk-size warning from Vite is not a
build failure.

## 12. Known operational limitations

- In-memory rate limits are per backend instance.
- yfinance availability and vendor revisions can change model inputs.
- Training and prediction depend on outbound network access to Yahoo Finance.
- MongoDB must be available for authentication, company management, and
  prediction history.
