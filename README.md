# 📊 Crypto Analytics Microservices System

A distributed, polyglot microservices architecture designed to fetch, persist, and analyze cryptocurrency data in real-time.

## 🏗️ Architecture Overview

This project implements a **Separation of Concerns** pattern, dividing transactional workloads from analytical processing using two different ecosystems (C# and Python).

1. **Orchestrator & Ingestion Engine (C# / ASP.NET Core 8)**
   - Acts as the main API gateway.
   - Fetches real-time and historical data from external APIs (CoinGecko).
   - Handles data persistence and caching for high performance.
   - Forwards historical data to the analytical engine.
   - Audit Logging

2. **Analytical Brain (Python / FastAPI)**
   - A dedicated microservice for data processing.
   - Receives arrays of historical prices.
   - Calculates trends and percentage changes, returning analytical insights to the orchestrator.

3. **Persistence Layer (PostgreSQL & Docker)**
   - Containerized relational database.
   - Stores search logs and audit trails using Entity Framework Core (Code-First approach).

4. **Data Visualization Frontend (Python / Streamlit)**
   - An interactive dashboard providing a user-friendly interface.
   - Allows users to search for cryptocurrencies and view analytical cards (Average, Max, Volatility, and Trend).
   - Generates and streams downloadable CSV reports in-memory without polluting the server disk.

## 🚀 Tech Stack

- **Backend (Transational):** C# .NET 8, ASP.NET Core Minimal APIs
- **Backend (Analytical):** Python 3, FastAPI, Pydantic
- **Database:** PostgreSQL  "Security note: The database credentials provided in this repository are for local development purposes only. In production environments, always use Environment Variables or Secret Managers."
- **ORM:** Entity Framework Core (EF Core)
- **Infrastructure:** Docker, Docker Compose
- **Patterns Used:** Dependency Injection, In-Memory Caching, DTOs, Asynchronous Programming.
- **Frontend:** Python, Streamlit, Pandas

## ⚙️ Configuration

Before running the application, you need to configure your database credentials:

1. Locate the `CryptoDataApi` folder.
2. Copy `appsettings.example.json` to `appsettings.json`.
3. Open `appsettings.json` and update the `DefaultConnection` string with your PostgreSQL credentials (host, database name, username, and password).
4. (Optional) If you are using a custom environment, you can set these values as environment variables:
   - `ConnectionStrings__DefaultConnection`

> **Note:** Never commit your `appsettings.json` or `.env` files to version control if they contain real production credentials.

## ⚙️ How to Run Locally

### 1. Start the Database
Ensure Docker is running, then start the PostgreSQL container:

```bash
docker-compose up -d
```

### 2. Start the Python Analytical Engine
Navigate to the CryptoBrainPython folder, activate your virtual environment, and run:
```bash
uvicorn main:app --port 8000 --reload
```

### 3. Start the C# API
Navigate to the CryptoDataApi folder. Apply the database migrations and run the server:

```bash
dotnet ef database update
dotnet run
```


### 4. Test the Endpoints
Open your browser or Postman and hit:

- **Current Price: 
```bash 
http://localhost:<YOUR_PORT>/price/bitcoin 
```
- **7-Day History & Analysis: 
```bash 
http://localhost:<YOUR_PORT>/price/ethereum/history
```
- **Audit Logs: 
```bash
`http://localhost:<YOUR_PORT>/logs` (Retrieves the last 10 search records from the PostgreSQL database).
```

> 🌴 Developed as a robust portfolio project to demonstrate backend engineering, microservices integration, and polyglot architecture.


### 📜 License

This project is distributed under the MIT License. See the [LICENSE](LICENSE) file for more information.
