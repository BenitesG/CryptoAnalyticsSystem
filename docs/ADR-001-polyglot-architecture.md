# ADR 001: Polyglot Microservices Architecture for Multi-Asset Analytics

## Status
Accepted / Updated

## Context
We needed to build a highly scalable market analytics platform capable of handling real-time data from diverse financial markets (Cryptocurrencies and Traditional B3 Stocks/REITs). The system requires fast and reliable routing, resilient external API consumption, heavy mathematical analysis (volatility, percentage changes), database auditing, and an interactive user interface.

## Decision
We decided to implement a polyglot, multi-tier architecture to enforce a strict **Separation of Concerns**:

1. **C# (.NET 8) - Orchestrator & Gateway:** 
   - Acts as the core backend. It provides strong typing and excellent performance for I/O operations.
   - **Factory Pattern & Interfaces:** Utilizes `IMarketDataService` to dynamically route requests to the appropriate data provider (`CoinGeckoService` or `BrapiService`) based on the asset type, ensuring the Open/Closed Principle (SOLID).
   - **Resiliency:** Integrates **Polly** for exponential backoff and retry patterns to handle external API transient failures.
   - **Persistence:** Uses Entity Framework Core with PostgreSQL for structured, code-first audit logging.

2. **Python (FastAPI) - Analytical Brain:** 
   - A dedicated microservice strictly for data processing. It leverages Python's unmatched ecosystem (NumPy) to compute statistical metrics (e.g., standard deviation for volatility) without blocking the main C# gateway.

3. **Python (Streamlit) - Presentation Layer:** 
   - A decoupled frontend that consumes the C# API to render interactive financial charts (Plotly) and UI components. It generates stateless CSV exports in-memory, protecting server disk space.

## Consequences

**Positive:** 
- **Extensibility:** Adding a new market provider (e.g., Yahoo Finance) only requires creating a new C# class implementing `IMarketDataService` without altering the core routing or Python logic.
- **Fault Tolerance:** The system survives temporary network glitches thanks to Polly retry policies and graceful 404 handling.
- **Independent Scalability:** The UI, the Analytical Engine, and the Orchestrator can be scaled horizontally on the cloud completely independent of each other.

**Negative:**
- **Operational Complexity:** Local development and CI/CD pipelines are more complex, requiring Docker Compose to orchestrate multiple environments, ports, and a database simultaneously.
- **Network Latency:** Inter-service communication (C# calling FastAPI via HTTP) adds a slight latency overhead compared to a monolithic approach.
