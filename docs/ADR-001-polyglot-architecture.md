# ADR 001: Polyglot Microservices Architecture for Multi-Asset Analytics

## Status
Accepted / Updated

## Context
We needed to build a highly scalable market analytics platform capable of handling real-time data from diverse financial markets (Cryptocurrencies, Stocks, and REITs/FIIs). The system requires fast routing, resilient external API consumption, fundamental data extraction, and heavy mathematical analysis.

## Decision
We implemented a polyglot, multi-tier architecture to enforce a strict **Separation of Concerns**:

1. **Orchestrator & Gateway (C# / ASP.NET Core 8):**
   - Routing Hub: Uses the `Factory Pattern` (`IMarketDataService`) to dynamically handle different asset types (Crypto vs B3).
   - Resiliency: Integrated **Polly** for exponential backoff retries.
   - Persistence: PostgreSQL via EF Core with audit logging.
   - Data Mapping: Maps complex external responses to strictly typed DTOs.

2. **Analytical Engine (Python / FastAPI):**
   - Fundamental Analysis: Implemented a **Web Scraping module** using `BeautifulSoup` to extract fundamental data (P/L, P/VP, Yield) from the web.
   - Mathematical Processing: Uses **NumPy** for volatility and trend calculation.
   - Data Normalization: Implemented a robust cleansing pipeline to transform localized Brazilian strings (e.g., "5,48%") into standardized float values.

3. **Presentation Layer (Python / Streamlit):**
   - Decoupled frontend using `Streamlit` and `Plotly` for interactive financial data visualization.

## Consequences

**Positive:**
- **Extensibility:** The system can now support any asset class by adding a new scraping or API service implementing `IMarketDataService`.
- **Maintainability:** Separation of analytical logic (Python) and transactional routing (C#) allows independent testing.

**Negative:**
- **Scraping Fragility:** Web scraping relies on HTML structure. If the source website (StatusInvest) changes its CSS classes, the scraping module will require maintenance.
- **Data Normalization Overhead:** The need to handle localized strings ("R$", "%", ",") adds complexity to the transformation layer.
