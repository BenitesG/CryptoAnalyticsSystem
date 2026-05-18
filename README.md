# 📊 Multi-Asset Market Analytics System

A distributed, polyglot microservices architecture designed to fetch, persist, and analyze data from both **Cryptocurrencies** and **Traditional Markets (B3 Stocks/REITs)** in real-time.

## 🏗️ Architecture Overview

This project implements a strict **Separation of Concerns** pattern, dividing transactional workloads from analytical processing and data ingestion using two different ecosystems (C# and Python).

1. **Orchestrator & API Gateway (C# / ASP.NET Core 8)**
   - Acts as the main API gateway, utilizing the **Factory Pattern** (`IMarketDataService`) to dynamically route requests based on asset type.
   - Fetches real-time and historical data from external APIs (**CoinGecko** for Crypto, **Brapi** for B3).
   - Handles data persistence, audit logging, and in-memory caching for high performance.
   - Resilient HTTP requests configured with **Polly** (Exponential Backoff and Retry Patterns).

2. **Analytical Brain & Data Ingestion (Python / FastAPI)**
   - A dedicated microservice for mathematical processing and **Advanced Web Scraping**.
   - **Scraping Engine:** Uses `BeautifulSoup` and Regular Expressions (`re`) to dynamically extract fundamental indicators (P/E, P/VP, Vacancy, Dividend Yield) from financial portals.
   - **Data Cleansing Pipeline:** Normalizes complex Brazilian financial strings, handles unicode/accents, and dynamically categorizes Real Estate Funds (Brick vs. Paper REITs).
   - **Trading Signals:** Calculates trends, percentage changes, and market volatility (risk) using `NumPy`, returning actionable insights (BUY/SELL/HOLD) to the orchestrator.

3. **Persistence Layer (PostgreSQL & Docker)**
   - Containerized relational database.
   - Stores search logs and audit trails using Entity Framework Core (Code-First approach).

4. **Data Visualization Frontend (Python / Streamlit)**
   - An interactive dashboard providing a user-friendly interface.
   - Allows users to toggle between Crypto and B3 markets, view analytical cards, and compare multiple assets simultaneously using interactive **Plotly** charts.
   - Generates and streams downloadable CSV reports in-memory without polluting the server disk.

## 🚀 Tech Stack

- **Backend (Transactional):** C# .NET 8, ASP.NET Core Minimal APIs, Polly
- **Backend (Analytical/Scraping):** Python 3, FastAPI, Pydantic, NumPy, BeautifulSoup4, Regex
- **Database:** PostgreSQL 
- **ORM:** Entity Framework Core (EF Core)
- **Infrastructure:** Docker, Docker Compose
- **Patterns Used:** Dependency Injection, Factory Pattern, In-Memory Caching, DTOs, Asynchronous Programming.
- **Frontend:** Python, Streamlit, Pandas, Plotly Express

## ⚙️ Configuration

Before running the application, you need to configure your database credentials and API Keys:

1. Locate the `MarketDataApi` folder.
2. Copy `appsettings.example.json` to `appsettings.json`.
3. Open `appsettings.json` and update the `DefaultConnection` string with your PostgreSQL credentials.
4. Add your free API Keys for the data providers (e.g., Brapi API Key).

> 🔒 **Security note:** The database credentials provided in this repository are for local development purposes only. In production environments, always use Environment Variables or Secret Managers. Never commit your `appsettings.json` or `.env` files.

## ⚙️ How to Run Locally

### ⚡ Quick Start (Windows Only)
If you are on Windows, you can bypass the manual steps below. Simply double-click the `start_dev.bat` file in the root directory, or run it via terminal:
```bash
.\start_dev.bat
```

> This script will automatically start the Docker database, the C# Orchestrator (with Hot Reload), the Python Engine, and the Streamlit Dashboard in separate terminal windows.

## ⚙️ How to Run Locally (Manual Method)

### 1. Start the Database
Ensure Docker is running, then start the PostgreSQL container from the root folder:

```bash
docker-compose up -d
```

### 2. Start the Python Analytical Engine
Navigate to the MarketBrain folder, activate your virtual environment, and run:
```bash
uvicorn main:app --port 8000 --reload
```

### 3. Start the Interactive Dashboard (Frontend)
Navigate to the MarketDashboard folder, activate its virtual environment, and run:

```bash
streamlit run app.py
```

### 4. Start the C# API
Navigate to the MarketDataApi folder. Apply the database migrations and run the server:

```bash
dotnet ef database update
dotnet run
```

### 5. Test the Endpoints
- Open your browser or access the built-in Swagger UI: 
```bash
http://localhost:<YOUR_PORT>/swagger
```

- Crypto Analysis: 
```bash
http://localhost:<YOUR_PORT>/price/crypto/bitcoin/history
```

- B3 Stock Analysis: 
```bash
http://localhost:<YOUR_PORT>/price/stock/petr4/history
```

- B3 Fundamentals Data:
```bash
http://localhost:<YOUR_PORT>/fundamentals/stock/petr4
```

- Audit Logs:
```bash
http://localhost:<YOUR_PORT>/logs
```
(Retrieves the last 10 search records).

> 🌴 Developed as a robust portfolio project to demonstrate backend engineering, microservices integration, web scraping, and polyglot architecture.

### 📜 License

This project is distributed under the MIT License. See the [LICENSE](LICENSE) file for more information.
