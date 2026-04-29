# ADR 001: Polyglot Microservices Architecture (C# & Python)

## Status
Accepted

## Context
We needed to build a Crypto Analytics system that handles both external API requests (fast, reliable routing) and heavy mathematical analysis (volatility, data science).

## Decision
We decided to implement a polyglot architecture:
1. **C# (.NET 8):** Used as the Orchestrator/API Gateway. C# provides strong typing, excellent performance for I/O operations (HTTP requests), and robust dependency injection for database persistence (Entity Framework).
2. **Python (FastAPI):** Used as the Analytical Engine. Python has an unmatched ecosystem for data processing (NumPy, Pandas).

## Consequences
**Positive:** 
- Clear separation of concerns.
- The system can scale independently (e.g., if data processing becomes heavy, we can scale the Python container without scaling the C# gateway).

**Negative:**
- Adds complexity to the deployment process (requires Docker Compose to orchestrate multiple containers).