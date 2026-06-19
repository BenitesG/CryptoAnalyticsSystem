# 📊 Multi-Asset Market Analytics System

A production-style, polyglot microservices system to **fetch, persist, and analyze** both **Cryptocurrencies** and **B3 Stocks/REITs** in near real-time, featuring secure **User Portfolios (Wallets)** and a **Dynamic Analytics Dashboard**.

## 🧭 Overview

This project follows strict **Separation of Concerns** by splitting transactional workloads (C#) from analytical processing and scraping (Python). The entire ecosystem is containerized, utilizing internal network routing and an API Gateway pattern to keep ingestion, analytics, and persistence cleanly isolated.

## 🧩 Architecture Diagram

![Architecture Diagram](docs/architecture-clean.png)

1. **Orchestrator & API Gateway (C# / ASP.NET Core 8)**
   - Acts as the single entry point, routing requests using the Factory Pattern (`IMarketDataService`).
   - Handles real-time data ingestion (CoinGecko for crypto, Brapi for B3).
   - **Tolerant Reader Proxy:** Proxies fundamental data requests securely to the internal Python engine.
   - **Secure Authentication:** Manages user registration and sign-in using `BCrypt.Net-Next` to securely salt and hash passwords before storing them.
   - **Portfolio Management:** Orchestrates user assets. Whenever a user buys more of an existing asset, the API automatically calculates the **Weighted Average Price** (Cost Basis) and consolidates holdings.
   - Persistence, audit logging, and in-memory caching (up to 10 minutes for fundamentals) to prevent rate-limiting.
   - Resilient HTTP clients configured with **Polly**.

2. **Analytical Brain (Python / FastAPI)**
   - Mathematical analysis plus fundamentals scraping, completely isolated from the outside world.
   - **Fundamentals Scraper:** Pulls B3 fundamentals from Fundamentus and normalizes Brazilian financial formats handling Unicode/Encoding issues.
   - **FII Classification:** Smartly categorizes FIIs as `tijolo` (brick), `papel` (paper), or `fof` using label analysis, string matching, and known overrides.
   - **Trading Signals:** Computes trend, percentage change, and volatility using NumPy.

3. **Data Visualization (Python / Streamlit)**
   - **Interactive User Authentication:** Login and signup forms right in the sidebar to secure personalized dashboards.
   - **Dynamic Portfolio Dashboard (The Wallet):** Fetches the user's active holdings from the database, calculating real-time portfolio value and total profit/loss (P&L %) using live market prices.
   - **Asset Segregation:** Displays assets cleanly divided into **Stocks & REITs** (BRL) and **Cryptocurrencies** (USD) tables.
   - **Asset Allocation Chart:** Renders an interactive Plotly Donut Chart representing the user's holdings based on current market value.
   - **Context-Aware Sidebar:** Dynamically toggles forms (hides 'Add to Portfolio' when searching markets, and hides 'Market Search' when looking at the wallet) to ensure a clean, modern user experience.
   - **Dynamic Fallback Logic:** If a ticker ends with `11` (e.g., TAEE11), the UI tries FII first and automatically falls back to Stock seamlessly if needed.

4. **Infrastructure & Persistence Layer (Docker + PostgreSQL)**
   - The entire stack is orchestrated via `docker-compose` within a private Docker Network.
   - Stores search logs, secure user credentials, and active portfolios using Entity Framework Core (Code-First approach).
   - **Race Condition Prevention:** Healthchecks ensure the C# API waits for PostgreSQL to be healthy before applying EF Core code-first migrations on startup.

## 🧰 Tech Stack

- **Transactional Backend:** C# .NET 8, ASP.NET Core Minimal APIs, Polly, BCrypt.Net-Next
- **Analytical/Scraping:** Python 3.11, FastAPI, Pydantic, NumPy, BeautifulSoup4
- **Database:** PostgreSQL 15
- **ORM:** Entity Framework Core
- **Infrastructure / DevOps:** Docker, Docker Compose, Multi-stage Builds, Healthchecks
- **Frontend:** Streamlit, Pandas, Plotly Express

## ⚙️ Configuration

Before running the app, configure your environment variables:

1. Create a `.env` file in the root directory (where the `docker-compose.yml` is located) and add your credentials:

POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
POSTGRES_DB=multiassetdb
BRAPI_API_KEY=your_brapi_api_key

> 🔒 **Security note:** Keep `.env` and `appsettings.json` files out of source control. Never commit production secrets.

## ▶️ How to Run

Thanks to full containerization, spinning up the entire ecosystem takes only a single command.

docker-compose up -d --build

Wait a few seconds for the database to become healthy and the C# API to run its migrations. Then, access the application:
- **Streamlit Dashboard:** 
```bash
http://localhost:8501
```
- **C# Swagger (API Gateway):** 
```bash
http://localhost:5091/swagger
```

*(**Note for Developers:** If you wish to use breakpoints or hot-reload, start only the database via Docker (`docker-compose up -d db`) and run the C# and Python services manually using your IDE).*

## 🔌 API Endpoints (Gateway)

All requests should be routed through the C# API Gateway (Port `5091`):

- **User Registration:** (POST) 
```bash
http://localhost:5091/users/register
```
- **User Login:** (POST) 
```bash
http://localhost:5091/users/login
```
- **Add to Portfolio:** (POST) 
```bash
http://localhost:5091/portfolios/add
```
- **Get Portfolio:** 
```bash
http://localhost:5091/portfolios/{userId}
```
- **Crypto Price/History:** 
```bash
http://localhost:5091/price/crypto/bitcoin/history
```
- **Stock Price/History:** 
```bash
http://localhost:5091/price/stock/petr4/history
```
- **Stock Fundamentals:** 
```bash
http://localhost:5091/fundamentals/stock/petr4
```
- **FII Fundamentals:** 
```bash
http://localhost:5091/fundamentals/fii/mxrf11
```
- **Audit Logs:** 
```bash
http://localhost:5091/logs
```

## 📌 Notes on Fundamentals Parsing

- `dividend_payout` can be derived when there is no explicit label using `REND. DISTRIBUÍDO / FFO`.
- FII classification uses text signals and known overrides for ambiguous tickers to prevent misclassification of Paper and FOFs.

## 📜 License

This project is distributed under the MIT License. See [LICENSE](LICENSE) for details.