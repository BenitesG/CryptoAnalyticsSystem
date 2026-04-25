from fastapi import FastAPI
from pydantic import BaseModel
from typing import List

app = FastAPI()

# C# Response model:
class PriceHistoryRequest(BaseModel):
    coin_name: str
    prices: List[float] 

# Analysis response
class AnalyticsResponse(BaseModel):
    trend: str # "UP", "DOWN" or "STABLE"
    percentage_change: float

# Endpoint route
@app.post("/analyze")
async def analyze_prices(data: PriceHistoryRequest) -> AnalyticsResponse:
    # Se não mandarem preços suficientes, não tem como analisar
    if not data.prices or len(data.prices) < 2:
        return AnalyticsResponse(trend="STABLE", percentage_change=0.0)

    first_price = data.prices[0]
    last_price = data.prices[-1]

    change = ((last_price - first_price) / first_price) * 100
    
    # defining thresholds for trend classification
    if change > 1.0:
        trend = "UP"
    elif change < -1.0:
        trend = "DOWN"
    else:
        trend = "STABLE"

    # round to 2 decimal places for better readability
    return AnalyticsResponse(trend=trend, percentage_change=round(change, 2))