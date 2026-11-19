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

## Phase 3 reliability and integrations

- Technician bookings accept an explicit `Idempotency-Key`. The HTTPX client retries transient failures with jitter, bounds each attempt, and opens a circuit after repeated outages. The local upstream simulator can time out after committing. Retrying the same key returns the original booking.
- Payment webhooks verify an HMAC SHA-256 signature over the original request bytes. Event deduplication, payment updates, and the audit entry share a SQLite transaction.
- Chat writes require the existing confirmation flow. A database transaction binds an approved write to its confirmation key and checks the quoted price. Customer identity comes from authentication, and tool arguments are validated independently of model output.
- Prompt screening catches common injection phrases. The LLM boundary redacts common identifiers and credential formats. Audit entries store action, outcome, request ID and a pseudonymous actor reference.

### Run the failure scenarios

```powershell
python -m pytest tests/test_reliability.py tests/test_webhooks.py tests/test_security.py -q
```

The tests reproduce a timeout after commit, a circuit opening, concurrent duplicate bookings, duplicate and conflicting payments, a rate limit, and invalid credentials.

### MCP

Install `requirements-reliability.txt`. Start DishCare, place an existing customer JWT in the current shell as `DISHCARE_CUSTOMER_TOKEN`, and run `python -m app.integrations.mcp_client get_balance`. The stdio server exposes balance and subscription queries under the JWT identity.

### WhatsApp and payments

Set the variables in `.env.example` using local secrets. The payment webhook is `POST /api/v1/webhooks/payments` and takes an event ID and an existing payment ID. For WhatsApp, configure Meta to call `/api/v1/webhooks/whatsapp`. The sender must match an enabled customer's E.164 number in the database. Use synthetic data for demos. Without a Meta access token, inbound events run through chat in simulation mode. An interrupted external delivery is recorded as uncertain and can be reconciled before a resend. Live Meta delivery requires a configured app and public HTTPS endpoint.

## Phase 4 voice, evaluation and monitoring

Use Python 3.11 and install the optional Voice AI packages in the project environment.

```powershell
python -m pip install -r requirements.txt -r requirements-ai.txt -r requirements-voice.txt
python -m piper.download_voices --data-dir models en_US-lessac-medium hi_IN-pratham-medium
```

Set `AI_ENABLED=true` and `VOICE_ENABLED=true` in `.env`, and configure Gemini or Groq. Faster Whisper loads the multilingual `base` model on CPU and downloads it on first use if it is absent from cache. Set `WHISPER_MODEL` to a downloaded local model directory for offline startup. Start Uvicorn with one worker. Set `DISHCARE_CUSTOMER_TOKEN` in the shell to a customer JWT from `/api/v1/auth/token`.

```powershell
python -m scripts.voice_client --language en
python -m scripts.voice_client --language hi
python -m scripts.voice_client --wav models/question-16k.wav --output reply.wav
```

Wear headphones to avoid feeding playback back into the microphone. Omit `--language` for Whisper language detection. Press Space on Windows or Enter on Unix to interrupt. The client displays the session ID for follow-up text or a typed confirmation. The WAV client expects mono 16 kHz PCM16 input.

```powershell
python -m pytest -q
python -m ruff check app tests evaluations scripts
python -m evaluations.runner --require-pass
python -m evaluations.runner --live --judge --case balance-en
python -m evaluations.prompt_comparison --simulate-regression
python -m evaluations.voice_eval models/voice-manifest.json
```

The offline evaluation replays controlled decisions through the real graph and SQLite. The live flag uses configured model credentials, and the judge checks relevance, evidence and unsupported claims. Voice evaluation expects a JSON array of objects with `wav`, `reference` and optional `language`. Each WAV path is relative to the manifest. Set `METRICS_KEY` to enable `GET /metrics`. Set `LLM_PRICES_PER_MILLION` to a JSON map of model IDs to `[input_usd, output_usd]` for estimated request costs.

- [Architecture](docs/architecture.md)
- [API and demo walkthrough](docs/api.md)
- [Reliability notes](docs/reliability.md)
- [Measured evaluation results](docs/evaluation_results.md)
- [Interview guide](docs/interview_guide.md)
