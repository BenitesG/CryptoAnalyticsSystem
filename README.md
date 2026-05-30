# 📊 Multi-Asset Market Analytics System

A production-style, polyglot microservices system to **fetch, persist, and analyze** both **Cryptocurrencies** and **B3 Stocks/REITs** in near real time.

## 🧭 Overview

This project follows **Separation of Concerns** by splitting transactional workloads (C#) from analytical processing and scraping (Python), keeping ingestion, analytics, and persistence cleanly isolated.

## 🧩 Architecture Diagram

![Architecture Diagram](docs/architecture-clean.svg)

1. **Orchestrator & API Gateway (C# / ASP.NET Core 8)**
   - API gateway using the Factory Pattern (`IMarketDataService`) to route requests by asset type.
   - Real-time and historical data ingestion (CoinGecko for crypto, Brapi for B3).
   - Persistence, audit logging, and in-memory caching for fast responses.
   - Resilient HTTP clients configured with Polly.

2. **Analytical Brain (Python / FastAPI)**
   - Mathematical analysis plus fundamentals scraping.
   - **Fundamentals Scraper:** Pulls B3 fundamentals from Fundamentus and normalizes Brazilian financial formats.
   - **FII Classification:** Categorizes FIIs as `tijolo`, `papel`, or `fof` using label analysis and known overrides.
   - **Trading Signals:** Computes trend, percentage change, and volatility using NumPy.

3. **Persistence Layer (PostgreSQL + Docker)**
   - Containerized database for local development.
   - Stores search logs and audit trails (EF Core, code-first).

4. **Data Visualization (Python / Streamlit)**
   - Interactive dashboard with multi-asset comparisons and Plotly charts.
   - Generates CSV downloads in memory.
   - Fallback logic: if a ticker ends with `11`, the UI tries FII first and falls back to stock.

## 🧰 Tech Stack

- **Transactional Backend:** C# .NET 8, ASP.NET Core Minimal APIs, Polly
- **Analytical/Scraping:** Python 3, FastAPI, Pydantic, NumPy, BeautifulSoup4
- **Database:** PostgreSQL
- **ORM:** Entity Framework Core
- **Infrastructure:** Docker, Docker Compose
- **Frontend:** Streamlit, Pandas, Plotly Express

## ⚙️ Configuration

Before running the app, configure database credentials and API keys:

1. In [MarketDataApi](MarketDataApi), copy [MarketDataApi/appsettings.example.json](MarketDataApi/appsettings.example.json) to [MarketDataApi/appsettings.json](MarketDataApi/appsettings.json).
2. Update `DefaultConnection` with your PostgreSQL credentials.
3. Add your API keys (for example, Brapi).

> 🔒 **Security note:** Keep [MarketDataApi/appsettings.json](MarketDataApi/appsettings.json) and `.env` files out of source control. Use environment variables or secret managers in production.

## ▶️ How to Run Locally

### ⚡ Quick Start (Windows)

Run the launcher in the repo root:

```bash
.\start_dev.bat
```

This starts Docker, the C# API, the Python engine, and the Streamlit dashboard in separate terminals.

### 🧪 Manual Method

1. **Start the database**

```bash
docker-compose up -d
```

2. **Start the Python engine**

```bash
cd MarketBrain
uvicorn main:app --port 8000 --reload
```

3. **Start the dashboard**

```bash
cd MarketDashboard
streamlit run app.py
```

4. **Start the C# API**

```bash
cd MarketDataApi
dotnet ef database update
dotnet run
```

## 🔌 Endpoints (examples)

### C# API

```bash
http://localhost:<YOUR_PORT>/swagger
http://localhost:<YOUR_PORT>/price/crypto/bitcoin/history
http://localhost:<YOUR_PORT>/price/stock/petr4/history
http://localhost:<YOUR_PORT>/fundamentals/stock/petr4
http://localhost:<YOUR_PORT>/fundamentals/fii/mxrf11
http://localhost:<YOUR_PORT>/logs
```

### Python Engine (direct)

```bash
http://localhost:8000/fundamentals/stock/petr4
http://localhost:8000/fundamentals/fii/mxrf11
http://localhost:8000/fundamentals-debug/mxrf11?asset_type=fii
```

## 📌 Notes on Fundamentals

- `dividend_payout` can be derived when there is no explicit label using `REND. DISTRIBUÍDO / FFO`.
- FII classification uses text signals and known overrides for ambiguous tickers.

## ✨ Highlights

- Polyglot microservices with clear separation between ingestion, analytics, and persistence.
- FastAPI analytics engine with deterministic fundamentals parsing for B3 stocks and FIIs.
- Streamlit dashboard with clean metrics, fallback logic, and multi-asset comparisons.
- Dockerized PostgreSQL + EF Core for logging and audit trails.

## 📜 License

This project is distributed under the MIT License. See [LICENSE](LICENSE) for details.
