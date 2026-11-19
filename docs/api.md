# API and local demos

Start the server with `python -m uvicorn app.main:app --port 8000`. Swagger is at `/docs`. Use the token endpoint with a synthetic account such as `CUST001`. An authenticated session binds business routes to the token subject.

| Endpoint | Payload and behavior |
| --- | --- |
| `POST /api/v1/auth/token` | OAuth2 password form. Returns a short-lived customer JWT. |
| `POST /api/v1/chat` | JSON with `message` and optional `session_id`. Returns answer, intent, tool results, sources and any pending confirmation. |
| `POST /api/v1/customers/{customer_id}/technicians` | Technician booking JSON, customer JWT and optional `Idempotency-Key`. Reuse the same key for an identical retry. |
| `POST /api/v1/webhooks/payments` | JSON `event_id` and existing `payment_id`. Sign the raw body using HMAC SHA-256 in `X-Hub-Signature-256`. |
| `GET /api/v1/webhooks/whatsapp` | Meta subscription challenge with `hub.mode`, `hub.verify_token`, `hub.challenge`. |
| `POST /api/v1/webhooks/whatsapp` | Signed Meta message notification. Set a registered test sender in the customers table. |
| `GET /api/v1/mcp/{tool}` | Customer JWT. Supported read tools are `get_balance` and `get_subscription`. |
| `POST /api/v1/voice/turn` | JWT and `application/octet-stream` PCM16 little-endian mono at 16 kHz. Optional `language=en` or `language=hi` and `session_id` query parameters. Returns WAV and `X-Session-ID`. |
| `WS /api/v1/voice/stream` | Authorization header containing a customer JWT. Same optional language and session parameters. |
| `GET /health` | Database and chat availability. |
| `GET /metrics` | Local counters and latency percentiles protected by the configured `X-Metrics-Key` header. |

The WebSocket sends a JSON `ready` event with the session ID and frame size. Send 1,024-byte binary frames. VAD ends a turn after trailing silence. The text command `end` flushes the current speech buffer. `interrupt` resets the buffer and cancels a pending reply. Each `reply` event carries the transcript, answer, output sample rate and timings in seconds and is followed by a binary PCM message. On `error`, no audio follows. Preserve the same session UUID for follow-up text or speech. Use a typed `CONFIRM <code>` on the text endpoint with that UUID if speech recognition cannot reproduce the code exactly.

## Demo

1. Ask for balance, an inactive subscription after recharge, and a no-signal diagnosis in separate sessions.
2. Ask to add a channel, cancel a subscription, book a technician, or speak to a human. Inspect the proposed action before confirming.
3. Run `python -m pytest tests/test_reliability.py tests/test_webhooks.py tests/test_security.py -q` for simulated timeout, replay, and security scenarios. Run `python -m scripts.simulate_webhook payments` twice against a seeded server with a local signing secret.
4. Run `python -m evaluations.prompt_comparison --simulate-regression` to demonstrate a detected regression and its exit code.
5. Start the Python microphone client, ask for balance in English or Hindi, and verify the transcript, answer and playback. Synthetic audio can be sent with the WAV option.

Keep tokens out of persistent shell history and source control. Serve HTTPS or WSS at the boundary and limit access to business and metrics endpoints. Turn off or sanitize Uvicorn access logs for an externally exposed WhatsApp verification endpoint because Meta puts the verification token in the query string.
