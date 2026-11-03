# ⚽ Moneyball EPL — AI Football Scouting & Player Valuation Tool

> **Description:** An explainable AI football scouting, recruitment, and player valuation web application for the English Premier League (2025–26). Combines **XGBoost** market-value estimation, exact **TreeSHAP** waterfall attribution, position-aware **cosine-similarity scouting**, interactive **multi-player percentile radars**, and a **fact-grounded AI Scouting Chatbot** (powered by deterministic NLU + optional Google Gemini Free-Tier API with zero-hallucination numeric verification).

---

## ✨ Key Features

- **🏠 Executive Overview (`/`)** — Dataset summary across **276 qualified Premier League outfield players** (≥900 minutes, 2025–26 season), model performance metrics ($R^2$, MAE, RMSE), and quick navigation.
- **🔍 Player Explorer & Profiles (`/players`, `/players/:id`)** — Search and filter by club, position (`D`, `M`, `F`), age, and valuation; inspect per-90 stats, percentile ranks, what-if scenario simulators, and individual valuation breakdowns.
- **🏆 League Rankings (`/rankings`)** — Customizable leaderboards across estimated market value, value gap (undervalued gems), goals/90, assists/90, xG/90, xAG/90, progressive passes, tackles, and minutes with position and age-band filters.
- **🎯 Lookalike Scouting Engine (`/scout`)** — Position-filtered, z-score standardized **cosine-similarity** search to discover statistical replacements, younger prospects, and undervalued alternatives within a target budget.
- **⚖️ Head-to-Head Comparison (`/compare`)** — Side-by-side stat tables, valuation driver differentials, and overlaid position-percentile radar profiles.
- **📊 Interactive Analytics Dashboard (`/dashboard`)** —
  - **SHAP Valuation Waterfall:** Step-by-step `£` breakdown from the league baseline to a player's final model estimate showing which features push value up or down.
  - **Multi-Player Percentile Radar:** Compare 2+ players simultaneously across 7 core scouting axes (`Goals/90`, `Assists/90`, `Non-pen xG/90`, `xAG/90`, `Prog Carries`, `Tackles/90`, `Blocks/90`) with dual raw + percentile columns.
- **💬 Fact-Grounded AI Scouting Chatbot (`/chat`)** —
  - Answers natural-language questions across **every module**: budget transfer shortlists (*"What is the best attacker to buy in the range of 35m to 55m?"*), player strengths & weaknesses, SHAP explanations, lookalike scouting, head-to-head comparisons, club squad totals, what-if simulations, and methodology Q&A.
  - **Optional Free-Tier Gemini Integration:** Connect a free Google AI Studio key (`gemini-3.5-flash-lite` via `google-genai` Interactions API) for slang/nickname query rewriting and natural football-scout prose. Every LLM response passes a strict `check_numbers` verifier so **zero invented or altered numbers** ever reach the UI.
- **🧪 Thesis Evaluation Console (`/eval`)** — Built-in user-study task runner and SQLite telemetry logger for evaluating human-AI scouting workflows.

---

## 🛠️ Tech Stack

| Layer | Technologies |
| :--- | :--- |
| **Machine Learning & XAI** | Python 3.11, `xgboost`, `scikit-learn`, `shap` (TreeSHAP), `scipy`, `pandas`, `numpy` |
| **Backend API** | `FastAPI`, `Uvicorn`, `Pydantic v2`, `SlowAPI` (rate limiting), `google-genai` (Gemini Interactions API) |
| **Frontend SPA** | `React 18`, `Vite 6`, `React Router v6`, `Recharts 3`, `Axios`, `React Hot Toast` |

---

## 📁 Project Structure

```text
├── artifacts/               # Pre-trained model bundle (bundle.joblib) & CV metrics summary
├── backend/
│   ├── app/
│   │   ├── chatbot/         # Deterministic NLU, engine, glossary, Gemini LLM & fact-checker
│   │   ├── api.py           # FastAPI REST endpoints (/api/players, /api/scout, /api/chat, ...)
│   │   ├── build.py         # End-to-end data ingestion, feature engineering, CV & SHAP builder
│   │   ├── features.py      # 28 engineered per-90, progression, defensive & context features
│   │   ├── model.py         # Linear baseline, Random Forest & XGBoost log-value regressors
│   │   ├── similarity.py    # Position-standardized cosine similarity scouting engine
│   │   └── store.py         # In-memory query, ranking, radar, waterfall & what-if store
│   ├── .env.example         # Template for optional GEMINI_API_KEY configuration
│   ├── config.yaml          # Model, dataset, target & application settings
│   └── requirements.txt     # Pinned Python dependencies
├── data/
│   ├── raw/                 # 2025–26 Premier League stats CSV & squad metadata XLSX
│   └── sample/              # Synthetic schema-compatible sample dataset
├── frontend/
│   ├── src/
│   │   ├── components/      # Navbar, WaterfallChart, RadarChart, reusable UI primitives
│   │   └── pages/           # Home, Players, PlayerDetail, Rankings, Scout, Compare, Dashboard, Chat, About, Eval
│   ├── package.json
│   └── vite.config.js       # Proxies /api requests to http://localhost:8000
├── scripts/
│   └── make_sample_data.py  # Generates synthetic sample datasets from column schemas
└── start_app.bat            # One-click Windows launcher for Backend + Frontend
```

---

## 🚀 Getting Started

### Prerequisites
- **Python 3.11+**
- **Node.js 18+** & **npm**

### 1. Clone the Repository
```bash
git clone https://github.com/bahaaahmedb-code/AI-Scouting-Tool.git
cd AI-Scouting-Tool
```

### 2. Backend Setup
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# (Optional) Rebuild the model & TreeSHAP artifact bundle from data/raw
python -m app.build

# Start the FastAPI server on port 8000
uvicorn app.api:app --port 8000 --reload
```

### 3. Frontend Setup
Open a second terminal:
```powershell
cd frontend
npm install
npm run dev
```
Open **http://localhost:5173** in your browser (interactive Swagger API docs are available at **http://localhost:8000/docs**).

> **Windows Quick Launch:** Once `.venv` and `node_modules` are installed, double-click `start_app.bat` to launch both servers and open the browser automatically.

---

## ✨ Optional: Connect Free Google Gemini API (AI Chat)

The chatbot answers all structured scouting, valuation, ranking, and SHAP questions **out of the box with zero API keys**. To enable conversational query rewriting and natural scout-report phrasing:

1. Get a free API key (no credit card required) from [Google AI Studio](https://aistudio.google.com/apikey).
2. Either click **🔑 Connect Free Gemini API** inside the **Chat** tab in the web UI, **or** copy `backend/.env.example` to `backend/.env`:
   ```env
   GEMINI_API_KEY=your_api_key_here
   GEMINI_MODEL=gemini-3.5-flash-lite
   LLM_REPHRASE=true
   ```

---

## 📊 Methodology & Research Caveat

- **Feature Space (28 Features):** Spans attacking output (`goals_p90`, `assists_p90`, `xg_p90`, `npxg_p90`, `xag_p90`), ball progression (`prog_carries_p90`, `prog_passes_p90`, `prog_passes_rec_p90`), defensive actions (`tackles_p90`, `interceptions_p90`, `blocks_p90`, `clearances_p90`), discipline, playing-time durability, team strength, position dummies, and non-linear age curves (`age`, `age_sq`).
- **Explainability:** TreeSHAP decomposes $\log(\text{Value})$ additively from the training baseline and maps cumulative steps directly into `£` impacts so scouts can audit *why* a player is priced above or below peers.
- **Target Variable Note:** By default (`target_source: synthetic` in `backend/config.yaml`), valuations are trained on a research-prototype synthetic target to demonstrate the full ML + XAI scouting pipeline. To train on real Transfermarkt valuations, set `target_source: csv` and supply `market_value_csv` in `backend/config.yaml`, then re-run `python -m app.build`.

---

## 📄 License

Developed as part of a B.Sc. Business Informatics Thesis project at the German International University (GIU). Intended for academic research and educational use.
