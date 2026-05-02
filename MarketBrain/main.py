from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
import numpy as np
app = FastAPI()

# C# Response model:
class PriceHistoryRequest(BaseModel):
    coin_name: str
    prices: List[float] 

# Analysis response
class AnalyticsResponse(BaseModel):
    trend: str 
    percentage_change: float
    volatility: float
    historical_prices: List[float]

# Endpoint route
@app.post("/analyze")
async def analyze_prices(data: PriceHistoryRequest) -> AnalyticsResponse:
    # Se não mandarem preços suficientes, não tem como analisar
    if not data.prices or len(data.prices) < 2:
        return AnalyticsResponse(trend="STABLE", percentage_change=0.0, volatility=0.0, historical_prices=[])

    first_price = data.prices[0]
    last_price = data.prices[-1]

    change = ((last_price - first_price) / first_price) * 100
    
    # Calculate volatility as the standard deviation of the price changes
    prices_array = np.array(data.prices)
    volatility = float(np.std(prices_array))
    
    # defining thresholds for trend classification
    if change > 1.0:
        trend = "UP"
    elif change < -1.0:
        trend = "DOWN"
    else:
        trend = "STABLE"

    # round to 2 decimal places for better readability
    return AnalyticsResponse(
        trend=trend, 
        percentage_change=round(change, 2), 
        volatility=round(volatility, 2),
        historical_prices=data.prices # Devolvendo a lista intacta!
    )