# AI Stock Market Predictor (AI-SMP)

An AI-powered stock market prediction system for Indian Metal & Mining sector companies. Uses machine learning models trained on historical stock data to predict future prices and generate BUY/SELL/HOLD signals.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Tech Stack](#2-tech-stack)
3. [Project Structure](#3-project-structure)
4. [How the Services Connect](#4-how-the-services-connect)
5. [Getting Started](#5-getting-started)
6. [Key Features](#6-key-features)
7. [API Reference](#7-api-reference)
8. [Database Schemas](#8-database-schemas)
9. [ML Models & Metrics](#9-ml-models--metrics)
10. [Data Flow](#10-data-flow)

---

## 1. Overview

AI-SMP is a **3-tier web application** that predicts stock prices using ensemble machine learning. Users can:

- Browse Metal & Mining sector companies listed on NSE/BSE
- Train 5 ML models on historical stock data
- Get real-time BUY/SELL/HOLD predictions
- Compare model performance with interactive charts
- View prediction history and export reports

### Architecture Diagram

```
┌──────────────────┐       HTTP        ┌──────────────────┐       HTTP        ┌──────────────────┐
│                  │  :5173            │                  │  :5000            │                  │
│    FRONTEND      │ ────────────────► │     BACKEND      │ ────────────────► │    AI SERVICE    │
│   (React+Vite)   │ ◄──────────────── │  (Node+Express)  │ ◄──────────────── │  (Python+FastAPI)│
│                  │    JSON           │                  │    JSON           │                  │
└──────────────────┘                   └────────┬─────────┘                   └────────┬─────────┘
                                                │                                     │
                                                ▼                                     ▼
                                         ┌──────────────┐                   ┌─────────────────┐
                                         │   MongoDB     │                   │ Yahoo Finance   │
                                         │  (port 27017) │                   │   (yfinance)    │
                                         └──────────────┘                   └─────────────────┘
                                                                            ┌─────────────────┐
                                                                            │ saved_models/   │
                                                                            │ (.pkl files)    │
                                                                            └─────────────────┘
```

---

## 2. Tech Stack

### Frontend

| Technology | Version | Purpose |
|-----------|---------|---------|
| React | 18.2.0 | UI framework |
| React Router DOM | 6.20.1 | Client-side routing |
| Axios | 1.6.2 | HTTP client |
| Recharts | 2.10.3 | Charts (Line, Bar, Radar) |
| React Hot Toast | 2.4.1 | Notifications |
| date-fns | 2.30.0 | Date formatting |
| Vite | 5.0.0 | Build tool & dev server |
| TailwindCSS | 3.3.6 | Styling |

### Backend

| Technology | Version | Purpose |
|-----------|---------|---------|
| Node.js | 18+ | Runtime |
| Express | 4.18.2 | Web framework |
| Mongoose | 8.0.2 | MongoDB ODM |
| JSON Web Token | 9.0.2 | Authentication |
| bcryptjs | 2.4.3 | Password hashing |
| Axios | 1.6.2 | HTTP client (to AI service) |
| express-rate-limit | 7.1.4 | Rate limiting |

### AI Service

| Technology | Version | Purpose |
|-----------|---------|---------|
| Python | 3.11 | Runtime |
| FastAPI | 0.104.1 | Web framework |
| Uvicorn | 0.24.0 | ASGI server |
| pandas | 2.1.4 | Data manipulation |
| NumPy | 1.26.2 | Numerical computing |
| yfinance | 1.7.0 | Stock data from Yahoo Finance |
| scikit-learn | 1.3.2 | ML models & metrics |
| XGBoost | 2.0.2 | Gradient boosting model |
| joblib | 1.3.2 | Model serialization |

### Database

| Technology | Purpose |
|-----------|---------|
| MongoDB | Stores users, companies, and prediction history |

---

## 3. Project Structure

```
C:\AI-SMP\
├── ai-service/                    # Python FastAPI - ML & Predictions
│   ├── run.py                     # Entry point
│   ├── requirements.txt           # Python dependencies
│   ├── saved_models/              # Trained .pkl model files
│   └── app/
│       ├── main.py                # FastAPI app, CORS, router mounting
│       ├── config.py              # Settings (HOST, PORT, DEBUG)
│       ├── routes/
│       │   ├── stock_routes.py    # Stock data endpoints
│       │   └── prediction_routes.py # Train, predict, evaluate endpoints
│       ├── services/
│       │   ├── data_service.py    # Yahoo Finance data fetching
│       │   ├── feature_engineering.py # 16 technical indicators
│       │   ├── prediction_service.py  # Training & prediction orchestration
│       │   └── model_manager.py   # Save/load .pkl models
│       ├── models/                # ML model definitions (5 models)
│       ├── schemas/               # Pydantic request/response models
│       └── utils/
│
├── backend/                       # Node.js Express - API & Auth
│   ├── package.json
│   ├── src/
│   │   ├── server.js              # Entry point
│   │   ├── app.js                 # Express setup, CORS, routes
│   │   ├── config/db.js           # MongoDB connection
│   │   ├── models/                # Mongoose schemas (User, Company, Prediction)
│   │   ├── routes/                # Auth, Company, Prediction routes
│   │   ├── controllers/           # Route handlers
│   │   └── middleware/            # JWT auth, error handling
│
├── frontend/                      # React + Vite - User Interface
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js             # Port 5173, /api proxy
│   └── src/
│       ├── main.jsx               # React entry point
│       ├── App.jsx                # Router, route guards, all routes
│       ├── context/AuthContext.jsx # Auth state management
│       ├── services/              # API layer (auth, company, prediction)
│       ├── pages/                 # 10 page components
│       └── components/            # Layout, charts, dashboard widgets
│
└── docs/
    └── PROJECT_OVERVIEW.md        # This file
```

---

## 4. How the Services Connect

### Communication Flow

```
1. User interacts with Frontend (React :5173)
2. Frontend sends HTTP request with JWT to Backend (Express :5000)
3. Backend verifies JWT via auth middleware
4. For ML operations, Backend proxies request to AI Service (FastAPI :8000)
5. AI Service fetches stock data from Yahoo Finance (yfinance)
6. AI Service processes data, runs ML models, returns prediction
7. Backend saves prediction to MongoDB, returns result to Frontend
8. Frontend renders charts and prediction results
```

### Service Ports

| Service | Port | URL |
|---------|------|-----|
| Frontend (Vite) | 5173 | http://localhost:5173 |
| Backend (Express) | 5000 | http://localhost:5000 |
| AI Service (FastAPI) | 8000 | http://localhost:8000 |
| MongoDB | 27017 | mongodb://localhost:27017 |

---

## 5. Getting Started

### Prerequisites

- Node.js 20.19+ (or 22.13+/24+)
- Python 3.9-3.12 (3.11 recommended; the pinned dependencies do not build on Python 3.13+)
- MongoDB running on localhost:27017

### Start the AI Service

```bash
cd ai-service
python -m venv venv

# Windows (PowerShell)
.\venv\Scripts\Activate.ps1
# Windows (cmd)
venv\Scripts\activate.bat
# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
python run.py
```

### Start the Backend

Copy `backend/.env.example` to `backend/.env`, then start the service:

```bash
cd backend
npm install
npm run dev
```

### Start the Frontend

Copy `frontend/.env.example` to `frontend/.env.local` if you need to change the API URL (optional), then start the service:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 in your browser.

### Environment Variables

The repository includes `.env.example` files for each service. Actual `.env` files are gitignored.

**AI Service** (`ai-service/.env`):
```
HOST=0.0.0.0
PORT=8000
DEBUG=True
```

**Backend** (`backend/.env`):
```
PORT=5000
MONGODB_URI=mongodb://localhost:27017/ai-smp
JWT_SECRET=replace-with-a-long-random-secret
JWT_EXPIRE=7d
AI_SERVICE_URL=http://localhost:8000
NODE_ENV=development
```

**Frontend** (`frontend/.env.local`, optional):
```
VITE_API_BASE_URL=http://localhost:5000/api
```

`VITE_API_BASE_URL` defaults to `http://localhost:5000/api` when unset.

---

## 6. Key Features

### Authentication

JWT-based authentication with protected routes.

**Flow:**
1. User registers → password hashed with bcrypt (10 salt rounds)
2. User logs in → JWT token generated (7-day expiry)
3. Token stored in localStorage, attached to every API request
4. Protected routes redirect to `/login` if no valid token
5. 401 responses auto-clear session and redirect to login

### Stock Data

Real-time stock data fetched from Yahoo Finance via `yfinance` library.

**Features:**
- OHLCV (Open, High, Low, Close, Volume) data
- Configurable time periods (1mo, 3mo, 6mo, 1y)
- Automatic data cleaning (remove NaN, duplicates, zero-volume days)
- Company info (name, sector, industry, market cap, current price)

### ML Training Pipeline

```
Yahoo Finance → Raw Data → Clean → Feature Engineering → Train/Test Split → 5 Models → Save
```

**16 Features Used:**

| Feature | Description |
|---------|-------------|
| Open, High, Low, Close, Volume | Raw price/volume data |
| SMA_10, SMA_20, SMA_50 | Simple Moving Averages |
| RSI_14 | Relative Strength Index |
| MACD, Signal_Line | Trend indicators |
| Bollinger_Upper, Bollinger_Lower | Volatility bands |
| Price_Change, Volume_Change | Percentage changes |
| High_Low_Range | Daily price range |

**Target Variable:** `Next_Day_Close` (next trading day's closing price)

### Predictions

**Ensemble Approach:**
- All 5 models predict independently
- Final prediction = average of all 5 predictions
- More robust than single-model predictions

**Signal Logic:**
```
If predicted price > current price by > 1%  → BUY
If predicted price < current price by > 1%  → SELL
Otherwise                                   → HOLD
```

### Charts & Dashboard

Uses **Recharts** library for interactive visualizations:

| Chart Type | Component | Purpose |
|-----------|-----------|---------|
| LineChart | StockChart | Stock price history over time |
| BarChart | ModelBarChart | Compare predictions from 5 ML models |
| BarChart | ComparisonPage | R2 scores across models |
| RadarChart | ComparisonPage | Model performance radar |

### Company Management

- 20 pre-seeded Indian Metal & Mining companies
- Admin can add, update, or soft-delete companies
- Companies searchable by name, category, or symbol

---

## 7. API Reference

### Backend Endpoints (port 5000)

#### Auth Routes (`/api/auth`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/auth/register` | No | Register new user |
| POST | `/api/auth/login` | No | Login, returns JWT |
| GET | `/api/auth/profile` | Yes | Get current user profile |
| PUT | `/api/auth/profile` | Yes | Update name/email |
| PUT | `/api/auth/change-password` | Yes | Change password |

#### Company Routes (`/api/companies`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/companies` | Yes | List all companies (optional `?category=`) |
| GET | `/api/companies/symbol/:symbol` | Yes | Find by Yahoo Finance symbol |
| GET | `/api/companies/:id` | Yes | Find by MongoDB ID |
| POST | `/api/companies` | Yes + Admin | Add new company |
| PUT | `/api/companies/:id` | Yes + Admin | Update company |
| DELETE | `/api/companies/:id` | Yes + Admin | Soft delete company |
| POST | `/api/companies/seed` | Yes | Seed 20 default companies |

#### Prediction Routes (`/api/predictions`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/predictions/train/:symbol` | Yes | Train ML models for stock |
| POST | `/api/predictions/predict/:symbol` | Yes | Run prediction (saves to DB) |
| GET | `/api/predictions/model-status/:symbol` | Yes | Check trained models |
| GET | `/api/predictions/evaluation/:symbol` | Yes | Get model metrics |
| GET | `/api/predictions/stock-data/:symbol` | Yes | Get stock price data |
| GET | `/api/predictions/stock-info/:symbol` | Yes | Get stock company info |
| GET | `/api/predictions/history` | Yes | Get prediction history |
| GET | `/api/predictions/compare/:symbol` | Yes | Get model comparison |
| GET | `/api/predictions/dashboard` | Yes | Get dashboard stats |

### AI Service Endpoints (port 8000)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/api/stock-data/{symbol}` | Fetch stock OHLCV data |
| GET | `/api/stock-data/{symbol}/info` | Fetch stock company info |
| POST | `/api/train/{symbol}` | Train all 5 ML models |
| POST | `/api/predict/{symbol}` | Run prediction |
| GET | `/api/model-status/{symbol}` | Check trained models |
| GET | `/api/evaluation/{symbol}` | Get evaluation metrics |

---

## 8. Database Schemas

### User

```javascript
{
  name: String,          // Required, trimmed
  email: String,         // Required, unique, lowercase
  password: String,      // Required, minlength 6, select: false (bcrypt hashed)
  role: String,          // enum: ["user", "admin"], default: "user"
  createdAt: Date,       // Auto-generated
  updatedAt: Date        // Auto-generated
}
```

### Company

```javascript
{
  symbol: String,        // Required, unique, uppercase (e.g., "HINDALCO.NS")
  name: String,          // Required, trimmed
  category: String,      // enum: ["Metal", "Mining"]
  subCategory: String,   // enum: ["Steel", "Aluminium", "Iron Ore", "Coal", "Zinc", "Copper", "Nickel", "Silver", "Gold", "Manganese"]
  exchange: String,      // enum: ["NSE", "BSE"], default: "NSE"
  isActive: Boolean,     // default: true (soft delete)
  addedBy: ObjectId,     // Ref: User
  createdAt: Date,
  updatedAt: Date
}
```

### Prediction

```javascript
{
  symbol: String,        // Required, uppercase
  companyName: String,
  currentPrice: Number,
  predictedPrice: Number,
  signal: String,        // enum: ["BUY", "SELL", "HOLD"]
  models: Map,           // { modelName: { prediction, mae, mse, rmse, r2_score, mape } }
  ensemblePrediction: Number,
  predictedBy: ObjectId, // Ref: User
  createdAt: Date,
  updatedAt: Date
}
// Compound index: { symbol: 1, createdAt: -1 }
```

---

## 9. ML Models & Metrics

### Models

| # | Model | Library | Key Parameters |
|---|-------|---------|----------------|
| 1 | Linear Regression | scikit-learn | OLS (default) |
| 2 | Decision Tree | scikit-learn | max_depth=10, random_state=42 |
| 3 | Random Forest | scikit-learn | n_estimators=100, max_depth=15, n_jobs=-1 |
| 4 | Support Vector Regression | scikit-learn | kernel="rbf", C=100, gamma="scale", epsilon=0.1 |
| 5 | XGBoost | xgboost | n_estimators=100, max_depth=6, learning_rate=0.1 |

**Note:** SVR requires feature scaling via StandardScaler (saved separately as `svr_scaler.pkl`).

### Ensemble

The final predicted price is the **arithmetic mean** of all 5 individual model predictions.

### Evaluation Metrics

| Metric | Formula | Description |
|--------|---------|-------------|
| MAE | mean(\|actual - predicted\|) | Average absolute error |
| MSE | mean((actual - predicted)²) | Mean squared error |
| RMSE | √MSE | Root mean squared error |
| R² | 1 - (SS_res / SS_tot) | Coefficient of determination |
| MAPE | mean(\|actual - predicted\| / actual) × 100 | Mean absolute percentage error |

### Model Persistence

Models are saved as `.pkl` files using joblib:

```
saved_models/
└── {SYMBOL}/           # e.g., HINDALCO_NS
    ├── linear_regression.pkl
    ├── decision_tree.pkl
    ├── random_forest.pkl
    ├── svr.pkl
    ├── svr_scaler.pkl
    ├── xgboost.pkl
    └── metrics.pkl
```

---

## 10. Data Flow

### Training Flow

```
1. User clicks "Train" for a stock symbol
2. Frontend: POST /api/predictions/train/:symbol
3. Backend verifies JWT, proxies to AI Service
4. AI Service fetches 1 year of OHLCV data from Yahoo Finance
5. Data is cleaned (remove NaN, duplicates, zero-volume days)
6. 16 technical features are engineered
7. Data split 80/20 (train/test)
8. All 5 models are trained on training set
9. Models evaluated on test set
10. Models and metrics saved to saved_models/ as .pkl files
11. Results returned through the chain to the frontend
```

### Prediction Flow

```
1. User clicks "Predict" for a stock symbol
2. Frontend: POST /api/predictions/predict/:symbol
3. Backend verifies JWT, proxies to AI Service
4. AI Service fetches last 6 months of data from Yahoo Finance
5. Data cleaned and 16 features engineered
6. Last row of feature data taken as input
7. All 5 trained models loaded from disk
8. Each model runs predict() on the input
9. Ensemble prediction = average of 5 predictions
10. Signal determined: BUY/SELL/HOLD
11. Backend saves prediction to MongoDB
12. Frontend displays: current price, predicted price, signal, model bar chart
```

### Chart Data Flow

```
Dashboard loads
  → useEffect fires on mount
  → predictionService.getStockData("TATASTEEL.NS", "6mo")
  → Backend proxies to AI Service
  → AI Service fetches from Yahoo Finance, cleans data
  → Data returned as JSON array
  → StockChart renders Recharts LineChart with price data
```

---

## Pre-Seeded Companies

| Symbol | Name | Category | Sub-Category |
|--------|------|----------|-------------|
| HINDALCO.NS | Hindalco Industries | Metal | Aluminium |
| TATASTEEL.NS | Tata Steel | Metal | Steel |
| VEDL.NS | Vedanta Limited | Metal | Zinc |
| COALINDIA.NS | Coal India | Mining | Coal |
| NMDC.NS | NMDC Limited | Mining | Iron Ore |
| JSWSTEEL.NS | JSW Steel | Metal | Steel |
| NATIONALUM.NS | NALCO | Metal | Aluminium |
| HINDZINC.NS | Hindustan Zinc | Metal | Zinc |
| SAIL.NS | Steel Authority of India | Metal | Steel |
| JINDALSTEL.NS | Jindal Steel & Power | Metal | Steel |
| APLAPOLLO.NS | APL Apollo Tubes | Metal | Steel |
| HINDCOPPER.NS | Hindustan Copper | Metal | Copper |
| JSL.NS | Jindal Stainless | Metal | Steel |
| JINDALSAW.NS | Jindal Saw | Metal | Steel |
| RATNAMANI.NS | Ratnamani Metals & Tubes | Metal | Steel |
| SHYAMMETL.NS | Shyam Metalics and Energy | Metal | Steel |
| WELCORP.NS | Welspun Corp | Metal | Steel |
| GPIL.NS | Godawari Power & Ispat | Metal | Steel |
| MOIL.NS | MOIL Limited | Mining | Manganese |
| GMDCLTD.NS | Gujarat Mineral Development Corporation | Mining | Coal |
