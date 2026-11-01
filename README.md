# AI-Based Stock Market Prediction

A full-stack web application for predicting Metal & Mining stock prices using 5 Machine Learning models with an ensemble approach.

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | React 18, Vite, TailwindCSS, Recharts |
| Backend | Node.js, Express, MongoDB, Mongoose |
| AI Service | Python, FastAPI, scikit-learn, XGBoost |
| Database | MongoDB (local) |
| Stock Data | Yahoo Finance (yfinance) |

## Project Structure

```
AI-SMP/
├── ai-service/        # Python FastAPI - ML Models & Predictions
├── backend/           # Node.js Express - API & Auth
└── frontend/          # React + Vite - User Interface
```

## ML Models

| # | Model | Library |
|---|-------|---------|
| 1 | Multiple Linear Regression | scikit-learn |
| 2 | Decision Tree Regressor | scikit-learn |
| 3 | Random Forest Regressor | scikit-learn |
| 4 | Support Vector Regressor (SVR) | scikit-learn |
| 5 | XGBoost Regressor | xgboost |

**Ensemble:** Average prediction from all 5 models

**Features Used:** SMA (10,20,50), RSI (14), MACD, Bollinger Bands, Price Change, Volume Change, High-Low Range

## Modules

### 1. User & Authentication Module
- Register / Login with JWT
- Password hashing with bcrypt
- Protected routes
- Role-based access (admin/user)

### 2. Company & Stock Management Module
- 10 pre-seeded Metal & Mining companies
- Categories: Metal (Steel, Aluminium, Zinc) / Mining (Coal, Iron Ore)
- Search and filter by category
- CRUD operations (admin only)

### 3. Stock Data Collection & Preprocessing Module
- Fetches OHLCV data from Yahoo Finance (yfinance)
- Cleans data (removes NaN, duplicates, zero volume)
- Feature engineering: 16 technical indicators
- Train/test split (80/20)

### 4. Machine Learning Prediction Module
- Trains 5 models on historical data
- Saves trained models as .pkl files
- Predicts next-day closing price
- Generates BUY/SELL/HOLD signal

### 5. Algorithm Comparison & Evaluation Module
- MAE, MSE, RMSE, R² Score, MAPE per model
- Best model identification
- Side-by-side comparison charts

### 6. Dashboard & Reports Module
- Overview stats (companies, predictions, accuracy)
- Stock price charts
- Prediction history
- Model performance reports

## Getting Started

### Prerequisites
- Python 3.9+
- Node.js 18+
- MongoDB (running on localhost:27017)

### 1. AI Service (Terminal 1)

```bash
cd ai-service
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate    # Linux/Mac
pip install -r requirements.txt
python run.py


Runs on: `http://localhost:8000`

### 2. Backend (Terminal 2)

```bash
cd backend
npm install
npm run dev
```

Runs on: `http://localhost:5000`

### 3. Frontend (Terminal 3)

```bash
cd frontend
npm install
npm run dev
```

Runs on: `http://localhost:5173`

## API Endpoints

### AI Service (Port 8000)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/api/stock-data/{symbol}` | Fetch stock data |
| GET | `/api/stock-data/{symbol}/info` | Stock info |
| POST | `/api/train/{symbol}` | Train 5 models |
| POST | `/api/predict/{symbol}` | Predict price |
| GET | `/api/model-status/{symbol}` | Model status |
| GET | `/api/evaluation/{symbol}` | Evaluation metrics |

### Backend (Port 5000)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/auth/register` | No | Register |
| POST | `/api/auth/login` | Yes | Login |
| GET | `/api/auth/profile` | Yes | Profile |
| GET | `/api/companies` | Yes | List companies |
| POST | `/api/companies/seed` | Yes | Seed companies |
| POST | `/api/predictions/train/:symbol` | Yes | Train models |
| POST | `/api/predictions/predict/:symbol` | Yes | Predict |
| GET | `/api/predictions/evaluation/:symbol` | Yes | Metrics |
| GET | `/api/predictions/dashboard` | Yes | Dashboard stats |

## Database Schema

### User

| Field | Type | Key |
|-------|------|-----|
| _id | ObjectId | Primary Key |
| name | String | - |
| email | String | Unique |
| password | String | - |
| role | String (enum: user, admin) | - |
| createdAt | Date | Auto |
| updatedAt | Date | Auto |

### Company

| Field | Type | Key |
|-------|------|-----|
| _id | ObjectId | Primary Key |
| symbol | String | Unique |
| name | String | - |
| category | String (enum: Metal, Mining) | - |
| subCategory | String (enum: Steel, Aluminium, Iron Ore, Coal, Zinc, Copper, Nickel, Silver, Gold) | - |
| exchange | String (enum: NSE, BSE) | - |
| isActive | Boolean | - |
| addedBy | ObjectId (ref: User) | Foreign Key |
| createdAt | Date | Auto |
| updatedAt | Date | Auto |

### Prediction

| Field | Type | Key |
|-------|------|-----|
| _id | ObjectId | Primary Key |
| symbol | String | Index |
| companyName | String | - |
| currentPrice | Number | - |
| predictedPrice | Number | - |
| signal | String (enum: BUY, SELL, HOLD) | - |
| models | Map\<String, Object\> (prediction, mae, mse, rmse, r2_score, mape) | - |
| ensemblePrediction | Number | - |
| predictedBy | ObjectId (ref: User) | Foreign Key |
| createdAt | Date | Compound Index (symbol, -createdAt) |
| updatedAt | Date | Auto |

## Pre-Seeded Companies

| Symbol | Name | Category | Sub-Category |
|--------|------|----------|--------------|
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

## Environment Variables

### ai-service/.env
```
HOST=0.0.0.0
PORT=8000
DEBUG=True
```

### backend/.env
```
PORT=5000
MONGODB_URI=mongodb://localhost:27017/ai-smp
JWT_SECRET=ai-smp-secret-key-2026
JWT_EXPIRE=7d
AI_SERVICE_URL=http://localhost:8000
NODE_ENV=development
```

## License

MIT
