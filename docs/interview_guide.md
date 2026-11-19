# DishCare AI interview guide

## Two-minute introduction

I built DishCare AI, a customer-support backend for a simulated DTH provider. It handles balance and recharge questions, no-signal troubleshooting, subscription changes, technician bookings, retention and escalation. Customers can use a REST chat endpoint, a signed WhatsApp webhook or a Python voice client.

I used LangGraph for routing and state, with typed intents and allowlisted tools. SQLite supplies current account facts, and a local vector index supplies policy passages. Before a write, the customer sees a proposal and confirms it. The verified business outcome determines the response.

The reliability demo covers an upstream that commits a booking and then times out. The client retries with the same key, and the transaction returns the original booking. Duplicate payment callbacks, cross-account attempts and malformed tool arguments are also covered. Voice uses local Silero VAD, Faster Whisper and Piper. I exercise the graph with controlled fixtures, run a small live model evaluation, and measure real speech inference separately.

## Five-minute walkthrough

1. Open Swagger, authenticate a seeded customer, and compare the balance API with the chat answer. Explain that tools supply current facts while RAG supplies policy context.
2. Ask a multi-intent question and follow the graph nodes. Explain why routine token and balance routes remain deterministic. Show a proposal and the exact confirmation, then verify the outcome in SQLite-backed APIs.
3. Simulate a technician timeout immediately after committing. Explain the difference between a timeout and a proven failure, then replay the same key and observe the same booking. Show a signed duplicate event and one unauthorized request.
4. Trace one voice turn from PCM through endpointing, transcription, graph and synthesis. Describe an interruption, and identify the time spent in each stage. Explain how SIP and RTP would connect to this design.
5. Compare offline and live evaluation reports. Point out fixture boundaries, judge limitations and small sample sizes. Show GitHub CI and explain how shared coordination would change a multi-worker deployment.

## Thirty project questions

1. **Why separate the supervisor from tools?** It routes requests, while authorization and validation live at the tool boundary.
2. **What does a direct balance lookup do?** It reads the authenticated account and returns the stored balance in paise.
3. **How does recharge troubleshooting work?** It reads payments and subscription state, and retrieves the recharge policy.
4. **Why use a graph?** Independent parts of a customer request can be handled by different nodes using shared evidence.
5. **What state persists?** Conversation history and pending actions persist in LangGraph checkpoints scoped to the customer and session.
6. **What prevents cross-customer reads?** The JWT subject supplies the effective account identity and the API rejects a mismatched route ID.
7. **How are tool arguments validated?** The executor applies the registered Pydantic schema before calling a business method.
8. **How do channel changes work?** The specialist proposes an action and calculates the current quote for confirmation.
9. **What if a quoted price changes?** The write rolls back when the verified resulting monthly fee differs from the approved quote.
10. **Why use a confirmation code?** It binds an explicit approval to a time-limited proposal and a conversation.
11. **Why verify the write?** A success response can be incomplete. Verification re-reads the resulting state.
12. **What does escalation do?** It creates a support record after confirmation so a human workflow can pick it up.
13. **How does retention use data?** It reads eligible offers and policy before proposing cancellation.
14. **How do retries avoid duplicate appointments?** Every attempt uses the same idempotency key and the upstream stores the committed result.
15. **What if the same key is reused with different input?** A canonical request hash detects the mismatch and returns a conflict.
16. **What makes payment deduplication transactional?** The event ID, payment update, and audit entry commit together.
17. **Why sign the exact webhook bytes?** JSON formatting can change without changing the parsed object. HMAC verifies what was received.
18. **How does WhatsApp identify a customer?** A signed notification carries the sender number and the service matches a unique enabled account.
19. **What if WhatsApp delivery is uncertain?** The ledger marks the operation uncertain and blocks automatic re-execution until it is reconciled.
20. **How does the circuit recover?** After the cooldown a half-open probe checks whether the upstream can answer.
21. **How is MCP scoped?** The server forwards permitted read tools under a customer JWT.
22. **What information appears in audit logs?** A pseudonymous actor reference, event type, outcome and request ID.
23. **What handles prompt injection?** Pattern screening handles common cases and independent authorization limits the effect of patterns it misses.
24. **What goes into a prompt?** The current request, bounded history and needed evidence, with common sensitive formats redacted.
25. **How is Gemini output validated?** The API receives a JSON Schema and returned text is validated with Pydantic.
26. **When does Groq take over?** A Gemini failure or timeout falls through to the configured fallback.
27. **What is cached?** Bounded Qdrant retrieval results for identical queries. Account facts and write outcomes follow their authoritative stores.
28. **How do you measure regressions?** Replay a fixed dataset, compare per-case intent, tools, arguments and task outcomes, and gate known expected results.
29. **What does the monitoring record?** Request duration, status, input and output token counts where present, and voice stage durations.
30. **What is still simulated?** Business systems and technician upstream, synthetic accounts, optional WhatsApp delivery, and escalation records.

## Twenty general engineering questions

1. **Structured output versus tool calling?** A structured output describes information in a schema. Tool calling asks the application to perform a named operation.
2. **What is retrieval grounding?** Answering with evidence from relevant source passages and citing where those passages came from.
3. **What controls agent loops?** Bounded steps, explicit exits, consumed work queues and recursion limits.
4. **When is an agent unnecessary?** When application code can route and validate a predictable operation directly.
5. **What does async I/O help?** It lets the process serve other requests while one waits for a database or network response.
6. **What is a transaction?** A set of changes that commit together or roll back together.
7. **What is a uniqueness constraint?** A database rule that prevents two rows sharing a key even under concurrent inserts.
8. **What is an idempotency key?** An identifier a client can reuse to return one operation's committed outcome.
9. **Why jitter?** Randomized delays spread retries across time and reduce synchronized load.
10. **When would you skip a retry?** When the response indicates invalid input, unauthorized access or another permanent error.
11. **What is a deadline?** The total allowed duration for a request, including downstream work and retries.
12. **Rate limit versus concurrency limit?** A rate limit counts arrivals over time. A concurrency limit counts active work.
13. **How do you prevent logging PII?** Log route templates, outcomes and counts, and keep raw headers, chat prompts and webhook bodies out of structured logs.
14. **What do latency percentiles reveal?** P50 represents the median. P95 and P99 reveal slow requests that averages hide.
15. **What causes a hallucination?** The model can produce a plausible claim unsupported by its retrieved or verified evidence.
16. **How do you validate an LLM judge?** Compare it to independently labeled human judgments, especially on disagreements and unsupported claims.
17. **Offline versus online evaluation?** Offline replay is repeatable and cheap. Online evaluation captures behavior in the deployed setting.
18. **What does first-contact resolution mean?** Share of eligible issues resolved in the first contact, using a defined repeat-contact window.
19. **How do you measure containment?** Divide eligible conversations resolved without human transfer by eligible conversations.
20. **What does CI verify?** Dependency installation, lint, tests and deterministic replay on a clean runner.

## Fifteen voice questions

1. **What is PCM?** A digital sequence of sampled sound amplitudes.
2. **Why 16 kHz mono?** It matches Whisper's input convention and limits bandwidth.
3. **What does one frame carry?** 512 samples or 32 ms of audio, encoded as 1,024 bytes.
4. **What is ASR?** Speech-to-text decoding that turns acoustic features into recognized tokens.
5. **What is TTS?** Rendering text into a waveform suitable for playback.
6. **What is VAD?** A model that identifies which frames contain speech.
7. **Why keep pre-roll?** It preserves the first sounds before VAD reaches its speech threshold.
8. **What is endpointing?** Detecting enough trailing silence to dispatch the current utterance.
9. **What is barge-in?** A control that stops a pending response or audio playback so the caller can speak again.
10. **What causes echo?** Microphone pickup of speaker playback. Headphones help in the demo and WebRTC offers echo-control tools for production.
11. **How are Hindi and English handled?** Whisper uses its multilingual model, and Piper uses separate voices selected from chat and ASR language.
12. **How is WER calculated?** Word substitutions plus deletions and insertions, divided by reference words.
13. **Where does voice latency accrue?** Endpointing, network transit, ASR, graph inference, TTS, and audio playback buffering.
14. **When would you choose WebRTC?** For interactive media that needs congestion control, jitter management and media-specific transport.
15. **How would you connect PSTN?** A SIP-capable gateway would route the call and bridge RTP media into a resampling and streaming layer.

## Support metrics and job fit

Average handling time includes time spent interacting and wrapping up per resolved contact. Customer satisfaction is the share of positive survey responses or the average survey score under a stated definition. Escalation rate is escalated conversations divided by eligible conversations. Churn rate uses a defined cohort and period to measure subscribers lost. Retention rate tracks how many remained in the starting cohort. For all of these, segment by channel, intent and sample size. DishCare records engineering signals and test outcomes. It does not claim measured business impact.

The project covers Python REST APIs, function calling, typed outputs, prompt versioning, SQL transactions, operational recovery and evaluation. It also demonstrates MCP, RAG, WhatsApp simulation, Hindi and English voice and support workflow design. For interview questions about scaling, explain when you would replace SQLite, run a shared limiter, separate model workers, and build a real agent handoff.
