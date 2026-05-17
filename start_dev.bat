@echo off
echo ========================================================
echo 🚀 Iniciating Market Analytics System (Dev ENV)...
echo ========================================================

echo 1. Iniciating SQL (PostgreSQL)...
docker-compose up -d

echo 2. Iniciating C# Orchestrator (Com Hot Reload)...
start "C# API" cmd /k "cd MarketDataApi && dotnet watch run"

echo 3. Iniciating Python Brain...
start "Python API" cmd /k "cd MarketBrain && call venv\Scripts\activate && uvicorn main:app --port 8000 --reload"

echo 4. Iniciating Dashboard Streamlit...
start "Dashboard" cmd /k "cd MarketDashboard && call venv\Scripts\activate && streamlit run app.py"

echo ========================================================
echo ✅ All services are up and running!
echo ========================================================