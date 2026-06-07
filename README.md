# 📊 Multi-Asset Market Analytics System

A production-style, polyglot microservices system to **fetch, persist, and analyze** both **Cryptocurrencies** and **B3 Stocks/REITs** in near real-time.

## 🧭 Overview

This project follows strict **Separation of Concerns** by splitting transactional workloads (C#) from analytical processing and scraping (Python). The entire ecosystem is containerized, utilizing internal network routing and an API Gateway pattern to keep ingestion, analytics, and persistence cleanly isolated.

## 🧩 Architecture Diagram

![Architecture Diagram](docs/architecture-clean.png)

1. **Orchestrator & API Gateway (C# / ASP.NET Core 8)**
   - Acts as the single entry point for the frontend, routing requests using the Factory Pattern (`IMarketDataService`).
   - Handles real-time data ingestion (CoinGecko for crypto, Brapi for B3).
   - **Tolerant Reader Proxy:** Proxies fundamental data requests securely to the internal Python engine.
   - Persistence, audit logging, and in-memory caching (up to 10 minutes for fundamentals) to prevent rate-limiting.
   - Resilient HTTP clients configured with **Polly**.

2. **Analytical Brain (Python / FastAPI)**
   - Mathematical analysis plus fundamentals scraping, completely isolated from the outside world.
   - **Fundamentals Scraper:** Pulls B3 fundamentals from Fundamentus and normalizes Brazilian financial formats handling Unicode/Encoding issues.
   - **FII Classification:** Smartly categorizes FIIs as `tijolo` (brick), `papel` (paper), or `fof` using label analysis, string matching, and known overrides.
   - **Trading Signals:** Computes trend, percentage change, and volatility using NumPy.

3. **Data Visualization (Python / Streamlit)**
   - Interactive dashboard with multi-asset comparisons and Plotly charts.
   - **Dynamic Fallback Logic:** If a ticker ends with `11` (e.g., TAEE11), the UI tries FII first and automatically falls back to Stock seamlessly if needed.

4. **Infrastructure & Persistence Layer (Docker + PostgreSQL)**
   - The entire stack is orchestrated via `docker-compose` within a private Docker Network.
   - **Race Condition Prevention:** Healthchecks ensure the C# API waits for PostgreSQL to be healthy before applying EF Core code-first migrations on startup.

## 🧰 Tech Stack

- **Transactional Backend:** C# .NET 8, ASP.NET Core Minimal APIs, Polly
- **Analytical/Scraping:** Python 3.11, FastAPI, Pydantic, NumPy, BeautifulSoup4
- **Database:** PostgreSQL 15
- **ORM:** Entity Framework Core
- **Infrastructure / DevOps:** Docker, Docker Compose, Multi-stage Builds, Healthchecks
- **Frontend:** Streamlit, Pandas, Plotly Express

## ⚙️ Configuration

Before running the app, configure your environment variables:

1. Create a `.env` file in the root directory (where the `docker-compose.yml` is located) and add your credentials:
```bash
POSTGRES_USER=your_user
POSTGRES_PASSWORD=your_password
POSTGRES_DB=multiassetdb
BRAPI_API_KEY=your_brapi_api_key
````
> 🔒 Security note: Keep .env and appsettings.json files out of source control. Never commit production secrets.
 
## ▶️ How to Run
Thanks to full containerization, spinning up the entire ecosystem (Database, C# API Gateway, Python Engine, and Streamlit UI) takes only a single command.

```bash
docker-compose up -d --build
```
Wait a few seconds for the database to become healthy and the C# API to run its migrations. Then, access the application:
Streamlit Dashboard: 
```bash
http://localhost:8501
````
C# Swagger (API Gateway): 
```bash
http://localhost:5091/swagger
```
> (Note for Developers: If you wish to use breakpoints or hot-reload, start only the database via Docker (docker-compose up -d db) and run the C# and Python services manually using your IDE).


## 🔌 API Endpoints (Gateway)
** All requests should be routed through the C# API Gateway (Port 5091): 
Crypto Price/History:
```bash
http://localhost:5091/price/crypto/bitcoin/history
```
Stock Price/History: 
```bash
http://localhost:5091/price/stock/petr4/history
```

Stock Fundamentals: 
```bash
http://localhost:5091/fundamentals/stock/petr4
```

FII Fundamentals:
```bash
http://localhost:5091/fundamentals/fii/mxrf11
```
Audit Logs: 
```bash
http://localhost:5091/logs
```
## 📌 Notes on Fundamentals Parsing
- dividend_payout can be derived when there is no explicit label using REND. DISTRIBUÍDO / FFO.
- FII classification uses text signals and known overrides for ambiguous tickers to prevent misclassification of Paper and FOFs.
  
## 📜 License
This project is distributed under the MIT License. See LICENSE for details.
