# DishCare AI

A production-oriented agentic AI customer support backend for a simulated DTH television service provider.

## Project objective

DishCare AI demonstrates secure business APIs, agentic orchestration, retrieval-augmented generation, production reliability, multilingual customer support and Voice AI.

This is an independent demonstration project. It is not affiliated with Dish TV and does not access its internal systems.

## Current milestone: Phase 1

- FastAPI REST backend with Swagger documentation
- SQLite relational database and synthetic customer records
- JWT authentication and Argon2 password hashing
- Customer-level authorization and data isolation
- Account balance and payment verification
- Subscription and channel management
- Personalized retention offer retrieval
- Complaint registration and tracking
- Simulated technician booking and human escalation
- Pydantic validation and structured business exceptions
- Automated API tests

## Technology stack

Python 3.11, FastAPI, Pydantic, SQLite, Aiosqlite, PyJWT, Pytest.

## Local setup

1. Create and activate a Python 3.11 virtual environment.
2. Install dependencies using `pip install -r requirements-dev.txt`.
3. Copy `.env.example` to `.env`.
4. Generate and configure a secure JWT secret.
5. Start the server using `python -m uvicorn app.main:app --reload`.

## API documentation

Swagger UI: http://127.0.0.1:8000/docs

Health check: http://127.0.0.1:8000/health

## Demonstration accounts

| Customer ID | Scenario                                      |
| ----------- | --------------------------------------------- |
| CUST001     | Active subscription                           |
| CUST002     | Successful recharge but inactive subscription |
| CUST003     | Failed recharge                               |

Demo password: `DemoPass123!`

These credentials are for synthetic local development data only.

## Testing

Run `python -m pytest tests/ -v`.

Run `python -m ruff check app tests` for linting.

## Development roadmap

- [x] Phase 1: Python backend and business foundation
- [ ] Phase 2: LangGraph, LLM integrations and RAG
- [ ] Phase 3: Production reliability, MCP and WhatsApp
- [ ] Phase 4: Voice AI, evaluation, monitoring and CI/CD

## Security

Environment secrets, databases and generated model files are excluded from version control. All records and business integrations are simulated.
