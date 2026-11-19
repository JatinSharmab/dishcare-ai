# Production reliability

A timeout is ambiguous. The technician simulator commits a booking before delaying its reply. HTTPX retries the same idempotency key with exponential jitter, and SQLite returns the committed result. An open circuit fails quickly and admits one recovery probe after its cooldown. A real technician service must honor the same key contract.

Use a single application worker for the in-memory rate limiter, circuit breaker and chat locks. A multi-worker deployment would need a shared limiter and coordinated conversation writes. The payment ledger uses a unique event ID and transactions, so concurrent deliveries share database-level protection.

A webhook signs its exact bytes. The receiver validates that signature before interpreting JSON, then deduplicates verified events. Copied event IDs with different payloads fail. WhatsApp delivery has a separate failure mode because a send can succeed before the reply reaches us. The operation ledger records uncertain delivery and prevents a blind resend.

In a local sandbox, run `python -m scripts.simulate_webhook payments` twice with the same event ID. The responses should show an accepted event followed by an accepted duplicate. Run `python -m pytest tests/test_reliability.py tests/test_webhooks.py tests/test_security.py -q` for concurrency and failure cases.

## Interview questions

- **Why use transactions with idempotency?** The booking and the stored response commit together. If either fails, SQLite rolls back both.
- **Why does a circuit breaker help?** After consecutive failures, it stops sending requests long enough for the upstream to recover. A half-open probe checks readiness.
- **Can prompt screening authorize actions?** Authorization comes from the JWT or signed channel identity and server-side tool validation. The model proposes changes, and the customer confirms before execution.
- **When is a ledger insufficient?** The ledger alone cannot prove that an external WhatsApp send succeeded. A provider receipt, reconciliation process or an external idempotency contract is needed.
- **What changes for multi-worker deployment?** Move process-local guardrails to a shared store and preserve the database uniqueness constraints.
