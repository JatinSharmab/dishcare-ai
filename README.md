# DishCare AI

A production-oriented, multilingual agentic AI customer support backend for a simulated DTH television service provider.

## Implemented Features

### Business Backend

- FastAPI REST APIs and Swagger documentation
- SQLite relational database
- JWT authentication and Argon2 password hashing
- Customer-level authorization
- Payment and recharge verification
- Subscription and channel management
- Personalized retention offers
- Complaint tracking
- Simulated technician bookings
- Simulated human-agent escalation

### Agentic AI

- Gemini Flash-Lite and Groq integrations
- LLM provider abstraction and fallback
- LangGraph supervisor architecture
- Multi-intent classification
- Specialized customer support nodes
- Native LLM function calling
- Pydantic-based tool argument validation
- Controlled and allowlisted tool execution
- Explicit customer confirmation for state-changing actions
- Business outcome verification
- Persistent SQLite conversation checkpoints
- Versioned prompts

### Retrieval-Augmented Generation

- Multilingual Sentence Transformer embeddings
- Local Qdrant vector database
- Markdown-based document ingestion
- Semantic similarity retrieval
- Fictional customer support policies and troubleshooting documentation
- English, Hindi and Hinglish support

## Architecture

Customer message → FastAPI authentication → LangGraph supervisor → Specialized agent → Validated tools / RAG → Verification → Customer response.

## Technology Stack

Python 3.11, FastAPI, SQLite, Pydantic, Gemini, Groq, LangGraph, Sentence Transformers, Qdrant, Pytest and HTTPX.

## Local Setup

1. Create and activate a Python 3.11 virtual environment.
2. Install dependencies using `pip install -r requirements-dev.txt`.
3. Install AI dependencies using `pip install -r requirements-ai.txt`.
4. Copy `.env.example` to `.env`.
5. Generate and configure a JWT signing secret.
6. Configure at least one Gemini or Groq API key.
7. Set `AI_ENABLED=true`.
8. Download embeddings using `python -m scripts.download_models`.
9. Start the server using `python -m uvicorn app.main:app --reload`.

## API Documentation

Swagger UI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

Health check: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

AI conversation endpoint: POST /api/v1/chat

## Terminal Chatbot

Run `python -m scripts.chat_client`.

## Demonstration Accounts

| Customer ID | Scenario                                      |
| ----------- | --------------------------------------------- |
| CUST001     | Active subscription                           |
| CUST002     | Successful recharge but inactive subscription |
| CUST003     | Failed recharge                               |

Demo password: `DemoPass123!`

These credentials are for synthetic local demonstration records only.

## Example Conversations

- What is my account balance?
- Maine recharge kar diya lekin channels nahi chal rahe.
- My television has no signal.
- Add Sports HD to my subscription.
- I want to cancel my subscription.
- Book a technician.
- Connect me to human support.

State-changing actions require a server-generated confirmation code.

## Testing

Run `python -m pytest tests/ -v`.

Run `python -m ruff check app tests scripts` for linting.

Automated workflow tests use controlled model responses rather than external LLM calls.

## Development Roadmap

- [x] Phase 1: Python backend and business foundation
- [x] Phase 2: Complete Agentic AI and RAG
- [ ] Phase 3: Production reliability, MCP and WhatsApp
- [ ] Phase 4: Voice AI, evaluation, monitoring and CI/CD

## Current Limitations

The application is a single-process local MVP using simulated business infrastructure. Distributed concurrency control, generalized request idempotency, advanced security protections and production-scale monitoring are subsequent milestones.

## Security

API keys, JWT secrets, local databases, conversation checkpoints and downloaded model files must never be committed to GitHub.
