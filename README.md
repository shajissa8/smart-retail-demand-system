# Smart Retail Demand System
![Documentation](https://img.shields.io/badge/Type-Academin%20Project-blue)
![Status](https://img.shields.io/badge/Status-Paper%20Submitted-brightgreen)
 
A production-grade demand forecasting platform that improves baseline model predictions through **Sales Momentum Intelligence (SMI) nudging**—a model-agnostic post-processing framework that applies dynamic demand adjustments based on historical sales patterns.
 
## Overview
 
Retail demand forecasting is critical for inventory optimization, but baseline models often miss momentum shifts in sales data. This system solves that by layering intelligent signal-based adjustments on top of any forecasting model (Chronos, Prophet, ARIMA, etc.).
 
The **SMI Nudger** detects three key market states from historical sales—hype cycles, momentum reversals, and low-confidence periods—and applies targeted multipliers to forecasts. The result: measurable accuracy improvements with no retraining required.
 
---
 
## Features
 
### SMI Nudger Framework
The nudger operates on three derived signals computed from the last 8 weeks of training history:
 
| Signal | What It Detects | Calculation |
|--------|-----------------|-------------|
| **Hype Index (HI)** | Sustained demand surge | Moving average of recent sales vs. historical baseline |
| **Momentum (M)** | Direction of change | Rate of sales growth/decline across recent weeks |
| **Persistence (P)** | Signal stability | Consistency of momentum direction (lower = more volatile) |
 
These signals generate three **nudger regimes**:
- **Strong Bull:** High HI + positive M → +1.1% multiplier (demand gaining momentum)
- **Momentum Reversal:** Positive M flips to negative → +1.4% multiplier (catch the peak before decline)
- **Low Confidence Bear:** Low persistence + negative trend → −0.45% multiplier (reduce overestimation)
### Horizon Decay
Nudge intensity decreases with forecast horizon:
- Weeks 1–2: Full multiplier (0.90 confidence)
- Weeks 3–4: 0.75 confidence
- Weeks 9–12: Near-zero adjustments (classical models dominate)
This reflects real-world uncertainty: near-term momentum is reliable; long-term predictions revert to baseline.
 
### Full-Stack Architecture
 
| Component | Technology | Role |
|-----------|-----------|------|
| **Frontend** | React.js + Recharts | Interactive dashboard, CSV upload, forecast visualization |
| **Backend** | Node.js + Express | API gateway, authentication, file processing, CSV parsing |
| **ML Service** | Flask + PyTorch | Chronos inference, SMI calculation, nudged forecast generation |
| **Database** | SQLite | User management, authentication tokens |
 
**Data Flow:**
1. User uploads CSV (sales history with date, store ID, demand columns)
2. Node backend auto-detects columns, calls Python preprocessing
3. Python cleans data, generates SMI signals from training history
4. Chronos model forecasts 12 weeks ahead
5. SMI Nudger applies regime-based multipliers
6. Frontend renders interactive charts (bar, line, area, pie, table)
---
 
## Results
 
### Walmart Dataset (Store 10, Weekly Forecast)
 
**Chronos Baseline vs. SMI-Nudged Chronos:**
 
| Metric | Baseline | Nudged | Improvement |
|--------|----------|--------|-------------|
| MASE | 0.476 | 0.431 | **−9.5%** |
| WQL | 0.0219 | 0.0199 | **−9.1%** |
 
**Prophet Baseline vs. SMI-Nudged Prophet:**
 
| Metric | Baseline | Nudged | Improvement |
|--------|----------|--------|-------------|
| MASE | 0.542 | 0.527 | **−2.9%** |
| WQL | 0.0250 | 0.0243 | **−2.8%** |
 
**Key Insight:** The nudger shows stronger gains on learned models (Chronos: −9.5%) than classical models (Prophet: −2.9%), because classical baselines already capture momentum implicitly. The nudger amplifies what advanced models learn.
 
---
 
## Architecture
 
### Backend (Node.js)
 
**Authentication:** JWT-based with bcrypt password hashing and role-based access control (user/admin).
 
**Endpoints:**
- `POST /register/` — Create new account
- `POST /login/` — Authenticate, receive JWT token
- `POST /forecast/` — Upload CSV, receive nudged forecast
- `POST /dataset/columns/` — Inspect CSV structure (auto-detect date, sales, store columns)
- `GET /health/` — Health check
**File Processing:**
- Multer handles CSV upload with 5MB size limit
- csv-parse auto-detects columns by keyword matching (date/time, sales/demand/units, store/product/SKU)
- Python subprocess called for data cleaning and SMI computation
### ML Service (Flask + PyTorch)
 
**Model:** Chronos T5-Small (pre-trained on 1B+ time series)
 
**Pipeline:**
1. **Scaling:** MinMaxScaler or log-transformation (for high-variance data)
2. **Inference:** 20 sample draws from Chronos, mean aggregation
3. **SMI Computation:** DataFrame built from training history, signals calculated, nudge multipliers applied
4. **Output:** Baseline forecast + nudged forecast + multiplier per week
**Computational Profile:**
- Inference time: ~2–5 seconds per forecast
- Memory: ~2–3 GB GPU (or CPU fallback)
- FLOPs: ~0.002 TF per 12-week forecast
### Frontend (React)
 
**Pages:**
- **Login/Register:** Credential entry, session management
- **Home:** CSV upload, feature overview, footer navigation
- **Forecast:** 12-week or 3-month aggregated view, toggle between periods, stat cards (total, average, peak, low), four visualization types (bar, line, area, pie), data table with delta badges
- **Comparison:** Side-by-side Chronos vs. Prophet, performance metrics (MAE, RMSE), interpretation guide
- **Admin:** User management table with search/filter, role assignment, disable/activate users
---
 
## Quick Start
 
### Prerequisites
- Node.js 16+
- Python 3.8+
- SQLite3
- CUDA 11.8+ (optional; CPU inference supported)
### Installation
 
1. **Backend:**
   ```bash
   cd backend
   npm install
   node index.js
   ```
   Runs on `http://localhost:3000`
2. **ML Service:**
   ```bash
   cd ../ml
   pip install -r requirements.txt
   python app.py
   ```
   Runs on `http://127.0.0.1:5001`
3. **Frontend:**
   ```bash
   cd ../frontend
   npm install
   npm run dev
   ```
   Runs on `http://localhost:5173`
### Usage
 
1. Open `http://localhost:5173` → Register account
2. Login → Navigate to **Home**
3. Upload CSV with columns: `Date`, `Store`, `Sales` (or similar keywords)
4. View 12-week forecast with SMI nudges applied
---
 
## How the Nudger Works
 
Imagine a retail store's sales data shows a spike over the last 2 months—maybe a seasonal trend or viral product moment. A standard forecasting model (like Chronos) learns this and predicts a moderate increase. But if the spike is *accelerating* and staying consistent, the actual demand might be even higher. The nudger detects this momentum and says: "Sales are not just high—they're *getting* higher. Bump up the forecast by 1.4% for the next few weeks."
 
Conversely, if sales were climbing but suddenly flatten out, the nudger recognizes the reversal and *reduces* the forecast slightly (−0.45%) to avoid overstock.
 
The nudger never retains the model. It's a **post-processor**: it takes whatever forecast a model produces and applies a small, smart adjustment based on what the historical data *pattern* says about momentum.
 
---
 
## Evaluation Metrics
 
| Metric | Definition | Why It Matters |
|--------|-----------|-----------------|
| **MASE** | Mean Absolute Scaled Error | Compared to naive forecast; >1 = worse than guessing last week's value |
| **WQL** | Weighted Quantile Loss | Penalizes underage/overage asymmetrically (inventory cost proxy) |
 
---
 
## Project Structure
 
```
smart-retail-demand-system/
├── backend/
│   ├── index.js                      # Express server, auth routes, forecast endpoint
│   ├── db/app.db                     # SQLite database
│   └── uploads/                      # Temporary CSV storage
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Login/                # Auth UI
│   │   │   ├── Home/                 # CSV upload & features
│   │   │   ├── Forecast/             # 12-week view with charts
│   │   │   ├── ForecastComparison/   # Model comparison
│   │   │   └── Admin/                # User management
│   │   └── App.jsx                   # Router
│   │   └── App.css                 
│   │   └── index.css
│   │   └── main.jsx
│   └── vite.config.js
├── ml/
│   ├── app.py                        # Flask endpoint for prediction
│   ├── model.py                      # Chronos pipeline, forecast logic
│   ├── smi_nudger.py                 # SMI signal computation & nudge application
│   ├── data_preprocessing_chronos.py # CSV cleaning, frequency alignment
│   └── preprocess_service.py         # Entry point from Node.js
```
 
---
 
## Known Limitations
 
1. **SMI tuning is store-agnostic:** Multiplier thresholds (HI cutoff, M threshold, P persistence) are fixed globally. Store-specific calibration could improve results further.
2. **8-week history requirement:** SMI needs at least 8 weeks of clean training data. Shorter series fall back to baseline forecast.
3. **Single-model pipeline:** Currently Chronos is the primary model. Multi-model ensemble would increase robustness.
4. **No external features:** SMI uses sales history only. Incorporating promotions, seasonality calendars, or macro indicators could improve accuracy.
---
 
## Contributing
 
This is a validated submission and competitive solution. For academic or commercial use, cite the SMI Nudge framework. Pull requests welcome for improvements to preprocessing, additional models, or evaluation metrics.
 
---
 
## License

MIT License
 
---
 
## Contact
 
Questions about the nudger, results, or architecture? Open an issue or reach out.
 
---
 
**Last Updated:** May 2026  
**Model:** Chronos T5-Small (Amazon)  
**Dataset:** Walmart Recruiting Sotres Sales Dataset, M5 Forecasting Accuracy Challenge Dataset (weekly) 
**Validation:** Holdout test set, MASE & WQL metrics
 
