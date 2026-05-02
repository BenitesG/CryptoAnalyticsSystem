# 📊 Multi-Asset Market Analytics System

A distributed, polyglot microservices architecture designed to fetch, persist, and analyze data from both **Cryptocurrencies** and **Traditional Markets (B3 Stocks/REITs)** in real-time.

## 🏗️ Architecture Overview

This project implements a **Separation of Concerns** pattern, dividing transactional workloads from analytical processing using two different ecosystems (C# and Python).

1. **Orchestrator & Ingestion Engine (C# / ASP.NET Core 8)**
   - Acts as the main API gateway, utilizing the **Factory Pattern** (`IMarketDataService`) to dynamically route requests.
   - Fetches real-time and historical data from external APIs (**CoinGecko** for Crypto, **Brapi** for B3).
   - Handles data persistence, audit logging, and in-memory caching for high performance.
   - Resilient HTTP requests configured with **Polly** (Retry Pattern).

2. **Analytical Brain (Python / FastAPI)**
   - A dedicated microservice for data processing.
   - Receives arrays of historical prices.
   - Calculates trends, percentage changes, and market volatility (risk), returning analytical insights to the orchestrator.

3. **Persistence Layer (PostgreSQL & Docker)**
   - Containerized relational database.
   - Stores search logs and audit trails using Entity Framework Core (Code-First approach).

4. **Data Visualization Frontend (Python / Streamlit)**
   - An interactive dashboard providing a user-friendly interface.
   - Allows users to toggle between Crypto and B3 markets, view analytical cards, and interactive Plotly charts.
   - Generates and streams downloadable CSV reports in-memory without polluting the server disk.

## 🚀 Tech Stack

- **Backend (Transactional):** C# .NET 8, ASP.NET Core Minimal APIs, Polly
- **Backend (Analytical):** Python 3, FastAPI, Pydantic, NumPy
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

### 1. Start the Database
Ensure Docker is running, then start the PostgreSQL container from the root folder:
```bash
docker-compose up -d
```

### 2. Start the Python Analytical Engine
Navigate to the CryptoBrainPython folder, activate your virtual environment, and run:
```bash
uvicorn main:app --port 8000 --reload
```

### 3. Start the Interactive Dashboard (Frontend)
Navigate to the CryptoDashboard folder, activate its virtual environment, and run:
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
>Open your browser or access the built-in Swagger UI to test:
```bash
http://localhost:<YOUR_PORT>/swagger
```

- **Crypto Analysis: 
```bash
http://localhost:<YOUR_PORT>/price/crypto/bitcoin/
```

- **Crypto History Analysis: 
```bash
http://localhost:<YOUR_PORT>/price/crypto/bitcoin/history
```

- **B3 Stock Analysis:
```bash
http://localhost:<YOUR_PORT>/price/stock/petr4/history
```

Audit Logs: 
```bash
http://localhost:<YOUR_PORT>/logs
```
(Retrieves the last 10 search records).

> 🌴 Developed as a robust portfolio project to demonstrate backend engineering, microservices integration, and polyglot architecture.

### 📜 License

This project is distributed under the MIT License. See the [LICENSE](LICENSE) file for more information.
