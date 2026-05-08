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
    action_signal: str 

# Endpoint route
@app.post("/analyze")
async def analyze_prices(data: PriceHistoryRequest) -> AnalyticsResponse:
    if not data.prices or len(data.prices) < 2:
        return AnalyticsResponse(trend="STABLE", percentage_change=0.0, volatility=0.0, historical_prices=[], action_signal="HOLD")

    first_price = data.prices[0]
    last_price = data.prices[-1]

    change = ((last_price - first_price) / first_price) * 100
    
    prices_array = np.array(data.prices)
    volatility = float(np.std(prices_array))
    average_price = float(np.mean(prices_array))
    
    if change > 1.0:
        trend = "UP"
    elif change < -1.0:
        trend = "DOWN"
    else:
        trend = "STABLE"

    signal = "HOLD" 
    
    price_to_avg_ratio = last_price / average_price

    if trend == "UP":
        if price_to_avg_ratio < 1.05: 
            signal = "BUY"
        else: 
            signal = "HOLD"
            
    elif trend == "DOWN":
        if price_to_avg_ratio < 0.95: 
            signal = "STRONG BUY" if volatility < average_price * 0.05 else "HOLD" 
        else:
            signal = "SELL" 
            
    elif trend == "STABLE":
        if volatility < average_price * 0.02: 
            signal = "BUY"

    return AnalyticsResponse(
        trend=trend, 
        percentage_change=round(change, 2), 
        volatility=round(volatility, 2),
        historical_prices=data.prices,
        action_signal=signal 
    )